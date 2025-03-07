import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_elements import elements, mui, html
from datetime import datetime

# Load Data
@st.cache_data
def load_data():
    file_path = "Asset Work History.csv"
    df = pd.read_csv(file_path, parse_dates=['OrderDate', 'ActualStartDateTime', 'ActualEndDateTime', 'ReportedDate', 'RequiredByDate'])
    # Ensure Month Name and Year are present
    df['Month Name'] = df['OrderDate'].dt.strftime('%B')
    df['Year'] = df['OrderDate'].dt.year.astype(int)
    # Map WorkPriority if needed
    df['WorkPriority'] = df['WorkPriority'].replace({
        'P1': 'P1 - High',
        'P2': 'P2 - Medium',
        'P3': 'P3 - Low'
    })
    # Calculate Duration if not provided
    if 'Duration' not in df.columns or df['Duration'].isna().all():
        df['Duration'] = (df['ActualEndDateTime'] - df['ActualStartDateTime']).dt.total_seconds() / 3600  # Convert to hours
    return df

df = load_data()

# Current date for aging calculations
current_date = pd.to_datetime("2025-03-07")

# Sidebar Theming
with st.sidebar:
    st.markdown('''
        <style>
        section[data-testid="stSidebar"] {
            width: 400px;
            background-color: #32659C;
            padding: 20px;
            color: white;
        }
        </style>
    ''', unsafe_allow_html=True)

    st.title(":wrench: Maintenance Dashboard")
    st.markdown("""
        This dashboard provides an analysis of maintenance work orders, including planned and unplanned maintenance,
        work requests, downtime tracking, and performance metrics. The data helps track work order trends,
        completion rates, and efficiency across different locations.
    """)

    # Sidebar Filters
    st.header("🔍 Filter Options")
    month_options = ['All'] + sorted(df['Month Name'].dropna().unique(), key=lambda x: pd.to_datetime(x, format='%B').month)
    year_options = ['All'] + sorted(df['Year'].dropna().unique())
    selected_months = st.multiselect("Select Month", month_options, default=['All'])
    selected_years = st.multiselect("Select Year", year_options, default=['All'])

    work_type_options = ['All'] + list(df['WorkType'].dropna().unique())
    selected_work_types = st.multiselect("Select Work Type", work_type_options, default=['All'])

    work_status_options = ['All', 'Open', 'Backlog', 'Postponed', 'Waiting for Parts', 'Waiting for Approval', 'In Progress']
    selected_work_status = st.multiselect("Select Work Status", work_status_options, default=['All'])

    work_priority_options = ['All', 'P1 - High', 'P2 - Medium', 'P3 - Low']
    selected_work_priority = st.multiselect("Select Work Priority", work_priority_options, default=['All'])

    location_options = ['All'] + list(df['ParentLocation'].dropna().unique())
    selected_locations = st.multiselect("Select Location", location_options, default=['All'])

# Apply Filters
filtered_df = df.copy()
if 'All' not in selected_months:
    filtered_df = filtered_df[filtered_df['Month Name'].isin(selected_months)]
if 'All' not in selected_years:
    filtered_df = filtered_df[filtered_df['Year'].isin(selected_years)]
if 'All' not in selected_work_types:
    filtered_df = filtered_df[filtered_df['WorkType'].isin(selected_work_types)]
if 'All' not in selected_work_status:
    filtered_df = filtered_df[filtered_df['WorkStatus'].isin(selected_work_status)]
if 'All' not in selected_work_priority:
    filtered_df = filtered_df[filtered_df['WorkPriority'].isin(selected_work_priority)]
if 'All' not in selected_locations:
    filtered_df = filtered_df[filtered_df['ParentLocation'].isin(selected_locations)]

