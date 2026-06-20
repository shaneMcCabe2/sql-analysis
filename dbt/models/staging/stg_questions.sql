-- Staging: clean, typed view over raw.questions.
-- Splits the pipe-delimited `tags` string into an array for easy filtering,
-- and keeps the columns most useful for analysis.
with source as (
    select * from {{ source('raw', 'questions') }}
)

select
    id                              as question_id,
    title,
    owner_user_id,
    creation_date,
    last_activity_date,
    score,
    view_count,
    answer_count,
    comment_count,
    favorite_count,
    accepted_answer_id,
    (accepted_answer_id is not null) as has_accepted_answer,
    tags                            as tags_raw,
    split(tags, '|')               as tags        -- array of individual tags
from source
