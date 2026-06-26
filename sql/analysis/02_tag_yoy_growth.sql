-- Year-over-year question-volume growth rates for tags with ≥500 questions/year.
-- Uses LAG to compute sequential YoY pct change; NULL in 2020 (no prior year).
-- Source: dbt_dev_marts.fct_tag_yearly

with base as (
    select
        tag,
        creation_year,
        num_questions,
        pct_answered,
        avg_score
    from `sql-analysis-500017`.`dbt_dev_marts`.`fct_tag_yearly`
    where creation_year between 2020 and 2022
),

-- Keep only tags that clear the volume floor in every year they appear,
-- then derive YoY deltas with LAG partitioned by tag.
with_lag as (
    select
        tag,
        creation_year,
        num_questions,
        pct_answered,
        avg_score,
        lag(num_questions) over (
            partition by tag order by creation_year
        )                                                               as prev_year_questions
    from base
    where tag in (
        -- sub-select tags that have ≥500 questions in at least two years
        select tag
        from base
        where num_questions >= 500
        group by tag
        having count(*) >= 2
    )
)

select
    tag,
    creation_year,
    num_questions,
    prev_year_questions,
    round(
        safe_divide(num_questions - prev_year_questions, prev_year_questions),
        4
    )                                                                   as yoy_growth_rate,
    round(pct_answered, 4)                                              as pct_answered,
    round(avg_score, 2)                                                 as avg_score
from with_lag
order by tag, creation_year
;
