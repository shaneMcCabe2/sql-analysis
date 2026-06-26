-- Advanced SQL keyword frequency: questions vs. accepted answers (2020-2022).
-- A keyword appearing more often in accepted answers than in questions signals
-- it's a *solution tool*; the inverse means it's a *struggle topic*.
-- Source: raw.questions + raw.answers (body not surfaced in dbt staging layer).

with keywords as (
    select keyword, label from unnest([
        struct(r'(?i)\bwith\s+\w[\w\s,]*\brecursive\b'         as keyword, 'Recursive CTE'         as label),
        struct(r'(?i)\bwith\s+\w+\s+as\s*\('                   as keyword, 'CTE (WITH ... AS)'     as label),
        struct(r'(?i)\bover\s*\('                               as keyword, 'Window function (OVER)'as label),
        struct(r'(?i)\bpartition\s+by\b'                        as keyword, 'PARTITION BY'          as label),
        struct(r'(?i)\brow_number\s*\('                         as keyword, 'ROW_NUMBER()'          as label),
        struct(r'(?i)\b(rank|dense_rank)\s*\('                  as keyword, 'RANK / DENSE_RANK'     as label),
        struct(r'(?i)\blateral\b'                               as keyword, 'LATERAL'               as label),
        struct(r'(?i)\bmerge\s+(into\s+)?\w'                    as keyword, 'MERGE'                 as label),
        struct(r'(?i)\bpivot\s*\('                              as keyword, 'PIVOT'                 as label),
        struct(r'(?i)\bunnest\s*\('                             as keyword, 'UNNEST()'              as label),
        struct(r'(?i)\bcoalesce\s*\('                           as keyword, 'COALESCE()'            as label),
        struct(r'(?i)\bcase\s+when\b'                           as keyword, 'CASE WHEN'             as label),
        struct(r'(?i)\b(cross|outer)\s+apply\b'                 as keyword, 'CROSS/OUTER APPLY'     as label),
        struct(r'(?i)\bjson_'                                   as keyword, 'JSON functions'         as label),
        struct(r'(?i)\bgenerate_series\b|\bgenerate_array\b'    as keyword, 'Series generation'     as label)
    ])
),

-- Questions in scope (SQL-family filter carried from raw)
all_questions as (
    select id, lower(coalesce(body, '')) as body_text
    from `sql-analysis-500017`.`raw`.`questions`
),

-- Only accepted answers (answers whose id = parent question's accepted_answer_id)
accepted_answers as (
    select a.id, lower(coalesce(a.body, '')) as body_text
    from `sql-analysis-500017`.`raw`.`answers` as a
    inner join `sql-analysis-500017`.`raw`.`questions` as q
        on a.id = q.accepted_answer_id
),

q_counts as (
    select kw.label, count(*) as in_questions
    from all_questions as q
    cross join keywords as kw
    where regexp_contains(q.body_text, kw.keyword)
    group by kw.label
),

a_counts as (
    select kw.label, count(*) as in_accepted_answers
    from accepted_answers as a
    cross join keywords as kw
    where regexp_contains(a.body_text, kw.keyword)
    group by kw.label
)

select
    q.label                                                             as keyword,
    q.in_questions,
    coalesce(a.in_accepted_answers, 0)                                  as in_accepted_answers,
    -- >1 means the feature appears proportionally more in solutions than problems
    round(safe_divide(
        coalesce(a.in_accepted_answers, 0), q.in_questions
    ), 4)                                                               as answer_to_question_ratio
from q_counts as q
left join a_counts as a using (label)
order by in_accepted_answers desc
;
