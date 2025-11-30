import pdfkit
import pandas as pd

# Create DataFrame from the updated KPI table
kpi_data = [
    {
        "KPI Number": f"KPI {i}",
        "KPI Name": row[0],
        "Definition": row[1],
        "Formula": row[2],
        "Insight (Why?)": row[3]
    }
    for i, row in enumerate([
        ("Current Open Work Orders", "The total number of maintenance tasks that are not yet completed or closed.", "Total number of work orders with status not marked as completed or closed.", "Shows the current workload, helping managers allocate resources and identify potential delays."),
        ("Completed Work Orders for Week", "The number of maintenance tasks finished during the current week.", "Total number of work orders completed in the week.", "Measures weekly productivity, indicating how efficiently the team is resolving tasks."),
        ("Work Orders In Progress", "The number of maintenance tasks currently being worked on.", "Total number of work orders with an 'In Progress' status.", "Reflects active maintenance efforts, aiding in resource planning and workload management."),
        ("Total Work Orders (Filtered)", "The total number of maintenance tasks within the selected filters (e.g., time period or location).", "Total number of work orders in the filtered dataset.", "Provides context for the scope of maintenance activities, helping assess overall activity levels."),
        ("Completed Work Orders (Filtered)", "The number of maintenance tasks completed within the selected filters.", "Total number of work orders marked as completed in the filtered dataset.", "Indicates completion success within specific criteria, highlighting team performance."),
        ("Emergency Maintenance YTD", "The number of unplanned breakdown repairs completed since the start of the year.", "Total number of breakdown work orders completed year-to-date.", "High emergency repairs suggest equipment reliability issues, prompting preventive actions."),
        ("Backlog Count YTD", "The number of maintenance tasks overdue since the start of the current year.", "Total number of open work orders past their due date in the current year.", "Tracks delays, helping prioritize overdue tasks and improve scheduling."),
        ("Backlog Count Total", "The total number of maintenance tasks overdue across all years.", "Total number of open work orders past their due date.", "Signals long-term inefficiencies, guiding process improvements to reduce backlog."),
        ("Projects In Progress", "The number of ongoing major maintenance or improvement projects.", "Total number of project-type work orders with an 'In Progress' status.", "Tracks active projects, supporting resource allocation and project timeline management."),
        ("Total Projects YTD", "The total number of major maintenance or improvement projects completed since the start of the year.", "Total number of project-type work orders completed year-to-date.", "Measures project activity, reflecting progress on strategic initiatives."),
        ("Planned Maintenance Percentage (PMP)", "The percentage of maintenance hours spent on planned, proactive tasks (e.g., inspections, scheduled repairs).", "(Total hours spent on planned maintenance) ÷ (Total maintenance hours) × 100", "A high PMP (≥85%) indicates proactive maintenance, reducing downtime and costs."),
        ("Corrective Maintenance Percentage", "The percentage of maintenance hours spent on unplanned or breakdown repairs.", "(Total hours spent on corrective maintenance) ÷ (Total maintenance hours) × 100", "A high percentage suggests reactive maintenance, increasing costs and downtime."),
        ("Work Order Completion Rate", "The percentage of maintenance tasks completed out of all tasks.", "(Number of completed work orders) ÷ (Total number of work orders) × 100", "A high rate (≥90%) reflects efficient operations and effective task management."),
        ("Work Orders by Location", "The distribution of maintenance tasks across different facility locations.", "Number of work orders per location.", "Identifies high-maintenance areas, guiding resource allocation and facility inspections."),
        ("Work Orders by Priority", "The distribution of maintenance tasks by urgency level (e.g., high, medium, low).", "Number of work orders per priority level.", "Highlights critical tasks, ensuring high-priority issues are addressed promptly."),
        ("Work Orders by Work Type", "The percentage breakdown of maintenance tasks by type (e.g., planned, corrective, projects).", "(Number of work orders per work type) ÷ (Total number of work orders) × 100", "Shows the mix of maintenance activities, helping balance proactive vs. reactive work."),
        ("PMP vs. Corrective Maintenance", "A comparison of hours spent on planned vs. corrective maintenance tasks.", "Planned hours and corrective hours displayed as proportions of total hours.", "Visualizes maintenance strategy; high corrective hours indicate reactive issues."),
        ("Monthly Work Order Trends", "The number of total and completed work orders over the past six months.", "Total and completed work orders per month.", "Tracks trends, revealing seasonal patterns or process improvements."),
        ("Work Order On-Time Completion", "The percentage of maintenance tasks completed by their due date.", "(Number of on-time work orders) ÷ (Total completed work orders with due dates) × 100", "High on-time rates (≥90%) indicate reliable scheduling and execution."),
        ("PM Compliance by Location", "The percentage of planned maintenance tasks completed on time at each location, reported for previous week, current month, and year-to-date.", "(Number of on-time planned work orders per location) ÷ (Total planned work orders per location) × 100", "Identifies compliance gaps by location, guiding targeted improvements and resource allocation."),
        ("Top 10 Work Types by Count", "The ten most common types of maintenance tasks and their cumulative share.", "Number of work orders per work type, with cumulative percentage.", "Highlights dominant activities, aiding resource planning and optimization."),
        ("Top 10 Failure Types by Count", "The ten most common reasons for equipment failures and their cumulative share.", "Number of work orders per failure type, with cumulative percentage.", "Identifies frequent failure modes, informing preventive strategies."),
        ("Top 10 System Types by Count", "The ten most common equipment or system types requiring maintenance and their cumulative share.", "Number of work orders per system type, with cumulative percentage.", "Pinpoints high-maintenance systems, guiding reliability improvements."),
        ("Open Work Orders Table", "A detailed list of all open maintenance tasks, including order date, asset, description, and status.", "List of work orders with status not marked as completed, closed, or cancelled.", "Provides granular visibility into pending tasks, aiding prioritization and resource assignment."),
        ("Completed/Closed Work Orders Table", "A detailed list of all completed or closed maintenance tasks, including order date, asset, and duration.", "List of work orders marked as completed or closed.", "Tracks completed work, helping evaluate team performance and task turnaround times."),
        ("Corrective Work Orders Table", "A detailed list of corrective maintenance tasks, including planned and unplanned repairs and breakdowns.", "List of work orders with types including planned corrective, unplanned corrective, breakdown, or planned improvement.", "Highlights corrective maintenance efforts, identifying areas for preventive action."),
        ("Emergency Work Orders Table", "A detailed list of high-priority, unplanned maintenance tasks (breakdowns or unplanned repairs).", "List of work orders with types breakdown or unplanned corrective maintenance and priority P1 - High.", "Ensures critical issues are tracked and resolved promptly, minimizing downtime."),
        ("Project Orders Table", "A detailed list of major maintenance or improvement project tasks.", "List of work orders with type Projects.", "Monitors project progress, supporting strategic initiative tracking and resource planning."),
        ("MTTR by Location", "The average time taken to repair equipment at each location.", "(Total repair time for completed work orders per location) ÷ (Number of repairs per location)", "Identifies locations with longer repair times, guiding process or training improvements."),
        ("Work Order Distribution by Work Type Table", "A detailed breakdown of maintenance tasks by type, including count, total hours, and percentage.", "Count, total hours, and (count per work type) ÷ (total work orders) × 100 per work type.", "Provides a comprehensive view of maintenance activities, aiding workload and strategy planning."),
        ("Work Orders by System Type Table", "A detailed breakdown of maintenance tasks by equipment or system type, including count and percentage.", "Count and (count per system type) ÷ (total work orders) × 100 per system type.", "Identifies high-maintenance equipment, informing reliability and replacement decisions."),
        ("Work Orders by Work Status Table", "A detailed breakdown of maintenance tasks by status (e.g., open, in progress, completed), including count and percentage.", "Count and (count per status) ÷ (total work orders) × 100 per status.", "Tracks task progress, helping managers monitor workflow and identify bottlenecks."),
        ("High-Priority Work Orders Table", "A detailed list of maintenance tasks with high priority (P1).", "List of work orders with priority P1 - High.", "Ensures urgent tasks are visible, supporting timely resolution of critical issues."),
        ("Buoy Bush Change-Out Reliability", "A detailed list and summary metrics (e.g., change-out count, MTTR, MTBF) for buoy bush replacements on specific assets.", "List of change-out records; MTTR = (Total change-out time) ÷ (Number of change-outs); MTBF = (Total days between change-outs) ÷ (Number of intervals).", "Tracks reliability of buoy bush components, predicting maintenance needs and optimizing schedules.")
    ], start=1)
]

kpi_df = pd.DataFrame(kpi_data)

# Convert DataFrame to HTML with escaped curly braces in CSS
html_content = f"""
<html>
<head>
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; }}
h1 {{ text-align: center; color: #333; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
th {{ background-color: #4CAF50; color: white; }}
tr:nth-child(even) {{ background-color: #f2f2f2; }}
tr:hover {{ background-color: #ddd; }}
</style>
</head>
<body>
<h1>GPMS Maintenance Dashboard KPI Manual</h1>
{kpi_df.to_html(index=False, escape=False)}
</body>
</html>
"""

# Save HTML to a temporary file
with open("kpi_manual.html", "w", encoding="utf-8") as f:
    f.write(html_content)

# Convert HTML to PDF
try:
    pdfkit.from_file("kpi_manual.html", "kpi_manual.pdf")
    print("PDF generated: kpi_manual.pdf")
except Exception as e:
    print(f"Error generating PDF: {e}")