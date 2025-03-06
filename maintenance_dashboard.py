import streamlit as st
import pandas as pd
import plotly.express as px

# Load Data
@st.cache_data
def load_data():
    file_path = "Asset Work History.csv"  # Ensure this file is in the same directory
    df = pd.read_csv(file_path, parse_dates=['OrderDate', 'ActualStartDateTime', 'ActualEndDateTime'])
    df['Month Name'] = df['OrderDate'].dt.strftime('%B')  # Extract Month Name
    df['Year'] = df['OrderDate'].dt.year.astype(int)  # Extract Year and ensure it's an integer
    return df

df = load_data()

# Sidebar Theming
with st.sidebar:
    st.markdown(f'''
        <style>
        section[data-testid="stSidebar"] {{
                width: 400px;
                background-color: #32659C;
                padding: 20px;
                color: white;
                }}
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
    selected_months = st.sidebar.multiselect("Select Month", month_options, default=['All'])
    selected_years = st.sidebar.multiselect("Select Year", year_options, default=['All'])

    work_type_options = ['All'] + list(df['WorkTypeValue'].dropna().unique())
    selected_work_types = st.sidebar.multiselect("Select Work Type", work_type_options, default=['All'])

    work_status_options = ['All', 'Open', 'Backlog', 'Postponed', 'Waiting for Parts', 'Waiting for Approval', 'In Progress']
    selected_work_status = st.sidebar.multiselect("Select Work Status", work_status_options, default=['All'])

    work_priority_options = ['All', 'P1 - High', 'P2 - Medium', 'P3 - Low']
    selected_work_priority = st.sidebar.multiselect("Select Work Priority", work_priority_options, default=['All'])

    location_options = ['All'] + list(df['ParentLocationValue'].dropna().unique())
    selected_locations = st.sidebar.multiselect("Select Location", location_options, default=['All'])

# Ensure Correct Work Priority Mapping
df['WorkPriorityValue'] = df['WorkPriorityValue'].replace({
    'P1': 'P1 - High',
    'P2': 'P2 - Medium',
    'P3': 'P3 - Low'
})

# Apply Filters
filtered_df = df.copy()
if 'All' not in selected_months:
    filtered_df = filtered_df[filtered_df['Month Name'].isin(selected_months)]
if 'All' not in selected_years:
    filtered_df = filtered_df[filtered_df['Year'].isin(selected_years)]
if 'All' not in selected_work_types:
    filtered_df = filtered_df[filtered_df['WorkTypeValue'].isin(selected_work_types)]
if 'All' not in selected_work_status:
    filtered_df = filtered_df[filtered_df['WorkStatusValue'].isin(selected_work_status)]
if 'All' not in selected_work_priority:
    filtered_df = filtered_df[filtered_df['WorkPriorityValue'].isin(selected_work_priority)]
if 'All' not in selected_locations:
    filtered_df = filtered_df[filtered_df['ParentLocationValue'].isin(selected_locations)]

# 🏗️ Main Dashboard
st.title("Maintenance Work Order Dashboard")

# **KPI Summary Section**
st.subheader("📊 Key Metrics")

col1, col2, col3 = st.columns(3)
col1.metric(label="Total Work Orders", value=len(filtered_df))
col2.metric(label="Average Duration (hrs)", value=round(filtered_df['Duration'].dropna().mean(), 2))
col3.metric(label="Open Work Orders", value=len(filtered_df[filtered_df['WorkStatusValue'].isin(work_status_options)]))

col4, col5 = st.columns(2)
col4.metric(label="Completed Work Orders", value=len(filtered_df[filtered_df['WorkStatusValue'] == 'Completed']))
col5.metric(label="Closed Work Orders", value=len(filtered_df[filtered_df['WorkStatusValue'] == 'Closed']))

# **🔍 Open Maintenance KPIs (Expandable)**
with st.expander("🛠 Open Maintenance KPIs", expanded=True):
    col1, col2, col3 = st.columns(3)
    col1.metric(label="Open Unplanned Work Orders", value="0")
    col2.metric(label="Open Planned Maintenance", value="0")
    col3.metric(label="Open Work Requests", value="0")

# **📊 Maintenance Performance KPIs (Expandable)**
with st.expander("📈 Maintenance Performance KPIs"):
    col1, col2, col3 = st.columns(3)
    col1.metric(label="Planned vs Unplanned", value="0.0% vs 0.0%")
    col2.metric(label="Mean Time to Repair (MTTR)", value="N/A")
    col3.metric(label="Mean Time Between Failures (MTBF)", value="N/A")

# **📍 Work Orders by Location Chart**
if not filtered_df.empty:
    st.subheader("📍 Work Orders by Location")
    location_chart = px.bar(
        filtered_df['ParentLocationValue'].value_counts().reset_index(), 
        x='ParentLocationValue', y='count', 
        title='Work Orders by Location', 
        labels={'ParentLocationValue': 'Location', 'count': 'Count'}
    )
    st.plotly_chart(location_chart)

# **⚡ Work Orders by Priority Level Chart**
if not filtered_df.empty:
    st.subheader("⚡ Work Orders by Priority Level")
    priority_chart = px.bar(
        filtered_df['WorkPriorityValue'].value_counts().reset_index(), 
        x='WorkPriorityValue', y='count', 
        title='Work Orders by Priority', 
        labels={'WorkPriorityValue': 'Priority Level', 'count': 'Count'}
    )
    st.plotly_chart(priority_chart)

# **📄 Data Table (Expandable)**
with st.expander("📄 Data Preview"):
    st.dataframe(filtered_df)

# **📥 Downloadable Report**
st.download_button(
    label="📥 Download Report as CSV", 
    data=filtered_df.to_csv(index=False), 
    file_name="maintenance_report.csv", 
    mime="text/csv"
)
