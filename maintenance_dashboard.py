import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_elements import elements, mui, html  # Added per your latest change

# Load Data
@st.cache_data
def load_data():
    file_path = "Asset Work History.csv"  # Correct file name
    df = pd.read_csv(file_path, parse_dates=['OrderDate', 'ActualStartDateTime', 'ActualEndDateTime', 'ReportedDate', 'RequiredByDate'])
    # Ensure Month Name and Year are present (already in CSV per your list, but verify)
    df['Month Name'] = df['OrderDate'].dt.strftime('%B')  # Extract Month Name
    df['Year'] = df['OrderDate'].dt.year.astype(int)  # Extract Year
    # Map WorkPriority if needed (assuming it might be P1, P2, P3)
    df['WorkPriority'] = df['WorkPriority'].replace({
        'P1': 'P1 - High',
        'P2': 'P2 - Medium',
        'P3': 'P3 - Low'
    })
    # Calculate Duration if not provided (optional, based on ActualStartDateTime and ActualEndDateTime)
    if 'Duration' not in df.columns or df['Duration'].isna().all():
        df['Duration'] = (df['ActualEndDateTime'] - df['ActualStartDateTime']).dt.total_seconds() / 3600  # Convert to hours
    return df

df = load_data()

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

    st.title(":wrench: About the Dataset")
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

# Main Dashboard
st.title("Maintenance Work Order Dashboard")

# KPI Summary Section
st.subheader("📊 Key Metrics")

col1, col2, col3 = st.columns(3)
col1.metric(label="Total Work Orders", value=len(filtered_df))
col2.metric(label="Average Duration (hrs)", value=round(filtered_df['Duration'].dropna().mean(), 2) if 'Duration' in filtered_df.columns else "N/A")
col3.metric(label="Open Work Orders", value=len(filtered_df[filtered_df['WorkStatus'] == 'Open']))

col4, col5 = st.columns(2)
col4.metric(label="Completed Work Orders", value=len(filtered_df[filtered_df['WorkStatus'] == 'Completed']))
col5.metric(label="Closed Work Orders", value=len(filtered_df[filtered_df['WorkStatus'] == 'Closed']))

# Open Maintenance KPIs (Expandable)
with st.expander("🛠 Open Maintenance KPIs", expanded=True):
    col1, col2, col3 = st.columns(3)
    col1.metric(label="Open Unplanned Work Orders", value=len(filtered_df[(filtered_df['WorkStatus'] == 'Open') & (filtered_df['WorkType'] == 'Unplanned')]))
    col2.metric(label="Open Planned Maintenance", value=len(filtered_df[(filtered_df['WorkStatus'] == 'Open') & (filtered_df['WorkType'] == 'Planned')]))
    col3.metric(label="Open Work Requests", value=len(filtered_df[(filtered_df['WorkStatus'] == 'Open') & (filtered_df['WorkType'] == 'Work Request')]))

# Maintenance Performance KPIs (Expandable)
with st.expander("📈 Maintenance Performance KPIs"):
    col1, col2, col3 = st.columns(3)
    planned = len(filtered_df[filtered_df['WorkType'] == 'Planned'])
    unplanned = len(filtered_df[filtered_df['WorkType'] == 'Unplanned'])
    total = planned + unplanned
    planned_pct = (planned / total * 100) if total > 0 else 0
    unplanned_pct = (unplanned / total * 100) if total > 0 else 0
    col1.metric(label="Planned vs Unplanned", value=f"{planned_pct:.1f}% vs {unplanned_pct:.1f}%")
    col2.metric(label="Mean Time to Repair (MTTR)", value="N/A")  # Requires duration data
    col3.metric(label="Mean Time Between Failures (MTBF)", value="N/A")  # Requires failure data

# Work Orders by Location Chart
if not filtered_df.empty and 'ParentLocation' in filtered_df:
    st.subheader("📍 Work Orders by Location")
    location_counts = filtered_df['ParentLocation'].value_counts().reset_index()
    location_counts.columns = ['ParentLocation', 'count']
    fig_location = px.bar(location_counts, x='ParentLocation', y='count', title='Work Orders by Location')
    st.plotly_chart(fig_location)

# Work Orders by Priority Level Chart
if not filtered_df.empty and 'WorkPriority' in filtered_df:
    st.subheader("⚡ Work Orders by Priority Level")
    priority_counts = filtered_df['WorkPriority'].value_counts().reset_index()
    priority_counts.columns = ['WorkPriority', 'count']
    fig_priority = px.bar(priority_counts, x='WorkPriority', y='count', title='Work Orders by Priority')
    st.plotly_chart(fig_priority)

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