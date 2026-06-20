-- Staging: clean, typed view over raw.users (authors of the SQL-family posts).
-- `age` is a mostly-null STRING in the source, so it is parsed defensively.
with source as (
    select * from {{ source('raw', 'users') }}
)

select
    id                       as user_id,
    display_name,
    reputation,
    safe_cast(age as int64)  as age,
    location,
    up_votes,
    down_votes,
    views                    as profile_views,
    creation_date            as account_created_at,
    last_access_date,
    website_url
from source
