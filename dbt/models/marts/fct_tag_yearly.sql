-- Mart: one row per (tag, year) over the SQL-family question set.
-- Each question is exploded across all its tags, so co-occurring tags
-- (python, pandas, ...) appear too -- but always within questions that carry
-- at least one SQL tag. This is the backbone for trend / answer-rate analysis.
{{ config(materialized = 'table') }}

with questions as (
    select
        question_id,
        creation_year,
        score,
        view_count,
        answer_count,
        is_answered,
        has_accepted_answer,
        tags
    from {{ ref('dim_questions') }}
),

exploded as (
    select
        tag,
        q.creation_year,
        q.score,
        q.view_count,
        q.answer_count,
        q.is_answered,
        q.has_accepted_answer
    from questions as q, unnest(q.tags) as tag
    where tag is not null and tag != ''
)

select
    concat(tag, '|', cast(creation_year as string))     as tag_year_key,
    tag,
    creation_year,
    count(*)                                            as num_questions,
    countif(is_answered)                                as num_answered,
    round(safe_divide(countif(is_answered), count(*)), 4)        as pct_answered,
    countif(has_accepted_answer)                        as num_accepted,
    round(safe_divide(countif(has_accepted_answer), count(*)), 4) as pct_accepted,
    round(avg(score), 2)                                as avg_score,
    approx_quantiles(score, 100)[offset(50)]            as median_score,
    sum(view_count)                                     as total_views,
    round(avg(answer_count), 2)                         as avg_answers_per_question
from exploded
group by tag, creation_year
