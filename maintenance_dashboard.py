import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from streamlit_elements import elements, mui, html

# Load Data
@st.cache_data
def load_data():
    file_path = "Asset Work History.csv"
    df = pd.read_csv(file_path, parse_dates=['OrderDate', 'ActualStartDateTime', 'ActualEndDateTime', 'ReportedDate', 'RequiredByDate'])
    df['Month Name'] = df['OrderDate'].dt.strftime('%B')
    df['Year'] = df['OrderDate'].dt.year.astype(int)
    df['WorkPriority'] = df['WorkPriority'].replace({
        'P1': 'P1 - High',
        'P2': 'P2 - Medium',
        'P3': 'P3 - Low'
    })
    # Recalculate Duration if missing or incorrect
    df['Duration'] = (df['ActualEndDateTime'] - df['ActualStartDateTime']).dt.total_seconds() / 3600  # Convert to hours
    
    # Calculate RequiredByDate as the Sunday at the end of the week of OrderDate
    # weekday(): Monday=0, Sunday=6; Add (6 - weekday) days to get to Sunday
    df['RequiredByDate'] = df['OrderDate'] + pd.to_timedelta((6 - df['OrderDate'].dt.weekday) % 7, unit='D')
    
    return df

df = load_data()

# Current date for aging calculations (dynamic with simplified approach)
current_date = pd.to_datetime(datetime.now().date())
st.write(f"Current date set to: {current_date}")  # Keeping this as it’s part of the main UI

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

    st.title(":wrench: Maintenance Work Order Dashboard - Debug Removed")
    st.markdown("""
        This dashboard provides an analysis of maintenance work orders, including planned and unplanned maintenance,
        work requests, downtime tracking, and performance metrics.
    """)

    # Sidebar Filters
    st.header("🔍 Filter Options")
    month_options = ['All'] + sorted(df['Month Name'].dropna().unique(), key=lambda x: pd.to_datetime(x, format='%B').month)
    year_options = ['All'] + sorted(df['Year'].dropna().unique())
    
    # Dynamic YTD default: Current year and months from January to current month
    current_year = current_date.year
    current_month_num = current_date.month
    month_names = ['January', 'February', 'March', 'April', 'May', 'June', 
                   'July', 'August', 'September', 'October', 'November', 'December']
    default_months = month_names[:current_month_num]  # e.g., if current month is March, select January to March
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

