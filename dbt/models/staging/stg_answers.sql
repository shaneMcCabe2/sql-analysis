-- Staging: clean, typed view over raw.answers.
-- Source answer rows carry empty question-only fields (title, tags, view_count);
-- we keep only the columns meaningful for an answer. question_id links back to
-- stg_questions (every answer here belongs to a question in our 2020-2022 set).
with source as (
    select * from {{ source('raw', 'answers') }}
)

select
    id                  as answer_id,
    parent_id           as question_id,
    owner_user_id,
    creation_date,
    last_activity_date,
    last_edit_date,
    score,
    comment_count
from source
