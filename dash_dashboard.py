# app.py
from flask import Flask
import dash
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
import dash_table
from dash.dependencies import Input, Output, State
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import duckdb
import numpy as np
import os
import base64
from io import BytesIO

# Flask server
server = Flask(__name__)

# Dash app
app = dash.Dash(__name__, server=server, external_stylesheets=[dbc.themes.DARKLY])

# Constants and Helper Functions (unchanged from Streamlit)
DATE_COLS = {'RequiredByDate': '%m/%d/%Y'}
DATETIME_COLS = {
    'OrderDate': '%m/%d/%Y %H:%M',
    'ReportedDate': '%m/%d/%Y %H:%M',
    'ActualStartDateTime': '%m/%d/%Y %H:%M',
    'ActualEndDateTime': '%m/%d/%Y %H:%M'
}
WORK_STATUSES_COMPLETED = ['Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog']

def parse_dates(df, date_columns):
    for col, fmt in date_columns.items():
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format=fmt, errors='coerce')

def calculate_duration(row):
    if pd.notnull(row['ActualStartDateTime']) and pd.notnull(row['ActualEndDateTime']):
        return (row['ActualEndDateTime'] - row['ActualStartDateTime']).total_seconds() / 3600
    return None

# Data Loading (adapted for Dash)
def load_data_uncached():
    file_path = "Asset Work History.xlsx"
    try:
        df = pd.read_excel(file_path)
    except FileNotFoundError:
        return pd.DataFrame()

    parse_dates(df, DATE_COLS)
    parse_dates(df, DATETIME_COLS)
    df['WorkPriority'] = df['WorkPriority'].replace({'P1': 'P1 - High', 'P2': 'P2 - Medium', 'P3': 'P3 - Low'})
    df['Duration'] = df.apply(calculate_duration, axis=1)
    df['RequiredByDate'] = df['RequiredByDate'].combine_first(
        df['OrderDate'] + pd.to_timedelta(6 - df['OrderDate'].dt.weekday, unit='D')
    )
    df['RequiredByDateEnd'] = df['RequiredByDate'] + pd.Timedelta(hours=23, minutes=59, seconds=59)
    df['OnTimeStatus'] = np.where(
        (df['WorkStatus'].isin(WORK_STATUSES_COMPLETED)) &
        (df['ActualEndDateTime'].notna()) &
        (df['RequiredByDateEnd'].notna()),
        np.where(df['ActualEndDateTime'] <= df['RequiredByDateEnd'], 'On Time', 'Late'),
        'Unknown'
    )
    reference_date = df['RequiredByDate'].combine_first(df['OrderDate']).combine_first(df['ActualEndDateTime'])
    df['WeekOfYear'] = reference_date.dt.isocalendar().week
    df['Month Name'] = df['OrderDate'].dt.strftime('%B')
    df['Year'] = df['OrderDate'].dt.year
    return df

# Load initial data
df = load_data_uncached()

# Calculate Work Order Metrics (unchanged from Streamlit)
def calculate_work_order_metrics(df):
    duckdb.register('df', df)
    current_date = pd.to_datetime(datetime.now().date())
    current_date_end = current_date + pd.Timedelta(hours=23, minutes=59, seconds=59)
    
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

    total_wo = len(df)
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
        planned_hours_month, total_hours_month = pmp_month_result or (0, 0)
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
        completed_month, total_month = completion_month_result or (0, 0)
        total_month = total_month if total_month is not None else 0
        completion_rate_month = (completed_month / total_month * 100) if total_month > 0 else 0
        completion_rate_trend.append({'Month': month_label, 'Completion Rate': completion_rate_month})

    pmp_trend_df = pd.DataFrame(pmp_trend)
    completion_rate_trend_df = pd.DataFrame(completion_rate_trend)

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
        "openω_wo_filtered": open_wo_filtered,
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

# Filter Options
month_options = ['All'] + sorted(df['Month Name'].dropna().unique(), key=lambda x: pd.to_datetime(x, format='%B').month)
year_options = ['All'] + sorted(df['Year'].dropna().astype(int).unique())
week_options = ['All'] + sorted(df['WeekOfYear'].dropna().astype(int).unique())
current_date = pd.to_datetime(datetime.now().date())
current_year = current_date.year
current_month_num = current_date.month
month_names = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
default_months = month_names[:current_month_num]
default_months = [month for month in default_months if month in month_options] or ['All']
default_years = [current_year] if current_year in year_options else ['All']
default_weeks = ['All']
work_type_options = ['All'] + list(df['WorkType'].dropna().unique())
work_status_options = ['All'] + list(df['WorkStatus'].dropna().unique())
work_priority_options = ['All', 'P1 - High', 'P2 - Medium', 'P3 - Low']
location_options = ['All'] + list(df['ParentLocation'].dropna().unique())

# Layout
app.layout = html.Div([
    # Header
    html.Div([
        html.H1("📊 GPMS Maintenance Dashboard", style={
            'textAlign': 'center', 'padding': '10px', 'backgroundColor': '#0E1117',
            'fontSize': '4em', 'fontFamily': '"Montserrat", sans-serif', 'fontWeight': '700', 'color': 'white', 'margin': '0'
        }),
        html.P(f"Current date set to: {current_date}", style={'textAlign': 'center', 'color': 'white'}),
        # Download KPI Manual
        html.A(
            "📖 Download KPI Manual (HTML)",
            href=f"data:application/octet-stream;base64,{base64.b64encode(open('kpi_manual.html', 'rb').read()).decode()}",
            download="kpi_manual.html",
            style={'fontSize': '16px', 'color': 'white'}
        ) if os.path.exists("kpi_manual.html") else html.P("Error: KPI Manual not found.", style={'fontSize': '16px', 'color': 'red'}),
        html.Button("🔁 Reload Data (Clear Cache)", id="reload-button", n_clicks=0, style={'margin': '10px'}),
    ], style={'padding': '10px'}),

    # Filters
    dbc.Row([
        dbc.Col([
            html.Label("Select Month"),
            dcc.Dropdown(id='month-filter', options=[{'label': m, 'value': m} for m in month_options], value=default_months, multi=True),
            html.Label("Select Year"),
            dcc.Dropdown(id='year-filter', options=[{'label': y, 'value': y} for y in year_options], value=default_years, multi=True),
            html.Label("Select Week of Year"),
            dcc.Dropdown(id='week-filter', options=[{'label': w, 'value': w} for w in week_options], value=default_weeks, multi=True),
        ], width=4),
        dbc.Col([
            html.Label("Select Work Type"),
            dcc.Dropdown(id='work-type-filter', options=[{'label': wt, 'value': wt} for wt in work_type_options], value=['All'], multi=True),
            html.Label("Select Work Status"),
            dcc.Dropdown(id='work-status-filter', options=[{'label': ws, 'value': ws} for ws in work_status_options], value=['All'], multi=True),
        ], width=4),
        dbc.Col([
            html.Label("Select Work Priority"),
            dcc.Dropdown(id='work-priority-filter', options=[{'label': wp, 'value': wp} for wp in work_priority_options], value=['All'], multi=True),
            html.Label("Select Location"),
            dcc.Dropdown(id='location-filter', options=[{'label': loc, 'value': loc} for loc in location_options], value=['All'], multi=True),
        ], width=4),
    ], style={'padding': '10px'}),

    # Tabs
    dcc.Tabs(id="tabs", value='dashboard-tab', children=[
        dcc.Tab(label='Dashboard', value='dashboard-tab'),
        dcc.Tab(label='Table Metrics', value='table-metrics-tab'),
        dcc.Tab(label='Gantt Chart', value='gantt-chart-tab'),
    ]),

    # Tab Content
    html.Div(id='tabs-content'),

    # Hidden store for filtered data
    dcc.Store(id='filtered-data'),
    dcc.Store(id='metrics-data'),
    dcc.Download(id="download-csv"),
], style={'backgroundColor': '#1a1a1a', 'color': 'white', 'padding': '20px'})

