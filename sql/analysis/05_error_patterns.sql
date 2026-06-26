-- Top SQL error patterns by question volume and upvote signal (2020-2022).
-- Scans raw.questions (title + body) against 14 common error signatures.
-- Each question can match multiple patterns; counts are per-pattern, not unique.
-- Body is stored as HTML; patterns target strings that survive HTML markup.

with error_signatures as (
    select pattern, label from unnest([
        struct(r'(?i)syntax\s+error'                                            as pattern, 'Syntax error'               as label),
        struct(r'(?i)\bora-\d{4,5}\b'                                          as pattern, 'Oracle ORA- error code'     as label),
        struct(r'(?i)(null value|unexpected null|\bnull\b.*error|null.*not allowed)' as pattern, 'NULL / unexpected null'     as label),
        struct(r'(?i)deadlock'                                                  as pattern, 'Deadlock'                   as label),
        struct(r'(?i)(not in group by|not contained in.*group|invalid use of group function|aggregate)' as pattern, 'GROUP BY / aggregate error' as label),
        struct(r'(?i)(access denied|permission denied|insufficient privilege)'  as pattern, 'Permission / access denied' as label),
        struct(r'(?i)(timeout|timed.?out|lock wait)'                            as pattern, 'Timeout / lock wait'        as label),
        struct(r'(?i)(duplicate (entry|key|value)|unique constraint|violates unique)' as pattern, 'Duplicate / unique violation' as label),
        struct(r'(?i)(foreign key|constraint violation|violates foreign)'       as pattern, 'Foreign-key constraint'     as label),
        struct(r'(?i)(conversion failed|cannot convert|invalid conversion|invalid cast)' as pattern, 'Type conversion error'      as label),
        struct(r'(?i)ambiguous (column|field|identifier)'                       as pattern, 'Ambiguous column/field'     as label),
        struct(r'(?i)(does not exist|table not found|column not found|relation.*does not|object not found|unknown column)' as pattern, 'Object / column not found'  as label),
        struct(r'(?i)subquery returns more than (1|one) row'                    as pattern, 'Subquery multi-row error'   as label),
        struct(r'(?i)(divide by zero|division by zero)'                         as pattern, 'Divide by zero'             as label)
    ])
),

questions as (
    select
        id,
        score,
        view_count,
        answer_count,
        accepted_answer_id is not null                          as has_accepted_answer,
        lower(coalesce(title, '') || ' ' || coalesce(body, '')) as search_text
    from `sql-analysis-500017`.`raw`.`questions`
),

matched as (
    select
        sig.label,
        q.id,
        q.score,
        q.view_count,
        q.answer_count,
        q.has_accepted_answer
    from questions as q
    cross join error_signatures as sig
    where regexp_contains(q.search_text, sig.pattern)
)

select
    label                                                       as error_pattern,
    count(*)                                                    as num_questions,
    round(avg(score), 2)                                        as avg_score,
    sum(score)                                                  as total_upvotes,
    sum(view_count)                                             as total_views,
    round(safe_divide(countif(answer_count > 0), count(*)), 4) as pct_answered,
    round(safe_divide(countif(has_accepted_answer), count(*)), 4) as pct_accepted,
    round(avg(answer_count), 2)                                 as avg_answers_per_q
from matched
group by label
order by num_questions desc
limit 10
;
