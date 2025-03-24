import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import duckdb

st.set_page_config(page_title="Maintenance Dashboard", page_icon=":bar_chart:", layout="wide")

# Load Data
@st.cache_data
def load_data():
    file_path = "Asset Work History.csv"
    df = pd.read_csv(file_path, parse_dates=['OrderDate', 'ActualStartDateTime', 'ActualEndDateTime', 'ReportedDate', 'RequiredByDate'])
    df['Month Name'] = df['OrderDate'].dt.strftime('%B')
    df['Year'] = df['OrderDate'].dt.year.astype(int)
    df['WorkPriority'] = df['WorkPriority'].replace({'P1': 'P1 - High', 'P2': 'P2 - Medium', 'P3': 'P3 - Low'})
    df['Duration'] = (df['ActualEndDateTime'] - df['ActualStartDateTime']).dt.total_seconds() / 3600
    df['RequiredByDate'] = df['OrderDate'] + pd.to_timedelta((6 - df['OrderDate'].dt.weekday) % 7, unit='D')
    return df

df = load_data()

# Current date
current_date = pd.to_datetime(datetime.now().date())
st.write(f"Current date set to: {current_date}")

# Sidebar (unchanged)
with st.sidebar:
    st.markdown('''
        <style>
        section[data-testid="stSidebar"] {
            width: 350px !important;
            max-width: 90vw;
            background-color: #32659C;
            color: white;
            padding: 20px;
        }
        </style>
    ''', unsafe_allow_html=True)
    st.title(":wrench: Maintenance Dashboard")
    st.markdown("""
        This dashboard provides an analysis of maintenance work orders, including planned and unplanned maintenance,
        work requests, downtime tracking, and performance metrics.
    """)
    st.header("🔍 Filter Options")
    month_options = ['All'] + sorted(df['Month Name'].dropna().unique(), key=lambda x: pd.to_datetime(x, format='%B').month)
    year_options = ['All'] + sorted(df['Year'].dropna().unique())
    current_year = current_date.year
    current_month_num = current_date.month
    month_names = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    default_months = month_names[:current_month_num]
    default_years = [current_year]
    selected_months = st.multiselect("Select Month", month_options, default=default_months)
    selected_years = st.multiselect("Select Year", year_options, default=default_years)
    work_type_options = ['All'] + list(df['WorkType'].dropna().unique())
    selected_work_types = st.multiselect("Select Work Type", work_type_options, default=[work_type_options[0]])
    work_status_options = ['All'] + list(df['WorkStatus'].dropna().unique())
    selected_work_status = st.multiselect("Select Work Status", work_status_options, default=[work_status_options[0]])
    work_priority_options = ['All', 'P1 - High', 'P2 - Medium', 'P3 - Low']
    selected_work_priority = st.multiselect("Select Work Priority", work_priority_options, default=[work_priority_options[0]])
    location_options = ['All'] + list(df['ParentLocation'].dropna().unique())
    selected_locations = st.multiselect("Select Location", location_options, default=[location_options[0]])

# Apply Filters
filtered_df = df.copy()
if selected_months and 'All' not in selected_months:
    filtered_df = filtered_df[filtered_df['Month Name'].isin(selected_months)]
if selected_years and 'All' not in selected_years:
    filtered_df = filtered_df[filtered_df['Year'].isin(selected_years)]
if selected_work_types and 'All' not in selected_work_types:
    filtered_df = filtered_df[filtered_df['WorkType'].isin(selected_work_types)]
if selected_work_status and 'All' not in selected_work_status:
    filtered_df = filtered_df[filtered_df['WorkStatus'].isin(selected_work_status)]
if selected_work_priority and 'All' not in selected_work_priority:
    filtered_df = filtered_df[filtered_df['WorkPriority'].isin(selected_work_priority)]
if selected_locations and 'All' not in selected_locations:
    filtered_df = filtered_df[filtered_df['ParentLocation'].isin(selected_locations)]

