# GPMS Maintenance Dashboard – Porting Guide (Calculations Spec)

This document extracts the business logic, KPIs, and data rules from the Streamlit dashboard so another team can re-implement it in a different stack (e.g., PHP). It focuses on calculations and data assumptions, not UI specifics.

Last updated: 2025-08-08

## What this covers
- Required input data and fields
- Data preprocessing and derived fields
- Filters and how they affect results
- KPI definitions (names, formulas, windows, statuses, groupings)
- Tables, charts, and trends with their logic
- Edge cases and consistency notes

---

## 1) Input data model (required fields)
The dashboard expects one flat table of work order history (Excel/DB). Column names used in the current app:

- Identifiers and descriptors
  - Order (work order id/code)
  - AssetName
  - AssetDescription
  - WorkDescription
  - ParentLocation (location/site/area)
  - SystemType (equipment/system grouping)
  - FailureType (reason for failure, optional)
  - RemedyType (e.g., Replaced, optional)
  - WorkType (categorical; see enum below)
  - WorkStatus (categorical; see enum below)
  - WorkPriority (P1, P2, P3 or mapped labels)

- Dates/times
  - OrderDate (datetime)
  - ReportedDate (datetime, optional)
  - RequiredByDate (date; may be null and computed from OrderDate)
  - ActualStartDateTime (datetime; may be null)
  - ActualEndDateTime (datetime; may be null)

- Durations
  - Duration (hours; derived if missing)

Enums used in logic (normalize casing/spaces):
- WorkStatus closed-like values: ["Closed", "Completed", "Closed - Was Backlog", "Completed - Was Backlog"].
- WorkStatus cancelled: ["Cancelled"].
- WorkType planned set: ["Planned Maint.", "Planned Corrective Maint.", "Planned Improvement", "Inspection", "Projects", "Predictive Maint"].
- WorkType corrective set: ["Breakdown", "Unplanned Corrective Maint."]
  - Note: Some parts of the source code also use "Unplanned Corrective Maintenance" (spelled out). Standardize to one string in your DB/application.
- WorkPriority: raw values may be P1/P2/P3; map to labels: P1 -> "P1 - High", P2 -> "P2 - Medium", P3 -> "P3 - Low".

Date formats used originally (for Excel parsing):
- RequiredByDate: MM/DD/YYYY
- OrderDate, ReportedDate, ActualStartDateTime, ActualEndDateTime: MM/DD/YYYY HH:MM

---

## 2) Preprocessing and derived fields
Implement these consistently before running any KPIs.

1) Priority mapping
- Map WorkPriority codes:
  - P1 -> "P1 - High"
  - P2 -> "P2 - Medium"
  - P3 -> "P3 - Low"

2) Duration (hours)
- If ActualStartDateTime and ActualEndDateTime are present:
  - Duration = (ActualEndDateTime - ActualStartDateTime) in hours.

3) RequiredByDate fallback
- When RequiredByDate is null but OrderDate exists:
  - RequiredByDate = the Saturday of the same week as OrderDate.
  - Implementation: OrderDate + (6 - weekday(OrderDate)) days, where Monday=0, …, Saturday=6.

4) RequiredByDateEnd (end-of-day)
- RequiredByDateEnd = RequiredByDate at 23:59:59 (same day).

5) OnTimeStatus
- For rows where WorkStatus is closed-like AND ActualEndDateTime and RequiredByDateEnd are present:
  - OnTimeStatus = "On Time" if ActualEndDateTime <= RequiredByDateEnd, else "Late".
- Else OnTimeStatus = "Unknown".

6) Temporal helpers
- WeekOfYear = ISO week of COALESCE(RequiredByDate, OrderDate, ActualEndDateTime).
- Month Name = month name of OrderDate (January…December).
- Year = calendar year of OrderDate.

7) “Now” reference used by KPIs
- current_date = today at 00:00:00 (date-only).
- current_date_end = current_date at 23:59:59.
- current_week_start = Monday of current week.
- current_week_end = Sunday of current week.

---

