-- Top 20 tags by total SQL-family question volume (2020-2022).
-- Pivots the per-year counts so you can see the trajectory at a glance.
-- Source: dbt_dev_marts.fct_tag_yearly

with yearly as (
    select
        tag,
        creation_year,
        num_questions,
        total_views
    from `sql-analysis-500017`.`dbt_dev_marts`.`fct_tag_yearly`
    where creation_year between 2020 and 2022
),

totals as (
    select
        tag,
        sum(num_questions)                                      as total_questions,
        sum(total_views)                                        as total_views,
        sum(if(creation_year = 2020, num_questions, 0))         as q_2020,
        sum(if(creation_year = 2021, num_questions, 0))         as q_2021,
        sum(if(creation_year = 2022, num_questions, 0))         as q_2022
    from yearly
    group by tag
)

select
    rank() over (order by total_questions desc)                 as rank,
    tag,
    total_questions,
    total_views,
    q_2020,
    q_2021,
    q_2022,
    -- simple 2020→2022 delta to surface directional movement
    q_2022 - q_2020                                            as delta_2020_2022
from totals
order by total_questions desc
limit 20
;