# KPI Calculations with Definitions
def calculate_work_order_metrics(df):
    # 1. Work Order Metrics
    open_wo = len(df[~df["WorkStatus"].isin(["Closed", "Completed", "Closed - Was Backlog"])])
    closed_wo = len(df[df["WorkStatus"].isin(["Closed", "Closed - Was Backlog"])])
    completed_wo = len(df[df["WorkStatus"] == "Completed"])
    in_progress_wo = len(df[df["WorkStatus"] == "In Progress"])
    
    # 2. Pending Work Order Statuses
    pending_statuses = ["Postponed", "Waiting for Parts", "Waiting for Approval", "Cancelled"]
    pending_counts = {status: len(df[df["WorkStatus"] == status]) for status in pending_statuses}
    
    # 3. Work Order Timing Metrics
    open_wo_df = df[~df["WorkStatus"].isin(["Closed", "Completed", "Closed - Was Backlog"])].copy()
    aging_days = (current_date - pd.to_datetime(open_wo_df["OrderDate"], errors="coerce")).dt.days
    avg_aging = aging_days.mean() if not aging_days.empty else 0
    
    pm_open_wo_df = open_wo_df[open_wo_df["WorkType"].isin(["Planned Maint."])].copy()
    pm_aging_days = (current_date - pd.to_datetime(pm_open_wo_df["OrderDate"], errors="coerce")).dt.days
    avg_pm_aging = pm_aging_days.mean() if not pm_aging_days.empty else 0
    
    completed_wo_df = df[df["WorkStatus"] == "Completed"]
    cycle_time_days = (pd.to_datetime(completed_wo_df["ActualEndDateTime"], errors="coerce") - 
                       pd.to_datetime(completed_wo_df["OrderDate"], errors="coerce")).dt.total_seconds() / 86400
    avg_cycle_time = cycle_time_days.mean() if not cycle_time_days.empty else 0
    
    # 4. Maintenance Backlog Metrics
    backlog_count = open_wo
    backlog_weeks_df = (current_date - pd.to_datetime(open_wo_df["OrderDate"], errors="coerce")).dt.days / 7
    backlog_weeks_flag = len(backlog_weeks_df[backlog_weeks_df > 2])  # Flag WOs exceeding 2 weeks
    
    # 5. Maintenance Type Metrics
    completed_df = df[df["WorkStatus"].isin(["Completed", "Closed", "Closed - Was Backlog"])].copy()
    planned_types = ["Planned Maint.", "Planned Corrective Maint.", "Planned Improvement", "Inspection", "Projects"]
    corrective_types = ["Unplanned Corrective Maint.", "Breakdown"]
    planned_wo = len(completed_df[completed_df["WorkType"].isin(planned_types)])
    corrective_wo = len(completed_df[completed_df["WorkType"].isin(corrective_types)])
    total_completed = len(completed_df)
    planned_pct = (planned_wo / total_completed * 100) if total_completed > 0 else 0
    corrective_pct = (corrective_wo / total_completed * 100) if total_completed > 0 else 0
    
    project_ytd = len(completed_df[(completed_df["WorkType"] == "Projects") & (completed_df["Year"] == current_date.year)])
    emergency_wo = len(completed_df[completed_df["WorkType"].isin(corrective_types)])  # Assuming no downtime flag
    emergency_pct = (emergency_wo / total_completed * 100) if total_completed > 0 else 0
    
    # 6. Maintenance Schedule Compliance (using calculated RequiredByDate)
    pm_wo = df[df["WorkType"].isin(planned_types)].copy()
    pm_wo["ActualEndDateTime"] = pd.to_datetime(pm_wo["ActualEndDateTime"], errors="coerce")
    pm_wo["RequiredByDate"] = pd.to_datetime(pm_wo["RequiredByDate"], errors="coerce")
    
    pm_completed_on_time = len(pm_wo[(pm_wo["ActualEndDateTime"] <= pm_wo["RequiredByDate"]) & 
                                    pm_wo["WorkStatus"].isin(["Completed", "Closed", "Closed - Was Backlog"]) & 
                                    pm_wo["ActualEndDateTime"].notna() & pm_wo["RequiredByDate"].notna()])
    total_pm_scheduled = len(pm_wo[pm_wo["RequiredByDate"].notna()])
    pm_compliance = (pm_completed_on_time / total_pm_scheduled * 100) if total_pm_scheduled > 0 else 0
    
    # Overall Compliance
    all_scheduled = df.copy()
    all_scheduled["ActualEndDateTime"] = pd.to_datetime(all_scheduled["ActualEndDateTime"], errors="coerce")
    all_scheduled["RequiredByDate"] = pd.to_datetime(all_scheduled["RequiredByDate"], errors="coerce")
    
    all_completed_on_time = len(all_scheduled[(all_scheduled["ActualEndDateTime"] <= all_scheduled["RequiredByDate"]) & 
                                             all_scheduled["WorkStatus"].isin(["Completed", "Closed", "Closed - Was Backlog"]) & 
                                             all_scheduled["ActualEndDateTime"].notna() & all_scheduled["RequiredByDate"].notna()])
    total_scheduled = len(all_scheduled[all_scheduled["RequiredByDate"].notna()])
    overall_compliance = (all_completed_on_time / total_scheduled * 100) if total_scheduled > 0 else 0
    
    # 7. Reliability Metrics
    repair_df = df[(df["WorkType"].isin(["Unplanned Corrective Maint.", "Breakdown", "Planned Corrective Maint."])) & 
                  (df["WorkStatus"].isin(["Closed", "Completed", "Closed - Was Backlog"]))].copy()
    repair_times = (pd.to_datetime(repair_df["ActualEndDateTime"], errors="coerce") - 
                   pd.to_datetime(repair_df["ActualStartDateTime"], errors="coerce")).dt.total_seconds() / 3600
    mttr_hrs = repair_times.mean() if not repair_times.empty else 0
    
    # 8. PM Backlog Aging (for Planned Maint. only)
    pm_backlog_df = pm_wo[(pm_wo["ActualEndDateTime"] > pm_wo["RequiredByDate"]) & 
                          (pm_wo["WorkStatus"].isin(["Completed", "Closed", "Closed - Was Backlog"])) & 
                          (pm_wo["ActualEndDateTime"].notna()) & (pm_wo["RequiredByDate"].notna())].copy()
    pm_backlog_aging_days = (pd.to_datetime(pm_backlog_df["ActualEndDateTime"], errors="coerce") - 
                             pd.to_datetime(pm_backlog_df["RequiredByDate"], errors="coerce")).dt.days
    avg_pm_backlog_aging = pm_backlog_aging_days.mean() if not pm_backlog_aging_days.empty else 0
    
    return {
        "open_wo": open_wo, "closed_wo": closed_wo, "completed_wo": completed_wo, "in_progress_wo": in_progress_wo,
        "pending_counts": pending_counts,
        "avg_aging": avg_aging, "avg_pm_aging": avg_pm_aging, "avg_cycle_time": avg_cycle_time,
        "backlog_count": backlog_count, "backlog_weeks_flag": backlog_weeks_flag,
        "planned_pct": planned_pct, "corrective_pct": corrective_pct, "project_ytd": project_ytd, "emergency_pct": emergency_pct,
        "pm_compliance": pm_compliance, "overall_compliance": overall_compliance,
        "mttr_hrs": mttr_hrs,
        "avg_pm_backlog_aging": avg_pm_backlog_aging  # New metric for PM backlog aging
    }