# Callbacks
@app.callback(
    [Output('filtered-data', 'data'),
     Output('metrics-data', 'data')],
    [Input('reload-button', 'n_clicks'),
     Input('month-filter', 'value'),
     Input('year-filter', 'value'),
     Input('week-filter', 'value'),
     Input('work-type-filter', 'value'),
     Input('work-status-filter', 'value'),
     Input('work-priority-filter', 'value'),
     Input('location-filter', 'value')]
)
def update_data(n_clicks, selected_months, selected_years, selected_weeks, selected_work_types, selected_work_status, selected_work_priority, selected_locations):
    df = load_data_uncached() if n_clicks > 0 else df
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
        return filtered_df.to_dict('records'), {}

    metrics = calculate_work_order_metrics(filtered_df)
    return filtered_df.to_dict('records'), metrics

@app.callback(
    Output('tabs-content', 'children'),
    [Input('tabs', 'value'),
     Input('filtered-data', 'data'),
     Input('metrics-data', 'data')]
)
def render_tab_content(tab, filtered_data, metrics_data):
    if not filtered_data:
        return html.Div("No data matches the selected filters. Please adjust your filter selections.", style={'color': 'yellow'})
    
    filtered_df = pd.DataFrame(filtered_data)
    metrics = metrics_data

    if tab == 'dashboard-tab':
        return html.Div([
            # Weekly Metrics
            html.H3("📅 Weekly Metrics"),
            dbc.Row([
                dbc.Col(html.Div([
                    html.P("KPI 1: CURRENT OPEN WORK ORDERS", className='metric-label'),
                    html.P(f"{metrics['open_wo_week']:,}", className='metric-value')
                ], className='metric-container'), width=4),
                dbc.Col(html.Div([
                    html.P("KPI 2: COMPLETED WORK ORDERS FOR THE CURRENT WEEK", className='metric-label'),
                    html.P(f"{metrics['completed_wo_week']:,}", className='metric-value')
                ], className='metric-container'), width=4),
                dbc.Col(html.Div([
                    html.P("KPI 3: WORK ORDERS IN PROGRESS", className='metric-label'),
                    html.P(f"{metrics['in_progress_wo_week']:,}", className='metric-value')
                ], className='metric-container'), width=4),
            ]),

            # High-Level Metrics
            html.H3("📊 High-Level Metrics"),
            dbc.Row([
                dbc.Col(html.Div([
                    html.P("KPI 4: TOTAL WORK ORDERS (FILTERED)", className='metric-label'),
                    html.P(f"{metrics['total_wo']:,}", className='metric-value')
                ], className='metric-container'), width=4),
                dbc.Col(html.Div([
                    html.P("KPI 5: COMPLETED WORK ORDERS (FILTERED)", className='metric-label'),
                    html.P(f"{metrics['completed_wo']:,}", className='metric-value')
                ], className='metric-container'), width=4),
                dbc.Col(html.Div([
                    html.P("KPI 6: EMERGENCY MAINTENANCE YTD (FILTERED)", className='metric-label'),
                    html.P(f"{metrics['emergency_ytd']:,}", className='metric-value')
                ], className='metric-container'), width=4),
            ]),
            dbc.Row([
                dbc.Col(html.Div([
                    html.P("KPI 7: BACKLOG COUNT YTD", className='metric-label'),
                    html.P(f"{metrics['backlog_count_ytd']:,}", className='metric-value')
                ], className='metric-container'), width=4),
                dbc.Col(html.Div([
                    html.P("KPI 8: BACKLOG COUNT TOTAL", className='metric-label'),
                    html.P(f"{metrics['backlog_count_total']:,}", className='metric-value')
                ], className='metric-container'), width=4),
                dbc.Col(html.Div(" "), width=4),
            ]),

            # Project Metrics
            html.H3("⏱️ Project Metrics"),
            dbc.Row([
                dbc.Col(html.Div([
                    html.P("KPI 9: PROJECTS IN PROGRESS", className='metric-label'),
                    html.P(f"{metrics['project_in_progress_count']:,}", className='metric-value')
                ], className='metric-container'), width=4),
                dbc.Col(html.Div([
                    html.P("KPI 10: TOTAL PROJECTS YTD", className='metric-label'),
                    html.P(f"{metrics['total_projects_ytd']:,}", className='metric-value')
                ], className='metric-container'), width=4),
                dbc.Col(html.Div(" "), width=4),
            ]),

            # Maintenance Efficiency Metrics
            html.H3("📏 Maintenance Efficiency Metrics"),
            dbc.Row([
                dbc.Col(html.Div([
                    html.P("KPI 11: PLANNED MAINTENANCE PERCENTAGE (PMP)", className='metric-label'),
                    html.P(f"{metrics['pmp']:.2f}", className='metric-value')
                ], className='metric-container'), width=4),
                dbc.Col(html.Div([
                    html.P("KPI 12: CORRECTIVE MAINTENANCE PERCENTAGE", className='metric-label'),
                    html.P(f"{metrics['corrective_pct']:.2f}", className='metric-value')
                ], className='metric-container'), width=4),
                dbc.Col(html.Div([
                    html.P("KPI 13: WORK ORDER COMPLETION RATE (%)", className='metric-label'),
                    html.P(f"{metrics['completion_rate']:.2f}", className='metric-value')
                ], className='metric-container'), width=4),
            ]),

            # Work Order Visualizations
            html.H3("📊 Work Order Visualizations"),
            dbc.Row([
                dbc.Col(dcc.Graph(figure=px.bar(
                    duckdb.query("SELECT ParentLocation, COUNT(*) as count FROM filtered_df GROUP BY ParentLocation").df().sort_values(by='count', ascending=False),
                    x='ParentLocation', y='count', title='Work Orders by Location', color='ParentLocation',
                    color_discrete_sequence=px.colors.qualitative.Pastel1
                ).update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white')), width=4),
                dbc.Col(dcc.Graφh(figure=px.bar(
                    duckdb.query("SELECT WorkPriority, COUNT(*) as count FROM filtered_df GROUP BY WorkPriority").df().sort_values(by='count', ascending=False),
                    x='WorkPriority', y='count', title='Work Orders by Priority', color='WorkPriority',
                    color_discrete_sequence=px.colors.qualitative.Pastel1
                ).update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white')), width=4),
                dbc.Col(dcc.Graph(figure=px.pie(
                    duckdb.query("SELECT WorkType, COUNT(*) as count FROM filtered_df GROUP BY WorkType").df(),
                    names='WorkType', values='count', title='Percentage of Work Orders by Work Type',
                    color_discrete_sequence=px.colors.qualitative.Pastel1
                ).update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white')), width=4),
            ]),

            # PMP vs. Corrective Maintenance
            dbc.Row([
                dbc.Col(dcc.Graph(figure=go.Figure(
                    data=[go.Pie(
                        labels=["Planned Maintenance", "Corrective Maintenance"],
                        values=[
                            duckdb.query("SELECT SUM(CASE WHEN WorkType IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects', 'Predictive Maint') THEN COALESCE(Duration, 0) ELSE 0 END) as planned_hours FROM filtered_df WHERE ActualStartDateTime IS NOT NULL AND ActualEndDateTime IS NOT NULL AND WorkStatus IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog') AND Duration IS NOT NULL").fetchone()[0] or 0,
                            duckdb.query("SELECT SUM(CASE WHEN WorkType IN ('Breakdown', 'Unplanned Corrective Maintenance') THEN COALESCE(Duration, 0) ELSE 0 END) as corrective_hours FROM filtered_df WHERE ActualStartDateTime IS NOT NULL AND ActualEndDateTime IS NOT NULL AND WorkStatus IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog') AND Duration IS NOT NULL").fetchone()[0] or 0
                        ],
                        textinfo="percent", textposition="inside", marker=dict(colors=px.colors.qualitative.Pastel1)
                    )],
                    layout=dict(title="Planned vs. Corrective Maintenance", plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white')
                )), width=4),

                # Monthly Work Order Trends
                dbc.Col(dcc.Graph(figure=go.Figure(
                    data=[
                        go.Scatter(x=metrics['monthly_wo_trend_df']['Month'], y=metrics['monthly_wo_trend_df']['Total Work Orders'], mode='lines+markers', name='Total Work Orders', line=dict(color=px.colors.qualitative.Pastel1[0])),
                        go.Scatter(x=metrics['monthly_wo_trend_df']['Month'], y=metrics['monthly_wo_trend_df']['Completed Work Orders'], mode='lines+markers', name='Completed Work Orders', line=dict(color=px.colors.qualitative.Pastel1[1]))
                    ],
                    layout=dict(title='Monthly Work Order Trends (Last 6 Months)', xaxis_title="Month", yaxis_title="Work Order Count", plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white', showlegend=True, yaxis=dict(rangemode="tozero"))
                )), width=4),

                # Work Order On-Time Completion
                dbc.Col(dcc.Graph(figure=go.Figure(
                    go.Indicator(
                        mode="gauge+number", value=metrics['on_time_completion_pct'],
                        title={"text": "Work Order On-Time Completion (%)"},
                        gauge={
                            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "white"},
                            "bar": {"color": px.colors.qualitative.Pastel1[1]},
                            "bgcolor": "rgba(0,0,0,0)", "bordercolor": "white",
                            "steps": [
                                {"range": [0, 30], "color": px.colors.qualitative.Pastel1[3]},
                                {"range": [30, 60], "color": px.colors.qualitative.Pastel1[6]},
                                {"range": [60, 90], "color": px.colors.qualitative.Pastel1[4]},
                                {"range": [90, 100], "color": px.colors.qualitative.Pastel1[2]}
                            ],
                            "threshold": {"line": {"color": "red", "width": 4}, "thickness": 0.75, "value": 90}
                        }
                    ),
                    layout=dict(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white')
                )), width=4),
            ]),

            # Compliance Trends
            html.H3("📈 Compliance Trends"),
            dcc.Graph(figure=go.Figure(
                data=[go.Bar(
                    x=duckdb.query("""
                        SELECT ParentLocation,
                            SUM(CASE WHEN OnTimeStatus = 'On Time' AND WorkStatus IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog') THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0) AS pm_compliance
                        FROM filtered_df
                        WHERE WorkType IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects', 'Predictive Maint')
                        AND RequiredByDate IS NOT NULL
                        AND RequiredByDate <= CURRENT_DATE
                        GROUP BY ParentLocation
                    """).df().sort_values('pm_compliance', ascending=False)['ParentLocation'],
                    y=duckdb.query("""
                        SELECT ParentLocation,
                            SUM(CASE WHEN OnTimeStatus = 'On Time' AND WorkStatus IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog') THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0) AS pm_compliance
                        FROM filtered_df
                        WHERE WorkType IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects', 'Predictive Maint')
                        AND RequiredByDate IS NOT NULL
                        AND RequiredByDate <= CURRENT_DATE
                        GROUP BY ParentLocation
                    """).df().sort_values('pm_compliance', ascending=False)['pm_compliance'],
                    marker_color=px.colors.qualitative.Pastel1,
                    name="PM Compliance (%)"
                )],
                layout=dict(
                    title="PM Compliance by Location",
                    xaxis_title="Location",
                    yaxis_title="Compliance (%)",
                    yaxis=dict(range=[0, 100]),
                    shapes=[dict(
                        type="line",
                        x0=-0.5,
                        x1=len(duckdb.query("SELECT ParentLocation FROM filtered_df GROUP BY ParentLocation").df()),
                        y0=80,
                        y1=80,
                        line=dict(color="red", width=2, dash="dash")
                    )],
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_color='white'
                )
            )),

            # Pareto Charts
            html.H3("📊 Pareto Analysis"),
            dbc.Row([
                dbc.Col(dcc.Graph(figure=go.Figure(
                    data=[
                        go.Bar(x=duckdb.query("SELECT WorkType, COUNT(*) as count FROM filtered_df GROUP BY WorkType ORDER BY count DESC LIMIT 10").df()['WorkType'],
                               y=duckdb.query("SELECT WorkType, COUNT(*) as count FROM filtered_df GROUP BY WorkType ORDER BY count DESC LIMIT 10").df()['count'],
                               name='Count', marker_color=px.colors.qualitative.Pastel1[0]),
                        go.Scatter(x=duckdb.query("SELECT WorkType, COUNT(*) as count FROM filtered_df GROUP BY WorkType ORDER BY count DESC LIMIT 10").df()['WorkType'],
                                   y=duckdb.query("SELECT WorkType, COUNT(*) as count FROM filtered_df GROUP BY WorkType ORDER BY count DESC LIMIT 10").df()['count'].cumsum() / duckdb.query("SELECT WorkType, COUNT(*) as count FROM filtered_df GROUP BY WorkType ORDER BY count DESC LIMIT 10").df()['count'].sum() * 100,
                                   name='Cumulative %', yaxis='y2', mode='lines+markers', line=dict(color='#FF6F61'))
                    ],
                    layout=dict(title="Top 10 Work Types by Count", xaxis_title="Work Type", yaxis=dict(title="Count"), yaxis2=dict(title="Cumulative %", overlaying='y', side='right', range=[0, 100]), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white')
                )), width=4),
                dbc.Col(dcc.Graph(figure=go.Figure(
                    data=[
                        go.Bar(x=duckdb.query("SELECT FailureType, COUNT(*) as count FROM filtered_df WHERE FailureType IS NOT NULL GROUP BY FailureType ORDER BY count DESC LIMIT 10").df()['FailureType'],
                               y=duckdb.query("SELECT FailureType, COUNT(*) as count FROM filtered_df WHERE FailureType IS NOT NULL GROUP BY FailureType ORDER BY count DESC LIMIT 10").df()['count'],
                               name='Count', marker_color=px.colors.qualitative.Pastel1[0]),
                        go.Scatter(x=duckdb.query("SELECT FailureType, COUNT(*) as count FROM filtered_df WHERE FailureType IS NOT NULL GROUP BY FailureType ORDER BY count DESC LIMIT 10").df()['FailureType'],
                                   y=duckdb.query("SELECT FailureType, COUNT(*) as count FROM filtered_df WHERE FailureType IS NOT NULL GROUP BY FailureType ORDER BY count DESC LIMIT 10").df()['count'].cumsum() / duckdb.query("SELECT FailureType, COUNT(*) as count FROM filtered_df WHERE FailureType IS NOT NULL GROUP BY FailureType ORDER BY count DESC LIMIT 10").df()['count'].sum() * 100,
                                   name='Cumulative %', yaxis='y2', mode='lines+markers', line=dict(color='#FF6F61'))
                    ],
                    layout=dict(title="Top 10 Failure Types by Count", xaxis_title="Failure Type", yaxis=dict(title="Count"), yaxis2=dict(title="Cumulative %", overlaying='y', side='right', range=[0, 100]), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white')
                )), width=4),
                dbc.Col(dcc.Graph(figure=go.Figure(
                    data=[
                        go.Bar(x=duckdb.query("SELECT SystemType, COUNT(*) as count FROM filtered_df WHERE SystemType IS NOT NULL GROUP BY SystemType ORDER BY count DESC LIMIT 10").df()['SystemType'],
                               y=duckdb.query("SELECT SystemType, COUNT(*) as count FROM filtered_df WHERE SystemType IS NOT NULL GROUP BY SystemType ORDER BY count DESC LIMIT 10").df()['count'],
                               name='Count', marker_color=px.colors.qualitative.Pastel1[0]),
                        go.Scatter(x=duckdb.query("SELECT SystemType, COUNT(*) as count FROM filtered_df WHERE SystemType IS NOT NULL GROUP BY SystemType ORDER BY count DESC LIMIT 10").df()['SystemType'],
                                   y=duckdb.query("SELECT SystemType, COUNT(*) as count FROM filtered_df WHERE SystemType IS NOT NULL GROUP BY SystemType ORDER BY count DESC LIMIT 10").df()['count'].cumsum() / duckdb.query("SELECT SystemType, COUNT(*) as count FROM filtered_df WHERE SystemType IS NOT NULL GROUP BY SystemType ORDER BY count DESC LIMIT 10").df()['count'].sum() * 100,
                                   name='Cumulative %', yaxis='y2', mode='lines+markers', line=dict(color='#FF6F61'))
                    ],
                    layout=dict(title="Top 10 System Types by Count", xaxis_title="System Type", yaxis=dict(title="Count"), yaxis2=dict(title="Cumulative %", overlaying='y', side='right', range=[0, 100]), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white')
                )), width=4),
            ]),

            # Data Preview
            html.H3("📄 Data Preview"),
            dash_table.DataTable(
                data=filtered_df.to_dict('records'),
                columns=[{'name': i, 'id': i} for i in filtered_df.columns],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'color': 'white', 'backgroundColor': 'rgba(0,0,0,0)'},
                style_header={'backgroundColor': 'rgba(255,255,255,0.1)', 'fontWeight': 'bold', 'color': 'white'},
            ),
            html.Button("📥 Download Report as CSV", id="download-button", n_clicks=0),
        ])

    elif tab == 'table-metrics-tab':
        current_date = pd.to_datetime(datetime.now())
        current_year = current_date.year
        current_month_index = current_date.month
        ytd_start = current_date.replace(month=1, day=1)
        expected_ytd_months = [datetime(current_year, m, 1).strftime('%B') for m in range(1, current_month_index + 1)]

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
            SELECT ParentLocation,
                SUM(CASE 
                    WHEN OnTimeStatus = 'On Time' 
                    AND WorkStatus IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog') 
                    THEN 1 ELSE 0 
                END) * 100.0 / NULLIF(COUNT(*), 0) AS pm_compliance
            FROM filtered_df
            WHERE WorkType IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects', 'Predictive Maint')
            AND RequiredByDate IS NOT NULL
            AND RequiredByDate BETWEEN ? AND ?
            GROUP BY ParentLocation
        """
        prev_week = current_date.isocalendar().week - 1
        prev_year = current_year if prev_week > 0 else current_year - 1
        if prev_week <= 0:
            prev_week = pd.to_datetime(f'{prev_year}-12-31').isocalendar().week
        prev_week_query = """
            SELECT ParentLocation,
                SUM(CASE 
                    WHEN OnTimeStatus = 'On Time' 
                    AND WorkStatus IN ('Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog')
                    THEN 1 ELSE 0 
                END) * 100.0 / NULLIF(COUNT(*), 0) AS pm_compliance
            FROM filtered_df
            WHERE WorkType IN ('Planned Maint.', 'Planned Corrective Maint.', 'Planned Improvement', 'Inspection', 'Projects', 'Predictive Maint')
            AND RequiredByDate IS NOT NULL
            AND EXTRACT(WEEK FROM RequiredByDate) = ?
            AND EXTRACT(YEAR FROM RequiredByDate) = ?
            GROUP BY ParentLocation
        """
        prev_week_df = duckdb.query(prev_week_query, params=[prev_week, prev_year]).df()
        prev_week_df = prev_week_df.rename(columns={'pm_compliance': 'Previous Week Compliance (%)'}) if not prev_week_df.empty else pd.DataFrame(columns=['ParentLocation', 'Previous Week Compliance (%)'])
        current_month_start = current_date.replace(day=1)
        curr_month_df = duckdb.query(base_query, params=[current_month_start, current_date]).df()
        curr_month_df = curr_month_df.rename(columns={'pm_compliance': 'Current Month Compliance (%)'}) if not curr_month_df.empty else pd.DataFrame(columns=['ParentLocation', 'Current Month Compliance (%)'])
        ytd_df = duckdb.query(base_query, params=[ytd_start, current_date]).df()
        ytd_df = ytd_df.rename(columns={'pm_compliance': 'YTD Compliance (%)'}) if not ytd_df.empty else pd.DataFrame(columns=['ParentLocation', 'YTD Compliance (%)'])
        compliance_df = prev_week_df.merge(curr_month_df, on='ParentLocation', how='outer').merge(ytd_df, on='ParentLocation', how='outer').sort_values('ParentLocation').replace(0.00, None)

        duckdb.unregister('filtered_df')

        return html.Div([
            html.H3("📋 Table Metrics"),
            html.H4("PM Compliance by Location"),
            dash_table.DataTable(
                data=compliance_df.to_dict('records'),
                columns=[
                    {'name': 'ParentLocation', 'id': 'ParentLocation'},
                    {'name': 'Previous Week Compliance (%)', 'id': 'Previous Week Compliance (%)', 'type': 'numeric', 'format': {'specifier': '.2f%'}},
                    {'name': 'Current Month Compliance (%)', 'id': 'Current Month Compliance (%)', 'type': 'numeric', 'format': {'specifier': '.2f%'}},
                    {'name': 'YTD Compliance (%)', 'id': 'YTD Compliance (%)', 'type': 'numeric', 'format': {'specifier': '.2f%'}}
                ],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'color': 'white', 'backgroundColor': 'rgba(0,0,0,0)'},
                style_header={'backgroundColor': 'rgba(255,255,255,0.1)', 'fontWeight': 'bold', 'color': 'white'},
            ),

            html.H4("Open Work Orders"),
            dash_table.DataTable(
                data=filtered_df[
                    ~filtered_df['WorkStatus'].isin(['Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog', 'Cancelled'])
                ][['OrderDate', 'Order', 'AssetName', 'WorkDescription', 'ActualStartDateTime', 'ActualEndDateTime', 'Duration', 'WorkType', 'SystemType', 'WorkStatus', 'WorkPriority', 'ParentLocation']].sort_values(by='OrderDate', ascending=False).to_dict('records'),
                columns=[
                    {'name': 'OrderDate', 'id': 'OrderDate', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY'}},
                    {'name': 'Order', 'id': 'Order'},
                    {'name': 'AssetName', 'id': 'AssetName'},
                    {'name': 'WorkDescription', 'id': 'WorkDescription'},
                    {'name': 'ActualStartDateTime', 'id': 'ActualStartDateTime', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY HH:mm'}},
                    {'name': 'ActualEndDateTime', 'id': 'ActualEndDateTime', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY HH:mm'}},
                    {'name': 'Duration', 'id': 'Duration', 'type': 'numeric', 'format': {'specifier': '.2f hrs'}},
                    {'name': 'WorkType', 'id': 'WorkType'},
                    {'name': 'SystemType', 'id': 'SystemType'},
                    {'name': 'WorkStatus', 'id': 'WorkStatus'},
                    {'name': 'WorkPriority', 'id': 'WorkPriority'},
                    {'name': 'ParentLocation', 'id': 'ParentLocation'}
                ],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'color': 'white', 'backgroundColor': 'rgba(0,0,0,0)'},
                style_header={'backgroundColor': 'rgba(255,255,255,0.1)', 'fontWeight': 'bold', 'color': 'white'},
            ),

            html.H4("Completed/Closed Work Orders"),
            dash_table.DataTable(
                data=filtered_df[
                    (filtered_df['WorkStatus'].isin(['Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog'])) &
                    (filtered_df['ActualEndDateTime'].notna())
                ][['OrderDate', 'Order', 'AssetName', 'WorkDescription', 'RequiredByDate', 'ActualStartDateTime', 'ActualEndDateTime', 'Duration', 'WorkType', 'SystemType', 'WorkStatus', 'WorkPriority']].sort_values('OrderDate', ascending=False).to_dict('records'),
                columns=[
                    {'name': 'OrderDate', 'id': 'OrderDate', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY'}},
                    {'name': 'Order', 'id': 'Order'},
                    {'name': 'AssetName', 'id': 'AssetName'},
                    {'name': 'WorkDescription', 'id': 'WorkDescription'},
                    {'name': 'RequiredByDate', 'id': 'RequiredByDate', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY'}},
                    {'name': 'ActualStartDateTime', 'id': 'ActualStartDateTime', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY HH:mm'}},
                    {'name': 'ActualEndDateTime', 'id': 'ActualEndDateTime', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY HH:mm'}},
                    {'name': 'Duration', 'id': 'Duration', 'type': 'numeric', 'format': {'specifier': '.2f hrs'}},
                    {'name': 'WorkType', 'id': 'WorkType'},
                    {'name': 'SystemType', 'id': 'SystemType'},
                    {'name': 'WorkStatus', 'id': 'WorkStatus'},
                    {'name': 'WorkPriority', 'id': 'WorkPriority'}
                ],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'color': 'white', 'backgroundColor': 'rgba(0,0,0,0)'},
                style_header={'backgroundColor': 'rgba(255,255,255,0.1)', 'fontWeight': 'bold', 'color': 'white'},
            ),

            html.H4("Corrective Work Orders"),
            dash_table.DataTable(
                data=duckdb.query("""
                    SELECT OrderDate, Order, AssetName, WorkDescription, RequiredByDate, ActualStartDateTime, ActualEndDateTime, Duration, WorkType, SystemType, WorkStatus, WorkPriority, ParentLocation
                    FROM filtered_df
                    WHERE WorkType IN ('Planned Corrective Maint.', 'Unplanned Corrective Maint.', 'Breakdown', 'Planned Improvement')
                    ORDER BY OrderDate DESC
                """).df().to_dict('records'),
                columns=[
                    {'name': 'OrderDate', 'id': 'OrderDate', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY'}},
                    {'name': 'Order', 'id': 'Order'},
                    {'name': 'AssetName', 'id': 'AssetName'},
                    {'name': 'WorkDescription', 'id': 'WorkDescription'},
                    {'name': 'RequiredByDate', 'id': 'RequiredByDate', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY'}},
                    {'name': 'ActualStartDateTime', 'id': 'ActualStartDateTime', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY HH:mm'}},
                    {'name': 'ActualEndDateTime', 'id': 'ActualEndDateTime', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY HH:mm'}},
                    {'name': 'Duration', 'id': 'Duration', 'type': 'numeric', 'format': {'specifier': '.2f hrs'}},
                    {'name': 'WorkType', 'id': 'WorkType'},
                    {'name': 'SystemType', 'id': 'SystemType'},
                    {'name': 'WorkStatus', 'id': 'WorkStatus'},
                    {'name': 'WorkPriority', 'id': 'WorkPriority'},
                    {'name': 'ParentLocation', 'id': 'ParentLocation'}
                ],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'color': 'white', 'backgroundColor': 'rgba(0,0,0,0)'},
                style_header={'backgroundColor': 'rgba(255,255,255,0.1)', 'fontWeight': 'bold', 'color': 'white'},
            ),

            html.H4("Cancelled Work Orders"),
            dash_table.DataTable(
                data=duckdb.query("""
                    SELECT OrderDate, Order, AssetName, WorkDescription, RequiredByDate, ActualStartDateTime, ActualEndDateTime, Duration, WorkType, SystemType, WorkStatus, WorkPriority, ParentLocation
                    FROM filtered_df
                    WHERE WorkStatus = 'Cancelled'
                    ORDER BY OrderDate DESC
                """).df().to_dict('records'),
                columns=[
                    {'name': 'OrderDate', 'id': 'OrderDate', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY'}},
                    {'name': 'Order', 'id': 'Order'},
                    {'name': 'AssetName', 'id': 'AssetName'},
                    {'name': 'WorkDescription', 'id': 'WorkDescription'},
                    {'name': 'RequiredByDate', 'id': 'RequiredByDate', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY'}},
                    {'name': 'ActualStartDateTime', 'id': 'ActualStartDateTime', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY HH:mm'}},
                    {'name': 'ActualEndDateTime', 'id': 'ActualEndDateTime', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY HH:mm'}},
                    {'name': 'Duration', 'id': 'Duration', 'type': 'numeric', 'format': {'specifier': '.2f hrs'}},
                    {'name': 'WorkType', 'id': 'WorkType'},
                    {'name': 'SystemType', 'id': 'SystemType'},
                    {'name': 'WorkStatus', 'id': 'WorkStatus'},
                    {'name': 'WorkPriority', 'id': 'WorkPriority'},
                    {'name': 'ParentLocation', 'id': 'ParentLocation'}
                ],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'color': 'white', 'backgroundColor': 'rgba(0,0,0,0)'},
                style_header={'backgroundColor': 'rgba(255,255,255,0.1)', 'fontWeight': 'bold', 'color': 'white'},
            ),

            html.H4("Emergency Work Orders (Breakdown, Unplanned)"),
            dash_table.DataTable(
                data=duckdb.query("""
                    SELECT OrderDate, Order, AssetName, WorkDescription, RequiredByDate, ActualStartDateTime, ActualEndDateTime, Duration, WorkType, SystemType, WorkStatus, WorkPriority, ParentLocation
                    FROM filtered_df
                    WHERE WorkType IN ('Breakdown', 'Unplanned Corrective Maint.')
                    AND WorkPriority = 'P1 - High'
                    ORDER BY OrderDate DESC
                """).df().to_dict('records'),
                columns=[
                    {'name': 'OrderDate', 'id': 'OrderDate', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY'}},
                    {'name': 'Order', 'id': 'Order'},
                    {'name': 'AssetName', 'id': 'AssetName'},
                    {'name': 'WorkDescription', 'id': 'WorkDescription'},
                    {'name': 'RequiredByDate', 'id': 'RequiredByDate', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY'}},
                    {'name': 'ActualStartDateTime', 'id': 'ActualStartDateTime', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY HH:mm'}},
                    {'name': 'ActualEndDateTime', 'id': 'ActualEndDateTime', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY HH:mm'}},
                    {'name': 'Duration', 'id': 'Duration', 'type': 'numeric', 'format': {'specifier': '.2f hrs'}},
                    {'name': 'WorkType', 'id': 'WorkType'},
                    {'name': 'SystemType', 'id': 'SystemType'},
                    {'name': 'WorkStatus', 'id': 'WorkStatus'},
                    {'name': 'WorkPriority', 'id': 'WorkPriority'},
                    {'name': 'ParentLocation', 'id': 'ParentLocation'}
                ],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'color': 'white', 'backgroundColor': 'rgba(0,0,0,0)'},
                style_header={'backgroundColor': 'rgba(255,255,255,0.1)', 'fontWeight': 'bold', 'color': 'white'},
            ),

            html.H4("Project Orders"),
            dash_table.DataTable(
                data=duckdb.query("""
                    SELECT Order, OrderDate, AssetName, WorkDescription, ActualStartDateTime, ActualEndDateTime, Duration, WorkType, SystemType, WorkStatus, WorkPriority
                    FROM filtered_df
                    WHERE WorkType = 'Projects'
                    ORDER BY OrderDate DESC
                """).df().to_dict('records'),
                columns=[
                    {'name': 'Order', 'id': 'Order'},
                    {'name': 'OrderDate', 'id': 'OrderDate', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY'}},
                    {'name': 'AssetName', 'id': 'AssetName'},
                    {'name': 'WorkDescription', 'id': 'WorkDescription'},
                    {'name': 'ActualStartDateTime', 'id': 'ActualStartDateTime', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY HH:mm'}},
                    {'name': 'ActualEndDateTime', 'id': 'ActualEndDateTime', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY HH:mm'}},
                    {'name': 'Duration', 'id': 'Duration', 'type': 'numeric', 'format': {'specifier': '.2f hrs'}},
                    {'name': 'WorkType', 'id': 'WorkType'},
                    {'name': 'SystemType', 'id': 'SystemType'},
                    {'name': 'WorkStatus', 'id': 'WorkStatus'},
                    {'name': 'WorkPriority', 'id': 'WorkPriority'}
                ],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'color': 'white', 'backgroundColor': 'rgba(0,0,0,0)'},
                style_header={'backgroundColor': 'rgba(255,255,255,0.1)', 'fontWeight': 'bold', 'color': 'white'},
            ),

            html.H4("Mean Time to Repair by Location (Hours)"),
            dash_table.DataTable(
                data=metrics['location_metrics'][['ParentLocation', 'mttr_hrs']].to_dict('records'),
                columns=[
                    {'name': 'ParentLocation', 'id': 'ParentLocation'},
                    {'name': 'mttr_hrs', 'id': 'mttr_hrs', 'type': 'numeric', 'format': {'specifier': '.2f'}}
                ],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'color': 'white', 'backgroundColor': 'rgba(0,0,0,0)'},
                style_header={'backgroundColor': 'rgba(255,255,255,0.1)', 'fontWeight': 'bold', 'color': 'white'},
            ),

            html.H4("Work Order Distribution by WorkType"),
            dash_table.DataTable(
                data=duckdb.query("""
                    SELECT WorkType, COUNT(*) AS count, ROUND(SUM(Duration), 2) AS hours, ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
                    FROM filtered_df
                    WHERE WorkType IS NOT NULL
                    GROUP BY WorkType
                    ORDER BY count DESC
                """).df().to_dict('records'),
                columns=[
                    {'name': 'WorkType', 'id': 'WorkType'},
                    {'name': 'count', 'id': 'count', 'type': 'numeric', 'format': {'specifier': 'd'}},
                    {'name': 'hours', 'id': 'hours', 'type': 'numeric', 'format': {'specifier': '.2f hrs'}},
                    {'name': 'percentage', 'id': 'percentage', 'type': 'numeric', 'format': {'specifier': '.2f%'}}
                ],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'color': 'white', 'backgroundColor': 'rgba(0,0,0,0)'},
                style_header={'backgroundColor': 'rgba(255,255,255,0.1)', 'fontWeight': 'bold', 'color': 'white'},
            ),

            html.H4("Work Order Distribution by SystemType"),
            dash_table.DataTable(
                data=duckdb.query("""
                    SELECT SystemType, COUNT(*) as count, ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
                    FROM filtered_df
                    WHERE SystemType IS NOT NULL
                    GROUP BY SystemType
                    ORDER BY count DESC
                """).df().to_dict('records'),
                columns=[
                    {'name': 'SystemType', 'id': 'SystemType'},
                    {'name': 'count', 'id': 'count'},
                    {'name': 'percentage', 'id': 'percentage', 'type': 'numeric', 'format': {'specifier': '.2f%'}}
                ],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'color': 'white', 'backgroundColor': 'rgba(0,0,0,0)'},
                style_header={'backgroundColor': 'rgba(255,255,255,0.1)', 'fontWeight': 'bold', 'color': 'white'},
            ),

            html.H4("Work Order Distribution by WorkStatus"),
            dash_table.DataTable(
                data=duckdb.query("""
                    SELECT WorkStatus, COUNT(*) as count, ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
                    FROM filtered_df
                    GROUP BY WorkStatus
                    ORDER BY count DESC
                """).df().to_dict('records'),
                columns=[
                    {'name': 'WorkStatus', 'id': 'WorkStatus'},
                    {'name': 'count', 'id': 'count'},
                    {'name': 'percentage', 'id': 'percentage', 'type': 'numeric', 'format': {'specifier': '.2f%'}}
                ],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'color': 'white', 'backgroundColor': 'rgba(0,0,0,0)'},
                style_header={'backgroundColor': 'rgba(255,255,255,0.1)', 'fontWeight': 'bold', 'color': 'white'},
            ),

            html.H4("High-Priority (P1) Work Orders"),
            dash_table.DataTable(
                data=duckdb.query("""
                    SELECT Order, OrderDate, AssetName, WorkDescription, WorkStatus
                    FROM filtered_df
                    WHERE WorkPriority = 'P1 - High'
                    ORDER BY OrderDate
                """).df().to_dict('records'),
                columns=[
                    {'name': 'Order', 'id': 'Order'},
                    {'name': 'OrderDate', 'id': 'OrderDate', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY'}},
                    {'name': 'AssetName', 'id': 'AssetName'},
                    {'name': 'WorkDescription', 'id': 'WorkDescription'},
                    {'name': 'WorkStatus', 'id': 'WorkStatus'}
                ],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'color': 'white', 'backgroundColor': 'rgba(0,0,0,0)'},
                style_header={'backgroundColor': 'rgba(255,255,255,0.1)', 'fontWeight': 'bold', 'color': 'white'},
            ),

            html.H4("Work Orders by FailureType"),
            dash_table.DataTable(
                data=duckdb.query("""
                    SELECT FailureType, COUNT(*) as count, ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
                    FROM filtered_df
                    WHERE FailureType IS NOT NULL
                    GROUP BY FailureType
                    ORDER BY count DESC
                """).df().to_dict('records'),
                columns=[
                    {'name': 'FailureType', 'id': 'FailureType'},
                    {'name': 'count', 'id': 'count'},
                    {'name': 'percentage', 'id': 'percentage', 'type': 'numeric', 'format': {'specifier': '.2f%'}}
                ],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'color': 'white', 'backgroundColor': 'rgba(0,0,0,0)'},
                style_header={'backgroundColor': 'rgba(255,255,255,0.1)', 'fontWeight': 'bold', 'color': 'white'},
            ),

            html.H4("Buoy Bush Change-Out Reliability"),
            dash_table.DataTable(
                data=duckdb.query("""
                    SELECT 
                        AssetName, AssetDescription, Order, OrderDate, WorkDescription, ActualStartDateTime, ActualEndDateTime, Duration, WorkStatus,
                        DATEDIFF('day', LAG(ActualEndDateTime) OVER (PARTITION BY AssetName ORDER BY ActualEndDateTime), ActualEndDateTime) AS DaysSinceLastChangeOut
                    FROM filtered_df
                    WHERE AssetName IN ('ABB-ME-BY-03', 'ABB-ME-BY-04', 'ABB-ME-BY-02', 'ABB-ME-BY-05')
                    AND SystemType = 'Buoy Body'
                    AND FailureType = 'Worn'
                    AND RemedyType = 'Replaced'
                    AND WorkDescription ILIKE '%UKP Bush%'
                    ORDER BY ActualEndDateTime DESC
                """).df().to_dict('records'),
                columns=[
                    {'name': 'AssetName', 'id': 'AssetName'},
                    {'name': 'AssetDescription', 'id': 'AssetDescription'},
                    {'name': 'Order', 'id': 'Order'},
                    {'name': 'OrderDate', 'id': 'OrderDate', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY'}},
                    {'name': 'WorkDescription', 'id': 'WorkDescription'},
                                        {'name': 'ActualStartDateTime', 'id': 'ActualStartDateTime', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY HH:mm'}},
                    {'name': 'ActualEndDateTime', 'id': 'ActualEndDateTime', 'type': 'datetime', 'format': {'specifier': 'MM/DD/YYYY HH:mm'}},
                    {'name': 'Duration', 'id': 'Duration', 'type': 'numeric', 'format': {'specifier': '.2f hrs'}},
                    {'name': 'WorkStatus', 'id': 'WorkStatus'},
                    {'name': 'DaysSinceLastChangeOut', 'id': 'DaysSinceLastChangeOut', 'type': 'numeric', 'format': {'specifier': 'd days'}}
                ],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'color': 'white', 'backgroundColor': 'rgba(0,0,0,0)'},
                style_header={'backgroundColor': 'rgba(255,255,255,0.1)', 'fontWeight': 'bold', 'color': 'white'},
            ),

            html.H4("Location Metrics"),
            dash_table.DataTable(
                data=metrics['location_metrics'].to_dict('records'),
                columns=[
                    {'name': 'ParentLocation', 'id': 'ParentLocation'},
                    {'name': 'open_wo', 'id': 'open_wo', 'type': 'numeric'},
                    {'name': 'avg_aging', 'id': 'avg_aging', 'type': 'numeric', 'format': {'specifier': '.2f days'}},
                    {'name': 'mttr_hrs', 'id': 'mttr_hrs', 'type': 'numeric', 'format': {'specifier': '.2f hrs'}},
                    {'name': 'avg_pm_backlog_aging', 'id': 'avg_pm_backlog_aging', 'type': 'numeric', 'format': {'specifier': '.2f days'}}
                ],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'color': 'white', 'backgroundColor': 'rgba(0,0,0,0)'},
                style_header={'backgroundColor': 'rgba(255,255,255,0.1)', 'fontWeight': 'bold', 'color': 'white'},
            ),

            html.H4("Project in Focus"),
            dash_table.DataTable(
                data=metrics['project_in_focus_result'].to_dict('records'),
                columns=[{'name': i, 'id': i} for i in metrics['project_in_focus_result'].columns],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'color': 'white', 'backgroundColor': 'rgba(0,0,0,0)'},
                style_header={'backgroundColor': 'rgba(255,255,255,0.1)', 'fontWeight': 'bold', 'color': 'white'},
            ),
        ])

    elif tab == 'gantt-chart-tab':
        gantt_df = filtered_df[
            filtered_df['ActualStartDateTime'].notna() &
            filtered_df['ActualEndDateTime'].notna() &
            filtered_df['WorkStatus'].isin(['Closed', 'Completed', 'Closed - Was Backlog', 'Completed - Was Backlog'])
        ].copy()

        if gantt_df.empty:
            return html.Div("No data available for Gantt Chart with the current filters.", style={'color': 'yellow'})

        gantt_df['Task'] = gantt_df['Order'] + ' - ' + gantt_df['WorkDescription'].str[:30]
        gantt_df['Resource'] = gantt_df['ParentLocation']
        gantt_df['Start'] = gantt_df['ActualStartDateTime']
        gantt_df['Finish'] = gantt_df['ActualEndDateTime']

        fig = px.timeline(
            gantt_df,
            x_start='Start',
            x_end='Finish',
            y='Task',
            color='Resource',
            title='Work Order Gantt Chart',
            hover_data=['WorkType', 'WorkStatus', 'WorkPriority'],
            color_discrete_sequence=px.colors.qualitative.Pastel1
        )
        fig.update_yaxes(autorange='reversed')
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='white',
            xaxis_title="Timeline",
            yaxis_title="Work Orders",
            showlegend=True
        )

        return html.Div([
            html.H3("📅 Gantt Chart"),
            dcc.Graph(figure=fig)
        ])

@app.callback(
    Output('download-csv', 'data'),
    Input('download-button', 'n_clicks'),
    State('filtered-data', 'data'),
    prevent_initial_call=True
)
def download_csv(n_clicks, filtered_data):
    if n_clicks > 0:
        df = pd.DataFrame(filtered_data)
        csv_string = df.to_csv(index=False)
        return dcc.send_data_frame(df.to_csv, "maintenance_dashboard_report.csv")

# CSS Styling
app.css.append_css({
    'external_url': 'https://codepen.io/chriddyp/pen/bWLwgP.css'
})

# Custom CSS for metric cards
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>GPMS Maintenance Dashboard</title>
        {%favicon%}
        {%css%}
        <style>
            .metric-container {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 20px;
                margin: 10px;
                text-align: center;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
            .metric-label {
                font-size: 16px;
                font-weight: bold;
                color: white;
                margin-bottom: 10px;
            }
            .metric-value {
                font-size: 24px;
                color: #FF6F61;
                margin: 0;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Run the app
if __name__ == '__main__':
    server.run(debug=True, host='0.0.0.0', port=8050)