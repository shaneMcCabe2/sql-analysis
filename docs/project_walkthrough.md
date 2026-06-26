# Project Walkthrough: SQL Stack Overflow Analysis

A stage-by-stage reference for interviews and code walkthroughs. Each section covers what was built, why the approach was chosen, the key technical decisions, and the most useful talking points.

---

## Overview

**Goal:** analyse SQL-tagged Stack Overflow questions (2020–2022) to surface ecosystem trends, common failure patterns, and how advanced SQL features appear in real-world questions and answers.

**Stack:** Python · Google BigQuery · dbt · Looker  
**Data:** `bigquery-public-data.stackoverflow` — ~91 GB public snapshot, frozen at 2022-09-25  
**Volume landed:** ~299k questions · 322k answers · 1.06M comments · 235k users

---

## Step 1 — Data ingestion (`sql/transfer/`, `ingest/`)

### What was built
SQL transfer queries that copy a filtered slice of the public Stack Overflow BigQuery dataset into a private `raw` dataset. A Python runner (`ingest/transfer.py`) executes them in order, handles retries, and logs progress.

### Why this approach
The public dataset already lives in BigQuery. A BQ→BQ `CREATE OR REPLACE TABLE … AS SELECT` is faster, cheaper, and more reproducible than scraping the web or downloading XML dumps. It also fits within BigQuery's free-tier query allowance (~91 GB on the first run).

### Key decisions
- **Scope filter:** `tags LIKE '%sql%'` captures the full SQL ecosystem (MySQL, PostgreSQL, SQL Server, SQLite, T-SQL, PL/SQL, Spark SQL) without manual enumeration. Side effect: also includes `nosql` and `apache-spark-sql` — acceptable given the portfolio framing; easy to tighten.
- **2020–2022 window:** The public dataset ends 2022-09-25. 2019 and earlier were excluded to keep the analysis current without diluting 2020–2022 trends with older traffic patterns.
- **Separate tables per entity:** `raw.questions`, `raw.answers`, `raw.comments`, `raw.users`, `raw.tags` — mirrors the source schema, keeps the staging layer's job simple.

### Talking points
> "I chose BQ-to-BQ transfer rather than web scraping because the data already existed in a queryable form and the cost was effectively zero within the free tier. The filter is one line of SQL — easy to audit or adjust."

> "The runner is idempotent: `CREATE OR REPLACE TABLE` means you can re-run it safely if a job fails partway through."

---

## Step 2 — dbt staging layer (`dbt/models/staging/`)

### What was built
Five dbt views that clean and type the raw tables:

| Model | Key transformations |
|---|---|
| `stg_questions` | Cast types; split pipe-delimited `tags` string → `ARRAY<STRING>`; derive `has_accepted_answer` bool |
| `stg_answers` | Cast types; align column names |
| `stg_users` | Cast types; rename `id` → `user_id` for clarity |
| `stg_comments` | Cast types |
| `stg_tags` | Cast types; expose `tag_name` and `count` |

Schema tests: `unique` and `not_null` on every primary key; `relationships` test on `stg_answers.question_id → stg_questions.question_id`.

### Why this approach
The staging layer is a data contract: anything downstream can rely on correct types, consistent names, and tested uniqueness guarantees. Separating "raw → typed" from "typed → analytical" means bugs are isolated to a single layer.

### Key decisions
- **`body` excluded from staging** — the raw body column is large HTML. It isn't needed for mart logic and would bloat the views unnecessarily. Analysis queries that need it hit `raw.questions` / `raw.answers` directly.
- **Tags split to ARRAY at staging** — raw stores tags as `|python|sql|pandas|`. Converting to ARRAY<STRING> once here means every downstream consumer gets a clean list, not a parsing problem.
- **Materialized as views** — staging models don't store data; they're logical transforms. The marts (tables) are where data is materialised.

### Talking points
> "I put the tag parsing in staging so it happens once and is tested. If the raw format ever changed, I'd fix it in one model, not in every query that consumes tags."

> "The relationship test on `stg_answers.question_id` would fail if the transfer queries got out of sync — it's an integration guard that caught a filter mismatch during development."

---

## Step 3 — dbt marts (`dbt/models/marts/`)

### What was built