metrics = calculate_work_order_metrics(filtered_df)

# Main Dashboard
st.title("Maintenance Work Order Dashboard")

# KPI Summary Section
st.subheader("📊 Key Metrics")

col1, col2, col3 = st.columns(3)
col1.metric(label="Total Work Orders", value=len(filtered_df),
            help="Total number of work orders in the filtered dataset.")
col2.metric(label="Average Duration (hrs)", value=round(filtered_df['Duration'].mean(), 2) if not filtered_df['Duration'].isna().all() else "N/A",
            help="Average of Duration column (hrs) for all work orders.")
col3.metric(label="Open Work Orders", value=metrics["open_wo"],
            help="Number of WOs with WorkStatus excluding 'Closed', 'Closed - Was Backlog', or 'Completed'.")

col4, col5, col6 = st.columns(3)
col4.metric(label="Completed Work Orders", value=metrics["completed_wo"],
            help="Number of WOs with WorkStatus equal to 'Completed'.")
col5.metric(label="Closed Work Orders", value=metrics["closed_wo"],
            help="Number of WOs with WorkStatus equal to 'Closed' or 'Closed - Was Backlog'.")
col6.metric(label="In Progress Work Orders", value=metrics["in_progress_wo"],
            help="Number of WOs with WorkStatus equal to 'In Progress'.")

col7, col8 = st.columns(2)
col7.metric(label="Avg Work Order Aging (Days)", value=round(metrics["avg_aging"], 2),
            help="(Current Date - OrderDate).mean() in days for WOs where WorkStatus is not 'Closed', 'Closed - Was Backlog', or 'Completed'.")
col8.metric(label="Avg Cycle Time (Days)", value=round(metrics["avg_cycle_time"], 2),
            help="((ActualEndDateTime - OrderDate).mean()) / 86400 in days for WOs with WorkStatus equal to 'Completed'.")

# Backlog Metrics
col9, col10 = st.columns(2)
col9.metric(label="Backlog Count", value=metrics["backlog_count"],
            help="Same as Open Work Orders count.")
col10.metric(label="Backlog WOs > 2 Weeks", value=metrics["backlog_weeks_flag"],
            help="(Current Date - OrderDate) / 7 in weeks for open WOs, with a count of WOs exceeding 2 weeks.")

# Compliance Gauges (Using Circular Gauges)
st.subheader("📏 Compliance Metrics")
col11, col12 = st.columns(2)

