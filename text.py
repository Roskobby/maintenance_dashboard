# -----------------------------------------
# Step 1: Imports and Configuration
# -----------------------------------------
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import duckdb
from datetime import datetime, timedelta

st.set_page_config(page_title="Maintenance Dashboard", page_icon="📊", layout="wide")

# -----------------------------------------
# Step 2: Data Loading and Initial Processing
# -----------------------------------------
@st.cache_data
def load_data():
    df = pd.read_csv("Asset Work History.csv")
    date_cols = ['OrderDate', 'ReportedDate', 'RequiredByDate']
    datetime_cols = ['ActualStartDateTime', 'ActualEndDateTime']
    for col in date_cols:
        df[col] = pd.to_datetime(df[col], format='%m/%d/%Y', errors='coerce')
    for col in datetime_cols:
        df[col] = pd.to_datetime(df[col], format='%m/%d/%Y %H:%M', errors='coerce')
    df['Month Name'] = df['OrderDate'].dt.strftime('%B')
    df['Year'] = df['OrderDate'].dt.year
    df['WorkPriority'] = df['WorkPriority'].replace({'P1': 'P1 - High', 'P2': 'P2 - Medium', 'P3': 'P3 - Low'})
    df['Duration'] = (df['ActualEndDateTime'] - df['ActualStartDateTime']).dt.total_seconds() / 3600
    df['RequiredByDateEnd'] = df['RequiredByDate'] + pd.Timedelta(hours=23, minutes=59, seconds=59)
    df['OnTimeStatus'] = np.where(
        (df['ActualEndDateTime'].notna()) & (df['RequiredByDateEnd'].notna()),
        np.where(df['ActualEndDateTime'] <= df['RequiredByDateEnd'], 'On Time', 'Late'),
        'Unknown'
    )
    return df

df = load_data()

# -----------------------------------------
# Step 3: Dashboard Filters (Including Dynamic Date Range)
# -----------------------------------------
st.sidebar.header("Filter Work Orders")
start_date = st.sidebar.date_input("Start Date", value=df['OrderDate'].min())
end_date = st.sidebar.date_input("End Date", value=df['OrderDate'].max())

month_options = ['All'] + sorted(df['Month Name'].unique(), key=lambda x: pd.to_datetime(x, format='%B').month)
year_options = ['All'] + sorted(df['Year'].unique())
work_type_options = ['All'] + df['WorkType'].dropna().unique().tolist()
work_status_options = ['All'] + df['WorkStatus'].dropna().unique().tolist()
priority_options = ['All', 'P1 - High', 'P2 - Medium', 'P3 - Low']
location_options = ['All'] + df['ParentLocation'].dropna().unique().tolist()

selected_months = st.sidebar.multiselect("Month", month_options, default=['All'])
selected_years = st.sidebar.multiselect("Year", year_options, default=['All'])
selected_work_types = st.sidebar.multiselect("Work Type", work_type_options, default=['All'])
selected_statuses = st.sidebar.multiselect("Work Status", work_status_options, default=['All'])
selected_priorities = st.sidebar.multiselect("Priority", priority_options, default=['All'])
selected_locations = st.sidebar.multiselect("Location", location_options, default=['All'])

# -----------------------------------------
# Step 4: Apply Filters to Data
# -----------------------------------------
filtered_df = df[(df['OrderDate'] >= pd.to_datetime(start_date)) & (df['OrderDate'] <= pd.to_datetime(end_date))]
if 'All' not in selected_months:
    filtered_df = filtered_df[filtered_df['Month Name'].isin(selected_months)]
if 'All' not in selected_years:
    filtered_df = filtered_df[filtered_df['Year'].isin(selected_years)]
if 'All' not in selected_work_types:
    filtered_df = filtered_df[filtered_df['WorkType'].isin(selected_work_types)]
if 'All' not in selected_statuses:
    filtered_df = filtered_df[filtered_df['WorkStatus'].isin(selected_statuses)]
if 'All' not in selected_priorities:
    filtered_df = filtered_df[filtered_df['WorkPriority'].isin(selected_priorities)]
