-- Staging: clean, typed view over raw.tags (full SO tag dictionary).
-- `count` is the site-wide number of questions carrying the tag (not limited
-- to our 2020-2022 SQL slice), so it is named explicitly.
with source as (
    select * from {{ source('raw', 'tags') }}
)

select
    id        as tag_id,
    tag_name,
    count     as sitewide_question_count
from source
