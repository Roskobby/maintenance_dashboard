import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import duckdb
import numpy as np

st.set_page_config(page_title="Maintenance Dashboard", page_icon=":bar_chart:", layout="wide")

# Load Data
@st.cache_data
def load_data():
    file_path = "Asset Work History.csv"
    df = pd.read_csv(file_path)

    # Define date columns
    date_cols = ['OrderDate', 'ReportedDate', 'RequiredByDate']
    datetime_cols = ['ActualStartDateTime', 'ActualEndDateTime']

    # Parse date columns with flexible formats
    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors='coerce')

    # Parse datetime columns with multiple possible formats
    for col in datetime_cols:
        df[col] = pd.to_datetime(df[col], errors='coerce')

    # Replace 'P1', 'P2', 'P3' in WorkPriority
    df['WorkPriority'] = df['WorkPriority'].replace({'P1': 'P1 - High', 'P2': 'P2 - Medium', 'P3': 'P3 - Low'})

    # Calculate Duration only for completed orders
    df['Duration'] = df.apply(
        lambda x: (x['ActualEndDateTime'] - x['ActualStartDateTime']).total_seconds() / 3600
        if pd.notnull(x['ActualStartDateTime']) and pd.notnull(x['ActualEndDateTime'])
        else None,
        axis=1
    )

    # Calculate RequiredByDateEnd
    df['RequiredByDateEnd'] = df['RequiredByDate'] + pd.Timedelta(hours=23, minutes=59, seconds=59)

    # Calculate OnTimeStatus
    df['OnTimeStatus'] = np.where(
        (df['ActualEndDateTime'].notna()) & (df['RequiredByDateEnd'].notna()),
        np.where(df['ActualEndDateTime'] <= df['RequiredByDateEnd'], 'On Time', 'Late'),
        'Unknown'
    )

    # Week of the Year
    reference_date = df['RequiredByDate'].combine_first(df['OrderDate']).combine_first(df['ActualEndDateTime'])
    df['WeekOfYear'] = reference_date.dt.isocalendar().week

    # Derive Month Name and Year for filters
    df['Month Name'] = df['OrderDate'].dt.strftime('%B')
    df['Year'] = df['OrderDate'].dt.year

    return df   

df = load_data()

# Current date
current_date = pd.to_datetime(datetime.now().date())
current_date_end = current_date + pd.Timedelta(hours=23, minutes=59, seconds=59)
st.write(f"Current date set to: {current_date}")

# Dashboard Filters
st.markdown(
    """
    <div style='text-align: center;'>
        <h1 style='font-size: 5em; font-family: "Comic Sans MS", cursive, sans-serif; font-weight: 600; color: #f63366;'>📊 Maintenance Dashboard</h1>
    </div>
    """,
    unsafe_allow_html=True
)

with st.container():
    # Define filter options
    month_options = ['All'] + sorted(df['Month Name'].dropna().unique(), key=lambda x: pd.to_datetime(x, format='%B').month)
    year_options = ['All'] + sorted(df['Year'].dropna().astype(int).unique())
    week_options = ['All'] + sorted(df['WeekOfYear'].dropna().astype(int).unique())
    current_year = current_date.year
    current_month_num = current_date.month
    month_names = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    default_months = month_names[:current_month_num]
    
    default_months = [month for month in default_months if month in month_options]
    if not default_months and 'All' in month_options:
        default_months = ['All']
    
    default_years = [current_year] if current_year in year_options else ['All']
    default_weeks = ['All']
    work_type_options = ['All'] + list(df['WorkType'].dropna().unique())
    work_status_options = ['All'] + list(df['WorkStatus'].dropna().unique())
    work_priority_options = ['All', 'P1 - High', 'P2 - Medium', 'P3 - Low']
    location_options = ['All'] + list(df['ParentLocation'].dropna().unique())
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        with st.container():
            st.markdown('<div class="filter-container">', unsafe_allow_html=True)
            selected_months = st.multiselect("Select Month", month_options, default=default_months, key="month_filter")
            selected_years = st.multiselect("Select Year", year_options, default=default_years, key="year_filter")
            selected_weeks = st.multiselect("Select Week of Year", week_options, default=default_weeks, key="week_filter")
            st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        with st.container():
            st.markdown('<div class="filter-container">', unsafe_allow_html=True)
            selected_work_types = st.multiselect("Select Work Type", work_type_options, default=['All'], key="work_type_filter")
            selected_work_status = st.multiselect("Select Work Status", work_status_options, default=['All'], key="work_status_filter")
            st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        with st.container():
            st.markdown('<div class="filter-container">', unsafe_allow_html=True)
            selected_work_priority = st.multiselect("Select Work Priority", work_priority_options, default=['All'], key="work_priority_filter")
            selected_locations = st.multiselect("Select Location", location_options, default=['All'], key="location_filter")
            st.markdown('</div>', unsafe_allow_html=True)

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
if selected_weeks and 'All' not in selected_weeks:
    filtered_df = filtered_df[filtered_df['WeekOfYear'].isin(selected_weeks)]

if filtered_df.empty:
    st.warning("No data matches the selected filters. Please adjust your filter selections.")
    st.stop()

