-- Mart: per-question SQL complexity score.
-- Scans the raw question body (HTML) for SQL feature keywords and assigns a
-- weighted score + tier. Stored at question grain so downstream analysis
-- (practice-question tool, dialect × complexity cross-tabs) can filter freely.
--
-- Score weights:  Basic=1  ·  Intermediate=2  ·  Advanced=3  ·  Expert=5  ·  Master=7
-- Note: body is HTML — \bselect\b will also match <select> form elements,
-- a known noise source. Impact is small given the SQL-scoped question set.
{{ config(materialized = 'table') }}

with base as (
    select
        q.question_id,
        q.creation_year,
        q.score,
        q.view_count,
        q.is_answered,
        q.has_accepted_answer,
        lower(coalesce(raw.body, '')) as body_text
    from {{ ref('dim_questions') }}           as q
    inner join {{ source('raw', 'questions') }} as raw
        on q.question_id = raw.id
),

features as (
    select
        question_id,
        creation_year,
        score,
        view_count,
        is_answered,
        has_accepted_answer,
        -- Basic (1 pt each)
        cast(regexp_contains(body_text, r'(?i)\bselect\b')          as int64) as f_select,
        cast(regexp_contains(body_text, r'(?i)\bwhere\b')           as int64) as f_where,
        cast(regexp_contains(body_text, r'(?i)\border\s+by\b')      as int64) as f_order_by,
        -- Intermediate (2 pts each)
        cast(regexp_contains(body_text, r'(?i)\bgroup\s+by\b')                              as int64) as f_group_by,
        cast(regexp_contains(body_text, r'(?i)\bjoin\b')                                    as int64) as f_join,
        cast(regexp_contains(body_text, r'(?i)\b(count|sum|avg|min|max)\s*\(')             as int64) as f_aggregate,
        cast(regexp_contains(body_text, r'(?i)\bhaving\b')                                  as int64) as f_having,
        -- Advanced (3 pts each)
        cast(regexp_contains(body_text, r'(?i)\bcase\s+when\b')                             as int64) as f_case_when,
        cast(regexp_contains(body_text, r'(?i)\b(union|intersect|except)\b')                as int64) as f_set_ops,
        cast(array_length(regexp_extract_all(body_text, r'(?i)\bselect\b')) > 1 as int64)            as f_subqueries,
        -- Expert (5 pts each)
        cast(regexp_contains(body_text, r'(?i)\bwith\s+\w+\s+as\s*\(')                    as int64) as f_cte,
        cast(regexp_contains(body_text, r'(?i)\bover\s*\(')                                as int64) as f_window,
        -- Master (7 pts each)
        cast(regexp_contains(body_text, r'(?i)\brecursive\b')                              as int64) as f_recursive,
        cast(regexp_contains(body_text, r'(?i)\blateral\b')                                as int64) as f_lateral,
        cast(regexp_contains(body_text, r'(?i)\b(cross|outer)\s+apply\b')                 as int64) as f_apply,
        cast(regexp_contains(body_text, r'(?i)\bpivot\s*\(')                              as int64) as f_pivot
    from base
),

scored as (
    select
        *,
        (f_select * 1  + f_where * 1     + f_order_by * 1)
        + (f_group_by * 2 + f_join * 2   + f_aggregate * 2 + f_having * 2)
        + (f_case_when * 3 + f_set_ops * 3 + f_subqueries * 3)
        + (f_cte * 5 + f_window * 5)
        + (f_recursive * 7 + f_lateral * 7 + f_apply * 7 + f_pivot * 7)
        as complexity_score
    from features
)

select
    question_id,
    creation_year,
    score,
    view_count,
    is_answered,
    has_accepted_answer,
    complexity_score,
    case
        when complexity_score = 0   then '0 · No SQL detected'
        when complexity_score <= 3  then '1 · Trivial'
        when complexity_score <= 8  then '2 · Basic'
        when complexity_score <= 14 then '3 · Intermediate'
        when complexity_score <= 22 then '4 · Advanced'
        else                             '5 · Expert'
    end as complexity_tier,
    f_select, f_where, f_order_by,
    f_group_by, f_join, f_aggregate, f_having,
    f_case_when, f_set_ops, f_subqueries,
    f_cte, f_window,
    f_recursive, f_lateral, f_apply, f_pivot
from scored