## 3) Filters (global)
All metrics operate on the filtered dataset:
- Month Name: multi-select; if omitted or "All" selected, do not filter by month.
- Year: multi-select; if omitted or "All" selected, do not filter by year.
- WeekOfYear: multi-select; if omitted or "All" selected, do not filter by week.
- WorkType: multi-select; if "All", do not filter by work type.
- WorkStatus: multi-select; if "All", do not filter by status.
- WorkPriority: multi-select; if "All", do not filter by priority.
- ParentLocation: multi-select; if "All", do not filter by location.

Note: Some weekly KPIs use the current calendar week window explicitly (see KPI 2 below).

---

## 4) KPI definitions (names, windows, formulas)
Notation (language-agnostic):
- ClosedStatuses = {Closed, Completed, Closed - Was Backlog, Completed - Was Backlog}
- OpenLike = NOT in (ClosedStatuses ∪ {Cancelled})
- PlannedTypes = {Planned Maint., Planned Corrective Maint., Planned Improvement, Inspection, Projects, Predictive Maint}
- CorrectiveTypes = {Breakdown, Unplanned Corrective Maint.}
- Between(a, b, x) means a <= x <= b

All counts are on the currently filtered dataset unless otherwise stated.

1) KPI: Current Open Work Orders
- Definition: Count of work orders with OpenLike status.
- Formula: COUNTIF(WorkStatus ∉ ClosedStatuses ∪ {Cancelled}).
- Window: current filters only.

2) KPI: Completed Work Orders for the Current Week
- Definition: Count of work orders completed in the current calendar week.
- Formula: COUNTIF(WorkStatus ∈ ClosedStatuses AND ActualEndDateTime BETWEEN current_week_start AND current_week_end).

3) KPI: Work Orders In Progress
- Definition: Count of work orders with WorkStatus = "In Progress".

4) KPI: Total Work Orders (Filtered)
- Definition: Total row count of filtered dataset.

5) KPI: Completed Work Orders (Filtered)
- Definition: Count of rows with WorkStatus ∈ ClosedStatuses.

6) KPI: Emergency Maintenance YTD (Filtered)
- Definition: Count of Breakdown-type work orders completed Year-To-Date.
- Formula: COUNTIF(WorkType = Breakdown AND WorkStatus in (ClosedStatuses ∪ {In Progress, Open, Waiting for Parts, Backlog}) AND ActualEndDateTime BETWEEN Jan 1 current year AND current_date).
  - Note: Includes some non-closed statuses as authored; revise if policy is “completed only.”

7) KPI: Backlog Count YTD
- Definition: Count of OpenLike work orders overdue in the current calendar year.
- Formula: COUNTIF(OpenLike AND RequiredByDateEnd < current_date_end AND RequiredByDateEnd >= Jan 1 current year).

8) KPI: Backlog Count Total
- Definition: Count of OpenLike work orders overdue (all time).
- Formula: COUNTIF(OpenLike AND RequiredByDateEnd < current_date_end).

9) KPI: Projects In Progress
- Definition: Count of work orders where WorkType = "Projects" AND WorkStatus = "In Progress".

10) KPI: Total Projects YTD
- Definition: Count of work orders where WorkType = "Projects" (year-to-date).
- Current implementation counts all Projects in filtered data (no explicit date window). If you need YTD strictly, add an ActualEndDateTime or OrderDate YTD filter.

11) KPI: Planned Maintenance Percentage (PMP)
- Definition: Share of maintenance hours spent on planned activities.
- Numerator: SUM(Duration) for PlannedTypes.
- Denominator: SUM(Duration) for PlannedTypes ∪ CorrectiveTypes.
- Filter rows to: ActualStartDateTime and ActualEndDateTime not null, WorkStatus ∈ ClosedStatuses, Duration not null.
- Formula: 100 * PlannedHours / (PlannedHours + CorrectiveHours). Target ≥ 85%.

12) KPI: Corrective Maintenance Percentage
- Definition: Share of maintenance hours spent on corrective (Breakdown/Unplanned) activities.
- Numerator: SUM(Duration) for CorrectiveTypes.
- Denominator: SUM(Duration) for PlannedTypes ∪ CorrectiveTypes.
- Same row filters as KPI 11.
- Formula: 100 * CorrectiveHours / (PlannedHours + CorrectiveHours).

13) KPI: Work Order Completion Rate (%)
- Definition: Percentage of completed/closed work orders out of total.
- Formula: 100 * COUNTIF(WorkStatus ∈ ClosedStatuses) / COUNT_ALL.

