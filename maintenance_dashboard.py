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
    return df

df = load_data()

# Title
st.title("Maintenance KPI Dashboard")

# KPI Calculations
today = pd.Timestamp(datetime.today())
open_wo = df[df['ActualEndDateTime'].isna()]
closed_wo = df[df['ActualEndDateTime'].notna()]

# KPI Tiles
st.header("Key Performance Indicators")
kpi1, kpi2, kpi3 = st.columns(3)

# Open Work Orders
kpi1.metric(label="Open Work Orders", value=len(open_wo))

# Average Work Order Cycle Time
cycle_time = (closed_wo['ActualEndDateTime'] - closed_wo['OrderDate']).dt.days.mean()
kpi2.metric(label="Avg Cycle Time (Days)", value=f"{cycle_time:.2f}")

# Planned vs Reactive Maintenance
def classify_work_type(wt):
    if wt in ['Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection']:
        return "Planned"
    elif wt in ['Breakdown', 'Unplanned Corrective Maint.']:
        return "Reactive"
    else:
        return "Other"

df['MaintenanceType'] = df['WorkType'].apply(classify_work_type)
planned_count = len(df[df['MaintenanceType'] == 'Planned'])
reactive_count = len(df[df['MaintenanceType'] == 'Reactive'])
total_maint = planned_count + reactive_count

planned_pct = (planned_count / total_maint) * 100 if total_maint else 0
reactive_pct = (reactive_count / total_maint) * 100 if total_maint else 0

kpi3.metric(label="Planned Maint. (%)", value=f"{planned_pct:.1f}%")

# Visualization Section
st.header("Detailed Visualizations")

# Work Order Status Count
fig_status = px.bar(df['WorkStatus'].value_counts().reset_index(),
                    x='index', y='WorkStatus',
                    labels={'index':'Work Status', 'WorkStatus':'Count'},
                    title="Work Orders by Status")
st.plotly_chart(fig_status)

# Maintenance Type Pie Chart
fig_pie = px.pie(names=['Planned', 'Reactive'], values=[planned_count, reactive_count],
                 title='Maintenance Type Distribution')
st.plotly_chart(fig_pie)

# Work Order Cycle Time Trend
closed_wo['Month'] = closed_wo['ActualEndDateTime'].dt.to_period('M').astype(str)
monthly_cycle_time = closed_wo.groupby('Month').apply(lambda x: (x['ActualEndDateTime'] - x['OrderDate']).dt.days.mean()).reset_index()
monthly_cycle_time.columns = ['Month', 'AvgCycleTime']
fig_cycle = px.line(monthly_cycle_time, x='Month', y='AvgCycleTime', markers=True,
                    title="Monthly Average Work Order Cycle Time")
st.plotly_chart(fig_cycle)

# Raw Data (Expandable)
with st.expander("Show Raw Data"):
    st.dataframe(df)
