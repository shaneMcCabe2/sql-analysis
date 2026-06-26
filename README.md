# sql-analysis

A portfolio project analyzing **SQL-tagged Stack Overflow questions (2020–2022)** to surface ecosystem trends, common failure patterns, and how advanced SQL features appear in practice.

Built end-to-end on Google Cloud: BigQuery public data → Python ingestion → dbt staging and marts → analytical SQL → Looker dashboard.

---

## Key findings

- **Every major SQL tag declined in volume 2020→2022** — a platform-wide SO traffic shift, not SQL-specific. `sql` (127k questions) is 2.5× larger than `mysql` at #2.
- **The modern data stack is growing against the trend**: Databricks (+69%), Snowflake (+51%), and TypeScript ORMs (+43%) rose despite the overall volume decline.
- **Timeout and permission errors are the hardest to resolve** — only 28% and 25% accepted-answer rates respectively, vs. 50% for GROUP BY/aggregate errors.
- **Window functions are the universal solution tool**: `OVER()` appears 1.66× more often in *accepted answers* than in questions; `LATERAL` and `CROSS APPLY` ratios exceed 2×.
- **`gaps-and-islands`** and **`greatest-n-per-group`** are the best-answered niches (97%, 96%) — pattern questions attract expert answerers.
- **Foreign-key constraints** generate the most error-related questions (10k+), but GROUP BY / aggregate errors are the most reliably resolved (50% accepted).

---

## Architecture

```
bigquery-public-data.stackoverflow
        (frozen public snapshot, ends 2022-09-25)
                        │
                        │  sql/transfer/*.sql
                        │  via ingest/transfer.py
                        ▼
              raw dataset (this project)
              ~299k questions · 322k answers
              1.06M comments · 235k users
                        │
                        │  dbt (staging layer)
                        ▼
              dbt_dev_staging.*  ← typed views, no body text
              stg_questions · stg_answers · stg_users
              stg_comments  · stg_tags
                        │
                        │  dbt (marts layer)
                        ▼
              dbt_dev_marts.*
              dim_questions     ← one enriched row per question
              fct_tag_yearly    ← per-tag/year aggregates
                        │
               ┌─────────────────────┐
               │                     │
               ▼                     ▼
        sql/analysis/          looker/
        6 showcase queries     LookML model + dashboard
```

---

## What each layer demonstrates

| Layer | What it does | Skills shown |
|---|---|---|
| **Transfer** (`sql/transfer/`, `ingest/`) | Filters and copies ~91 GB from the public BQ dataset into a private raw zone | SQL-based ETL, Python scripting, GCP/BQ cost awareness |
| **Staging** (`dbt/models/staging/`) | Types, cleans, and standardises raw tables into views; splits tag strings to arrays; adds relationship tests | dbt, data contracts, SQL typing, automated testing |
| **Marts** (`dbt/models/marts/`) | Joins staging models into analytics-ready tables partitioned for query efficiency | Dimensional modelling, BQ partitioning/clustering, dbt `ref()` DAG |
| **Analysis** (`sql/analysis/`) | Six showcase queries covering trends, text mining, and feature frequency | Window functions, regex, UNNEST, CTEs, analytical SQL |
| **Dashboard** (`looker/`) | LookML model and tiles surfacing the mart tables for interactive exploration | Looker, semantic layer design, BI presentation |

---

## Layout

| Path | Purpose |
|---|---|
| `sql/transfer/` | BQ→BQ transfer queries (public → `raw`) |
| `ingest/` | `config.py` (env + client), `transfer.py` (runner) |
| `dbt/` | dbt project: `staging/` views → `marts/` tables |
| `sql/analysis/` | Six standalone showcase queries |
| `sql/checks/` | Ad-hoc data-quality / sanity queries |
| `docs/` | Project walkthrough and interview reference |
| `looker/` | LookML model, views, and dashboard definition |
| `secure/` | Service-account key (gitignored) |

---

## Data source

- **Origin:** `bigquery-public-data.stackoverflow` — public, **frozen** snapshot (last refreshed Nov 2022; data ends **2022-09-25**).
- **Scope:** the "SQL family" — any question whose tags contain `sql` (`sql`, `mysql`, `postgresql`, `sql-server`, `tsql`, `plsql`, `sqlite`, …).
- **Volume landed:** ~299k questions, 322k answers, 1.06M comments, 235k users.

*Note: the public dataset cannot supply 2023+ data. Fresher data would require the archive.org XML dump (latest 2024-04-02), which is out of scope here.*

---

## Setup

```bash
python3.12 -m venv .venv          # dbt-core 1.11 does not support Python 3.13+
.venv/bin/pip install -r requirements.txt
cp .env.example .env              # fill in GCP_PROJECT_ID and GOOGLE_APPLICATION_CREDENTIALS
```

## Common commands

```bash
source .venv/bin/activate

# (Re)build the raw landing zone from the public dataset (~91 GB scanned, idempotent)
python -m ingest.transfer --dry-run   # estimate first
python -m ingest.transfer             # execute

# dbt
DBT_PROFILES_DIR=$(pwd)/dbt dbt debug --project-dir dbt
DBT_PROFILES_DIR=$(pwd)/dbt dbt build --project-dir dbt

# Run an analysis query (example)
export GOOGLE_APPLICATION_CREDENTIALS=secure/<key>.json
grep -v '^\s*--' sql/analysis/03_rising_falling_tags.sql \
  | bq query --project_id=<your-project> --nouse_legacy_sql
```

## Notes

- `.env` and `secure/` hold credentials and are gitignored.
- Python **3.12** is required (dbt-core 1.11 does not support 3.13/3.14).
- The "SQL family" filter also matches `nosql` / `apache-spark-sql`; see `sql/transfer/01_questions.sql` to tighten it.
- For interactive exploration, see `docs/project_walkthrough.md` for a full pipeline walkthrough.