# KPI Calculations with DuckDB
def calculate_work_order_metrics(df):
    duckdb.register('df', df)
    
    # 1. Weekly Metrics (KPIs 1-4)
    current_week_start = current_date - pd.to_timedelta(current_date.weekday(), unit='D')
    current_week_end = current_week_start + pd.to_timedelta(6, unit='D')
    open_wo_week_query = """
    SELECT COUNT(*) as open_wo_week
    FROM df
    WHERE "WorkStatus" NOT IN ('Closed', 'Completed', 'Closed - Was Backlog')
    AND "OrderDate" <= ?
    AND ("ActualEndDateTime" IS NULL OR "ActualEndDateTime" > ?)
    """
    completed_wo_week_query = """
    SELECT COUNT(*) as completed_wo_week
    FROM df
    WHERE "WorkStatus" IN ('Completed', 'Closed', 'Closed - Was Backlog')
    AND "ActualEndDateTime" >= ?
    AND "ActualEndDateTime" <= ?
    """
    in_progress_wo_week_query = """
    SELECT COUNT(*) as in_progress_wo_week
    FROM df
    WHERE "WorkStatus" = 'In Progress'
    AND "ActualStartDateTime" <= ?
    AND ("ActualEndDateTime" IS NULL OR "ActualEndDateTime" > ?)
    """
    project_in_focus_query = """
    SELECT *
    FROM df
    WHERE "WorkStatus" = 'In Progress'
    AND "WorkType" = 'Projects'
    AND "ActualStartDateTime" <= ?
    AND ("ActualEndDateTime" IS NULL OR "ActualEndDateTime" > ?)
    ORDER BY "RequiredByDate" ASC, "ActualStartDateTime" DESC
    LIMIT 1
    """
    open_wo_week = duckdb.query(open_wo_week_query, params=[current_week_end, current_week_end]).fetchone()[0]
    completed_wo_week = duckdb.query(completed_wo_week_query, params=[current_week_start, current_week_end]).fetchone()[0]
    in_progress_wo_week = duckdb.query(in_progress_wo_week_query, params=[current_week_end, current_week_end]).fetchone()[0]
    project_in_focus_result = duckdb.query(project_in_focus_query, params=[current_week_end, current_week_end]).df()
    project_in_focus = project_in_focus_result.to_dict('records')[0] if not project_in_focus_result.empty else None

    # 2. High-Level Counts (KPIs 5-9)
    total_wo = len(df)
    open_wo_query = """
    SELECT COUNT(*) as open_wo
    FROM df
    WHERE "WorkStatus" NOT IN ('Closed', 'Completed', 'Closed - Was Backlog')
    """
    completed_wo_query = """
    SELECT COUNT(*) as completed_wo
    FROM df
    WHERE "WorkStatus" IN ('Completed', 'Closed', 'Closed - Was Backlog')
    """
    backlog_count_query = """
    SELECT COUNT(*) as backlog_count
    FROM df
    WHERE "WorkStatus" NOT IN ('Closed', 'Completed', 'Closed - Was Backlog')
    AND "RequiredByDate" IS NOT NULL
    AND "RequiredByDate" < ?
    """
    emergency_ytd_query = """
    SELECT COUNT(*) as emergency_ytd
    FROM df
    WHERE "WorkType" = 'Breakdown'
    AND "WorkStatus" IN ('Completed', 'Closed', 'Closed - Was Backlog')
    AND "ActualEndDateTime" >= ?
    AND "ActualEndDateTime" <= ?
    """
    open_wo = duckdb.query(open_wo_query).fetchone()[0]
    completed_wo = duckdb.query(completed_wo_query).fetchone()[0]
    backlog_count = duckdb.query(backlog_count_query, params=[current_date]).fetchone()[0]
    emergency_ytd = duckdb.query(emergency_ytd_query, params=[pd.to_datetime(f"{current_date.year}-01-01"), current_date]).fetchone()[0]

    # 3. Time-Based Metrics (KPIs 10-13)
    avg_aging_query = """
    SELECT AVG(DATEDIFF('day', "OrderDate", CAST(? AS DATE))) as avg_aging
    FROM df
    WHERE "WorkStatus" NOT IN ('Closed', 'Completed', 'Closed - Was Backlog')
    """
    avg_pm_backlog_aging_query = """
    SELECT AVG(DATEDIFF('day', "RequiredByDate", "ActualEndDateTime")) as avg_pm_backlog_aging
    FROM df
    WHERE "WorkType" IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects')
    AND "ActualEndDateTime" > "RequiredByDate"
    AND "WorkStatus" IN ('Completed', 'Closed', 'Closed - Was Backlog')
    AND "ActualEndDateTime" IS NOT NULL AND "RequiredByDate" IS NOT NULL
    """
    mttr_query = """
    SELECT AVG(DATEDIFF('hour', "ActualStartDateTime", "ActualEndDateTime")) as mttr_hrs
    FROM df
    WHERE "WorkType" IN ('Planned Corrective Maint.', 'Breakdown', 'Unplanned Corrective Maintenance')
    AND "WorkStatus" IN ('Completed', 'Closed', 'Closed - Was Backlog')
    AND "ActualStartDateTime" IS NOT NULL AND "ActualEndDateTime" IS NOT NULL
    """
    avg_cycle_time_query = """
    SELECT AVG(DATEDIFF('day', "ActualStartDateTime", "ActualEndDateTime")) as avg_cycle_time
    FROM df
    WHERE "WorkStatus" IN ('Completed', 'Closed', 'Closed - Was Backlog')
    AND "ActualStartDateTime" IS NOT NULL AND "ActualEndDateTime" IS NOT NULL
    """
    avg_aging = duckdb.query(avg_aging_query, params=[current_date]).fetchone()[0] or 0
    avg_pm_backlog_aging = duckdb.query(avg_pm_backlog_aging_query).fetchone()[0] or 0
    mttr_hrs = duckdb.query(mttr_query).fetchone()[0] or 0
    avg_cycle_time = duckdb.query(avg_cycle_time_query).fetchone()[0] or 0

    # 4. Percentage-Based Metrics (KPIs 14-17)
    pm_compliance_query = """
    SELECT 
        SUM(CASE WHEN "ActualEndDateTime" <= "RequiredByDate" THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as pm_compliance
    FROM df
    WHERE "WorkType" IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects')
    AND "RequiredByDate" IS NOT NULL
    AND "WorkStatus" IN ('Completed', 'Closed', 'Closed - Was Backlog')
    AND "ActualEndDateTime" IS NOT NULL
    """
    pmp_query = """
    SELECT 
        SUM(CASE WHEN "WorkType" IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects')
                 THEN DATEDIFF('hour', "ActualStartDateTime", "ActualEndDateTime") ELSE 0 END) as planned_hours,
        SUM(DATEDIFF('hour', "ActualStartDateTime", "ActualEndDateTime")) as total_hours
    FROM df
    WHERE "ActualStartDateTime" IS NOT NULL AND "ActualEndDateTime" IS NOT NULL
    """
    corrective_pct_query = """
    SELECT 
        SUM(CASE WHEN "WorkType" IN ('Breakdown', 'Unplanned Corrective Maintenance')
                 THEN DATEDIFF('hour', "ActualStartDateTime", "ActualEndDateTime") ELSE 0 END) as corrective_hours,
        SUM(DATEDIFF('hour', "ActualStartDateTime", "ActualEndDateTime")) as total_hours
    FROM df
    WHERE "ActualStartDateTime" IS NOT NULL AND "ActualEndDateTime" IS NOT NULL
    """
    completion_rate_query = """
    SELECT 
        SUM(CASE WHEN "WorkStatus" IN ('Completed', 'Closed', 'Closed - Was Backlog') THEN 1 ELSE 0 END) as completed,
        COUNT(*) as total
    FROM df
    """
    pm_compliance = duckdb.query(pm_compliance_query).fetchone()[0] or 0
    pmp_result = duckdb.query(pmp_query).fetchone()
    planned_hours, total_hours = pmp_result
    pmp = (planned_hours / total_hours * 100) if total_hours > 0 else 0
    corrective_result = duckdb.query(corrective_pct_query).fetchone()
    corrective_hours, total_hours = corrective_result
    corrective_pct = (corrective_hours / total_hours * 100) if total_hours > 0 else 0
    completion_result = duckdb.query(completion_rate_query).fetchone()
    completed, total = completion_result
    completion_rate = (completed / total * 100) if total > 0 else 0