14) KPI: Work Orders by Location
- Definition: Count of work orders grouped by ParentLocation.

15) KPI: Work Orders by Priority
- Definition: Count of work orders grouped by WorkPriority (after mapping P1/P2/P3 to labels).

16) KPI: Percentage of Work Orders by Work Type
- Definition: Share of work orders grouped by WorkType.
- Formula: 100 * COUNT(workorders per WorkType) / COUNT_ALL.

17) KPI: Planned vs Corrective Hours (Pie)
- Definition: Distribution of SUM(Duration) between PlannedTypes and CorrectiveTypes.
- Row filters: ActualStartDateTime and ActualEndDateTime present, WorkStatus ∈ ClosedStatuses, Duration not null.

18) KPI: Monthly Work Order Trends (last 6 months)
- Definition: By calendar month (last 6 months including current):
  - Total Work Orders: COUNTIF(OrderDate BETWEEN month_start AND month_end).
  - Completed Work Orders: COUNTIF(WorkStatus ∈ ClosedStatuses AND ActualEndDateTime BETWEEN month_start AND month_end).

19) KPI: Work Order On-Time Completion (%)
- Definition: Percentage of completed work orders delivered by RequiredByDateEnd.
- Formula on rows with RequiredByDate and ActualEndDateTime and WorkStatus ∈ ClosedStatuses:
  - 100 * COUNTIF(OnTimeStatus = "On Time") / COUNT_ALL.

20) KPI: PM Compliance by Location
- Definition: For each ParentLocation and PlannedTypes: 100 * OnTimeClosed / Total.
- OnTimeClosed = COUNTIF(OnTimeStatus = "On Time" AND WorkStatus ∈ ClosedStatuses).
- Evaluate for:
  - Previous Week (ISO week = current week - 1, with year crossover handled).
  - Current Month (RequiredByDate between first-of-month and today).
  - YTD (RequiredByDate between Jan 1 and today).

21) KPI: Top 10 Work Types by Count (Pareto)
- Definition: Top 10 WorkType by count, plus cumulative percentage.

22) KPI: Top 10 Failure Types by Count (Pareto)
- Definition: Top 10 FailureType (non-null) by count, plus cumulative percentage.

23) KPI: Top 10 System Types by Count (Pareto)
- Definition: Top 10 SystemType (non-null) by count, plus cumulative percentage.

Location Metrics table (used in Table view):
- For each ParentLocation:
  - open_wo: COUNTIF(OpenLike).
  - avg_aging (days): AVG(days between OrderDate and current_date).
  - mttr_hrs: average repair duration for CorrectiveTypes with WorkStatus ∈ ClosedStatuses and Duration not null.
    - Implemented as: SUM(Duration for corrective & closed) / COUNT(rows for corrective & closed with Duration).
  - avg_pm_backlog_aging (days): AVG(RequiredByDate → ActualEndDateTime days) for rows where OnTimeStatus = "Late".

---

## 5) Tables (data views)
All scoped by current filters unless noted.

- Open Work Orders
  - Rows where WorkStatus ∉ (ClosedStatuses ∪ {Cancelled}).
  - Columns: OrderDate, Order, AssetName, WorkDescription, ActualStartDateTime, ActualEndDateTime, Duration, WorkType, SystemType, WorkStatus, WorkPriority, ParentLocation.

- Completed/Closed Work Orders
  - Rows where WorkStatus ∈ ClosedStatuses AND ActualEndDateTime not null.
  - Columns: OrderDate, Order, AssetName, WorkDescription, RequiredByDate, ActualStartDateTime, ActualEndDateTime, Duration, WorkType, SystemType, WorkStatus, WorkPriority.

- Corrective Work Orders
  - Rows where WorkType ∈ (Planned Corrective Maint., Unplanned Corrective Maint., Breakdown, Planned Improvement).

- Cancelled Work Orders
  - Rows where WorkStatus = Cancelled.

- Emergency Work Orders
  - Rows where WorkType ∈ (Breakdown, Unplanned Corrective Maint.) AND WorkPriority = "P1 - High".

- Project Orders
  - Rows where WorkType = "Projects".

