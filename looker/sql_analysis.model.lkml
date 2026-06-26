connection: "sql_analysis_bq"

# BigQuery connection must be configured in Looker admin pointing to:
# Project: sql-analysis-500017
# Dataset: dbt_dev_marts

include: "/looker/views/*.view.lkml"
include: "/looker/dashboards/*.dashboard.lookml"

explore: fct_tag_yearly {
  label: "Tag Yearly Trends"
  description: "Per-tag, per-year aggregates across SQL-family SO questions (2020-2022)."
}

explore: dim_questions {
  label: "Questions"
  description: "One enriched row per SQL-family Stack Overflow question (2020-2022)."
}