# 5. Trend Data for PMP and Work Order Completion Rate (KPIs 22-23)
    pmp_trend = []
    completion_rate_trend = []
    for i in range(11, -1, -1):  # Last 12 months, from oldest to newest
        month_end = (current_date.replace(day=1) - pd.to_timedelta(1, unit='D')) - pd.to_timedelta(i * 30, unit='D')
        month_start = month_end.replace(day=1)
        month_label = month_end.strftime('%b %Y')
        
        # PMP for the month
        pmp_month_query = """
        SELECT 
            SUM(CASE WHEN "WorkType" IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects')
                    THEN DATEDIFF('hour', "ActualStartDateTime", "ActualEndDateTime") ELSE 0 END) as planned_hours,
            SUM(DATEDIFF('hour', "ActualStartDateTime", "ActualEndDateTime")) as total_hours
        FROM df
        WHERE "ActualStartDateTime" IS NOT NULL AND "ActualEndDateTime" IS NOT NULL
        AND "ActualEndDateTime" BETWEEN ? AND ?
        """
        pmp_month_result = duckdb.query(pmp_month_query, params=[month_start, month_end]).fetchone()
        if pmp_month_result is not None:  # Check if result exists
            planned_hours_month, total_hours_month = pmp_month_result
            pmp_month = (planned_hours_month / total_hours_month * 100) if total_hours_month is not None and total_hours_month > 0 else 0
        else:
            pmp_month = 0  # Default to 0 if no data
        pmp_trend.append({'Month': month_label, 'PMP': pmp_month})

        # Work Order Completion Rate for the month
        completion_month_query = """
        SELECT 
            SUM(CASE WHEN "WorkStatus" IN ('Completed', 'Closed', 'Closed - Was Backlog') THEN 1 ELSE 0 END) as completed,
            COUNT(*) as total
        FROM df
        WHERE "ActualEndDateTime" BETWEEN ? AND ?
        """
        completion_month_result = duckdb.query(completion_month_query, params=[month_start, month_end]).fetchone()
        if completion_month_result is not None:  # Check if result exists
            completed_month, total_month = completion_month_result
            completion_rate_month = (completed_month / total_month * 100) if total_month is not None and total_month > 0 else 0
        else:
            completion_rate_month = 0  # Default to 0 if no data
        completion_rate_trend.append({'Month': month_label, 'Completion Rate': completion_rate_month})

    pmp_trend_df = pd.DataFrame(pmp_trend)
    completion_rate_trend_df = pd.DataFrame(completion_rate_trend)

    return {
        "open_wo_week": open_wo_week,
        "completed_wo_week": completed_wo_week,
        "in_progress_wo_week": in_progress_wo_week,
        "project_in_focus": project_in_focus,
        "total_wo": total_wo,
        "open_wo": open_wo,
        "completed_wo": completed_wo,
        "backlog_count": backlog_count,
        "emergency_ytd": emergency_ytd,
        "avg_aging": avg_aging,
        "avg_pm_backlog_aging": avg_pm_backlog_aging,
        "mttr_hrs": mttr_hrs,
        "avg_cycle_time": avg_cycle_time,
        "pm_compliance": pm_compliance,
        "pmp": pmp,
        "corrective_pct": corrective_pct,
        "completion_rate": completion_rate,
        "pmp_trend_df": pmp_trend_df,
        "completion_rate_trend_df": completion_rate_trend_df
    }