# KPI Calculations
def calculate_work_order_metrics(df):
    duckdb.register('df', df)
    
    # Weekly Metrics (KPIs 1-4)
    current_week_start = current_date - pd.to_timedelta(current_date.weekday(), unit='D')
    current_week_end = current_week_start + pd.to_timedelta(6, unit='D')
    current_open_wo_week_query = """
    SELECT COUNT(*) as open_wo_week
    FROM df
    WHERE "WorkStatus" NOT IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Cancelled', 'Completed - Was Backlog')
    """
    completed_wo_week_query = """
    SELECT COUNT(*) as completed_wo_week
    FROM df
    WHERE "WorkStatus" IN ('Completed', 'Closed', 'Closed - Was Backlog', 'Completed - Was Backlog')
    AND "ActualEndDateTime" IS NOT NULL
    AND "ActualEndDateTime" >= ?
    AND "ActualEndDateTime" <= ?
    """
    in_progress_wo_week_query = """
    SELECT COUNT(*) as in_progress_wo_week
    FROM df
    WHERE "WorkStatus" = 'In Progress'
    """
    project_in_progress_query = """
    SELECT *
    FROM df
    WHERE "WorkType" = 'Projects' AND "WorkStatus" = 'In Progress'
    """
    total_projects_ytd_query = """
    SELECT COUNT(*) as total_projects_ytd
    FROM df
    WHERE "WorkType" = 'Projects'
    AND "ActualEndDateTime" IS NOT NULL
    AND "ActualEndDateTime" >= ?
    AND "ActualEndDateTime" <= ?
    """
    open_wo_week = duckdb.query(current_open_wo_week_query).fetchone()[0] or 0
    completed_wo_week = duckdb.query(completed_wo_week_query, params=[current_week_start, current_week_end]).fetchone()[0] or 0
    in_progress_wo_week = duckdb.query(in_progress_wo_week_query).fetchone()[0] or 0
    project_in_focus_result = duckdb.query(project_in_progress_query).df()
    project_in_progress_count = len(project_in_focus_result)
    total_projects_ytd = duckdb.query(total_projects_ytd_query, params=[
        pd.to_datetime(f"{current_date.year}-01-01"), current_date
    ]).fetchone()[0] or 0

    # High-Level Counts (KPIs 5-9)
    total_wo = len(df)  # Total work orders in filtered dataset
    open_wo_query = """
    SELECT COUNT(*) as open_wo
    FROM df
    WHERE "WorkStatus" NOT IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Cancelled', 'Completed - Was Backlog')
    """
    completed_wo_query = """
    SELECT COUNT(*) as completed_wo
    FROM df
    WHERE "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog')
    """
    backlog_count_total_query = """
    SELECT COUNT(*) as backlog_count
    FROM df
    WHERE "WorkStatus" NOT IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Cancelled', 'Completed - Was Backlog')
    AND "RequiredByDateEnd" IS NOT NULL
    AND "RequiredByDateEnd" < ?
    """
    backlog_count_ytd_query = """
    SELECT COUNT(*) as backlog_count_ytd
    FROM df
    WHERE "WorkStatus" NOT IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Cancelled', 'Completed - Was Backlog')
    AND "RequiredByDateEnd" IS NOT NULL
    AND "RequiredByDateEnd" < ?
    AND "RequiredByDateEnd" >= ?
    """
    emergency_ytd_query = """
    SELECT COUNT(*) as emergency_ytd
    FROM df
    WHERE "WorkType" = 'Breakdown'
    AND "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog', 'In Progress', 'Open', 'Waiting for Parts', 'Backlog') 
    AND "ActualEndDateTime" IS NOT NULL
    AND "ActualEndDateTime" >= ?
    AND "ActualEndDateTime" <= ?
    """
    open_wo_filtered = duckdb.query(open_wo_query).fetchone()[0] or 0
    completed_wo = duckdb.query(completed_wo_query).fetchone()[0] or 0
    backlog_count_total = duckdb.query(backlog_count_total_query, params=[current_date_end]).fetchone()[0] or 0
    backlog_count_ytd = duckdb.query(backlog_count_ytd_query, params=[
        current_date_end,
        pd.to_datetime(f"{current_date.year}-01-01")
    ]).fetchone()[0] or 0
    emergency_ytd = duckdb.query(emergency_ytd_query, params=[
        pd.to_datetime(f"{current_date.year}-01-01"),
        current_date
    ]).fetchone()[0] or 0

    # Time-Based Metrics (KPIs 10-12)
    avg_aging_query = """
    SELECT AVG(DATEDIFF('day', "OrderDate", CAST(? AS DATE))) as avg_aging
    FROM df
    WHERE "WorkStatus" NOT IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Cancelled')
    AND "OrderDate" IS NOT NULL
    """
    avg_pm_backlog_aging_query = """
    SELECT AVG(DATEDIFF('day', "RequiredByDate", "ActualEndDateTime")) as avg_pm_backlog_aging
    FROM df
    WHERE "WorkType" IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects', 'Predictive Maint')
    AND "OnTimeStatus" = 'Late'
    AND "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog')
    AND "ActualEndDateTime" IS NOT NULL AND "RequiredByDate" IS NOT NULL
    """
    avg_cycle_time_query = """
    SELECT AVG(DATEDIFF('day', "ActualStartDateTime", "ActualEndDateTime")) as avg_cycle_time
    FROM df 
    WHERE "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog')
    AND "ActualStartDateTime" IS NOT NULL AND "ActualEndDateTime" IS NOT NULL
    """
    avg_aging = duckdb.query(avg_aging_query, params=[current_date]).fetchone()[0] or 0
    avg_pm_backlog_aging = duckdb.query(avg_pm_backlog_aging_query).fetchone()[0] or 0
    avg_cycle_time = duckdb.query(avg_cycle_time_query).fetchone()[0] or 0

    # Percentage-Based Metrics (KPIs 13-16)
    pm_compliance_query = """
    SELECT 
        SUM(CASE WHEN "OnTimeStatus" = 'On Time' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0) as pm_compliance
    FROM df
    WHERE "WorkType" IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects', 'Predictive Maint')
    AND "RequiredByDate" IS NOT NULL
    AND "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog')
    AND "ActualEndDateTime" IS NOT NULL
    """
    pmp_query = """
    SELECT 
        SUM(CASE WHEN "WorkType" IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects', 'Predictive Maint')
                 THEN COALESCE("Duration", 0) ELSE 0 END) as planned_hours,
        SUM(CASE WHEN "WorkType" IN ('Breakdown', 'Unplanned Corrective Maintenance')
                 THEN COALESCE("Duration", 0) ELSE 0 END) as corrective_hours,
        SUM(COALESCE("Duration", 0)) as total_hours
    FROM df
    WHERE "ActualStartDateTime" IS NOT NULL AND "ActualEndDateTime" IS NOT NULL
    AND "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog')
    AND "Duration" IS NOT NULL
    """
    corrective_pct_query = """
    SELECT 
        SUM(CASE WHEN "WorkType" IN ('Breakdown', 'Unplanned Corrective Maintenance')
                 THEN COALESCE("Duration", 0) ELSE 0 END) as corrective_hours,
        SUM(CASE WHEN "WorkType" IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects', 'Predictive Maint')
                 THEN COALESCE("Duration", 0) ELSE 0 END) as planned_hours
    FROM df
    WHERE "ActualStartDateTime" IS NOT NULL AND "ActualEndDateTime" IS NOT NULL
    AND "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog')
    AND "Duration" IS NOT NULL
    """
    completion_rate_query = """
    SELECT 
        SUM(CASE WHEN "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog') THEN 1 ELSE 0 END) as completed,
        COUNT(*) as total
    FROM df
    """
    pm_compliance = duckdb.query(pm_compliance_query).fetchone()[0] or 0
    pmp_result = duckdb.query(pmp_query).fetchone()
    planned_hours, corrective_hours, total_hours = pmp_result or (0, 0, 0)
    pmp = (planned_hours / (planned_hours + corrective_hours) * 100) if (planned_hours + corrective_hours) > 0 else 0
    corrective_result = duckdb.query(corrective_pct_query).fetchone()
    corrective_hours_corrective, planned_hours_corrective = corrective_result or (0, 0)
    corrective_pct = (corrective_hours_corrective / (planned_hours_corrective + corrective_hours_corrective) * 100) if (planned_hours_corrective + corrective_hours_corrective) > 0 else 0
    completion_result = duckdb.query(completion_rate_query).fetchone()
    completed, total = completion_result
    completion_rate = (completed / total * 100) if total > 0 else 0

    # Debug
    # st.write(f"KPI 14: Planned Hours = {planned_hours:.2f}, Corrective Hours = {corrective_hours:.2f}, Total Hours = {total_hours:.2f}, PMP = {pmp:.2f}%")
    # st.write(f"KPI 16: Planned Hours = {planned_hours_corrective:.2f}, Corrective Hours = {corrective_hours_corrective:.2f}, Corrective % = {corrective_pct:.2f}%")
    # st.write(f"KPI 16 Raw: Corrective % = {(corrective_hours_corrective / (planned_hours_corrective + corrective_hours_corrective) * 100) if (planned_hours_corrective + corrective_hours_corrective) > 0 else 0:.2f}%")

    # Validate hours
    expected_total = planned_hours + corrective_hours
    if abs(total_hours - expected_total) > 0.01:
        #st.warning(f"Total hours ({total_hours:.2f}) ≠ Planned + Corrective ({expected_total:.2f})")
        worktype_query = """
        SELECT "WorkType", SUM(COALESCE("Duration", 0)) as hours
        FROM df
        WHERE "ActualStartDateTime" IS NOT NULL AND "ActualEndDateTime" IS NOT NULL
        AND "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog')
        AND "Duration" IS NOT NULL
        GROUP BY "WorkType"
        """
        # st.write("WorkType Breakdown:", duckdb.query(worktype_query).df())

    # Check for other WorkType values
    worktype_query = """
    SELECT DISTINCT "WorkType"
    FROM df
    WHERE "WorkType" NOT IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects', 'Breakdown', 'Unplanned Corrective Maint.', 'Predictive Maint')
    """
    other_worktypes = duckdb.query(worktype_query).df()
    #if not other_worktypes.empty:
        #st.write(f"Debug: Other WorkType values found: {other_worktypes['WorkType'].tolist()}")

    # Trend Data for PMP and Work Order Completion Rate (KPIs 17-18)
    pmp_trend = []
    completion_rate_trend = []
    for i in range(11, -1, -1):
        month_end = (current_date.replace(day=1) - pd.to_timedelta(1, unit='D')) - pd.to_timedelta(i * 30, unit='D')
        month_start = month_end.replace(day=1)
        month_label = month_end.strftime('%b %Y')
        
        pmp_month_query = """
        SELECT 
            SUM(CASE WHEN "WorkType" IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects', 'Predictive Maint')
                     THEN DATEDIFF('hour', "ActualStartDateTime", "ActualEndDateTime") ELSE 0 END) as planned_hours,
            SUM(DATEDIFF('hour', "ActualStartDateTime", "ActualEndDateTime")) as total_hours
        FROM df
        WHERE "ActualStartDateTime" IS NOT NULL AND "ActualEndDateTime" IS NOT NULL
        AND "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog')
        AND "ActualEndDateTime" BETWEEN ? AND ?
        """
        pmp_month_result = duckdb.query(pmp_month_query, params=[month_start, month_end]).fetchone()
        planned_hours_month, total_hours_month = pmp_month_result
        total_hours_month = total_hours_month if total_hours_month is not None else 0
        pmp_month = (planned_hours_month / total_hours_month * 100) if total_hours_month > 0 else 0
        pmp_trend.append({'Month': month_label, 'PMP': pmp_month})

        completion_month_query = """
        SELECT 
            SUM(CASE WHEN "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog') THEN 1 ELSE 0 END) as completed,
            COUNT(*) as total
        FROM df
        WHERE "ActualEndDateTime" IS NOT NULL
        AND "ActualEndDateTime" BETWEEN ? AND ?
        """
        completion_month_result = duckdb.query(completion_month_query, params=[month_start, month_end]).fetchone()
        completed_month, total_month = completion_month_result
        total_month = total_month if total_month is not None else 0
        completion_rate_month = (completed_month / total_month * 100) if total_month > 0 else 0
        completion_rate_trend.append({'Month': month_label, 'Completion Rate': completion_rate_month})

    pmp_trend_df = pd.DataFrame(pmp_trend)
    completion_rate_trend_df = pd.DataFrame(completion_rate_trend)

    # Location-Based Metrics for Table
    week_filter = "" if not selected_weeks or 'All' in selected_weeks else "AND WeekOfYear IN ({})".format(
        ",".join([str(w) for w in selected_weeks])
    )
    location_metrics_query = f"""
    SELECT 
        "ParentLocation",
        SUM(CASE WHEN "WorkStatus" NOT IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog', 'Cancelled') THEN 1 ELSE 0 END) as open_wo,
        AVG(DATEDIFF('day', "OrderDate", CAST(? AS DATE))) as avg_aging,
        SUM(CASE 
            WHEN "WorkType" IN ('Breakdown', 'Unplanned Corrective Maint.')
            AND "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog')
            AND "Duration" IS NOT NULL
            THEN "Duration"
            ELSE 0 
        END) * 1.0 / NULLIF(
            SUM(CASE 
                WHEN "WorkType" IN ('Breakdown', 'Unplanned Corrective Maint.')
                AND "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog')
                AND "Duration" IS NOT NULL
                THEN 1 
                ELSE 0 
            END), 0
        ) as mttr_hrs,
        AVG(CASE WHEN "OnTimeStatus" = 'Late' THEN DATEDIFF('day', "RequiredByDate", "ActualEndDateTime") END) as avg_pm_backlog_aging
    FROM df
    WHERE "ParentLocation" IS NOT NULL
    {week_filter}
    GROUP BY "ParentLocation"
    """
    location_metrics = duckdb.query(location_metrics_query, params=[current_date]).df()

    # Work Order Count Trend for last 6 months (including current month)
    monthly_wo_trend = []
    current_month = current_date.replace(day=1)  
    for i in range(5, -1, -1):
        month_start = (current_month - pd.offsets.MonthBegin(i)).replace(hour=0, minute=0, second=0)
        month_end = (month_start + pd.offsets.MonthEnd(0)).replace(hour=23, minute=59, second=59)
        month_label = month_start.strftime('%b %Y')
        
        total_wo_month_query = """
        SELECT COUNT(*) as total_wo_month
        FROM df
        WHERE "OrderDate" BETWEEN ? AND ?
        """
        completed_wo_month_query = """
        SELECT COUNT(*) as completed_wo_month
        FROM df
        WHERE "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog')
        AND "ActualEndDateTime" BETWEEN ? AND ?
        """
        total_wo_month = duckdb.query(total_wo_month_query, params=[month_start, month_end]).fetchone()[0] or 0
        completed_wo_month = duckdb.query(completed_wo_month_query, params=[month_start, month_end]).fetchone()[0] or 0
        
        monthly_wo_trend.append({
            'Month': month_label,
            'Total Work Orders': total_wo_month,
            'Completed Work Orders': completed_wo_month
        })

    # Ensure all 6 months are included, even if no data
    expected_months = [(current_month - pd.offsets.MonthBegin(i)).strftime('%b %Y') for i in range(5, -1, -1)]
    monthly_wo_trend_df = pd.DataFrame(monthly_wo_trend)
    if not monthly_wo_trend_df.empty:
        # Reindex to include all expected months
        monthly_wo_trend_df = monthly_wo_trend_df.set_index('Month').reindex(expected_months).fillna(0).reset_index()
    else:
        # Create empty DataFrame with expected months
        monthly_wo_trend_df = pd.DataFrame({
            'Month': expected_months,
            'Total Work Orders': [0] * 6,
            'Completed Work Orders': [0] * 6
        })

    # Work Order On-Time Completion Percentage
    on_time_completion_query = """
    SELECT 
        SUM(CASE WHEN "OnTimeStatus" = 'On Time' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0) as on_time_completion_pct
    FROM df
    WHERE "RequiredByDate" IS NOT NULL
    AND "ActualEndDateTime" IS NOT NULL
    AND "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog')
    """
    on_time_completion_pct = duckdb.query(on_time_completion_query).fetchone()[0] or 0

    return {
        "open_wo_week": open_wo_week,
        "completed_wo_week": completed_wo_week,
        "in_progress_wo_week": in_progress_wo_week,
        "project_in_progress_count": project_in_progress_count,
        "total_projects_ytd": total_projects_ytd,
        "project_in_focus_result": project_in_focus_result,
        "total_wo": total_wo,
        "open_wo_filtered": open_wo_filtered,
        "completed_wo": completed_wo,
        "backlog_count_total": backlog_count_total,
        "backlog_count_ytd": backlog_count_ytd,
        "emergency_ytd": emergency_ytd,
        "avg_aging": avg_aging,
        "avg_pm_backlog_aging": avg_pm_backlog_aging,
        "avg_cycle_time": avg_cycle_time,
        "pm_compliance": pm_compliance,
        "pmp": pmp,
        "corrective_pct": corrective_pct,
        "completion_rate": completion_rate,
        "pmp_trend_df": pmp_trend_df,
        "completion_rate_trend_df": completion_rate_trend_df,
        "location_metrics": location_metrics,
        "monthly_wo_trend_df": monthly_wo_trend_df,
        "on_time_completion_pct": on_time_completion_pct 
    }

