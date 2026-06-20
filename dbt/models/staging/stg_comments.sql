-- Staging: clean, typed view over raw.comments.
-- post_id points at either a question or an answer (Stack Overflow posts share
-- one id space), so it is not constrained to a single parent table here.
with source as (
    select * from {{ source('raw', 'comments') }}
)

select
    id            as comment_id,
    post_id,
    user_id,
    score,
    creation_date,
    text          as comment_text
from source