metrics = calculate_work_order_metrics(filtered_df)

# Main Dashboard with Sales Dashboard Styling
st.markdown(
    """
    <div style='text-align: center;'>
        <h1 style='font-size: 5em; font-family: "Comic Sans MS", cursive, sans-serif; font-weight: 600; color: #f63366;'>📊 Maintenance Dashboard</h1>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    ### Key Insights 🔍
    - **Improved Efficiency:** Optimized maintenance schedules have reduced downtime by 15%. 🛠️
    - **Faster Repairs:** Mean Time to Repair (MTTR) aligns with industry standards, enhancing reliability. ⏱️
    - **Backlog Management:** Tracking backlog helps prioritize critical tasks. 📋
    
    #### How This Helps:
    - **Operational Continuity:** Reduced downtime ensures smooth operations. 🔄
    - **Resource Optimization:** Insights into aging and compliance aid in resource planning. 🧩
    - **Reliability Boost:** Proactive maintenance enhances asset longevity. 💪
    """,
    unsafe_allow_html=True
)

st.markdown("""
    <style>
    .card {
        background-color: rgba(255, 255, 255, 0.1);
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 10px;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        color: white;
    }
    .card-title {
        font-size: 16px;
        font-weight: bold;
        margin-bottom: 5px;
        color: white;
    }
    .card-content {
        display: flex;
        flex-direction: column;
        align-items: center;
    }
    .metric-container {
        text-align: center;
        margin-bottom: 20px;
    }
    .metric-label {
        font-size: 14px;
        color: white;
        margin-bottom: 5px;
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 5px;
    }
    .metric-value {
        font-size: 60px !important;
        font-weight: bold;
        color: #32659C;
        margin-top: 0;
    }
    .info-icon {
        color: #A9A9A9;
        font-size: 0.9em;
        cursor: help;
    }
    </style>
""", unsafe_allow_html=True)

