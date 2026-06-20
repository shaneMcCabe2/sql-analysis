-- Mart: one enriched row per SQL-family question.
-- Joins author reputation and derives answer-timing / answered flags so the
-- analysis layer can stay simple. Materialized as a partitioned table.
{{
  config(
    materialized = 'table',
    partition_by = {'field': 'creation_date', 'data_type': 'timestamp', 'granularity': 'month'},
    cluster_by = ['owner_user_id']
  )
}}

with questions as (
    select * from {{ ref('stg_questions') }}
),

users as (
    select user_id, display_name, reputation
    from {{ ref('stg_users') }}
),

first_answer as (
    select question_id, min(creation_date) as first_answer_at
    from {{ ref('stg_answers') }}
    group by question_id
)

select
    q.question_id,
    q.title,
    q.owner_user_id,
    u.display_name                        as owner_display_name,
    u.reputation                          as owner_reputation,
    q.creation_date,
    extract(year from q.creation_date)    as creation_year,
    q.score,
    q.view_count,
    q.answer_count,
    q.comment_count,
    q.favorite_count,
    (q.answer_count > 0)                  as is_answered,
    q.has_accepted_answer,
    fa.first_answer_at,
    timestamp_diff(fa.first_answer_at, q.creation_date, hour)
                                          as hours_to_first_answer,
    q.tags
from questions as q
left join users as u
    on q.owner_user_id = u.user_id
left join first_answer as fa
    on q.question_id = fa.question_id