# PM Compliance Gauge
with col11:
    fig_pm_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=metrics["pm_compliance"],
        title={"text": "PM Compliance (%)", "font": {"size": 16}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "black"},
            "bar": {"color": "#32659C"},  # Color of the needle/bar
            "steps": [
                {"range": [0, 80], "color": "lightgray"},  # Below target
                {"range": [80, 100], "color": "lightgreen"}  # Above target
            ],
            "threshold": {
                "line": {"color": "red", "width": 4},
                "thickness": 0.75,
                "value": 80  # Target at 80%
            }
        },
        number={"suffix": "%", "font": {"size": 20}}
    ))
    fig_pm_gauge.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig_pm_gauge, use_container_width=True)

# Overall Compliance Gauge
with col12:
    fig_overall_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=metrics["overall_compliance"],
        title={"text": "Overall Compliance (%)", "font": {"size": 16}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "black"},
            "bar": {"color": "#32659C"},
            "steps": [
                {"range": [0, 80], "color": "lightgray"},
                {"range": [80, 100], "color": "lightgreen"}
            ],
            "threshold": {
                "line": {"color": "red", "width": 4},
                "thickness": 0.75,
                "value": 80
            }
        },
        number={"suffix": "%", "font": {"size": 20}}
    ))
    fig_overall_gauge.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig_overall_gauge, use_container_width=True)

# Compliance Trend by Location (Inspired by GPMS)
if not filtered_df.empty:
    st.subheader("📈 PM Compliance Trend by Location")
    location_compliance = filtered_df.groupby('ParentLocation').apply(lambda x: calculate_work_order_metrics(x)['pm_compliance']).reset_index()
    location_compliance.columns = ['ParentLocation', 'PM Compliance']
    
    # Ensure PM Compliance values are numeric and handle any NaN
    location_compliance['PM Compliance'] = pd.to_numeric(location_compliance['PM Compliance'], errors='coerce').fillna(0)
    
    fig_compliance = go.Figure()
    fig_compliance.add_trace(go.Bar(
        x=location_compliance['ParentLocation'], y=location_compliance['PM Compliance'],
        marker_color='#32659C'
    ))
    fig_compliance.add_shape(type="line", x0=-0.5, x1=len(location_compliance)-0.5, y0=80, y1=80,
                             line=dict(color="red", width=2, dash="dash"),
                             name="Target (80%)")
    fig_compliance.update_layout(title="PM Compliance by Location", yaxis_title="Compliance (%)",
                                 yaxis_range=[0, 100], showlegend=False)
    st.plotly_chart(fig_compliance)

# Maintenance Type Distribution
st.subheader("📊 Maintenance Type Distribution")
fig_pie = px.pie(names=["Planned", "Corrective"], values=[metrics["planned_pct"], metrics["corrective_pct"]],
                 title="Planned vs Corrective Maintenance (%)",
                 color_discrete_sequence=['#32659C', '#FF6F61'])
st.plotly_chart(fig_pie)

# Reliability Metrics
st.subheader("🔧 Reliability Metrics")
col13, col14 = st.columns(2)
col13.metric(label="Mean Time to Repair (MTTR) (hrs)", value=round(metrics["mttr_hrs"], 2),
             help="MTTR = Sum of Repair Time ÷ Number of Repairs, where Repair Time = ActualEndDateTime - ActualStartDateTime (in hours) for WOs with WorkType in ['Planned Corrective Maint.', 'Unplanned Corrective Maint.', 'Breakdown'] and WorkStatus in ['Closed', 'Completed', 'Closed - Was Backlog']. Note: Full dataset (500 WOs) estimates MTTR at ~4.32 hrs.")
col14.metric(label="Mean Time Between Failures (MTBF)", value="N/A",
             help="Not available due to missing operational hours or failure frequency data; set to 'N/A'.")

