-- Data validation: cross-layer consistency checks (raw → staging → marts).
-- Run this standalone to verify the pipeline hasn't dropped, duplicated,
-- or mis-derived anything between layers.
-- All counts should match; derived booleans should agree with their raw source columns.

with raw_q as (
    select
        count(*)                                        as n,
        sum(score)                                      as score_sum,
        sum(view_count)                                 as view_sum,
        countif(accepted_answer_id is not null)         as accepted_count,
        countif(answer_count > 0)                       as answered_count
    from `sql-analysis-500017`.`raw`.`questions`
),

dim_q as (
    select
        count(*)                                        as n,
        count(distinct question_id)                     as n_unique,
        sum(score)                                      as score_sum,
        sum(view_count)                                 as view_sum,
        countif(has_accepted_answer)                    as accepted_count,
        countif(is_answered)                            as answered_count
    from `sql-analysis-500017`.`dbt_dev_marts`.`dim_questions`
),

raw_a as (
    select count(*) as n
    from `sql-analysis-500017`.`raw`.`answers`
),

stg_a as (
    select count(*) as n
    from `sql-analysis-500017`.`dbt_dev_staging`.`stg_answers`
),

-- Check that fct_tag_yearly aggregates match dim_questions for a spot-check tag + year
fct_sql_2020 as (
    select sum(num_questions) as n
    from `sql-analysis-500017`.`dbt_dev_marts`.`fct_tag_yearly`
    where tag = 'sql' and creation_year = 2020
),

dim_sql_2020 as (
    select count(*) as n
    from `sql-analysis-500017`.`dbt_dev_marts`.`dim_questions`
    where 'sql' in unnest(tags) and creation_year = 2020
)

select
    'raw → dim_questions row count'         as check_name,
    cast(rq.n as string)                    as expected,
    cast(dq.n as string)                    as actual,
    rq.n = dq.n                             as passed
from raw_q rq, dim_q dq

union all select
    'dim_questions: no duplicate question_ids',
    cast(dq.n as string),
    cast(dq.n_unique as string),
    dq.n = dq.n_unique
from dim_q dq

union all select
    'raw → dim_questions score sum',
    cast(rq.score_sum as string),
    cast(dq.score_sum as string),
    rq.score_sum = dq.score_sum
from raw_q rq, dim_q dq

union all select
    'raw → dim_questions view count sum',
    cast(rq.view_sum as string),
    cast(dq.view_sum as string),
    rq.view_sum = dq.view_sum
from raw_q rq, dim_q dq

union all select
    'has_accepted_answer matches raw accepted_answer_id IS NOT NULL',
    cast(rq.accepted_count as string),
    cast(dq.accepted_count as string),
    rq.accepted_count = dq.accepted_count
from raw_q rq, dim_q dq

union all select
    'is_answered matches raw answer_count > 0',
    cast(rq.answered_count as string),
    cast(dq.answered_count as string),
    rq.answered_count = dq.answered_count
from raw_q rq, dim_q dq

union all select
    'raw → stg_answers row count',
    cast(ra.n as string),
    cast(sa.n as string),
    ra.n = sa.n
from raw_a ra, stg_a sa

union all select
    'fct_tag_yearly sql/2020 count matches dim_questions',
    cast(f.n as string),
    cast(d.n as string),
    f.n = d.n
from fct_sql_2020 f, dim_sql_2020 d

order by passed asc, check_name
;