# KPI Calculations
def calculate_work_order_metrics(df):
    # 1. Work Order Metrics
    open_wo = len(df[~df["WorkStatus"].isin(["Closed", "Completed", "Cancelled"])])
    closed_wo = len(df[df["WorkStatus"].isin(["Closed", "Completed"])])
    cancelled_wo = len(df[df["WorkStatus"] == "Cancelled"])
    completed_wo = len(df[df["WorkStatus"].isin(["Completed", "Completed - Was Backlog"])])
    
    # 2. Work Order Timing Metrics
    open_wo_df = df[~df["WorkStatus"].isin(["Closed", "Completed", "Cancelled"])]
    aging_days = (current_date - pd.to_datetime(open_wo_df["OrderDate"])).dt.days
    avg_aging = aging_days.mean() if not aging_days.empty else 0
    
    completed_wo_df = df[df["WorkStatus"].isin(["Completed", "Completed - Was Backlog"])]
    cycle_time_days = (pd.to_datetime(completed_wo_df["ActualEndDateTime"]) - pd.to_datetime(completed_wo_df["OrderDate"])).dt.total_seconds() / 86400
    avg_cycle_time = cycle_time_days.mean() if not cycle_time_days.empty else 0
    
    # 3. Maintenance Backlog Metrics
    backlog_count = open_wo
    total_planned_hrs = df[df["WorkStatus"].isin(["Open"])]["PlannedDurationHrs"].sum()
    available_hrs_per_week = 40  # Assume 40 hours/week as baseline (adjustable)
    backlog_weeks = total_planned_hrs / available_hrs_per_week if available_hrs_per_week > 0 else 0
    
    # 4. Maintenance Type Metrics
    completed_df = df[df["WorkStatus"].isin(["Completed", "Closed"])]
    planned_types = ["Planned Maint.", "Planned Corrective Maint.", "Planned Improvement", "Inspection"]
    corrective_types = ["Unplanned Corrective Maint.", "Breakdown"]
    planned_wo = len(completed_df[completed_df["WorkType"].isin(planned_types)])
    corrective_wo = len(completed_df[completed_df["WorkType"].isin(corrective_types)])
    total_completed = len(completed_df)
    planned_pct = (planned_wo / total_completed * 100) if total_completed > 0 else 0
    corrective_pct = (corrective_wo / total_completed * 100) if total_completed > 0 else 0
    reactive_pct = corrective_pct  # As per your definition
    
    # 5. Maintenance Schedule Compliance
    pm_wo = df[df["WorkType"].isin(planned_types)]
    pm_completed_on_time = len(pm_wo[(pd.to_datetime(pm_wo["ActualEndDateTime"], errors="coerce") <= pd.to_datetime(pm_wo["RequiredByDate"], errors="coerce")) & 
                                    pm_wo["WorkStatus"].isin(["Completed", "Closed"])])
    total_pm_scheduled = len(pm_wo)
    pm_compliance = (pm_completed_on_time / total_pm_scheduled * 100) if total_pm_scheduled > 0 else 0
    
    all_scheduled = df[df["RequiredByDate"].notna()]
    all_completed_on_time = len(all_scheduled[(pd.to_datetime(all_scheduled["ActualEndDateTime"], errors="coerce") <= pd.to_datetime(all_scheduled["RequiredByDate"], errors="coerce")) & 
                                             all_scheduled["WorkStatus"].isin(["Completed", "Closed"])])
    total_scheduled = len(all_scheduled)
    overall_compliance = (all_completed_on_time / total_scheduled * 100) if total_scheduled > 0 else 0
    
    # 6. Reliability Metrics
    breakdown_df = df[df["WorkType"].isin(["Breakdown", "Unplanned Corrective Maint."])]
    mttr_hrs = ((pd.to_datetime(breakdown_df["ActualEndDateTime"], errors="coerce") - pd.to_datetime(breakdown_df["ActualStartDateTime"], errors="coerce")).dt.total_seconds() / 3600).mean() if not breakdown_df.empty else 0
    # MTBF requires operational hours data; placeholder
    mtbf_hrs = 0  # To be refined with operational hours data
    
    return {
        "open_wo": open_wo, "closed_wo": closed_wo, "cancelled_wo": cancelled_wo, "completed_wo": completed_wo,
        "avg_aging": avg_aging, "avg_cycle_time": avg_cycle_time,
        "backlog_count": backlog_count, "backlog_weeks": backlog_weeks,
        "planned_pct": planned_pct, "corrective_pct": corrective_pct, "reactive_pct": reactive_pct,
        "pm_compliance": pm_compliance, "overall_compliance": overall_compliance,
        "mttr_hrs": mttr_hrs, "mtbf_hrs": mtbf_hrs
    }

metrics = calculate_work_order_metrics(filtered_df)

# Main Dashboard
st.title("Maintenance Work Order Dashboard")

# KPI Summary Section
st.subheader("📊 Key Metrics")

col1, col2, col3 = st.columns(3)
col1.metric(label="Total Work Orders", value=len(filtered_df))
col2.metric(label="Average Duration (hrs)", value=round(filtered_df['Duration'].dropna().mean(), 2) if 'Duration' in filtered_df.columns else "N/A")
col3.metric(label="Open Work Orders", value=metrics["open_wo"], help="Count of WOs not Closed, Completed, or Cancelled")

col4, col5, col6 = st.columns(3)
col4.metric(label="Completed Work Orders", value=metrics["completed_wo"])
col5.metric(label="Closed Work Orders", value=metrics["closed_wo"])
col6.metric(label="Cancelled Work Orders", value=metrics["cancelled_wo"])

col7, col8 = st.columns(2)
col7.metric(label="Avg Work Order Aging (Days)", value=round(metrics["avg_aging"], 2), help="Avg days open for current open WOs")
col8.metric(label="Avg Cycle Time (Days)", value=round(metrics["avg_cycle_time"], 2), help="Avg days from OrderDate to ActualEndDateTime")