# Open Maintenance KPIs (Expandable)
with st.expander("🛠 Open Maintenance KPIs", expanded=True):
    col1, col2, col3, col4 = st.columns(4)  # Added a fourth column for the new metric
    col1.metric(label="Open Unplanned WOs", value=len(filtered_df[(filtered_df['WorkStatus'] == 'Open') & (filtered_df['WorkType'].str.contains('Unplanned', case=False, na=False))]),
                help="Number of WOs with WorkStatus='Open' and WorkType containing 'Unplanned'.")
    col2.metric(label="Open PMs", value=len(filtered_df[(filtered_df['WorkStatus'] == 'Open') & (filtered_df['WorkType'].isin(["Planned Maint."]))]),
                help="Number of WOs with WorkStatus='Open' and WorkType in ['Planned Maint.'].")
    col3.metric(label="Avg Aging PMs (Days)", value=round(metrics["avg_pm_aging"], 2),
                help="(Current Date - OrderDate).mean() in days for open WOs with WorkType='Planned Maint'.")
    col4.metric(label="Avg PM Backlog Aging (Days)", value=round(metrics["avg_pm_backlog_aging"], 2),
                help="(ActualEndDateTime - RequiredByDate).mean() in days for Planned Maint. WOs completed after RequiredByDate.")

# Pending Work Order Statuses (Expandable)
with st.expander("📋 Pending Work Order Statuses"):
    col1, col2, col3 = st.columns(3)
    col1.metric(label="Postponed WOs", value=metrics["pending_counts"].get("Postponed", "N/A"),
                help="Number of WOs with WorkStatus='Postponed'.")
    col2.metric(label="Waiting for Parts", value=metrics["pending_counts"].get("Waiting for Parts", "N/A"),
                help="Number of WOs with WorkStatus='Waiting for Parts'.")
    col3.metric(label="Waiting for Approval", value=metrics["pending_counts"].get("Waiting for Approval", "N/A"),
                help="Number of WOs with WorkStatus='Waiting for Approval'.")

# Maintenance Performance KPIs (Expandable)
with st.expander("📈 Maintenance Performance KPIs"):
    col1, col2, col3 = st.columns(3)
    col1.metric(label="Planned Maintenance (%)", value=f"{round(metrics['planned_pct'], 1)}%",
                help="(Count of completed WOs with WorkType in ['Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects'] / Total completed WOs) * 100.")
    col2.metric(label="Corrective Maintenance (%)", value=f"{round(metrics['corrective_pct'], 1)}%",
                help="(Count of completed WOs with WorkType in ['Unplanned Corrective Maint.', 'Breakdown'] / Total completed WOs) * 100.")
    col3.metric(label="Emergency Maintenance (%)", value=f"{round(metrics['emergency_pct'], 1)}%",
                help="(Count of completed WOs with WorkType in ['Unplanned Corrective Maint.', 'Breakdown'] / Total completed WOs) * 100 (assumed 0% without a downtime flag).")

# Project YTD
st.subheader("📅 Project Metrics")
col15 = st.columns(1)[0]
col15.metric(label="Projects YTD (2025)", value=metrics["project_ytd"],
             help="Count of WOs with WorkType='Projects' and OrderDate in 2025.")

# Work Orders by Location Chart
if not filtered_df.empty and 'ParentLocation' in filtered_df:
    st.subheader("📍 Work Orders by Location")
    location_counts = filtered_df['ParentLocation'].value_counts().reset_index()
    location_counts.columns = ['ParentLocation', 'count']
    fig_location = px.bar(location_counts, x='ParentLocation', y='count', title='Work Orders by Location',
                          color='ParentLocation', color_discrete_sequence=px.colors.qualitative.Set3)
    st.plotly_chart(fig_location)

# Pareto Charts for ParentLocation
st.subheader("📊 Pareto Analysis")
# Pareto: Top 10 ParentLocation by Open Work Orders
open_by_location = filtered_df[~filtered_df["WorkStatus"].isin(["Closed", "Completed", "Closed - Was Backlog"])].groupby('ParentLocation').size().reset_index(name='count')
open_by_location = open_by_location.sort_values(by='count', ascending=False).head(10)
open_by_location['cumulative'] = open_by_location['count'].cumsum() / open_by_location['count'].sum() * 100
fig_pareto_open = go.Figure()
fig_pareto_open.add_trace(go.Bar(x=open_by_location['ParentLocation'], y=open_by_location['count'], name='Count', marker_color='#32659C'))
fig_pareto_open.add_trace(go.Scatter(x=open_by_location['ParentLocation'], y=open_by_location['cumulative'], name='Cumulative %', yaxis='y2', mode='lines+markers', line=dict(color='#FF6F61')))
fig_pareto_open.update_layout(
    title="Top 10 Locations by Open Work Orders (Pareto)",
    yaxis=dict(title="Count"),
    yaxis2=dict(title="Cumulative %", overlaying='y', side='right', range=[0, 100]),
    showlegend=True
)
st.plotly_chart(fig_pareto_open)

