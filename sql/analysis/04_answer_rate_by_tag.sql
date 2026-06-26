-- Answer and acceptance rates by tag, aggregated across 2020-2022.
-- Minimum 500 total questions to exclude long-tail tags with inflated rates.
-- Shows both ends: best- and worst-served SQL sub-communities.
-- Source: dbt_dev_marts.fct_tag_yearly

with aggregated as (
    select
        tag,
        sum(num_questions)                                              as total_questions,
        sum(num_answered)                                               as total_answered,
        sum(num_accepted)                                               as total_accepted,
        round(safe_divide(sum(num_answered), sum(num_questions)), 4)    as pct_answered,
        round(safe_divide(sum(num_accepted), sum(num_questions)), 4)    as pct_accepted,
        round(avg(avg_score), 2)                                        as avg_score,
        round(avg(avg_answers_per_question), 2)                         as avg_answers_per_q
    from `sql-analysis-500017`.`dbt_dev_marts`.`fct_tag_yearly`
    where creation_year between 2020 and 2022
    group by tag
    having sum(num_questions) >= 500
),

ranked as (
    select
        *,
        row_number() over (order by pct_answered desc)      as best_answered_rank,
        row_number() over (order by pct_answered asc)       as worst_answered_rank,
        row_number() over (order by pct_accepted desc)      as best_accepted_rank
    from aggregated
)

select
    case
        when best_answered_rank  <= 15 then 'highest answer rate'
        when worst_answered_rank <= 15 then 'lowest answer rate'
    end                                                             as cohort,
    tag,
    total_questions,
    pct_answered,
    pct_accepted,
    avg_score,
    avg_answers_per_q,
    best_answered_rank,
    worst_answered_rank
from ranked
where best_answered_rank <= 15 or worst_answered_rank <= 15
order by cohort, pct_answered desc
;