metrics = calculate_work_order_metrics(filtered_df)
project_in_focus_result = metrics["project_in_focus_result"]

# CSS Styles
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

# -----------------------------------------
# Create Tabs for Dashboard and Table Metrics
# -----------------------------------------
dashboard_tab, table_metrics_tab = st.tabs(["Dashboard", "Table Metrics"])

with dashboard_tab:
    # Weekly Metrics (KPIs 1-4)
    st.markdown("### 📅 Weekly Metrics", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">CURRENT OPEN WORK ORDERS<span class="info-icon" title="Total number of current open work orders.">ⓘ</span></p>
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
                <p class="metric-label">WORK ORDERS IN PROGRESS <span class="info-icon" title="Number of work orders in progress">ⓘ</span></p>
                <p class="metric-value">{:,}</p>
            </div>
            """.format(metrics["in_progress_wo_week"]),
            unsafe_allow_html=True
        )

    # High-Level Metrics (KPIs 5-9)
    st.markdown("### 📊 High-Level Metrics", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">TOTAL WORK ORDERS (FILTERED) <span class="info-icon" title="Total number of work orders in the filtered dataset.">ⓘ</span></p>
                <p class="metric-value">{:,}</p>
            </div>
            """.format(metrics["total_wo"]),
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">COMPLETED WORK ORDERS (FILTERED) <span class="info-icon" title="Number of completed or closed work orders in the filtered dataset.">ⓘ</span></p>
                <p class="metric-value">{:,}</p>
            </div>
            """.format(metrics["completed_wo"]),
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">EMERGENCY MAINTENANCE YTD (FILTERED) <span class="info-icon" title="Number of breakdown maintenance work orders completed year to date in the filtered dataset.">ⓘ</span></p>
                <p class="metric-value">{:,}</p>
            </div>
            """.format(metrics["emergency_ytd"]),
            unsafe_allow_html=True
        )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">BACKLOG COUNT YTD <span class="info-icon" title="Number of overdue work orders from this calendar year.">ⓘ</span></p>
                <p class="metric-value">{:,}</p>
            </div>
            """.format(metrics["backlog_count_ytd"]),
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">BACKLOG COUNT TOTAL <span class="info-icon" title="Total number of overdue work orders across all years.">ⓘ</span></p>
                <p class="metric-value">{:,}</p>
            </div>
            """.format(metrics["backlog_count_total"]),
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(" ", unsafe_allow_html=True)  # Spacer

    # Time-Based / Project Metrics (KPIs 10-12, 13-14)
    st.markdown("### ⏱️ Time-Based / Project Metrics", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">AVERAGE AGING (DAYS) <span class="info-icon" title="Average age of open work orders in days (filtered dataset).">ⓘ</span></p>
                <p class="metric-value">{:.2f}</p>
            </div>
            """.format(round(metrics["avg_aging"], 2)),
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">AVERAGE PM BACKLOG AGING (DAYS) <span class="info-icon" title="Average days past due for planned maintenance work orders (filtered dataset).">ⓘ</span></p>
                <p class="metric-value">{:.2f}</p>
            </div>
            """.format(round(metrics["avg_pm_backlog_aging"], 2)),
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">AVERAGE CYCLE TIME (DAYS) <span class="info-icon" title="Average time to complete work orders in days (filtered dataset).">ⓘ</span></p>
                <p class="metric-value">{:.2f}</p>
            </div>
            """.format(round(metrics["avg_cycle_time"], 2)),
            unsafe_allow_html=True
        )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">PROJECTS IN PROGRESS <span class="info-icon" title="Number of active 'Projects' work orders.">ⓘ</span></p>
                <p class="metric-value">{:,}</p>
            </div>
            """.format(metrics["project_in_progress_count"]),
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">TOTAL PROJECTS YTD <span class="info-icon" title="Total number of 'Projects' completed since Jan 1 this year.">ⓘ</span></p>
                <p class="metric-value">{:,}</p>
            </div>
            """.format(metrics["total_projects_ytd"]),
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(" ", unsafe_allow_html=True)  # Spacer

    # Projects in Progress List
    if metrics["project_in_progress_count"] > 0:
        st.markdown("#### 📋 Projects in Progress List")
        st.dataframe(project_in_focus_result)

    # Percentage-Based Metrics (KPIs 13-16)
    st.markdown("### 📏 Performance Metrics", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">PM COMPLIANCE (%) <span class="info-icon" title="Percentage of planned maintenance work orders completed on or before their due date (filtered dataset).">ⓘ</span></p>
                <p class="metric-value">{:.2f}</p>
            </div>
            """.format(round(metrics["pm_compliance"], 1)),
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">PLANNED MAINTENANCE PERCENTAGE (PMP) <span class="info-icon" title="Percentage of maintenance hours spent on planned activities (benchmark: 85% or higher) (filtered dataset).">ⓘ</span></p>
                <p class="metric-value">{:.2f}</p>
            </div>
            """.format(metrics["pmp"]),
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">CORRECTIVE MAINTENANCE PERCENTAGE <span class="info-icon" title="Percentage of maintenance hours spent on corrective (breakdown or unplanned) activities (filtered dataset).">ⓘ</span></p>
                <p class="metric-value">{:.2f}</p>
            </div>
            """.format(metrics["corrective_pct"]),
            unsafe_allow_html=True
        )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">WORK ORDER COMPLETION RATE (%) <span class="info-icon" title="Percentage of work orders completed out of total work orders (benchmark: 90% or higher) (filtered dataset).">ⓘ</span></p>
                <p class="metric-value">{:.2f}</p>
            </div>
            """.format(round(metrics["completion_rate"], 1)),
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(" ", unsafe_allow_html=True)  # Spacer

    with col3:
        st.markdown(" ", unsafe_allow_html=True)  # Spacer

    # Work Order Visualizations (KPIs 19-25)
    st.markdown("### 📊 Work Order Visualizations", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)

    # KPI 19: Work Orders by Location
    with col1:
        if not filtered_df.empty and 'ParentLocation' in filtered_df:
            location_query = """
            SELECT "ParentLocation", COUNT(*) as count
            FROM df
            GROUP BY "ParentLocation"
            """
            location_counts = duckdb.query(location_query).df()
            # Sort by count in descending order for tallest to shortest bars
            location_counts = location_counts.sort_values(by='count', ascending=False)
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

    # KPI 20: Work Orders by Priority Level
    with col2:
        if not filtered_df.empty and 'WorkPriority' in filtered_df:
            priority_query = """
            SELECT "WorkPriority", COUNT(*) as count
            FROM df
            GROUP BY "WorkPriority"
            """
            priority_counts = duckdb.query(priority_query).df()
            # Sort by count in descending order for tallest to shortest bars
            priority_counts = priority_counts.sort_values(by='count', ascending=False)
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

    # KPI 21: Percentage of Work Orders by Work Type
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

    col1, col2, col3 = st.columns(3)

    # Compliance Trends (KPI 22)
    st.markdown("### 📈 Compliance Trends", unsafe_allow_html=True)
    if not filtered_df.empty and 'ParentLocation' in filtered_df:
        compliance_query = """
        SELECT "ParentLocation",
            SUM(CASE WHEN "OnTimeStatus" = 'On Time' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as pm_compliance
        FROM df
        WHERE "WorkType" IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects', 'Predictive Maint')
        AND "OnTimeStatus" IS NOT NULL
        AND "RequiredByDate" IS NOT NULL
        AND "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog')
        AND "ActualEndDateTime" IS NOT NULL
        GROUP BY "ParentLocation"
        """
        location_compliance = duckdb.query(compliance_query).df()
        
        # Sort by compliance in descending order for tallest to shortest
        location_compliance = location_compliance.sort_values('pm_compliance', ascending=False)
        
        fig_compliance = go.Figure()
        fig_compliance.add_trace(
            go.Bar(
                x=location_compliance['ParentLocation'],
                y=location_compliance['pm_compliance'],
                marker_color=px.colors.qualitative.Pastel1[:len(location_compliance)]  # Use Pastel1 colors
            )
        )
        fig_compliance.add_shape(
            type="line",
            x0=-0.5,
            x1=len(location_compliance)-0.5,
            y0=80,
            y1=80,
            line=dict(color="red", width=2, dash="dash")
        )
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


    # KPI 23: PMP vs. Corrective Maintenance
    with col1:
        st.subheader("PMP vs. Corrective Maintenance")
        pmp_vs_corrective_query = """
        SELECT 
            SUM(CASE WHEN "WorkType" IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects', 'Predictive Maint')
                    THEN COALESCE("Duration", 0) ELSE 0 END) as planned_hours,
            SUM(CASE WHEN "WorkType" IN ('Breakdown', 'Unplanned Corrective Maintenance')
                    THEN COALESCE("Duration", 0) ELSE 0 END) as corrective_hours
        FROM filtered_df
        WHERE "ActualStartDateTime" IS NOT NULL AND "ActualEndDateTime" IS NOT NULL
        AND "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog')
        AND "Duration" IS NOT NULL
        """
        pmp_vs_corrective_result = duckdb.query(pmp_vs_corrective_query).fetchone()
        planned_hours_pie, corrective_hours_pie = pmp_vs_corrective_result or (0, 0)
        total_pie_hours = planned_hours_pie + corrective_hours_pie
        corrective_pct = (corrective_hours_pie / total_pie_hours * 100) if total_pie_hours > 0 else 0
        planned_pct = (planned_hours_pie / total_pie_hours * 100) if total_pie_hours > 0 else 0  # Use direct calculation

        # Debug
        #st.write(f"KPI 23: Planned Hours = {planned_hours_pie:.2f}, Corrective Hours = {corrective_hours_pie:.2f}, Total Hours = {total_pie_hours:.2f}")
        #st.write(f"KPI 23 Raw: Planned % = {(planned_hours_pie / total_pie_hours * 100):.2f}, Corrective % = {(corrective_hours_pie / total_pie_hours * 100):.2f}")
        #st.write(f"KPI 23 Display: Planned % = {planned_pct:.2f}, Corrective % = {corrective_pct:.2f}")

        fig = go.Figure(
            data=[
                go.Pie(
                    labels=["Planned Maintenance", "Corrective Maintenance"],
                    values=[planned_hours_pie, corrective_hours_pie],  # Use hours directly
                    textinfo="percent",
                    textposition="inside",
                    texttemplate="%{percent:.2%}",  # Format as percentage
                    marker=dict(colors=px.colors.qualitative.Pastel1),
                )
            ]
        )
        fig.update_layout(
            title="Planned vs. Corrective Maintenance",
            showlegend=True,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=40, b=0, l=0, r=0),
        )
        st.plotly_chart(fig, use_container_width=True)

    # KPI 24: Monthly Work Order Trends
    with col2:
        fig_wo_trend = go.Figure()
        fig_wo_trend.add_trace(
            go.Scatter(
                x=metrics["monthly_wo_trend_df"]['Month'],
                y=metrics["monthly_wo_trend_df"]['Total Work Orders'],
                mode='lines+markers',
                name='Total Work Orders',
                line=dict(color=px.colors.qualitative.Pastel1[0])
            )
        )
        fig_wo_trend.add_trace(
            go.Scatter(
                x=metrics["monthly_wo_trend_df"]['Month'],
                y=metrics["monthly_wo_trend_df"]['Completed Work Orders'],
                mode='lines+markers',
                name='Completed Work Orders',
                line=dict(color=px.colors.qualitative.Pastel1[1])
            )
        )
        fig_wo_trend.update_layout(
            title='Monthly Work Order Trends (Last 6 Months)',
            xaxis_title="Month",
            yaxis_title="Work Order Count",
            margin=dict(l=40, r=40, t=40, b=40),
            font=dict(size=14, color="white"),
            plot_bgcolor='rgba(0, 0, 0, 0)',
            paper_bgcolor='rgba(0, 0, 0, 0)',
            showlegend=True,
            yaxis=dict(rangemode="tozero")  # Ensure y-axis starts at 0 but scales dynamically
        )
        st.plotly_chart(fig_wo_trend, use_container_width=True)

    # KPI 25: Work Order On-Time Completion
    with col3:
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=metrics["on_time_completion_pct"],
            title={"text": "Work Order On-Time Completion (%)"},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "white"},
                "bar": {"color": px.colors.qualitative.Pastel1[1]},  # Light blue for gauge bar
                "bgcolor": "rgba(0, 0, 0, 0)",
                "bordercolor": "white",
                "steps": [
                    {"range": [0, 30], "color": px.colors.qualitative.Pastel1[3]},   # Red for 0-10%
                    {"range": [30, 60], "color": px.colors.qualitative.Pastel1[6]},  # Teal for 10-30%
                    {"range": [60, 90], "color": px.colors.qualitative.Pastel1[4]},  # Pink for 30-50%
                    {"range": [90, 100], "color": px.colors.qualitative.Pastel1[2]}  # Green for 90-100%
                ],
                "threshold": {
                    "line": {"color": "red", "width": 4},
                    "thickness": 0.75,
                    "value": 90  # Benchmark at 90%
                }
            }
        ))
        fig_gauge.update_layout(
            margin=dict(l=40, r=40, t=40, b=40),
            font=dict(size=14, color="white"),
            plot_bgcolor='rgba(0, 0, 0, 0)',
            paper_bgcolor='rgba(0, 0, 0, 0)'
        )
        st.plotly_chart(fig_gauge, use_container_width=True)

    # Pareto Charts (KPIs 26-28)
    st.markdown("### 📊 Pareto Analysis", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)

    # KPI 26: Top 10 Work Types by Count
    with col1:
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
            marker_color=px.colors.qualitative.Pastel1[0]
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

    # KPI 27: Top 10 FailureType by Count
    with col2:
        pareto_failure_type_query = """
        SELECT "FailureType", COUNT(*) as count
        FROM df
        WHERE "FailureType" IS NOT NULL
        GROUP BY "FailureType"
        ORDER BY count DESC
        LIMIT 10
        """
        failure_type_counts = duckdb.query(pareto_failure_type_query).df()
        failure_type_counts['cumulative'] = failure_type_counts['count'].cumsum() / failure_type_counts['count'].sum() * 100
        fig_pareto_failure_type = go.Figure()
        fig_pareto_failure_type.add_trace(go.Bar(
            x=failure_type_counts['FailureType'],
            y=failure_type_counts['count'],
            name='Count',
            marker_color=px.colors.qualitative.Pastel1[0]
        ))
        fig_pareto_failure_type.add_trace(go.Scatter(
            x=failure_type_counts['FailureType'],
            y=failure_type_counts['cumulative'],
            name='Cumulative %',
            yaxis='y2',
            mode='lines+markers',
            line=dict(color='#FF6F61')  # Coral, like KPI 26 & 27
        ))
        fig_pareto_failure_type.update_layout(
            title="Top 10 Failure Types by Count",
            xaxis_title="Failure Type",
            yaxis=dict(title="Count"),
            yaxis2=dict(title="Cumulative %", overlaying='y', side='right', range=[0, 100]),
            showlegend=True,
            margin=dict(l=40, r=40, t=40, b=40),
            font=dict(size=14, color="white"),
            plot_bgcolor='rgba(0, 0, 0, 0)',
            paper_bgcolor='rgba(0, 0, 0, 0)'
        )
        st.plotly_chart(fig_pareto_failure_type, use_container_width=True)

    # KPI 28: Top 10 SystemType by Count
    with col3:
        pareto_system_type_query = """
        SELECT "SystemType", COUNT(*) as count
        FROM df
        WHERE "SystemType" IS NOT NULL
        GROUP BY "SystemType"
        ORDER BY count DESC
        LIMIT 10
        """
        system_type_counts = duckdb.query(pareto_system_type_query).df()
        system_type_counts['cumulative'] = system_type_counts['count'].cumsum() / system_type_counts['count'].sum() * 100
        fig_pareto_system_type = go.Figure()
        fig_pareto_system_type.add_trace(go.Bar(
            x=system_type_counts['SystemType'],
            y=system_type_counts['count'],
            name='Count',
            marker_color=px.colors.qualitative.Pastel1[0]  # Light blue
        ))
        fig_pareto_system_type.add_trace(go.Scatter(
            x=system_type_counts['SystemType'],
            y=system_type_counts['cumulative'],
            name='Cumulative %',
            yaxis='y2',
            mode='lines+markers',
            line=dict(color='#FF6F61')  # Coral
        ))
        fig_pareto_system_type.update_layout(
            title="Top 10 System Types by Count",
            xaxis_title="System Type",
            yaxis=dict(title="Count"),
            yaxis2=dict(title="Cumulative %", overlaying='y', side='right', range=[0, 100]),
            showlegend=True,
            margin=dict(l=40, r=40, t=40, b=40),
            font=dict(size=14, color="white"),
            plot_bgcolor='rgba(0, 0, 0, 0)',
            paper_bgcolor='rgba(0, 0, 0, 0)'
        )
        st.plotly_chart(fig_pareto_system_type, use_container_width=True)

    # Data Table and Downloadable Report
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

# -----------------------------------------
# Table Metrics Tab
# -----------------------------------------
with table_metrics_tab:
    st.markdown("### 📋 Table Metrics", unsafe_allow_html=True)
    
    # Open Orders (unchanged)
    with st.expander("📅 Open Work Orders"):
        st.markdown("#### Open Work Orders")
        if not filtered_df.empty:
            display_df = filtered_df[
                filtered_df['WorkStatus'].isin(['Open', 'Backlog', 'In Progress', 'Waiting for Approval'])
            ][[
                'OrderDate', 'Order', 'AssetName', 'WorkDescription', 'RequiredByDate', 
                'ActualStartDateTime', 'ActualEndDateTime', 'Duration', 
                'WorkType', 'SystemType', 'WorkStatus', 'WorkPriority'
            ]].sort_values('OrderDate', ascending=False)
            st.dataframe(
                display_df,
                use_container_width=True,
                column_config={
                    'OrderDate': st.column_config.DateColumn(format="MM/DD/YYYY"),
                    'RequiredByDate': st.column_config.DateColumn(format="MM/DD/YYYY"),
                    'ActualStartDateTime': st.column_config.DatetimeColumn(format="MM/DD/YYYY HH:mm"),
                    'ActualEndDateTime': st.column_config.DatetimeColumn(format="MM/DD/YYYY HH:mm"),
                    'Duration': st.column_config.NumberColumn(format="%.2f hrs", min_value=0)
                }
            )
        else:
            st.write("No open work orders for the selected filters.")
    
    # Completed/Closed Work Orders (unchanged)
    with st.expander("✅ Completed/Closed Work Orders"):
        st.markdown("#### Completed/Closed Work Orders")
        if not filtered_df.empty:
            display_df = filtered_df[
                (filtered_df['WorkStatus'].isin(['Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog'])) &
                (filtered_df['ActualEndDateTime'].notna())
            ][[
                'OrderDate', 'Order', 'AssetName', 'WorkDescription', 'RequiredByDate', 
                'ActualStartDateTime', 'ActualEndDateTime', 'Duration', 
                'WorkType', 'SystemType', 'WorkStatus', 'WorkPriority'
            ]].sort_values('OrderDate', ascending=False)
            st.dataframe(
                display_df,
                use_container_width=True,
                column_config={
                    'OrderDate': st.column_config.DateColumn(format="MM/DD/YYYY"),
                    'RequiredByDate': st.column_config.DateColumn(format="MM/DD/YYYY"),
                    'ActualStartDateTime': st.column_config.DatetimeColumn(format="MM/DD/YYYY HH:mm"),
                    'ActualEndDateTime': st.column_config.DatetimeColumn(format="MM/DD/YYYY HH:mm"),
                    'Duration': st.column_config.NumberColumn(format="%.2f hrs", min_value=0)
                }
            )
        else:
            st.write("No completed/closed work orders for the selected filters.")
    
    # New: Corrective Work Orders
    with st.expander("📋 Corrective Work Orders"):
        st.markdown("#### Corrective Work Orders")
        if not filtered_df.empty:
            corrective_query = """
                SELECT 
                    "OrderDate",
                    "Order",
                    "AssetName",
                    "WorkDescription",
                    "RequiredByDate",
                    "ActualStartDateTime",
                    "ActualEndDateTime",
                    "Duration",
                    "WorkType",
                    "SystemType",
                    "WorkStatus",
                    "WorkPriority",
                    "ParentLocation"
                FROM filtered_df
                WHERE "WorkType" IN ('Planned Corrective Maint.', 'Unplanned Corrective Maint.', 'Breakdown', 'Planned Improvement')
                ORDER BY "OrderDate" DESC
            """
            corrective_df = duckdb.query(corrective_query).df()
            st.dataframe(
                corrective_df,
                use_container_width=True,
                column_config={
                    'OrderDate': st.column_config.DateColumn(format="MM/DD/YYYY"),
                    'RequiredByDate': st.column_config.DateColumn(format="MM/DD/YYYY"),
                    'ActualStartDateTime': st.column_config.DatetimeColumn(format="MM/DD/YYYY HH:mm"),
                    'ActualEndDateTime': st.column_config.DatetimeColumn(format="MM/DD/YYYY HH:mm"),
                    'Duration': st.column_config.NumberColumn(format="%.2f hrs", min_value=0)
                }
            )
        else:
            st.write("No corrective work orders for the selected filters.")
    
    # New: Emergency Work Orders
    with st.expander("🚨 Emergency Work Orders"):
        st.markdown("#### Emergency Work Orders (Breakdown, Unplanned)")
        if not filtered_df.empty:
            emergency_query = """
                SELECT 
                    "OrderDate",
                    "Order",
                    "AssetName",
                    "WorkDescription",
                    "RequiredByDate",
                    "ActualStartDateTime",
                    "ActualEndDateTime",
                    "Duration",
                    "WorkType",
                    "SystemType",
                    "WorkStatus",
                    "WorkPriority",
                    "ParentLocation"
                FROM filtered_df
                WHERE "WorkType" IN ('Breakdown', 'Unplanned Corrective Maint.')
                AND "WorkPriority" = 'P1 - High'
                ORDER BY "OrderDate" DESC
            """
            emergency_df = duckdb.query(emergency_query).df()
            st.dataframe(
                emergency_df,
                use_container_width=True,
                column_config={
                    'OrderDate': st.column_config.DateColumn(format="MM/DD/YYYY"),
                    'RequiredByDate': st.column_config.DateColumn(format="MM/DD/YYYY"),
                    'ActualStartDateTime': st.column_config.DatetimeColumn(format="MM/DD/YYYY HH:mm"),
                    'ActualEndDateTime': st.column_config.DatetimeColumn(format="MM/DD/YYYY HH:mm"),
                    'Duration': st.column_config.NumberColumn(format="%.2f hrs", min_value=0)
                }
            )
        else:
            st.write("No emergency work orders for the selected filters.")
    
    # Project Orders YTD
    with st.expander("🏗️ Project Orders YTD"):
        st.markdown("#### Project Work Orders Year to Date")
        if not filtered_df.empty:
            ytd_start = pd.to_datetime(f"{current_date.year}-01-01")
            project_query = """
                SELECT "Order", OrderDate, AssetName, WorkDescription, 
                       WorkType, SystemType, WorkStatus, WorkPriority
                FROM filtered_df
                WHERE WorkType = 'Projects'
                AND OrderDate >= ?
                AND OrderDate <= ?
                ORDER BY OrderDate
            """
            project_df = duckdb.query(project_query, params=[ytd_start, current_date]).df()
            st.dataframe(
                project_df,
                use_container_width=True,
                column_config={
                    'OrderDate': st.column_config.DateColumn(format="MM/DD/YYYY")
                }
            )
        else:
            st.write("No project orders for the selected filters.")
    
    # MTTR by Location 
    with st.expander("🌐 MTTR by Location"):
        st.markdown("#### Mean Time to Repair by Location (Hours)")
        st.dataframe(
            metrics["location_metrics"][['ParentLocation', 'mttr_hrs']].style.format({
                'mttr_hrs': '{:.2f}'
            }),
            use_container_width=True
        )
    
    # Work Orders by WorkType 
    with st.expander("🛠️ Work Order Distribution by WorkType"):
        st.markdown("#### Work Order Distribution by WorkType")
        if not filtered_df.empty:
            worktype_query = """
                SELECT 
                    WorkType,
                    COUNT(*) AS count,
                    ROUND(SUM(Duration), 2) AS hours,
                    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
                FROM filtered_df
                WHERE WorkType IS NOT NULL
                GROUP BY WorkType
                ORDER BY count DESC
            """
            worktype_df = duckdb.query(worktype_query).df()
            st.dataframe(
                worktype_df,
                use_container_width=True,
                column_config={
                    'count': st.column_config.NumberColumn(format="%d"),
                    'hours': st.column_config.NumberColumn(format="%.2f hrs"),
                    'percentage': st.column_config.NumberColumn(format="%.2f%%")
                }
            )
        else:
            st.write("No WorkType data for the selected filters.")
        
    # Work Orders by SystemType 
    with st.expander("🛠️ Work Orders by SystemType"):
        st.markdown("#### Work Order Distribution by SystemType")
        if not filtered_df.empty:
            system_type_query = """
                SELECT SystemType, COUNT(*) as count,
                       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
                FROM filtered_df
                WHERE SystemType IS NOT NULL
                GROUP BY SystemType
                ORDER BY count DESC
            """
            system_type_df = duckdb.query(system_type_query).df()
            st.dataframe(
                system_type_df,
                use_container_width=True,
                column_config={
                    'percentage': st.column_config.NumberColumn(format="%.2f%%")
                }
            )
        else:
            st.write("No SystemType data for the selected filters.")
    
    # Work Orders by WorkStatus
    with st.expander("📊 Work Orders by WorkStatus"):
        st.markdown("#### Work Order Distribution by WorkStatus")
        if not filtered_df.empty:
            status_query = """
                SELECT WorkStatus, COUNT(*) as count,
                       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
                FROM filtered_df
                GROUP BY WorkStatus
                ORDER BY count DESC
            """
            status_df = duckdb.query(status_query).df()
            st.dataframe(
                status_df,
                use_container_width=True,
                column_config={
                    'percentage': st.column_config.NumberColumn(format="%.2f%%")
                }
            )
        else:
            st.write("No WorkStatus data for the selected filters.")
    
    # High-Priority Work Orders
    with st.expander("🚨 High-Priority Work Orders"):
        st.markdown("#### High-Priority (P1) Work Orders")
        if not filtered_df.empty:
            high_priority_query = """
                SELECT "Order", OrderDate, AssetName, WorkDescription, WorkStatus
                FROM filtered_df
                WHERE WorkPriority = 'P1 - High'
                ORDER BY OrderDate
            """
            high_priority_df = duckdb.query(high_priority_query).df()
            st.dataframe(
                high_priority_df,
                use_container_width=True,
                column_config={
                    'OrderDate': st.column_config.DateColumn(format="MM/DD/YYYY")
                }
            )
        else:
            st.write("No high-priority work orders for the selected filters.")
    
    # FailureType Breakdown
    with st.expander("⚠️ FailureType Breakdown"):
        st.markdown("#### Work Orders by FailureType")
        if not filtered_df.empty:
            failure_type_query = """
                SELECT FailureType, COUNT(*) as count,
                       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
                FROM filtered_df
                WHERE FailureType IS NOT NULL
                GROUP BY FailureType
                ORDER BY count DESC
            """
            failure_type_df = duckdb.query(failure_type_query).df()
            st.dataframe(
                failure_type_df,
                use_container_width=True,
                column_config={
                    'percentage': st.column_config.NumberColumn(format="%.2f%%")
                }
            )
        else:
            st.write("No FailureType data for the selected filters.")

    # Buoy Bush Change-Out Reliability
    with st.expander("🔧 Buoy Bush Change-Out Reliability"):
        st.markdown("#### Buoy Bush Change-Out Reliability")

        if not filtered_df.empty:
            reliability_query = """
                SELECT 
                    "AssetName",
                    "AssetDescription",
                    "Order",
                    "OrderDate",
                    "WorkDescription",
                    "ActualStartDateTime",
                    "ActualEndDateTime",
                    "Duration",
                    "WorkStatus",
                    DATEDIFF('day', 
                        LAG("ActualEndDateTime") OVER (
                            PARTITION BY "AssetName" 
                            ORDER BY "ActualEndDateTime"
                        ),
                        "ActualEndDateTime"
                    ) AS "DaysSinceLastChangeOut"
                FROM filtered_df
                WHERE "AssetName" IN ('ABB-ME-BY-03', 'ABB-ME-BY-04', 'ABB-ME-BY-02', 'ABB-ME-BY-05')
                AND "SystemType" = 'Buoy Body'
                AND "FailureType" = 'Worn'
                AND "RemedyType" = 'Replaced'
                AND "WorkDescription" ILIKE '%UKP Bush%'
                ORDER BY "ActualEndDateTime" DESC
            """
            reliability_df = duckdb.query(reliability_query).df()

            st.markdown("##### 📄 Raw Change-Out Records (Latest First)")
            st.dataframe(
                reliability_df,
                use_container_width=True,
                column_config={
                    'OrderDate': st.column_config.DateColumn(format="MM/DD/YYYY"),
                    'ActualStartDateTime': st.column_config.DatetimeColumn(format="MM/DD/YYYY HH:mm"),
                    'ActualEndDateTime': st.column_config.DatetimeColumn(format="MM/DD/YYYY HH:mm"),
                    'Duration': st.column_config.NumberColumn(format="%.2f hrs", min_value=0),
                    'DaysSinceLastChangeOut': st.column_config.NumberColumn(format="%d days", min_value=0)
                }
            )

            if not reliability_df.empty:
                st.markdown("##### 📊 Combined Reliability Metrics per Buoy")

                valid_df = reliability_df[reliability_df['DaysSinceLastChangeOut'].notnull()]

                combined_df = valid_df.groupby(['AssetName', 'AssetDescription']).agg(
                    ChangeOutCount=('Order', 'count'),
                    MTTR_Hrs=('Duration', 'mean'),
                    MTBF_Days=('DaysSinceLastChangeOut', 'mean'),
                    TotalChangeOutHours=('Duration', 'sum'),
                    LastChangeOutDate=('ActualEndDateTime', 'max')
                ).reset_index()

                combined_df['NextEstimatedChangeOut'] = pd.to_datetime(combined_df['LastChangeOutDate']) + pd.to_timedelta(combined_df['MTBF_Days'], unit='D')
                combined_df['MTTR_Hrs'] = combined_df['MTTR_Hrs'].round(2)
                combined_df['MTBF_Days'] = combined_df['MTBF_Days'].round(2)
                combined_df['TotalChangeOutHours'] = combined_df['TotalChangeOutHours'].round(2)

                st.dataframe(
                    combined_df,
                    use_container_width=True,
                    column_config={
                        'ChangeOutCount': st.column_config.NumberColumn(format="%d"),
                        'MTTR_Hrs': st.column_config.NumberColumn(format="%.2f hrs"),
                        'MTBF_Days': st.column_config.NumberColumn(format="%.2f days"),
                        'TotalChangeOutHours': st.column_config.NumberColumn(format="%.2f hrs"),
                        'LastChangeOutDate': st.column_config.DatetimeColumn(format="YYYY-MM-DD"),
                        'NextEstimatedChangeOut': st.column_config.DatetimeColumn(format="YYYY-MM-DD")
                    }
                )
            else:
                st.info("No summary metrics available.")
        else:
            st.warning("No buoy bush change-out data for the selected filters.")


    # Apply consistent styling
    st.markdown("""
        <style>
        .stDataFrame {
            background-color: rgba(0, 0, 0, 0);
            color: white;
        }
        .stDataFrame th, .stDataFrame td {
            color: white;
        }
        .st-expander {
            background-color: rgba(0, 0, 0, 0);
            color: white;
        }
        .st-expanderHeader {
            color: white;
        }
        </style>
    """, unsafe_allow_html=True)