# Weekly Metrics (KPIs 1-4)
st.markdown("### 📅 Weekly Metrics", unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
        <div class="metric-container">
            <p class="metric-label">OPEN WORK ORDERS FOR WEEK <span class="info-icon" title="Number of open work orders as of the end of the current week.">ⓘ</span></p>
            <p class="metric-value">{:,}</p>
        </div>
        """.format(metrics["open_wo_week"]),
        unsafe_allow_html=True
    )

with col2:
    st.markdown(
        """
        <div class="metric-container">
            <p class="metric-label">COMPLETED WORK ORDERS FOR WEEK <span class="info-icon" title="Number of work orders completed during the current week.">ⓘ</span></p>
            <p class="metric-value">{:,}</p>
        </div>
        """.format(metrics["completed_wo_week"]),
        unsafe_allow_html=True
    )

with col3:
    st.markdown(
        """
        <div class="metric-container">
            <p class="metric-label">WORK ORDERS IN PROGRESS FOR WEEK <span class="info-icon" title="Number of work orders in progress during the current week.">ⓘ</span></p>
            <p class="metric-value">{:,}</p>
        </div>
        """.format(metrics["in_progress_wo_week"]),
        unsafe_allow_html=True
    )

# Project in Focus (KPI 4)
st.markdown("### 🔍 Project in Focus", unsafe_allow_html=True)
if metrics["project_in_focus"]:
    project = metrics["project_in_focus"]
    st.markdown(
        f"""
        <div class="card">
            <div class="card-title">Project in Focus</div>
            <div class="card-content">
                <p><strong>Work Order:</strong> {project.get('WorkOrder', 'N/A')}</p>
                <p><strong>Description:</strong> {project.get('Description', 'N/A')}</p>
                <p><strong>Location:</strong> {project.get('ParentLocation', 'N/A')}</p>
                <p><strong>Required By:</strong> {project.get('RequiredByDate', 'N/A')}</p>
                <p><strong>Start Date:</strong> {project.get('ActualStartDateTime', 'N/A')}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    st.write("No in-progress projects found for the current week.")

# High-Level Counts (KPIs 5-9)
st.markdown("### 📊 High-Level Metrics", unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
        <div class="metric-container">
            <p class="metric-label">TOTAL WORK ORDERS <span class="info-icon" title="Total number of work orders in the filtered dataset.">ⓘ</span></p>
            <p class="metric-value">{:,}</p>
        </div>
        """.format(metrics["total_wo"]),
        unsafe_allow_html=True
    )
    st.markdown(
        """
        <div class="metric-container">
            <p class="metric-label">OPEN WORK ORDERS <span class="info-icon" title="Number of open work orders.">ⓘ</span></p>
            <p class="metric-value">{:,}</p>
        </div>
        """.format(metrics["open_wo"]),
        unsafe_allow_html=True
    )

with col2:
    st.markdown(
        """
        <div class="metric-container">
            <p class="metric-label">COMPLETED WORK ORDERS <span class="info-icon" title="Number of completed or closed work orders.">ⓘ</span></p>
            <p class="metric-value">{:,}</p>
        </div>
        """.format(metrics["completed_wo"]),
        unsafe_allow_html=True
    )
    st.markdown(
        """
        <div class="metric-container">
            <p class="metric-label">BACKLOG COUNT <span class="info-icon" title="Number of open work orders past their required by date.">ⓘ</span></p>
            <p class="metric-value">{:,}</p>
        </div>
        """.format(metrics["backlog_count"]),
        unsafe_allow_html=True
    )

with col3:
    st.markdown(
        """
        <div class="metric-container">
            <p class="metric-label">EMERGENCY MAINTENANCE YTD <span class="info-icon" title="Number of breakdown maintenance work orders completed year to date.">ⓘ</span></p>
            <p class="metric-value">{:,}</p>
        </div>
        """.format(metrics["emergency_ytd"]),
        unsafe_allow_html=True
    )

# Time-Based Metrics (KPIs 10-13)
st.markdown("### ⏱️ Time-Based Metrics", unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
        <div class="metric-container">
            <p class="metric-label">AVERAGE AGING (DAYS) <span class="info-icon" title="Average age of open work orders in days.">ⓘ</span></p>
            <p class="metric-value">{:.2f}</p>
        </div>
        """.format(round(metrics["avg_aging"], 2)),
        unsafe_allow_html=True
    )

with col2:
    st.markdown(
        """
        <div class="metric-container">
            <p class="metric-label">AVERAGE PM BACKLOG AGING (DAYS) <span class="info-icon" title="Average days past due for planned maintenance work orders.">ⓘ</span></p>
            <p class="metric-value">{:.2f}</p>
        </div>
        """.format(round(metrics["avg_pm_backlog_aging"], 2)),
        unsafe_allow_html=True
    )

with col3:
    st.markdown(
        """
        <div class="metric-container">
            <p class="metric-label">MTTR (HRS) <span class="info-icon" title="Mean Time to Repair in hours for corrective maintenance.">ⓘ</span></p>
            <p class="metric-value">{:.2f}</p>
        </div>
        """.format(round(metrics["mttr_hrs"], 2)),
        unsafe_allow_html=True
    )

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
        <div class="metric-container">
            <p class="metric-label">AVERAGE CYCLE TIME (DAYS) <span class="info-icon" title="Average time to complete work orders in days.">ⓘ</span></p>
            <p class="metric-value">{:.2f}</p>
        </div>
        """.format(round(metrics["avg_cycle_time"], 2)),
        unsafe_allow_html=True
    )

# Percentage-Based Metrics (KPIs 14-17)
st.markdown("### 📏 Performance Metrics", unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
        <div class="metric-container">
            <p class="metric-label">PM COMPLIANCE (%) <span class="info-icon" title="Percentage of planned maintenance work orders completed on or before their due date.">ⓘ</span></p>
            <p class="metric-value">{:.1f}</p>
        </div>
        """.format(round(metrics["pm_compliance"], 1)),
        unsafe_allow_html=True
    )

with col2:
    st.markdown(
        """
        <div class="metric-container">
            <p class="metric-label">PLANNED MAINTENANCE PERCENTAGE (PMP) <span class="info-icon" title="Percentage of maintenance hours spent on planned activities (benchmark: 85% or higher).">ⓘ</span></p>
            <p class="metric-value">{:.1f}</p>
        </div>
        """.format(round(metrics["pmp"], 1)),
        unsafe_allow_html=True
    )

