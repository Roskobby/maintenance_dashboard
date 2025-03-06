import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_elements import elements, mui, html

# Load Data
@st.cache_data
def load_data():
    file_path = "Asset Work History.csv"  # Ensure this file is in the same directory
    df = pd.read_csv(file_path, parse_dates=['OrderDate', 'ActualStartDateTime', 'ActualEndDateTime'])
    df['Month Name'] = df['OrderDate'].dt.strftime('%B')  # Extract Month Name
    df['Year'] = df['OrderDate'].dt.year.astype(int)  # Extract Year and ensure it's an integer
    return df

df = load_data()

# Sidebar Filters
st.sidebar.header("Filter Options")

# Month and Year Filters with "All" Option
month_options = ['All'] + sorted(df['Month Name'].dropna().unique(), key=lambda x: pd.to_datetime(x, format='%B').month)
year_options = ['All'] + sorted(df['Year'].dropna().unique())
selected_months = st.sidebar.multiselect("Select Month", month_options, default=['All'])
selected_years = st.sidebar.multiselect("Select Year", year_options, default=['All'])

# Work Type Multi-Select with "All" Option
work_type_options = ['All'] + list(df['WorkType'].dropna().unique())
selected_work_types = st.sidebar.multiselect("Select Work Type", work_type_options, default=['All'])

# System Type Multi-Select with "All" Option
system_type_options = ['All'] + list(df['SystemType'].dropna().unique())
selected_system_types = st.sidebar.multiselect("Select System Type", system_type_options, default=['All'])

# Failure Type Multi-Select with "All" Option
failure_type_options = ['All'] + list(df['FailureType'].dropna().unique())
selected_failure_types = st.sidebar.multiselect("Select Failure Type", failure_type_options, default=['All'])

# Work Status Filter with "All" Option and Open Work Orders
open_work_statuses = ["Open", "Backlog", "Postponed", "Waiting for Parts", "Waiting for Approval", "In Progress"]
work_status_options = ['All'] + list(df['WorkStatus'].dropna().unique())
selected_work_status = st.sidebar.multiselect("Select Work Status", work_status_options, default=['All'])

# Work Priority Selector with "All" Option
work_priority_options = ['All', 'P1 - High', 'P2 - Medium', 'P3 - Low']
selected_work_priority = st.sidebar.multiselect("Select Work Priority", work_priority_options, default=['All'])


df['WorkPriority'] = df['WorkPriority'].replace({
    'P1': 'P1 - High',
    'P2': 'P2 - Medium',
    'P3': 'P3 - Low'
})


# Location Selector with "All" Option
location_options = ['All'] + list(df['ParentLocation'].dropna().unique())
selected_locations = st.sidebar.multiselect("Select Location", location_options, default=['All'])

# Apply Filters (Excluding "All" selections)
filtered_df = df.copy()
if 'All' not in selected_months:
    filtered_df = filtered_df[filtered_df['Month Name'].isin(selected_months)]
if 'All' not in selected_years:
    filtered_df = filtered_df[filtered_df['Year'].isin(selected_years)]
if 'All' not in selected_work_types:
    filtered_df = filtered_df[filtered_df['WorkType'].isin(selected_work_types)]
if 'All' not in selected_system_types:
    filtered_df = filtered_df[filtered_df['SystemType'].isin(selected_system_types)]
if 'All' not in selected_failure_types:
    filtered_df = filtered_df[filtered_df['FailureType'].isin(selected_failure_types)]
if 'All' not in selected_work_status:
    filtered_df = filtered_df[filtered_df['WorkStatus'].isin(selected_work_status)]
if 'All' not in selected_work_priority:
    filtered_df = filtered_df[filtered_df['WorkPriority'].isin(selected_work_priority)]
if 'All' not in selected_locations:
    filtered_df = filtered_df[filtered_df['ParentLocation'].isin(selected_locations)]

# Main Dashboard
st.title("Maintenance Work Order Dashboard")

# Styled Cards with Streamlit Elements
with elements("dashboard"):  
    mui.Grid(container=True, spacing=2, children=[
        mui.Paper(children=[mui.Typography("Total Work Orders"), mui.Typography(f"{len(filtered_df)}", variant="h4")], sx={"padding": 2, "backgroundColor": "#E3F2FD"}),
        mui.Paper(children=[mui.Typography("Average Duration (hrs)"), mui.Typography(f"{round(filtered_df['Duration'].dropna().mean(), 2)}", variant="h4")], sx={"padding": 2, "backgroundColor": "#E8F5E9"}),
        mui.Paper(children=[mui.Typography("Open Work Orders"), mui.Typography(f"{len(filtered_df[filtered_df['WorkStatus'].isin(open_work_statuses)])}", variant="h4")], sx={"padding": 2, "backgroundColor": "#FFEBEE"}),
        mui.Paper(children=[mui.Typography("Completed Work Orders"), mui.Typography(f"{len(filtered_df[filtered_df['WorkStatus'] == 'Completed'])}", variant="h4")], sx={"padding": 2, "backgroundColor": "#FFF3E0"}),
        mui.Paper(children=[mui.Typography("Closed Work Orders"), mui.Typography(f"{len(filtered_df[filtered_df['WorkStatus'] == 'Closed'])}", variant="h4")], sx={"padding": 2, "backgroundColor": "#ECEFF1"})
    ])

# Work Orders by Location
if not filtered_df.empty:
    location_chart = px.bar(filtered_df['ParentLocation']._counts().reset_index(), x='ParentLocation', y='count', title='Work Orders by Location', labels={'ParentLocation': 'Location', 'count': 'Count'})
    st.plotly_chart(location_chart)

# Work Orders by Priority Level
if not filtered_df.empty:
    priority_chart = px.bar(filtered_df['WorkPriority']._counts().reset_index(), x='WorkPriority', y='count', title='Work Orders by Priority', labels={'WorkPriority': 'Priority Level', 'count': 'Count'})
    st.plotly_chart(priority_chart)

# Data Table
st.write("### Data Preview")
st.dataframe(filtered_df)

# Downloadable Report
st.download_button(label="Download Report as CSV", data=filtered_df.to_csv(index=False), file_name="maintenance_report.csv", mime="text/csv")
