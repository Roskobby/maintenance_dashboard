import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

# Load Data
@st.cache_data
def load_data():
    df = pd.read_csv("Asset Work History.csv")
    df['OrderDate'] = pd.to_datetime(df['OrderDate'], errors='coerce')
    df['ActualEndDateTime'] = pd.to_datetime(df['ActualEndDateTime'], errors='coerce')
    df['Month'] = df['OrderDate'].dt.strftime('%B')
    df['Year'] = df['OrderDate'].dt.year
    return df

df = load_data()

# Sidebar Filters
st.sidebar.header("Filter Work Orders")
month_options = ['All'] + sorted(df['Month'].dropna().unique().tolist(), key=lambda x: datetime.strptime(x, '%B').month)
year_options = ['All'] + sorted(df['Year'].dropna().unique().astype(str).tolist())
selected_month = st.sidebar.multiselect("Select Month", month_options, default=['All'])
selected_year = st.sidebar.multiselect("Select Year", year_options, default=['All'])

filtered_df = df.copy()
if 'All' not in selected_month:
    filtered_df = filtered_df[filtered_df['Month'].isin(selected_month)]
if 'All' not in selected_year:
    filtered_df = filtered_df[filtered_df['Year'].astype(str).isin(selected_year)]

# KPI Calculations
open_wo = filtered_df[filtered_df['Work Status'].isin(['Open', 'Backlog'])]
closed_wo = filtered_df[filtered_df['Work Status'].isin(['Closed', 'Completed', 'Completed - Was Backlog'])]
cancelled_wo_count = filtered_df[filtered_df['Work Status'] == 'Cancelled'].shape[0]
cycle_time = (closed_wo['ActualEndDateTime'] - closed_wo['OrderDate']).dt.days.mean()

# Work Order Summary by Location
location_counts = filtered_df['ParentLocation'].value_counts().reset_index()
location_counts.columns = ['ParentLocation', 'Count']

# KPI Display
st.title("Maintenance KPI Dashboard")
st.header("Key Performance Indicators")
kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric(label="Open Work Orders", value=open_wo.shape[0])
kpi2.metric(label="Avg Cycle Time (Days)", value=f"{cycle_time:.2f}")
kpi3.metric(label="Cancelled Work Orders", value=cancelled_wo_count)

# Visualization Section
st.header("Detailed Visualizations")

# Work Order Status Counts
status_counts = filtered_df['Work Status'].value_counts().reset_index()
status_counts.columns = ['Status', 'Count']
fig_status = px.bar(status_counts, x='Status', y='Count', title="Work Orders by Status")
st.plotly_chart(fig_status)

# Work Orders by Location
fig_location = px.bar(location_counts, x='ParentLocation', y='Count', title="Work Orders by Location")
st.plotly_chart(fig_location)

# Monthly Work Order Cycle Time Trend
closed_wo['Month'] = closed_wo['ActualEndDateTime'].dt.to_period('M').astype(str)
monthly_cycle_time = closed_wo.groupby('Month').apply(lambda x: (x['ActualEndDateTime'] - x['OrderDate']).dt.days.mean()).reset_index()
monthly_cycle_time.columns = ['Month', 'AvgCycleTime']
cycle_fig = px.line(monthly_cycle_time, x='Month', y='AvgCycleTime', markers=True, title="Monthly Average Work Order Cycle Time")
st.plotly_chart(cycle_fig)

# Raw Data (Expandable)
with st.expander("Show Raw Data"):
    st.dataframe(filtered_df)

# Downloadable Report
st.download_button(
    label="📥 Download Report as CSV",
    data=filtered_df.to_csv(index=False),
    file_name="maintenance_report.csv",
    mime="text/csv"
)