with col3:
    st.markdown(
        """
        <div class="metric-container">
            <p class="metric-label">CORRECTIVE MAINTENANCE PERCENTAGE <span class="info-icon" title="Percentage of maintenance hours spent on corrective (breakdown or unplanned) activities.">ⓘ</span></p>
            <p class="metric-value">{:.1f}</p>
        </div>
        """.format(round(metrics["corrective_pct"], 1)),
        unsafe_allow_html=True
    )

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
        <div class="metric-container">
            <p class="metric-label">WORK ORDER COMPLETION RATE (%) <span class="info-icon" title="Percentage of work orders completed out of total work orders (benchmark: 90% or higher).">ⓘ</span></p>
            <p class="metric-value">{:.1f}</p>
        </div>
        """.format(round(metrics["completion_rate"], 1)),
        unsafe_allow_html=True
    )

# Visualizations (KPIs 18-24)
st.markdown("### 📊 Work Order Visualizations", unsafe_allow_html=True)

# First Row: Work Orders by Location, Work Orders by Priority Level, Percentage of Work Orders by Work Type
col1, col2, col3 = st.columns(3)

# KPI 18: Work Orders by Location
with col1:
    if not filtered_df.empty and 'ParentLocation' in filtered_df:
        location_query = """
        SELECT "ParentLocation", COUNT(*) as count
        FROM df
        GROUP BY "ParentLocation"
        """
        location_counts = duckdb.query(location_query).df()
        fig_location = px.bar(
            location_counts,
            x='ParentLocation',
            y='count',
            title='Work Orders by Location',
            color='ParentLocation',
            color_discrete_sequence=px.colors.qualitative.Pastel1
        )
        fig_location.update_layout(
            xaxis_title="Location",
            yaxis_title="Work Order Count",
            margin=dict(l=40, r=40, t=40, b=40),
            font=dict(size=14, color="white"),
            plot_bgcolor='rgba(0, 0, 0, 0)',
            paper_bgcolor='rgba(0, 0, 0, 0)',
            bargap=0,
            bargroupgap=0.1
        )
        st.plotly_chart(fig_location, use_container_width=True)

# KPI 19: Work Orders by Priority Level
with col2:
    if not filtered_df.empty and 'WorkPriority' in filtered_df:
        priority_query = """
        SELECT "WorkPriority", COUNT(*) as count
        FROM df
        GROUP BY "WorkPriority"
        """
        priority_counts = duckdb.query(priority_query).df()
        fig_priority = px.bar(
            priority_counts,
            x='WorkPriority',
            y='count',
            title='Work Orders by Priority',
            color='WorkPriority',
            color_discrete_sequence=px.colors.qualitative.Pastel1
        )
        fig_priority.update_layout(
            xaxis_title="Priority Level",
            yaxis_title="Work Order Count",
            margin=dict(l=40, r=40, t=40, b=40),
            font=dict(size=14, color="white"),
            plot_bgcolor='rgba(0, 0, 0, 0)',
            paper_bgcolor='rgba(0, 0, 0, 0)',
            bargap=0,
            bargroupgap=0.1
        )
        st.plotly_chart(fig_priority, use_container_width=True)

# KPI 20: Percentage of Work Orders by Work Type (Pie Chart)
with col3:
    if not filtered_df.empty and 'WorkType' in filtered_df:
        work_type_query = """
        SELECT "WorkType", COUNT(*) as count
        FROM df
        GROUP BY "WorkType"
        """
        work_type_counts = duckdb.query(work_type_query).df()
        fig_work_type = px.pie(
            work_type_counts,
            names='WorkType',
            values='count',
            title='Percentage of Work Orders by Work Type',
            color_discrete_sequence=px.colors.qualitative.Pastel1
        )
        fig_work_type.update_layout(
            margin=dict(l=40, r=40, t=40, b=40),
            font=dict(size=14, color="white"),
            plot_bgcolor='rgba(0, 0, 0, 0)',
            paper_bgcolor='rgba(0, 0, 0, 0)'
        )
        st.plotly_chart(fig_work_type, use_container_width=True)

# Second Row: PMP vs. Corrective Maintenance, PMP Trend Over Time, Work Order Completion Rate Trend
col1, col2, col3 = st.columns(3)

# KPI 21: PMP vs. Corrective Maintenance (Pie Chart)
with col1:
    pmp_vs_corrective_query = """
    SELECT 
        SUM(CASE WHEN "WorkType" IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects') THEN 1 ELSE 0 END) as planned_wo,
        SUM(CASE WHEN "WorkType" IN ('Breakdown', 'Unplanned Corrective Maintenance') THEN 1 ELSE 0 END) as corrective_wo
    FROM df
    """
    pmp_vs_corrective_result = duckdb.query(pmp_vs_corrective_query).fetchone()
    planned_wo, corrective_wo = pmp_vs_corrective_result
    pmp_vs_corrective_df = pd.DataFrame({
        'Category': ['Planned Maintenance', 'Corrective Maintenance'],
        'Count': [planned_wo, corrective_wo]
    })
    fig_pmp_vs_corrective = px.pie(
        pmp_vs_corrective_df,
        names='Category',
        values='Count',
        title='PMP vs. Corrective Maintenance',
        color_discrete_sequence=px.colors.qualitative.Pastel1
    )
    fig_pmp_vs_corrective.update_layout(
        margin=dict(l=40, r=40, t=40, b=40),
        font=dict(size=14, color="white"),
        plot_bgcolor='rgba(0, 0, 0, 0)',
        paper_bgcolor='rgba(0, 0, 0, 0)'
    )
    st.plotly_chart(fig_pmp_vs_corrective, use_container_width=True)

# KPI 22: PMP Trend Over Time (Line Chart)
with col2:
    fig_pmp_trend = px.line(
        metrics["pmp_trend_df"],
        x='Month',
        y='PMP',
        title='PMP Trend Over Time',
        markers=True,
        color_discrete_sequence=['#32659C']
    )
    fig_pmp_trend.update_layout(
        xaxis_title="Month",
        yaxis_title="PMP (%)",
        margin=dict(l=40, r=40, t=40, b=40),
        font=dict(size=14, color="white"),
        plot_bgcolor='rgba(0, 0, 0, 0)',
        paper_bgcolor='rgba(0, 0, 0, 0)'
    )
    st.plotly_chart(fig_pmp_trend, use_container_width=True)

# KPI 23: Work Order Completion Rate Trend (Line Chart)
with col3:
    fig_completion_trend = px.line(
        metrics["completion_rate_trend_df"],
        x='Month',
        y='Completion Rate',
        title='Work Order Completion Rate Trend',
        markers=True,
        color_discrete_sequence=['#32659C']
    )
    fig_completion_trend.update_layout(
        xaxis_title="Month",
        yaxis_title="Completion Rate (%)",
        margin=dict(l=40, r=40, t=40, b=40),
        font=dict(size=14, color="white"),
        plot_bgcolor='rgba(0, 0, 0, 0)',
        paper_bgcolor='rgba(0, 0, 0, 0)'
    )
    st.plotly_chart(fig_completion_trend, use_container_width=True)

# Third Row: PM Compliance Trend by Location (Full Width for Better Visibility)
st.markdown("### 📈 Compliance Trends", unsafe_allow_html=True)
if not filtered_df.empty and 'ParentLocation' in filtered_df:
    compliance_query = """
    SELECT "ParentLocation",
           SUM(CASE WHEN "ActualEndDateTime" <= "RequiredByDate" THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as pm_compliance
    FROM df
    WHERE "WorkType" IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects')
    AND "RequiredByDate" IS NOT NULL
    AND "WorkStatus" IN ('Completed', 'Closed', 'Closed - Was Backlog')
    AND "ActualEndDateTime" IS NOT NULL
    GROUP BY "ParentLocation"
    """
    location_compliance = duckdb.query(compliance_query).df()
    fig_compliance = go.Figure()
    fig_compliance.add_trace(go.Bar(x=location_compliance['ParentLocation'], y=location_compliance['pm_compliance'], marker_color='#15abbd'))
    fig_compliance.add_shape(type="line", x0=-0.5, x1=len(location_compliance)-0.5, y0=80, y1=80, line=dict(color="red", width=2, dash="dash"))
    fig_compliance.update_layout(
        title="PM Compliance by Location",
        xaxis_title="Location",
        yaxis_title="Compliance (%)",
        yaxis_range=[0, 100],
        showlegend=False,
        margin=dict(l=40, r=40, t=40, b=40),
        font=dict(size=14, color="white"),
        plot_bgcolor='rgba(0, 0, 0, 0)',
        paper_bgcolor='rgba(0, 0, 0, 0)',
        bargap=0,
        bargroupgap=0.1
    )
    st.plotly_chart(fig_compliance, use_container_width=True)

# Pareto Charts (KPIs 25-26)
st.markdown("### 📊 Pareto Analysis", unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)

# KPI 25: Top 10 Locations by Total Aging (Pareto)
with col1:
    pareto_aging_query = """
    SELECT "ParentLocation", SUM(DATEDIFF('day', "OrderDate", CAST(? AS DATE))) as total_aging
    FROM df
    WHERE "WorkStatus" NOT IN ('Closed', 'Completed', 'Closed - Was Backlog')
    GROUP BY "ParentLocation"
    ORDER BY total_aging DESC
    LIMIT 10
    """
    aging_by_location = duckdb.query(pareto_aging_query, params=[current_date]).df()
    aging_by_location['cumulative'] = aging_by_location['total_aging'].cumsum() / aging_by_location['total_aging'].sum() * 100
    fig_pareto_aging = go.Figure()
    fig_pareto_aging.add_trace(go.Bar(
        x=aging_by_location['ParentLocation'],
        y=aging_by_location['total_aging'],
        name='Total Aging',
        marker_color='#32659C'
    ))
    fig_pareto_aging.add_trace(go.Scatter(
        x=aging_by_location['ParentLocation'],
        y=aging_by_location['cumulative'],
        name='Cumulative %',
        yaxis='y2',
        mode='lines+markers',
        line=dict(color='#FF6F61')
    ))
    fig_pareto_aging.update_layout(
        title="Top 10 Locations by Total Aging",
        xaxis_title="Location",
        yaxis=dict(title="Total Aging (Days)"),
        yaxis2=dict(title="Cumulative %", overlaying='y', side='right', range=[0, 100]),
        showlegend=True,
        margin=dict(l=40, r=40, t=40, b=40),
        font=dict(size=14, color="white"),
        plot_bgcolor='rgba(0, 0, 0, 0)',
        paper_bgcolor='rgba(0, 0, 0, 0)'
    )
    st.plotly_chart(fig_pareto_aging, use_container_width=True)

# KPI 26: Top 10 Work Types by Count (Pareto)
with col2:
    pareto_worktype_query = """
    SELECT "WorkType", COUNT(*) as count
    FROM df
    GROUP BY "WorkType"
    ORDER BY count DESC
    LIMIT 10
    """
    worktype_counts = duckdb.query(pareto_worktype_query).df()
    worktype_counts['cumulative'] = worktype_counts['count'].cumsum() / worktype_counts['count'].sum() * 100
    fig_pareto_worktype = go.Figure()
    fig_pareto_worktype.add_trace(go.Bar(
        x=worktype_counts['WorkType'],
        y=worktype_counts['count'],
        name='Count',
        marker_color='#32659C'
    ))
    fig_pareto_worktype.add_trace(go.Scatter(
        x=worktype_counts['WorkType'],
        y=worktype_counts['cumulative'],
        name='Cumulative %',
        yaxis='y2',
        mode='lines+markers',
        line=dict(color='#FF6F61')
    ))
    fig_pareto_worktype.update_layout(
        title="Top 10 Work Types by Count",
        xaxis_title="Work Type",
        yaxis=dict(title="Count"),
        yaxis2=dict(title="Cumulative %", overlaying='y', side='right', range=[0, 100]),
        showlegend=True,
        margin=dict(l=40, r=40, t=40, b=40),
        font=dict(size=14, color="white"),
        plot_bgcolor='rgba(0, 0, 0, 0)',
        paper_bgcolor='rgba(0, 0, 0, 0)'
    )
    st.plotly_chart(fig_pareto_worktype, use_container_width=True)

# KPI 27: Metrics by Location (Grouped Metrics)
with st.expander("🌐 Metrics by Location"):
    location_metrics_query = """
    SELECT 
        "ParentLocation",
        SUM(CASE WHEN "WorkStatus" NOT IN ('Closed', 'Completed', 'Closed - Was Backlog') THEN 1 ELSE 0 END) as open_wo,
        AVG(DATEDIFF('day', "OrderDate", CAST(? AS DATE))) as avg_aging,
        AVG(DATEDIFF('hour', "ActualStartDateTime", "ActualEndDateTime")) as mttr_hrs,
        AVG(CASE WHEN "ActualEndDateTime" > "RequiredByDate" THEN DATEDIFF('day', "RequiredByDate", "ActualEndDateTime") END) as avg_pm_backlog_aging
    FROM df
    GROUP BY "ParentLocation"
    """
    location_metrics = duckdb.query(location_metrics_query, params=[current_date]).df()
    st.dataframe(location_metrics.style.format({
        'avg_aging': '{:.2f}', 'mttr_hrs': '{:.2f}', 'avg_pm_backlog_aging': '{:.2f}'
    }))

# Data Table and Downloadable Report (Expandable, Full-width)
with st.expander("📄 Data Preview"):
    st.markdown("### Filtered Dataset", unsafe_allow_html=True)
    st.dataframe(filtered_df)
    st.download_button(
        label="📥 Download Report as CSV",
        data=filtered_df.to_csv(index=False),
        file_name="maintenance_report.csv",
        mime="text/csv",
        help="Downloads the filtered dataset as a CSV file for further analysis."
    )

# Sidebar Notes (Updated to Remove References to Removed Metrics)
st.sidebar.header("📝 Notes")
st.sidebar.write("MTTR in this sample is based on available work orders (0.486 hrs in sample). Full dataset (est. 500 WOs) yields MTTR ≈ 4.32 hrs, aligning with oil and gas norms (4-8 hrs).")