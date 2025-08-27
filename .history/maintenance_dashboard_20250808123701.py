# -----------------------------------------
# Imports and Configuration
# -----------------------------------------
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import duckdb
import numpy as np
import os
import base64


st.set_page_config(page_title="GPMS Maintenance Dashboard", page_icon=":bar_chart:", layout="wide")

# Function to create a download link for a file
def get_binary_file_downloader_html(file_path, file_label):
    if not os.path.exists(file_path):
        st.error(f"Error: {file_path} not found. Please ensure the KPI manual HTML file is generated.")
        return None
    with open(file_path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{os.path.basename(file_path)}">{file_label}</a>'
    return href

# Compact download link at the top of the dashboard
st.markdown(
    '<p style="font-size:16px;">📖 <a href="data:application/octet-stream;base64,{}" download="kpi_manual.html">Download KPI Manual (HTML)</a> to view metric definitions.</p>'.format(
        base64.b64encode(open("kpi_manual.html", "rb").read()).decode()
    ) if os.path.exists("kpi_manual.html") else '<p style="font-size:16px;color:red;">Error: KPI Manual not found.</p>',
    unsafe_allow_html=True
)

# 🔁 Reload Button Logic (Top of Main Page)
refresh_data = st.button("🔁 Reload Data (Clear Cache)")

# -----------------------------------------
# Constants and Helper Functions
# -----------------------------------------
# Constants
DATE_COLS = {'RequiredByDate': '%m/%d/%Y'}
DATETIME_COLS = {
    'OrderDate': '%m/%d/%Y %H:%M',
    'ReportedDate': '%m/%d/%Y %H:%M',
    'ActualStartDateTime': '%m/%d/%Y %H:%M',
    'ActualEndDateTime': '%m/%d/%Y %H:%M'
}
WORK_STATUSES_COMPLETED = ['Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog']

# Helper function to parse dates
def parse_dates(df, date_columns):
    for col, fmt in date_columns.items():
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format=fmt, errors='coerce')

# Helper function to calculate duration
def calculate_duration(row):
    """
    Calculate the duration in hours between start and end datetimes.
    
    Args:
        row: DataFrame row containing ActualStartDateTime and ActualEndDateTime
        
    Returns:
        float: Duration in hours or None if either datetime is missing
    """
    if pd.notnull(row['ActualStartDateTime']) and pd.notnull(row['ActualEndDateTime']):
        return (row['ActualEndDateTime'] - row['ActualStartDateTime']).total_seconds() / 3600
    return None

# Helper function to create consistent chart styling
def apply_chart_styling(fig, title, xaxis_title=None, yaxis_title=None):
    """
    Apply consistent styling to Plotly charts.
    
    Args:
        fig: Plotly figure object
        title: Chart title
        xaxis_title: X-axis title (optional)
        yaxis_title: Y-axis title (optional)
        
    Returns:
        fig: Styled Plotly figure
    """
    fig.update_layout(
        title=title,
        xaxis_title=xaxis_title,
        yaxis_title=yaxis_title,
        margin=dict(l=40, r=40, t=40, b=40),
        font=dict(size=14, color="white"),
        plot_bgcolor='rgba(0, 0, 0, 0)',
        paper_bgcolor='rgba(0, 0, 0, 0)'
    )
    return fig

