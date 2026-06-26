-- Fastest-rising and steepest-falling SQL-family tags: 2020 vs 2022.
-- Requires the tag to have ≥200 questions in BOTH years to exclude noise.
-- Returns the top 10 risers and top 10 fallers ranked by absolute growth rate.
-- Source: dbt_dev_marts.fct_tag_yearly

with y2020 as (
    select tag, num_questions as q_2020, pct_answered as pct_answered_2020
    from `sql-analysis-500017`.`dbt_dev_marts`.`fct_tag_yearly`
    where creation_year = 2020
),

y2022 as (
    select tag, num_questions as q_2022, pct_answered as pct_answered_2022
    from `sql-analysis-500017`.`dbt_dev_marts`.`fct_tag_yearly`
    where creation_year = 2022
),

joined as (
    select
        y20.tag,
        y20.q_2020,
        y22.q_2022,
        y22.q_2022 - y20.q_2020                                         as abs_change,
        round(safe_divide(y22.q_2022 - y20.q_2020, y20.q_2020), 4)     as growth_rate,
        round(y20.pct_answered_2020, 4)                                  as pct_answered_2020,
        round(y22.pct_answered_2022, 4)                                  as pct_answered_2022
    from y2020 as y20
    inner join y2022 as y22 using (tag)
    -- both years must clear the floor independently
    where y20.q_2020 >= 200 and y22.q_2022 >= 200
),

ranked as (
    select
        *,
        row_number() over (order by growth_rate desc)   as riser_rank,
        row_number() over (order by growth_rate asc)    as faller_rank
    from joined
)

select
    case when riser_rank <= 10 then 'rising' else 'falling' end     as direction,
    coalesce(
        nullif(cast(riser_rank as string), ''),
        cast(faller_rank as string)
    )                                                               as rank_within_group,
    tag,
    q_2020,
    q_2022,
    abs_change,
    growth_rate,
    pct_answered_2020,
    pct_answered_2022
from ranked
where riser_rank <= 10 or faller_rank <= 10
order by direction desc, growth_rate desc
;