- WorkType / SystemType / WorkStatus distributions
  - Groupings with Count, Hours (where applicable), and Percentage of total.

- Buoy Bush Change-Out Reliability (specialized)
  - Filter: AssetName ∈ {ABB-ME-BY-02, -03, -04, -05}, SystemType = "Buoy Body", FailureType = "Worn", RemedyType = "Replaced", WorkDescription contains "UKP Bush".
  - Compute DaysSinceLastChangeOut per AssetName using ordered lag of ActualEndDateTime.
  - Summary per AssetName & AssetDescription:
    - ChangeOutCount = COUNT(orders)
    - TotalChangeOutHours = SUM(Duration)
    - LastChangeOutDate = MAX(ActualEndDateTime)
    - MTTR_Hrs = AVG(Duration) over valid change-outs
    - MTBF_Days = AVG(DaysSinceLastChangeOut) over valid intervals
    - NextEstimatedChangeOut = LastChangeOutDate + MTBF_Days

---

## 6) Gantt chart (scheduling view)
- Source rows: WorkStatus ∈ {Open, In Progress, Waiting for Parts, Backlog} AND RequiredByDate not null.
- For each row:
  - StartDate = RequiredByDate - 6 days
  - EndDate = RequiredByDate
  - Label/Group by: Order (and optionally ParentLocation as color/resource), with hover fields WorkDescription, WorkPriority, SystemType.

---

## 7) Implementation notes for a PHP/SQL stack
- Use DB date functions to reproduce:
  - Duration (hours) = TIMESTAMPDIFF(HOUR, ActualStartDateTime, ActualEndDateTime).
  - RequiredByDate fallback to Saturday: DATE_ADD(OrderDate, INTERVAL (6 - WEEKDAY(OrderDate)) DAY) in MySQL (WEEKDAY: Monday=0).
  - RequiredByDateEnd = TIMESTAMP(CONCAT(RequiredByDate, ' 23:59:59')).
  - ISO Week: use built-in ISO week functions or a reliable library; store WeekOfYear at ETL time if needed.
  - On-time check: ActualEndDateTime <= RequiredByDateEnd.
- Consistency: choose one canonical string for each WorkType and WorkStatus; fix any legacy variants during import or via mapping tables.
- Filtering order: apply all UI filters first; then compute summaries.
- Week windows: define week as Monday–Sunday to match ISO logic above.

---

## 8) Edge cases and validations
- Missing dates: If OrderDate is null, RequiredByDate fallback cannot be computed; those rows cannot contribute to on-time metrics.
- Duration negatives/zeros: guard against clock issues; ignore negative durations in averages.
- Division by zero: when computing percentages, return 0 when denominator is 0.
- Time zones: ensure consistent timezone handling from source to DB.
- Partial months/weeks: trends use calendar boundaries; when fewer months exist, include months with zero values to keep charts aligned.

---

## 9) Minimal acceptance checks
After port:
- Pick a known slice (e.g., one month + one location) and verify:
  - KPI 11 (PMP) + KPI 12 (Corrective %) sum to ~100% (when only planned/corrective hours exist).
  - KPI 13 matches closed/total for the slice.
  - KPI 19 equals OnTimeClosed/Completed for the slice.
  - Backlog counts change as of “today” when RequiredByDateEnd crosses current_date.

---

## 10) Source references
- Streamlit: `maintenance_dashboard.py` (primary logic)
- KPI manual generator: `kpi_manual.py` (descriptions)
- Alternative UI (Dash): `dash_dashboard.py` (same formulas, UI differs)

Notes
- The working file name in code is "Asset Work History.xlsx"; your repository also contains a similarly named file (e.g., "Asset Work History-<machine>.xlsx"). Align the ingestion path/name in your environment.
- Where DuckDB uses DATEDIFF/ISO-week, translate to your SQL dialect or compute in PHP.

---

## 11) Glossary
- PMP: Planned Maintenance Percentage.
- MTTR: Mean Time To Repair.
- MTBF: Mean Time Between Failures (here, proxied by days between specific change-outs).
- YTD: Year-to-date (Jan 1 to today).
- Closed-like statuses: statuses indicating completion/closure.

---

If anything is unclear or you need sample SQL for your database, reach out and we can tailor snippets for MySQL/PostgreSQL.