**`dim_questions`** — one enriched row per SQL-family question.
- Joins `stg_questions` → `stg_users` (author reputation) → `stg_answers` (first-answer timing)
- Derives `is_answered`, `hours_to_first_answer`, `creation_year`
- Materialised as a partitioned table (by `creation_date` month, clustered by `owner_user_id`)

**`fct_tag_yearly`** — one row per `(tag, year)`.
- Explodes the tags array so each question contributes a row for every one of its tags
- Aggregates: question count, answer rate, acceptance rate, avg/median score, total views
- Materialised as a table — fast to query from Looker and ad-hoc analysis

### Why this approach
Dimensional modelling separates entity data (questions, their attributes) from pre-aggregated facts (tag trends). This means the dashboard never has to aggregate 299k rows at query time; it reads from the fact table directly.

### Key decisions
- **Partition `dim_questions` by month** — time-series queries on 299k rows without a partition scan would be fast anyway, but partitioning is the production habit to demonstrate.
- **UNNEST at the mart layer, not staging** — the tag explosion produces many rows (one per tag per question). Doing this in staging would make every downstream join more expensive; doing it once in `fct_tag_yearly` keeps staging grain clean.
- **`pct_answered` and `pct_accepted` stored as 0–1 floats** — avoids repeated `safe_divide` in every consumer; Looker can format as percentages.

### Talking points
> "dim_questions answers 'what happened to this question?' — author reputation at the time, how long until someone answered, whether it was accepted. fct_tag_yearly answers 'how is this tag trending?' — those are two very different query patterns so they live in two tables."

> "I used `approx_quantiles` for the median score in fct_tag_yearly rather than an exact median. At this scale the approximation is fine, and it's dramatically cheaper in BigQuery."

---

## Step 4 — Analytical SQL (`sql/analysis/`)

Six showcase queries that each answer a distinct business question.

---

### `01_top_tags_by_volume.sql` — Tag volume with year pivot

**Question:** Which SQL tags dominate, and how did their volume change year-over-year?

**Approach:** Aggregate `fct_tag_yearly`, pivot year counts with conditional `SUM(IF(...))`, rank by total, add a 2020→2022 delta column.

