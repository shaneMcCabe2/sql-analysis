- dashboard: sql_trends
  title: SQL Stack Overflow Trends (2020–2022)
  layout: newspaper
  preferred_viewer: dashboards-next
  description: "Tag volume trends, answer rates, rising/falling ecosystems, and advanced SQL feature usage across 299k SQL-family Stack Overflow questions."

  filters:
  - name: year
    title: Year
    type: field_filter
    default_value: "2020,2021,2022"
    allow_multiple_values: true
    required: false
    ui_config:
      type: checkboxes
      display: inline
    explore: fct_tag_yearly
    field: fct_tag_yearly.creation_year

  elements:

  # ── Row 1: headline KPIs ──────────────────────────────────────────────────

  - title: Total SQL Questions
    name: kpi_total_questions
    model: sql_analysis
    explore: fct_tag_yearly
    type: single_value
    fields: [fct_tag_yearly.total_questions]
    listen:
      year: fct_tag_yearly.creation_year
    value_format: "#,##0"
    row: 0
    col: 0
    width: 4
    height: 2

  - title: Overall % Answered
    name: kpi_pct_answered
    model: sql_analysis
    explore: fct_tag_yearly
    type: single_value
    fields: [fct_tag_yearly.pct_answered]
    listen:
      year: fct_tag_yearly.creation_year
    value_format: "0.0%"
    row: 0
    col: 4
    width: 4
    height: 2

  - title: Overall % Accepted
    name: kpi_pct_accepted
    model: sql_analysis
    explore: fct_tag_yearly
    type: single_value
    fields: [fct_tag_yearly.pct_accepted]
    listen:
      year: fct_tag_yearly.creation_year
    value_format: "0.0%"
    row: 0
    col: 8
    width: 4
    height: 2

  - title: Total Views
    name: kpi_total_views
    model: sql_analysis
    explore: fct_tag_yearly
    type: single_value
    fields: [fct_tag_yearly.total_views]
    listen:
      year: fct_tag_yearly.creation_year
    value_format: "#,##0,,\"M\""
    row: 0
    col: 12
    width: 4
    height: 2

  # ── Row 2: Tag volume trend (line) ────────────────────────────────────────

  - title: Question Volume by Top 10 Tags
    name: tag_volume_trend
    model: sql_analysis
    explore: fct_tag_yearly
    type: looker_line
    fields:
    - fct_tag_yearly.creation_year
    - fct_tag_yearly.tag
    - fct_tag_yearly.total_questions
    pivots: [fct_tag_yearly.tag]
    filters:
      fct_tag_yearly.tag: ''
    sorts: [fct_tag_yearly.total_questions desc 0]
    limit: 30
    column_limit: 10
    listen:
      year: fct_tag_yearly.creation_year
    x_axis_gridlines: false
    y_axis_gridlines: true
    show_view_names: false
    show_y_axis_labels: true
    show_x_axis_label: false
    x_axis_datetime_label: "%Y"
    point_style: circle
    interpolation: linear
    row: 2
    col: 0
    width: 16
    height: 7

  # ── Row 2: Answer rate by tag (top 15) ───────────────────────────────────

  - title: Best-Answered Tags (min 500 questions)
    name: best_answered_tags
    model: sql_analysis
    explore: fct_tag_yearly
    type: looker_bar
    fields:
    - fct_tag_yearly.tag
    - fct_tag_yearly.pct_answered
    - fct_tag_yearly.total_questions
    filters:
      fct_tag_yearly.total_questions: ">500"
    sorts: [fct_tag_yearly.pct_answered desc]
    limit: 15
    listen:
      year: fct_tag_yearly.creation_year
    show_view_names: false
    x_axis_gridlines: false
    y_axis_gridlines: true
    y_axis_min: ["0.5"]
    value_format: "0%"
    row: 2
    col: 16
    width: 8
    height: 7

  # ── Row 3: Rising vs falling tags (bar) ──────────────────────────────────

  - title: 2020 vs 2022 — Top Rising Tags
    name: rising_tags
    model: sql_analysis
    explore: fct_tag_yearly
    type: looker_bar
    fields:
    - fct_tag_yearly.tag
    - fct_tag_yearly.total_questions
    filters:
      fct_tag_yearly.creation_year: "2020,2022"
    pivots: [fct_tag_yearly.creation_year]
    sorts: [fct_tag_yearly.total_questions desc 0]
    limit: 10
    show_view_names: false
    bar_style: grouped
    note_state: expanded
    note_display: above
    note_text: "Databricks +69% · Snowflake +51% · TypeScript ORMs +43%"
    row: 9
    col: 0
    width: 12
    height: 7

  - title: 2020 vs 2022 — Top Falling Tags
    name: falling_tags
    model: sql_analysis
    explore: fct_tag_yearly
    type: looker_bar
    fields:
    - fct_tag_yearly.tag
    - fct_tag_yearly.total_questions
    filters:
      fct_tag_yearly.creation_year: "2020,2022"
    pivots: [fct_tag_yearly.creation_year]
    sorts: [fct_tag_yearly.total_questions asc 0]
    limit: 10
    show_view_names: false
    bar_style: grouped
    note_state: expanded
    note_display: above
    note_text: "string −79% · count −77% · where-clause −75%"
    row: 9
    col: 12
    width: 12
    height: 7

  # ── Row 4: Monthly question volume from dim_questions ─────────────────────

  - title: Monthly Question Volume (SQL Family)
    name: monthly_volume
    model: sql_analysis
    explore: dim_questions
    type: looker_area
    fields:
    - dim_questions.creation_month
    - dim_questions.count
    sorts: [dim_questions.creation_month asc]
    limit: 500
    show_view_names: false
    x_axis_gridlines: false
    y_axis_gridlines: true
    show_x_axis_label: false
    interpolation: linear
    fill_style: solid
    opacity: 0.3
    row: 16
    col: 0
    width: 24
    height: 6

  # ── Row 5: Answer timing distribution ────────────────────────────────────

  - title: Time to First Answer Distribution
    name: time_to_answer
    model: sql_analysis
    explore: dim_questions
    type: looker_bar
    fields:
    - dim_questions.time_to_answer_tier
    - dim_questions.count
    filters:
      dim_questions.is_answered: "Yes"
    sorts: [dim_questions.time_to_answer_tier asc]
    limit: 10
    show_view_names: false
    x_axis_gridlines: false
    note_state: expanded
    note_display: below
    note_text: "Answered questions only"
    row: 22
    col: 0
    width: 12
    height: 6

  - title: Questions by Author Reputation Tier
    name: reputation_tier
    model: sql_analysis
    explore: dim_questions
    type: looker_pie
    fields:
    - dim_questions.reputation_tier
    - dim_questions.count
    sorts: [dim_questions.count desc]
    limit: 10
    show_view_names: false
    value_labels: legend
    label_type: labPer
    row: 22
    col: 12
    width: 12
    height: 6