# -----------------------------------------
# Data Loading and Preprocessing
# -----------------------------------------
def load_data_uncached():
    """
    Load and preprocess data from the Excel file without caching.
    
    Returns:
        pd.DataFrame: Processed dataframe with calculated fields or empty dataframe if file not found
    """
    file_path = "Asset Work History.xlsx"  
    try:
        df = pd.read_excel(file_path)  
    except FileNotFoundError:
        st.error(f"File not found: {file_path}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()

    # Parse date and datetime columns
    parse_dates(df, DATE_COLS)
    parse_dates(df, DATETIME_COLS)

    # Replace priority codes
    df['WorkPriority'] = df['WorkPriority'].replace({'P1': 'P1 - High', 'P2': 'P2 - Medium', 'P3': 'P3 - Low'})

    # Calculate Duration
    df['Duration'] = df.apply(calculate_duration, axis=1)

    # Fill missing RequiredByDate
    df['RequiredByDate'] = df['RequiredByDate'].combine_first(
        df['OrderDate'] + pd.to_timedelta(6 - df['OrderDate'].dt.weekday, unit='D')
    )

    # Calculate RequiredByDateEnd
    df['RequiredByDateEnd'] = df['RequiredByDate'] + pd.Timedelta(hours=23, minutes=59, seconds=59)

    # Calculate OnTimeStatus
    df['OnTimeStatus'] = np.where(
        (df['WorkStatus'].isin(WORK_STATUSES_COMPLETED)) &
        (df['ActualEndDateTime'].notna()) &
        (df['RequiredByDateEnd'].notna()),
        np.where(df['ActualEndDateTime'] <= df['RequiredByDateEnd'], 'On Time', 'Late'),
        'Unknown'
    )

    # Week of the Year for filtering
    try:
        reference_date = df['RequiredByDate'].combine_first(df['OrderDate']).combine_first(df['ActualEndDateTime'])
        df['WeekOfYear'] = reference_date.dt.isocalendar().week
    except Exception as e:
        # If there's an issue creating WeekOfYear, set it to None
        df['WeekOfYear'] = None

    # Month and Year for filtering
    if 'OrderDate' in df.columns and not df['OrderDate'].isna().all():
        df['Month Name'] = df['OrderDate'].dt.strftime('%B')
        df['Year'] = df['OrderDate'].dt.year
    else:
        # Create empty columns if OrderDate is not available or all NaN
        df['Month Name'] = None
        df['Year'] = None

    return df

@st.cache_data
def load_data_cached():
    return load_data_uncached()

# ✅ Load data based on button click
df = load_data_uncached() if refresh_data else load_data_cached()

# -----------------------------------------
# Current Date and Dashboard Header
# -----------------------------------------
current_date = pd.to_datetime(datetime.now().date())
current_date_end = current_date + pd.Timedelta(hours=23, minutes=59, seconds=59)
st.write(f"Current date set to: {current_date}")

st.markdown(
    """
    <div style='text-align: center; padding: 10px 0; background-color: #0E1117;'>
        <h1 style='
            font-size: 4em;
            font-family: "Montserrat", sans-serif;
            font-weight: 700;
            color: white;
            margin: 0;
        '>📊 GPMS Maintenance Dashboard</h1>
    </div>
    """,
    unsafe_allow_html=True
)



# -----------------------------------------
# Dashboard Filters
# -----------------------------------------
with st.container():
    # Define filter options with error handling
    try:
        # Check if Month Name column exists and has valid data
        if 'Month Name' in df.columns and not df['Month Name'].isna().all():
            month_options = ['All'] + sorted(df['Month Name'].dropna().unique(), key=lambda x: pd.to_datetime(x, format='%B').month)
        else:
            month_options = ['All']
            st.warning("Month Name data is not available. Month filtering will be limited.")
    except Exception as e:
        month_options = ['All']
        st.warning(f"Error processing month data: {str(e)}. Month filtering will be limited.")
    
    try:
        # Check if Year column exists and has valid data
        if 'Year' in df.columns and not df['Year'].isna().all():
            year_options = ['All'] + sorted(df['Year'].dropna().astype(int).unique())
        else:
            year_options = ['All']
            st.warning("Year data is not available. Year filtering will be limited.")
    except Exception as e:
        year_options = ['All']
        st.warning(f"Error processing year data: {str(e)}. Year filtering will be limited.")
    
    try:
        # Check if WeekOfYear column exists and has valid data
        if 'WeekOfYear' in df.columns and not df['WeekOfYear'].isna().all():
            week_options = ['All'] + sorted(df['WeekOfYear'].dropna().astype(int).unique())
        else:
            week_options = ['All']
            st.warning("Week data is not available. Week filtering will be limited.")
    except Exception as e:
        week_options = ['All']
        st.warning(f"Error processing week data: {str(e)}. Week filtering will be limited.")
    
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

# -----------------------------------------
# Apply Filters to Data
# -----------------------------------------
filtered_df = df.copy()
if selected_months and 'All' not in selected_months and 'Month Name' in df.columns:
    filtered_df = filtered_df[filtered_df['Month Name'].isin(selected_months)]
if selected_years and 'All' not in selected_years and 'Year' in df.columns:
    filtered_df = filtered_df[filtered_df['Year'].isin(selected_years)]
if selected_work_types and 'All' not in selected_work_types:
    filtered_df = filtered_df[filtered_df['WorkType'].isin(selected_work_types)]
if selected_work_status and 'All' not in selected_work_status:
    filtered_df = filtered_df[filtered_df['WorkStatus'].isin(selected_work_status)] 
if selected_work_priority and 'All' not in selected_work_priority:
    filtered_df = filtered_df[filtered_df['WorkPriority'].isin(selected_work_priority)]
if selected_locations and 'All' not in selected_locations:
    filtered_df = filtered_df[filtered_df['ParentLocation'].isin(selected_locations)]
if selected_weeks and 'All' not in selected_weeks and 'WeekOfYear' in df.columns:
    filtered_df = filtered_df[filtered_df['WeekOfYear'].isin(selected_weeks)]

if filtered_df.empty:
    st.warning("No data matches the selected filters. Please adjust your filter selections.")
    st.stop()

# -----------------------------------------
# Metrics Calculation
# -----------------------------------------
def calculate_work_order_metrics(df):
    """
    Calculate various work order metrics from the provided dataframe.
    
    This function computes a wide range of maintenance KPIs including:
    - Weekly metrics (open, completed, in-progress work orders)
    - High-level counts (total, open, completed, backlog, emergency)
    - Percentage-based metrics (PM compliance, PMP, corrective percentage)
    - Trend data for PMP and completion rates
    - Location-based metrics
    
    Args:
        df (pd.DataFrame): Filtered dataframe containing work order data
        
    Returns:
        dict: Dictionary containing all calculated metrics
    """
    duckdb.register('df', df)
    
    # Weekly Metrics (KPIs 1-3)
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
    """
    open_wo_week = duckdb.query(current_open_wo_week_query).fetchone()[0] or 0
    completed_wo_week = duckdb.query(completed_wo_week_query, params=[current_week_start, current_week_end]).fetchone()[0] or 0
    in_progress_wo_week = duckdb.query(in_progress_wo_week_query).fetchone()[0] or 0
    project_in_focus_result = duckdb.query(project_in_progress_query).df()
    project_in_progress_count = len(project_in_focus_result)
    total_projects_ytd = duckdb.query(total_projects_ytd_query).fetchone()[0] or 0

    # High-Level Counts (KPIs 4-8)
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

    # Percentage-Based Metrics (KPIs 11-13)
    pm_compliance = 0.0
    pmp = 0.0
    corrective_pct = 0.0
    completion_rate = 0.0

    pm_compliance_query = """
    SELECT 
        SUM(CASE WHEN "OnTimeStatus" = 'On Time' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0) as pm_compliance
    FROM df
    WHERE "WorkType" IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects', 'Predictive Maint')
    AND COALESCE("RequiredByDate", "OrderDate") IS NOT NULL
    AND "WorkStatus" NOT IN ('Cancelled')
    """
    try:
        result = duckdb.query(pm_compliance_query).fetchone()
        pm_compliance = result[0] if result and result[0] is not None else 0.0
    except Exception as e:
        print(f"Error in pm_compliance query: {e}")

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
    try:
        pmp_result = duckdb.query(pmp_query).fetchone()
        planned_hours, corrective_hours, total_hours = pmp_result if pmp_result else (0, 0, 0)
        pmp = (planned_hours / (planned_hours + corrective_hours) * 100) if (planned_hours + corrective_hours) > 0 else 0.0
    except Exception as e:
        print(f"Error in pmp query: {e}")

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
    try:
        corrective_result = duckdb.query(corrective_pct_query).fetchone()
        corrective_hours_corrective, planned_hours_corrective = corrective_result if corrective_result else (0, 0)
        corrective_pct = (corrective_hours_corrective / (planned_hours_corrective + corrective_hours_corrective) * 100) if (planned_hours_corrective + corrective_hours_corrective) > 0 else 0.0
    except Exception as e:
        print(f"Error in corrective_pct query: {e}")

    completion_rate_query = """
    SELECT 
        SUM(CASE WHEN "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog') THEN 1 ELSE 0 END) as completed,
        COUNT(*) as total
    FROM df
    """
    try:
        completion_result = duckdb.query(completion_rate_query).fetchone()
        completed, total = completion_result if completion_result else (0, 0)
        completion_rate = (completed / total * 100) if total > 0 else 0.0
    except Exception as e:
        print(f"Error in completion_rate query: {e}")

    # Check for other WorkType values
    worktype_query = """
    SELECT DISTINCT "WorkType"
    FROM df
    WHERE "WorkType" NOT IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects', 'Breakdown', 'Unplanned Corrective Maint.', 'Predictive Maint')
    """
    other_worktypes = duckdb.query(worktype_query).df()

    # Trend Data for PMP and Work Order Completion Rate (KPIs 14-15)
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
        try:
            pmp_month_result = duckdb.query(pmp_month_query, params=[month_start, month_end]).fetchone()
            planned_hours_month, total_hours_month = pmp_month_result or (0, 0)
            total_hours_month = total_hours_month if total_hours_month is not None else 0
            pmp_month = (planned_hours_month / total_hours_month * 100) if total_hours_month > 0 else 0
        except Exception as e:
            print(f"Error calculating PMP for month {month_label}: {e}")
            pmp_month = 0
        
        pmp_trend.append({'Month': month_label, 'PMP': pmp_month})

        try:
            completion_month_query = """
            SELECT 
                SUM(CASE WHEN "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog') THEN 1 ELSE 0 END) as completed,
                COUNT(*) as total
            FROM df
            WHERE "ActualEndDateTime" IS NOT NULL
            AND "ActualEndDateTime" BETWEEN ? AND ?
            """
            completion_month_result = duckdb.query(completion_month_query, params=[month_start, month_end]).fetchone()
            completed_month, total_month = completion_month_result or (0, 0)
            total_month = total_month if total_month is not None else 0
            completion_rate_month = (completed_month / total_month * 100) if total_month > 0 else 0
        except Exception as e:
            print(f"Error calculating completion rate for month {month_label}: {e}")
            completion_rate_month = 0
            
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
        monthly_wo_trend_df = monthly_wo_trend_df.set_index('Month').reindex(expected_months).fillna(0).reset_index()
    else:
        monthly_wo_trend_df = pd.DataFrame({
            'Month': expected_months,
            'Total Work Orders': [0] * 6,
            'Completed Work Orders': [0] * 6
        })

    # Work Order On-Time Completion Percentage (KPI 16)
    on_time_completion_query = """
    SELECT 
        SUM(CASE WHEN "OnTimeStatus" = 'On Time' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0) as on_time_completion_pct
    FROM df
    WHERE "RequiredByDate" IS NOT NULL
    AND "ActualEndDateTime" IS NOT NULL
    AND "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog')
    """
    try:
        on_time_completion_pct_result = duckdb.query(on_time_completion_query).fetchone()
        on_time_completion_pct = on_time_completion_pct_result[0] if on_time_completion_pct_result and on_time_completion_pct_result[0] is not None else 0
    except Exception as e:
        print("Error in on_time_completion_query:", e)
        on_time_completion_pct = 0


    duckdb.unregister('df')
    
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

# -----------------------------------------
# CSS Styles
# -----------------------------------------
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
        color: #A9A9A9; 
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
# Dashboard Tabs
# -----------------------------------------
dashboard_tab, table_metrics_tab, gantt_chart_tab = st.tabs(["Dashboard", "Table Metrics", "Gantt Chart"])

with dashboard_tab:
    # Weekly Metrics (KPIs 1-3)
    st.markdown("### 📅 Weekly Metrics", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">KPI 1: CURRENT OPEN WORK ORDERS<span class="info-icon" title="Total number of current open work orders.">ⓘ</span></p>
                <p class="metric-value">{:,}</p>
            </div>
            """.format(metrics["open_wo_week"]),
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">KPI 2: COMPLETED WORK ORDERS FOR THE CURRENT WEEK <span class="info-icon" title="Number of work orders completed during the current week.">ⓘ</span></p>
                <p class="metric-value">{:,}</p>
            </div>
            """.format(metrics["completed_wo_week"]),
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">KPI 3: WORK ORDERS IN PROGRESS <span class="info-icon" title="Number of work orders in progress">ⓘ</span></p>
                <p class="metric-value">{:,}</p>
            </div>
            """.format(metrics["in_progress_wo_week"]),
            unsafe_allow_html=True
        )

    # High-Level Metrics (KPIs 4-8)
    st.markdown("### 📊 High-Level Metrics", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">KPI 4: TOTAL WORK ORDERS (FILTERED) <span class="info-icon" title="Total number of work orders in the filtered dataset.">ⓘ</span></p>
                <p class="metric-value">{:,}</p>
            </div>
            """.format(metrics["total_wo"]),
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">KPI 5: COMPLETED WORK ORDERS (FILTERED) <span class="info-icon" title="Number of completed or closed work orders in the filtered dataset.">ⓘ</span></p>
                <p class="metric-value">{:,}</p>
            </div>
            """.format(metrics["completed_wo"]),
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">KPI 6: EMERGENCY MAINTENANCE YTD (FILTERED) <span class="info-icon" title="Number of breakdown maintenance work orders completed year to date in the filtered dataset.">ⓘ</span></p>
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
                <p class="metric-label">KPI 7: BACKLOG COUNT YTD <span class="info-icon" title="Number of overdue work orders from this calendar year.">ⓘ</span></p>
                <p class="metric-value">{:,}</p>
            </div>
            """.format(metrics["backlog_count_ytd"]),
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">KPI 8: BACKLOG COUNT TOTAL <span class="info-icon" title="Total number of overdue work orders across all years.">ⓘ</span></p>
                <p class="metric-value">{:,}</p>
            </div>
            """.format(metrics["backlog_count_total"]),
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(" ", unsafe_allow_html=True)  # Spacer

    # Project Metrics (KPIs 9-10, 11-12)
    st.markdown("### ⏱️Project Metrics", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">KPI 9: PROJECTS IN PROGRESS <span class="info-icon" title="Number of active 'Projects' work orders.">ⓘ</span></p>
                <p class="metric-value">{:,}</p>
            </div>
            """.format(metrics["project_in_progress_count"]),
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">KPI 10: TOTAL PROJECTS YTD <span class="info-icon" title="Total number of 'Projects' completed since Jan 1 this year.">ⓘ</span></p>
                <p class="metric-value">{:,}</p>
            </div>
            """.format(metrics["total_projects_ytd"]),
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(" ", unsafe_allow_html=True)  # Spacer

    # Percentage-Based Metrics (KPIs 11-13)
    st.markdown("### 📏 Maintenance Efficiency Metrics", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">KPI 11: PLANNED MAINTENANCE PERCENTAGE (PMP) <span class="info-icon" title="Percentage of maintenance hours spent on planned activities (benchmark: 85% or higher) (filtered dataset).">ⓘ</span></p>
                <p class="metric-value">{:.2f}</p>
            </div>
            """.format(metrics["pmp"]),
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">KPI 12: CORRECTIVE MAINTENANCE PERCENTAGE <span class="info-icon" title="Percentage of maintenance hours spent on corrective (breakdown or unplanned) activities (filtered dataset).">ⓘ</span></p>
                <p class="metric-value">{:.2f}</p>
            </div>
            """.format(metrics["corrective_pct"]),
            unsafe_allow_html=True
        )
        
    with col3:
        st.markdown(
            """
            <div class="metric-container">
                <p class="metric-label">KPI 13: WORK ORDER COMPLETION RATE (%) <span class="info-icon" title="Percentage of work orders completed out of total work orders (benchmark: 90% or higher) (filtered dataset).">ⓘ</span></p>
                <p class="metric-value">{:.2f}</p>
            </div>
            """.format(round(metrics["completion_rate"], 1)),
            unsafe_allow_html=True
        )

    col1, col2, col3 = st.columns(3)


    with col1:
        st.markdown(" ", unsafe_allow_html=True)  # Spacer

    with col2:
        st.markdown(" ", unsafe_allow_html=True)  # Spacer

    # Work Order Visualizations (KPIs 14-16)
    st.markdown("### 📊 Work Order Visualizations", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)

    # KPI 14: Work Orders by Location
    with col1:
        if not filtered_df.empty and 'ParentLocation' in filtered_df:
            location_query = """
            SELECT "ParentLocation", COUNT(*) as count
            FROM filtered_df
            GROUP BY "ParentLocation"
            """
            location_counts = duckdb.query(location_query).df()
            location_counts = location_counts.sort_values(by='count', ascending=False)
            fig_location = px.bar(
                location_counts,
                x='ParentLocation',
                y='count',
                title='Work Orders by Location',
                color='ParentLocation',
                color_discrete_sequence=px.colors.qualitative.Pastel1
            )
            fig_location = apply_chart_styling(
                fig_location,
                title='Work Orders by Location',
                xaxis_title="Location",
                yaxis_title="Work Order Count"
            )
            fig_location.update_layout(bargap=0, bargroupgap=0.1)
            st.plotly_chart(fig_location, use_container_width=True)

    # KPI 15: Work Orders by Priority Level
    with col2:
        if not filtered_df.empty and 'WorkPriority' in filtered_df:
            priority_query = """
            SELECT "WorkPriority", COUNT(*) as count
            FROM filtered_df
            GROUP BY "WorkPriority"
            """
            priority_counts = duckdb.query(priority_query).df()
            priority_counts = priority_counts.sort_values(by='count', ascending=False)
            fig_priority = px.bar(
                priority_counts,
                x='WorkPriority',
                y='count',
                title='Work Orders by Priority',
                color='WorkPriority',
                color_discrete_sequence=px.colors.qualitative.Pastel1
            )
            fig_priority = apply_chart_styling(
                fig_priority,
                title='Work Orders by Priority',
                xaxis_title="Priority Level",
                yaxis_title="Work Order Count"
            )
            fig_priority.update_layout(bargap=0, bargroupgap=0.1)
            st.plotly_chart(fig_priority, use_container_width=True)

    # KPI 16: Percentage of Work Orders by Work Type
    with col3:
        if not filtered_df.empty and 'WorkType' in filtered_df:
            work_type_query = """
            SELECT "WorkType", COUNT(*) as count
            FROM filtered_df
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
            fig_work_type = apply_chart_styling(
                fig_work_type,
                title='Percentage of Work Orders by Work Type'
            )
            st.plotly_chart(fig_work_type, use_container_width=True)


    col1, col2, col3 = st.columns(3)

    # KPI 17: PMP vs. Corrective Maintenance
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
        planned_hours_pie = planned_hours_pie or 0
        corrective_hours_pie = corrective_hours_pie or 0
        total_pie_hours = planned_hours_pie + corrective_hours_pie
        corrective_pct = (corrective_hours_pie / total_pie_hours * 100) if total_pie_hours > 0 else 0
        planned_pct = (planned_hours_pie / total_pie_hours * 100) if total_pie_hours > 0 else 0  # Use direct calculation

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

    # KPI 18: Monthly Work Order Trends
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

    # KPI 19: Work Order On-Time Completion
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

    # KPI 20 – PM Compliance Trends by Location
    st.markdown("### 📈 Compliance Trends", unsafe_allow_html=True)

    if not filtered_df.empty and 'ParentLocation' in filtered_df:
        kpi22_df = filtered_df.copy()

        # Fill RequiredByDate if missing
        kpi22_df['RequiredByDate'] = kpi22_df.apply(
            lambda x: x['OrderDate'] + pd.Timedelta(days=(6 - x['OrderDate'].weekday()))
            if pd.isnull(x['RequiredByDate']) and pd.notnull(x['OrderDate']) else x['RequiredByDate'],
            axis=1
        )

        # Ensure RequiredByDateEnd and OnTimeStatus are accurate
        kpi22_df['RequiredByDateEnd'] = kpi22_df['RequiredByDate'] + pd.Timedelta(hours=23, minutes=59, seconds=59)

        kpi22_df['OnTimeStatus'] = np.where(
            (kpi22_df['WorkStatus'].isin(['Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog'])) &
            (kpi22_df['ActualEndDateTime'].notna()) &
            (kpi22_df['RequiredByDateEnd'].notna()),
            np.where(kpi22_df['ActualEndDateTime'] <= kpi22_df['RequiredByDateEnd'], 'On Time', 'Late'),
            'Unknown'
        )

        duckdb.register('filtered_df', kpi22_df)

        # Compliance query with Cancelled included in denominator
        compliance_query = """
            SELECT 
                "ParentLocation",
                SUM(CASE 
                    WHEN "OnTimeStatus" = 'On Time' 
                    AND "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog') 
                    THEN 1 ELSE 0 
                END) * 100.0
                / NULLIF(COUNT(*), 0) AS pm_compliance
            FROM filtered_df
            WHERE "WorkType" IN (
                'Planned Maint.', 
                'Planned Corrective Maint.', 
                'Planned Improvement', 
                'Inspection', 
                'Projects', 
                'Predictive Maint'
            )
            AND "RequiredByDate" IS NOT NULL
            AND "RequiredByDate" <= CURRENT_DATE
            GROUP BY "ParentLocation"
        """

        location_compliance = duckdb.query(compliance_query).df().fillna(0)

        if not location_compliance.empty:
            location_compliance = location_compliance.sort_values('pm_compliance', ascending=False)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=location_compliance['ParentLocation'],
                y=location_compliance['pm_compliance'],
                marker_color=px.colors.qualitative.Pastel1[:len(location_compliance)],
                name="PM Compliance (%)"
            ))
            fig.add_shape(
                type="line",
                x0=-0.5,
                x1=len(location_compliance) - 0.5,
                y0=80,
                y1=80,
                line=dict(color="red", width=2, dash="dash")
            )
            fig.update_layout(
                title="PM Compliance by Location",
                xaxis_title="Location",
                yaxis_title="Compliance (%)",
                yaxis=dict(range=[0, 100]),
                showlegend=False,
                margin=dict(l=40, r=40, t=40, b=40),
                font=dict(size=14, color="white"),
                plot_bgcolor='rgba(0, 0, 0, 0)',
                paper_bgcolor='rgba(0, 0, 0, 0)',
                bargap=0.15
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No PM compliance data based on the selected filters.")

        duckdb.unregister('filtered_df')

    else:
        st.warning("No data available for compliance trends under current filters.")


    # Pareto Charts (KPIs 21-23)
    st.markdown("### 📊 Pareto Analysis", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)

    # KPI 21: Top 10 Work Types by Count
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

    # KPI 22: Top 10 FailureType by Count
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

    # KPI 23: Top 10 SystemType by Count
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

    # PM Compliance by Location
    with st.expander("📊 PM Compliance by Location"):
        st.markdown("#### PM Compliance by Location")

        # Current date context
        current_date = pd.to_datetime(datetime.now())
        current_year = current_date.year
        current_month_index = current_date.month
        ytd_start = current_date.replace(month=1, day=1)

        # Build list of expected months up to current
        expected_ytd_months = [datetime(current_year, m, 1).strftime('%B') for m in range(1, current_month_index + 1)]

        # Determine if current filters are default
        default_selected = (
            set(selected_years) == {current_year} and
            all(month in selected_months for month in expected_ytd_months)
        )

        # Patch RequiredByDate and OnTimeStatus
        filtered_df['RequiredByDate'] = filtered_df.apply(
            lambda x: x['OrderDate'] + pd.Timedelta(days=(6 - x['OrderDate'].weekday()))
            if pd.isnull(x['RequiredByDate']) and pd.notnull(x['OrderDate']) else x['RequiredByDate'], axis=1)

        filtered_df['RequiredByDateEnd'] = filtered_df['RequiredByDate'] + pd.Timedelta(hours=23, minutes=59, seconds=59)

        filtered_df['OnTimeStatus'] = np.where(
            (filtered_df['WorkStatus'].isin(['Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog'])) &
            (filtered_df['ActualEndDateTime'].notna()) &
            (filtered_df['RequiredByDateEnd'].notna()),
            np.where(filtered_df['ActualEndDateTime'] <= filtered_df['RequiredByDateEnd'], 'On Time', 'Late'),
            'Unknown')

        duckdb.register('filtered_df', filtered_df)

        base_query = """
            SELECT "ParentLocation",
                SUM(CASE 
                    WHEN "OnTimeStatus" = 'On Time' 
                    AND "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog') 
                    THEN 1 ELSE 0 
                END) * 100.0 / NULLIF(COUNT(*), 0) AS pm_compliance
            FROM filtered_df
            WHERE "WorkType" IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects', 'Predictive Maint')
            AND "RequiredByDate" IS NOT NULL
            AND "RequiredByDate" BETWEEN ? AND ?
            GROUP BY "ParentLocation"
        """

        # Previous Week
        prev_week = current_date.isocalendar().week - 1
        prev_year = current_year if prev_week > 0 else current_year - 1
        if prev_week <= 0:
            prev_week = pd.to_datetime(f'{prev_year}-12-31').isocalendar().week
        prev_week_query = """
            SELECT "ParentLocation",
                SUM(CASE 
                    WHEN "OnTimeStatus" = 'On Time' 
                    AND "WorkStatus" IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog')
                    THEN 1 ELSE 0 
                END) * 100.0 / NULLIF(COUNT(*), 0) AS pm_compliance
            FROM filtered_df
            WHERE "WorkType" IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects', 'Predictive Maint')
            AND "RequiredByDate" IS NOT NULL
            AND EXTRACT(WEEK FROM "RequiredByDate") = ?
            AND EXTRACT(YEAR FROM "RequiredByDate") = ?
            GROUP BY "ParentLocation"
        """

        prev_week_df = duckdb.query(prev_week_query, params=[prev_week, prev_year]).df()
        prev_week_df = prev_week_df.rename(columns={'pm_compliance': 'Previous Week Compliance (%)'}) if not prev_week_df.empty else pd.DataFrame(columns=['ParentLocation', 'Previous Week Compliance (%)'])

        # Current Month
        current_month_start = current_date.replace(day=1)
        curr_month_df = duckdb.query(base_query, params=[current_month_start, current_date]).df()
        curr_month_df = curr_month_df.rename(columns={'pm_compliance': 'Current Month Compliance (%)'}) if not curr_month_df.empty else pd.DataFrame(columns=['ParentLocation', 'Current Month Compliance (%)'])

        # YTD always forced to current year to current date
        ytd_df = duckdb.query(base_query, params=[ytd_start, current_date]).df()
        ytd_df = ytd_df.rename(columns={'pm_compliance': 'YTD Compliance (%)'}) if not ytd_df.empty else pd.DataFrame(columns=['ParentLocation', 'YTD Compliance (%)'])

        compliance_df = prev_week_df.merge(curr_month_df, on='ParentLocation', how='outer')
        compliance_df = compliance_df.merge(ytd_df, on='ParentLocation', how='outer')
        compliance_df = compliance_df.sort_values('ParentLocation').replace(0.00, None)

        if not compliance_df.empty:
            st.dataframe(compliance_df, use_container_width=True, column_config={
                'Previous Week Compliance (%)': st.column_config.NumberColumn(format="%.2f%%", min_value=0, max_value=100),
                'Current Month Compliance (%)': st.column_config.NumberColumn(format="%.2f%%", min_value=0, max_value=100),
                'YTD Compliance (%)': st.column_config.NumberColumn(format="%.2f%%", min_value=0, max_value=100)
            })
        else:
            st.write("No PM compliance data for the selected periods.")

        duckdb.unregister('filtered_df')

        # Open Work Orders Table Metric
    with st.expander("📂 Open Work Orders"):
        st.markdown("#### Open Work Orders")
        if not filtered_df.empty:
            open_wo_df = filtered_df[
                ~filtered_df['WorkStatus'].isin(['Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog', 'Cancelled'])
            ][[
                'OrderDate', 'Order', 'AssetName', 'WorkDescription', 'ActualStartDateTime', 'ActualEndDateTime', 'Duration', 'WorkType', 'SystemType',
                'WorkStatus', 'WorkPriority', 'ParentLocation'
            ]].sort_values(by='OrderDate', ascending=False)

            st.dataframe(
                open_wo_df,
                use_container_width=True,
                column_config={
                    'OrderDate': st.column_config.DateColumn(format="MM/DD/YYYY"),
                    'ActualStartDateTime': st.column_config.DatetimeColumn(format="MM/DD/YYYY HH:mm"),
                    'ActualEndDateTime': st.column_config.DatetimeColumn(format="MM/DD/YYYY HH:mm"),
                    'Duration': st.column_config.NumberColumn(format="%.2f hrs", min_value=0)
                }
            )
        else:
            st.info("No open work orders based on current filters.")

    
    # Completed/Closed Work Orders
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

    with st.expander("❌ Cancelled Work Orders"):
        st.markdown("#### Cancelled Work Orders")
        if not filtered_df.empty:
            cancelled_query = """
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
                WHERE "WorkStatus" = 'Cancelled'
                ORDER BY "OrderDate" DESC
            """
            cancelled_df = duckdb.query(cancelled_query).df()
            st.dataframe(
                cancelled_df,
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
            st.write("No cancelled work orders based on current filters.")

    
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

    # Project Orders
    with st.expander("🏗️ Project Orders"):
        st.markdown("### 🎗️ Project Orders")

        # Register filtered_df
        duckdb.register("filtered_df", filtered_df)

        # Query filtered data
        project_table_query = """
        SELECT "Order", OrderDate, AssetName, WorkDescription, 
            ActualStartDateTime, ActualEndDateTime, Duration,
            WorkType, SystemType, WorkStatus, WorkPriority
        FROM filtered_df
        WHERE WorkType = 'Projects'
        ORDER BY OrderDate DESC
        """
        project_table_df = duckdb.query(project_table_query).df()

        # Unregister to keep session clean
        duckdb.unregister("filtered_df")

        # Display
        st.dataframe(
            project_table_df,
            use_container_width=True,
            column_config={
                'OrderDate': st.column_config.DateColumn(format="MM/DD/YYYY"),
                'ActualStartDateTime': st.column_config.DatetimeColumn(format="MM/DD/YYYY HH:mm"),
                'Duration': st.column_config.NumberColumn(format="%.2f hrs", min_value=0)
            }
        )


    
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

            st.markdown("##### 📄 Raw Change-Out Records")
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
                st.markdown("##### 📊 Combined Reliability Metrics per Buoy Bushes")

                # Group full dataset first for count and total
                summary_df = reliability_df.groupby(['AssetName', 'AssetDescription']).agg(
                    ChangeOutCount=('Order', 'count'),
                    TotalChangeOutHours=('Duration', 'sum'),
                    LastChangeOutDate=('ActualEndDateTime', 'max')
                ).reset_index()

                # Calculate MTTR and MTBF from valid intervals
                valid_df = reliability_df[reliability_df['DaysSinceLastChangeOut'].notnull()]
                reliability_avg = valid_df.groupby('AssetName').agg(
                    MTTR_Hrs=('Duration', 'mean'),
                    MTBF_Days=('DaysSinceLastChangeOut', 'mean')
                ).reset_index()

                # Merge results
                combined_df = summary_df.merge(reliability_avg, on='AssetName', how='left')
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


# -----------------------------------------
# Gannt Chart Tab
# -----------------------------------------
with gantt_chart_tab:
    st.markdown("📅 Gantt Chart – Scheduling View")

    gantt_df = filtered_df[
        (filtered_df['WorkStatus'].isin(['Open', 'In Progress', 'Waiting for Parts', 'Backlog'])) &
        (filtered_df['RequiredByDate'].notnull())
    ].copy()

    if not gantt_df.empty:
        gantt_df['StartDate'] = gantt_df['RequiredByDate'] - pd.Timedelta(days=6)  # (you can adjust how many days before)
        gantt_df['EndDate'] = gantt_df['RequiredByDate']

        fig_gantt = px.timeline(
            gantt_df,
            x_start="StartDate",
            x_end="EndDate",
            y="Order",
            color="ParentLocation",
            hover_data=["WorkDescription", "WorkPriority", "SystemType"],
            title="Gantt Chart – All Active (Open/In-Progress) Work Orders"
        )
        fig_gantt.update_yaxes(autorange="reversed")
        fig_gantt.update_layout(
            xaxis_title="Timeline",
            yaxis_title="Work Order",
            margin=dict(l=40, r=40, t=40, b=40),
            font=dict(size=14, color="white"),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_gantt, use_container_width=True)
    else:
        st.info("No open or in-progress work orders available for Gantt scheduling view.")



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

      # Apply Tab styling 

    st.markdown("""
    <style>
    .stTabs [data-baseweb="tab"] {
        background-color: #1F2937;  /* Darker than main bg for contrast */
        color: white;
        padding: 12px 20px;
        font-size: 1.1rem;
        font-weight: 600;
        border-radius: 5px 5px 0 0;
        margin-right: 5px;
        border: 1px solid #3E4C59;
    }

    .stTabs [aria-selected="true"] {
        background-color: #2563EB !important; /* Active tab highlight */
        color: white;
        border-bottom: 2px solid #2563EB;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background-color: #374151;
        cursor: pointer;
    }
    </style>
""", unsafe_allow_html=True)