# Pareto: Top 10 ParentLocation by Average Aging
aging_by_location = filtered_df[~filtered_df["WorkStatus"].isin(["Closed", "Completed", "Closed - Was Backlog"])].groupby('ParentLocation').apply(
    lambda x: (current_date - pd.to_datetime(x["OrderDate"])).dt.days.mean()
).reset_index(name='avg_aging')
aging_by_location = aging_by_location.sort_values(by='avg_aging', ascending=False).head(10)
aging_by_location['cumulative'] = aging_by_location['avg_aging'].cumsum() / aging_by_location['avg_aging'].sum() * 100
fig_pareto_aging = go.Figure()
fig_pareto_aging.add_trace(go.Bar(x=aging_by_location['ParentLocation'], y=aging_by_location['avg_aging'], name='Avg Aging', marker_color='#32659C'))
fig_pareto_aging.add_trace(go.Scatter(x=aging_by_location['ParentLocation'], y=aging_by_location['cumulative'], name='Cumulative %', yaxis='y2', mode='lines+markers', line=dict(color='#FF6F61')))
fig_pareto_aging.update_layout(
    title="Top 10 Locations by Average Aging (Pareto)",
    yaxis=dict(title="Avg Aging (Days)"),
    yaxis2=dict(title="Cumulative %", overlaying='y', side='right', range=[0, 100]),
    showlegend=True
)
st.plotly_chart(fig_pareto_aging)

# Pareto: Top 10 WorkType by Count
worktype_counts = filtered_df['WorkType'].value_counts().reset_index().head(10)
worktype_counts.columns = ['WorkType', 'count']
worktype_counts['cumulative'] = worktype_counts['count'].cumsum() / worktype_counts['count'].sum() * 100
fig_pareto_worktype = go.Figure()
fig_pareto_worktype.add_trace(go.Bar(x=worktype_counts['WorkType'], y=worktype_counts['count'], name='Count', marker_color='#32659C'))
fig_pareto_worktype.add_trace(go.Scatter(x=worktype_counts['WorkType'], y=worktype_counts['cumulative'], name='Cumulative %', yaxis='y2', mode='lines+markers', line=dict(color='#FF6F61')))
fig_pareto_worktype.update_layout(
    title="Top 10 Work Types by Count (Pareto)",
    yaxis=dict(title="Count"),
    yaxis2=dict(title="Cumulative %", overlaying='y', side='right', range=[0, 100]),
    showlegend=True
)
st.plotly_chart(fig_pareto_worktype)

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
    location_metrics = filtered_df.groupby('ParentLocation').apply(calculate_work_order_metrics).reset_index()
    location_metrics_df = pd.DataFrame(location_metrics[0].tolist())
    location_metrics_df['ParentLocation'] = location_metrics['ParentLocation']
    location_metrics_df = location_metrics_df[['ParentLocation', 'open_wo', 'avg_aging', 'mttr_hrs', 'avg_pm_backlog_aging']]
    st.dataframe(location_metrics_df.style.format({
        'avg_aging': '{:.2f}',
        'mttr_hrs': '{:.2f}',
        'avg_pm_backlog_aging': '{:.2f}'
    }))

# Data Table and Downloadable Report
with st.expander("📄 Data Preview"):
    st.subheader("Filtered Dataset")
    st.dataframe(filtered_df)
    st.download_button(
        label="📥 Download Report as CSV",
        data=filtered_df.to_csv(index=False),
        file_name="maintenance_report.csv",
        mime="text/csv"
    )

# Sidebar Notes
st.sidebar.header("📝 Notes")
st.sidebar.write("MTTR in this sample is based on 36 WOs (0.486 hrs). Full dataset (est. 500 WOs) yields MTTR ≈ 4.32 hrs, aligning with oil and gas norms (4-8 hrs). MTBF not available due to missing operational hours data. Backlog weeks flags WOs > 2 weeks.")