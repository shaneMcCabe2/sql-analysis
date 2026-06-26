view: fct_tag_yearly {
  sql_table_name: `sql-analysis-500017`.`dbt_dev_marts`.`fct_tag_yearly` ;;

  # ── Dimensions ────────────────────────────────────────────────────────────

  dimension: tag_year_key {
    primary_key: yes
    hidden: yes
    type: string
    sql: ${TABLE}.tag_year_key ;;
  }

  dimension: tag {
    type: string
    sql: ${TABLE}.tag ;;
    description: "Stack Overflow tag name."
    link: {
      label: "View on Stack Overflow"
      url: "https://stackoverflow.com/questions/tagged/{{ value | url_encode }}"
    }
  }

  dimension: creation_year {
    type: number
    sql: ${TABLE}.creation_year ;;
    description: "Question creation year (2020, 2021, or 2022)."
  }

  dimension: pct_answered_tier {
    type: tier
    sql: ${TABLE}.pct_answered * 100 ;;
    tiers: [50, 70, 85, 95]
    style: integer
    description: "Answer-rate bucket (%)."
  }

  # ── Measures ──────────────────────────────────────────────────────────────

  measure: total_questions {
    type: sum
    sql: ${TABLE}.num_questions ;;
    description: "Total questions across selected tags and years."
    value_format_name: decimal_0
  }

  measure: total_answered {
    type: sum
    sql: ${TABLE}.num_answered ;;
    value_format_name: decimal_0
  }

  measure: total_accepted {
    type: sum
    sql: ${TABLE}.num_accepted ;;
    value_format_name: decimal_0
  }

  measure: pct_answered {
    type: average
    sql: ${TABLE}.pct_answered ;;
    description: "Average share of questions with ≥1 answer (weighted by row, not by question volume)."
    value_format_name: percent_1
  }

  measure: pct_accepted {
    type: average
    sql: ${TABLE}.pct_accepted ;;
    description: "Average share of questions with an accepted answer."
    value_format_name: percent_1
  }

  measure: avg_score {
    type: average
    sql: ${TABLE}.avg_score ;;
    description: "Average question score."
    value_format_name: decimal_2
  }

  measure: total_views {
    type: sum
    sql: ${TABLE}.total_views ;;
    description: "Total view count across selected tags and years."
    value_format_name: decimal_0
  }

  measure: avg_answers_per_question {
    type: average
    sql: ${TABLE}.avg_answers_per_question ;;
    value_format_name: decimal_2
  }

  measure: count_tag_year_rows {
    type: count
    hidden: yes
  }
}
