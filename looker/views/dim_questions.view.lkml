view: dim_questions {
  sql_table_name: `sql-analysis-500017`.`dbt_dev_marts`.`dim_questions` ;;

  # ── Primary key ───────────────────────────────────────────────────────────

  dimension: question_id {
    primary_key: yes
    type: number
    sql: ${TABLE}.question_id ;;
  }

  # ── Question dimensions ───────────────────────────────────────────────────

  dimension: title {
    type: string
    sql: ${TABLE}.title ;;
    link: {
      label: "View on Stack Overflow"
      url: "https://stackoverflow.com/questions/{{ question_id._value }}"
    }
  }

  dimension: creation_year {
    type: number
    sql: ${TABLE}.creation_year ;;
  }

  dimension_group: creation {
    type: time
    timeframes: [raw, date, month, quarter, year]
    datatype: timestamp
    sql: ${TABLE}.creation_date ;;
  }

  dimension: score {
    type: number
    sql: ${TABLE}.score ;;
  }

  dimension: view_count {
    type: number
    sql: ${TABLE}.view_count ;;
  }

  dimension: answer_count {
    type: number
    sql: ${TABLE}.answer_count ;;
  }

  dimension: comment_count {
    type: number
    sql: ${TABLE}.comment_count ;;
  }

  dimension: is_answered {
    type: yesno
    sql: ${TABLE}.is_answered ;;
  }

  dimension: has_accepted_answer {
    type: yesno
    sql: ${TABLE}.has_accepted_answer ;;
  }

  dimension: hours_to_first_answer {
    type: number
    sql: ${TABLE}.hours_to_first_answer ;;
    description: "Hours between question creation and first answer (null if unanswered)."
  }

  dimension: time_to_answer_tier {
    type: tier
    sql: ${TABLE}.hours_to_first_answer ;;
    tiers: [1, 6, 24, 72, 168]
    style: integer
    description: "Buckets: <1h, 1-6h, 6-24h, 1-3 days, 3-7 days, >7 days."
  }

  # ── Author dimensions ─────────────────────────────────────────────────────

  dimension: owner_user_id {
    type: number
    sql: ${TABLE}.owner_user_id ;;
    hidden: yes
  }

  dimension: owner_display_name {
    type: string
    sql: ${TABLE}.owner_display_name ;;
  }

  dimension: owner_reputation {
    type: number
    sql: ${TABLE}.owner_reputation ;;
  }

  dimension: reputation_tier {
    type: tier
    sql: ${TABLE}.owner_reputation ;;
    tiers: [100, 1000, 5000, 25000]
    style: integer
    description: "Reputation buckets: <100, 100-1k, 1k-5k, 5k-25k, 25k+."
  }

  # ── Measures ──────────────────────────────────────────────────────────────

  measure: count {
    type: count
    label: "Number of Questions"
    drill_fields: [question_id, title, creation_date, score, view_count]
  }

  measure: pct_answered {
    type: average
    sql: case when ${is_answered} then 1.0 else 0.0 end ;;
    value_format_name: percent_1
    label: "% Answered"
  }

  measure: pct_accepted {
    type: average
    sql: case when ${has_accepted_answer} then 1.0 else 0.0 end ;;
    value_format_name: percent_1
    label: "% Accepted"
  }

  measure: avg_score {
    type: average
    sql: ${score} ;;
    value_format_name: decimal_2
  }

  measure: total_views {
    type: sum
    sql: ${view_count} ;;
    value_format_name: decimal_0
  }

  measure: median_hours_to_answer {
    type: percentile
    percentile: 50
    sql: ${hours_to_first_answer} ;;
    value_format_name: decimal_1
    description: "Median hours from question creation to first answer (answered questions only)."
  }

  measure: avg_owner_reputation {
    type: average
    sql: ${owner_reputation} ;;
    value_format_name: decimal_0
  }
}