**Finding:** Every top-20 tag declined. `sql` (127k) is 2.5× the size of `mysql` (#2). `sqlalchemy` had the smallest drop (−103 questions), suggesting a stable ORM user base with fewer "google before asking" alternatives.

**Significance:** Shows a macro platform trend that contextualises all the other analyses — volume decline is systematic, not tag-specific.

---

### `02_tag_yoy_growth.sql` — Sequential YoY growth rates

**Question:** Are the declines consistent year-to-year, or are some tags accelerating/recovering?

**Approach:** `LAG(num_questions) OVER (PARTITION BY tag ORDER BY creation_year)` to compute sequential growth rates; minimum 500 questions/year floor to exclude long-tail noise.

**Finding:** `google-bigquery` grew +25% in 2021 before pulling back in 2022. Generic SQL keyword tags (`count`, `datetime`, `group-by`) fell 40–60% in 2021 — likely SO de-duplication effects as canonical answers accumulate.

**Significance:** Demonstrates window functions for time-series analysis and the difference between an absolute floor and a percentage filter.

---

### `03_rising_falling_tags.sql` — Fastest rising and falling tags (2020 vs 2022)

**Question:** Which tags bucked the declining trend, and which collapsed fastest?

**Approach:** Self-join `fct_tag_yearly` on tag with years 2020 and 2022; require ≥200 questions in both years; compute `safe_divide(q_2022 - q_2020, q_2020)` as growth rate; `ROW_NUMBER()` to rank top 10 risers and fallers.

**Finding:**
- **Rising:** Databricks (+69%), Snowflake (+51%), TypeScript ORMs (+43%) — the modern data stack and typed-language ecosystem
- **Falling:** `string`, `count`, `where-clause`, `window-functions` — pure SQL keyword tags collapsing as existing answers cover them

**Significance:** The riser list is effectively a signal of where hiring is happening in the data space during 2020–2022.

---

### `04_answer_rate_by_tag.sql` — Best and worst answered tags

**Question:** Which SQL sub-communities get their questions resolved, and which are left hanging?

**Approach:** Aggregate across all years with `HAVING sum(num_questions) >= 500`; `ROW_NUMBER()` to find the top and bottom 15 by `pct_answered`.

**Finding:**
- **Best:** `gaps-and-islands` (97%), `greatest-n-per-group` (96%) — expert-magnet pattern questions
- **Worst:** `xampp` (56%), `odbc` (57%), `mysql-connector` (59%) — connector/driver setup in environment-specific stacks

**Significance:** Illustrates how question type (conceptual puzzle vs. environment setup) predicts answerability, not just tag popularity.

---

### `05_error_patterns.sql` — Top SQL error signatures by volume and upvote signal

**Question:** What are the most common SQL mistakes, measured by question volume and community upvote signal?

**Approach:** Array of 14 regex patterns cross-joined against `raw.questions` (title + body concatenated, lowercased). Each question can match multiple patterns. Groups by pattern label; outputs count, avg score, total upvotes, pct answered/accepted.

**Why raw, not staging:** The dbt staging layer intentionally excludes the `body` column (large HTML, not needed for mart logic). These showcase queries access raw directly.

**Finding:**

| Pattern | Questions | Notes |
|---|---|---|
| Foreign-key constraint | 10,370 | Most common; 44% accepted |
| Object/column not found | 6,357 | |
| Syntax error | 5,855 | |
| GROUP BY / aggregate | 5,821 | Highest accepted rate at 50% |
| Timeout / lock wait | 5,551 | Hardest: only 28% accepted |
| Permission / access denied | 2,026 | 25% accepted — nearly as hard |

**Significance:** Demonstrates regex-based text mining in SQL (no Python/ML needed), UNNEST with struct literals to parameterise the pattern list, and reading from a layer below dbt when justified.

---

### `06_keyword_frequency.sql` — Advanced SQL keyword frequency: questions vs. accepted answers

**Question:** Which advanced SQL features appear as *problems* (in questions) vs. *solutions* (in accepted answers)?

**Approach:** Two subquery branches — `all_questions` and `accepted_answers` (accepted answers only, joined back to their parent question). Cross-joined with a keyword array, then ratio of accepted-answer hits to question hits computed with `safe_divide`.

**Finding:**

| Keyword | Ratio | Interpretation |
|---|---|---|
| LATERAL | 2.03 | Almost never the problem topic; very often the solution |
| CROSS/OUTER APPLY | 1.99 | Same — expert reach-for tool |
| ROW_NUMBER() | 1.78 | People ask about ranking; window functions answer it |
| MERGE | 0.26 | Asked about more than it appears as a solution |
| JSON functions | 0.48 | A struggle topic more than a solution tool |

**Significance:** Reframes "feature usage" as a directional signal — the answer-to-question ratio cleanly separates expert solution tools from common pain points. Shows how to derive insight from text at scale without ML.

---

## Step 5 — Looker dashboard (`looker/`)

### What was built
A LookML semantic layer over the two mart tables, with a dashboard definition covering five views:

1. **Question volume trend** — top-10 tags as a line chart by year
2. **Rising vs. falling tags** — bar chart of 2020→2022 growth rate
3. **Answer rate by tag** — horizontal bar of best/worst answered tags
4. **Feature frequency: answers vs. questions** — grouped bar of answer-to-question ratios
5. **Question volume over time** — monthly time series from `dim_questions`

### Key LookML decisions
- **Explores are join-free** — both mart tables are already denormalised; no Looker joins needed. This keeps the semantic layer simple and queries fast.
- **Measures defined in LookML** — `pct_answered`, `avg_score`, `total_views` are defined once in the view so every dashboard tile shares the same logic.
- **`creation_year` as a filter** — exposed as a dimension with default value 2020–2022 so all tiles are year-filterable without custom SQL.

---

## Skills demonstrated (summary)

| Skill | Where |
|---|---|
| SQL (advanced) | Window functions, CTEs, UNNEST, REGEXP, aggregation, self-joins, LAG/LEAD |
| BigQuery | Partitioned tables, clustering, INFORMATION_SCHEMA, approximate aggregates |
| dbt | Staging/marts pattern, `ref()` DAG, schema tests, materialization config |
| Python | BQ client, CLI runner, environment config |
| Looker / LookML | Semantic layer design, view/measure/explore definition, dashboard YAML |
| Data modelling | Dimensional modelling (dim/fct), grain decisions, exploded tags pattern |
| Text mining | Regex-based classification without ML, pattern parameterisation in SQL |
| GCP | Service accounts, dataset IAM, BigQuery cost management |