# Backlog Metrics
col9, col10 = st.columns(2)
col9.metric(label="Backlog Count", value=metrics["backlog_count"])
col10.metric(label="Backlog (Weeks)", value=round(metrics["backlog_weeks"], 2))

# Compliance Gauges
st.subheader("📏 Compliance Metrics")
col11, col12 = st.columns(2)
col11.progress(metrics["pm_compliance"] / 100, text=f"PM Compliance: {round(metrics['pm_compliance'], 2)}%")
col12.progress(metrics["overall_compliance"] / 100, text=f"Overall Compliance: {round(metrics['overall_compliance'], 2)}%")

# Maintenance Type Distribution
st.subheader("📊 Maintenance Type Distribution")
fig_pie = px.pie(names=["Planned", "Corrective/Reactive"], values=[metrics["planned_pct"], metrics["corrective_pct"]],
                 title="Planned vs Corrective Maintenance (%)")
st.plotly_chart(fig_pie)

# Reliability Metrics
st.subheader("🔧 Reliability Metrics")
col13, col14 = st.columns(2)
col13.metric(label="Mean Time to Repair (MTTR) (hrs)", value=round(metrics["mttr_hrs"], 2),
             help="Avg repair time for breakdown/corrective tasks")
col14.metric(label="Mean Time Between Failures (MTBF) (hrs)", value=round(metrics["mtbf_hrs"], 2),
             help="Requires operational hours data for accuracy")

# Open Maintenance KPIs (Expandable)
with st.expander("🛠 Open Maintenance KPIs", expanded=True):
    col1, col2, col3 = st.columns(3)
    col1.metric(label="Open Unplanned Work Orders", value=len(filtered_df[(filtered_df['WorkStatus'] == 'Open') & (filtered_df['WorkType'] == 'Unplanned')]))
    col2.metric(label="Open Planned Maintenance", value=len(filtered_df[(filtered_df['WorkStatus'] == 'Open') & (filtered_df['WorkType'] == 'Planned Maint.')]))
    col3.metric(label="Open Work Requests", value=len(filtered_df[(filtered_df['WorkStatus'] == 'Open') & (filtered_df['WorkType'] == 'Work Request')]))

# Maintenance Performance KPIs (Expandable)
with st.expander("📈 Maintenance Performance KPIs"):
    col1, col2, col3 = st.columns(3)
    col1.metric(label="Planned Maintenance (%)", value=f"{round(metrics['planned_pct'], 1)}%")
    col2.metric(label="Corrective Maintenance (%)", value=f"{round(metrics['corrective_pct'], 1)}%")
    col3.metric(label="Reactive Maintenance (%)", value=f"{round(metrics['reactive_pct'], 1)}%")

# Work Orders by Location Chart
if not filtered_df.empty and 'ParentLocation' in filtered_df:
    st.subheader("📍 Work Orders by Location")
    location_counts = filtered_df['ParentLocation'].value_counts().reset_index()
    location_counts.columns = ['ParentLocation', 'count']
    fig_location = px.bar(location_counts, x='ParentLocation', y='count', title='Work Orders by Location',
                          color='ParentLocation', color_discrete_sequence=px.colors.qualitative.Set3)
    st.plotly_chart(fig_location)

# Work Orders by Priority Level Chart
if not filtered_df.empty and 'WorkPriority' in filtered_df:
    st.subheader("⚡ Work Orders by Priority Level")
    priority_counts = filtered_df['WorkPriority'].value_counts().reset_index()
    priority_counts.columns = ['WorkPriority', 'count']
    fig_priority = px.bar(priority_counts, x='WorkPriority', y='count', title='Work Orders by Priority',
                          color='WorkPriority', color_discrete_sequence=px.colors.qualitative.Set2)
    st.plotly_chart(fig_priority)

# Grouped Metrics by Location (Expandable)
with st.expander("🌐 Metrics by Location"):
    location_group = filtered_df.groupby('ParentLocation').apply(calculate_work_order_metrics).reset_index()
    location_group = location_group[['ParentLocation', 'open_wo', 'avg_aging', 'mttr_hrs']]
    st.dataframe(location_group.style.format({
        'avg_aging': '{:.2f}',
        'mttr_hrs': '{:.2f}'
    }))

# Data Table (Expandable)
with st.expander("📄 Data Preview"):
    st.dataframe(filtered_df)

# Downloadable Report
st.download_button(
    label="📥 Download Report as CSV",
    data=filtered_df.to_csv(index=False),
    file_name="maintenance_report.csv",
    mime="text/csv"
)

# Sidebar Notes
st.sidebar.header("📝 Notes")
st.sidebar.write("MTBF calculation requires operational hours data. Adjust `available_hrs_per_week` (currently 40) in code as needed.")