if 'All' not in selected_locations:
    filtered_df = filtered_df[filtered_df['ParentLocation'].isin(selected_locations)]

# -----------------------------------------
# Step 5: KPI Calculations with DuckDB
# -----------------------------------------
duckdb.register('df', filtered_df)
metrics = duckdb.query("""
SELECT 
    COUNT(*) FILTER (WHERE WorkStatus NOT IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Cancelled')) AS open_wo,
    COUNT(*) FILTER (WHERE WorkStatus IN ('Closed', 'Completed', 'Closed - Was Backlog')) AS completed_wo,
    AVG(Duration) AS avg_duration,
    COUNT(*) FILTER (WHERE OnTimeStatus = 'On Time') * 100.0 / COUNT(*) FILTER (WHERE OnTimeStatus IN ('On Time','Late')) AS pm_compliance
FROM df
""").fetchdf().iloc[0]

# -----------------------------------------
# Step 6: CSS Styling
# -----------------------------------------
st.markdown("""
    <style>
        .metric { font-size: 50px; color: #32659C; }
        .metric-label { font-size: 16px; color: #888; }
        .card {padding: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);}
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------
# Step 7: Display Main KPIs
# -----------------------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Open WOs", metrics['open_wo'])
col2.metric("Completed WOs", metrics['completed_wo'])
col3.metric("Avg Duration (hrs)", f"{metrics['avg_duration']:.2f}")
col4.metric("PM Compliance (%)", f"{metrics['pm_compliance']:.1f}%")

# -----------------------------------------
# Step 8: Visualization - Work Orders by Location
# -----------------------------------------
st.subheader("📍 Work Orders by Location")
wo_location = duckdb.query("SELECT ParentLocation, COUNT(*) AS count FROM df GROUP BY ParentLocation").df()
fig_location = px.bar(wo_location, x='ParentLocation', y='count', color='ParentLocation')
st.plotly_chart(fig_location, use_container_width=True)

# -----------------------------------------
# Step 9: Visualization - Work Orders by Type
# -----------------------------------------
st.subheader("📌 Work Orders by Type")
wo_type = duckdb.query("SELECT WorkType, COUNT(*) AS count FROM df GROUP BY WorkType").df()
fig_type = px.pie(wo_type, names='WorkType', values='count')
st.plotly_chart(fig_type, use_container_width=True)

# -----------------------------------------
# Step 10: Visualization - PMP Trend
# -----------------------------------------
st.subheader("📈 Planned Maintenance Percentage (PMP) Trend")
filtered_df['MonthYear'] = filtered_df['OrderDate'].dt.strftime('%Y-%m')
pmp_trend = filtered_df.groupby('MonthYear').apply(lambda x: (x['WorkType'].isin(['Planned Maint.', 'Inspection']).sum() / len(x))*100).reset_index(name='PMP')
fig_pmp = px.line(pmp_trend, x='MonthYear', y='PMP', markers=True)
st.plotly_chart(fig_pmp, use_container_width=True)

# -----------------------------------------
# Step 11: Pareto Analysis - Work Types
# -----------------------------------------
st.subheader("🔝 Pareto - Work Types")
pareto_df = wo_type.sort_values('count', ascending=False)
pareto_df['cum_pct'] = pareto_df['count'].cumsum() / pareto_df['count'].sum() * 100
fig_pareto = go.Figure([go.Bar(x=pareto_df['WorkType'], y=pareto_df['count']),
                        go.Scatter(x=pareto_df['WorkType'], y=pareto_df['cum_pct'], mode='lines+markers', yaxis='y2')])
fig_pareto.update_layout(yaxis2=dict(overlaying='y', side='right'))
st.plotly_chart(fig_pareto, use_container_width=True)

# -----------------------------------------
# Step 12: Data Preview and Download
# -----------------------------------------
with st.expander("🔍 View Filtered Data"):
    st.dataframe(filtered_df)
    st.download_button("📥 Download CSV", filtered_df.to_csv(index=False), "filtered_data.csv")

# -----------------------------------------
# Step 13: Notes Section
# -----------------------------------------
st.markdown("**Note:** MTTR and PMP are calculated from filtered dataset. Adjust filters to update.")
