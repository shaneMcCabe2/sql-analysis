# sql-analysis

A SQL portfolio project analyzing **SQL-tagged Stack Overflow questions (2020–2022)**.
Data is transferred from Google's public BigQuery Stack Overflow dataset into a
private `raw` landing zone, modeled with dbt, and explored with analytical SQL.

## Data source

- **Origin:** `bigquery-public-data.stackoverflow` — a public, **frozen** snapshot
  (last refreshed Nov 2022; data ends **2022-09-25**).
- **Scope:** the "SQL family" — any question whose tags contain `sql`
  (`sql`, `mysql`, `postgresql`, `sql-server`, `tsql`, `plsql`, `sqlite`, …).
- **Volume landed:** ~299k questions, 322k answers, 1.06M comments, 235k users.
- *Note:* the public dataset cannot supply 2023+ data. Fresher data would require
  the archive.org XML dump (latest 2024-04-02, 21 GB `stackoverflow.com-Posts.7z`),
  which is out of scope here.

## Architecture

```
  bigquery-public-data.stackoverflow   ──>   raw (this project)   ──>   dbt          ──>   sql/analysis/
  (frozen public snapshot)                   sql/transfer/*.sql         staging +          portfolio
                                             via ingest/transfer.py     marts models       queries
```

1. **Transfer** — `sql/transfer/*.sql` (run by `ingest/transfer.py`) copy a
   filtered slice of the public dataset into this project's `raw` dataset.
2. **Transform** — dbt models in `dbt/models/staging` clean/type the raw data;
   `dbt/models/marts` build the analytical tables.
3. **Analyze** — standalone showcase queries live in `sql/analysis/`.

## Layout

| Path              | Purpose                                                |
| ----------------- | ------------------------------------------------------ |
| `sql/transfer/`   | BQ→BQ transfer queries (public → `raw`)                |
| `ingest/`         | `config.py` (env + client), `transfer.py` (runner)     |
| `dbt/`            | dbt project (staging → marts)                          |
| `sql/analysis/`   | Standalone analytical queries (portfolio showcase)     |
| `sql/checks/`     | Ad-hoc data-quality / sanity queries                   |
| `secure/`         | Service-account key (gitignored — never commit)        |

## Setup

```bash
python3.12 -m venv .venv          # dbt does not support Python 3.13+
.venv/bin/pip install -r requirements.txt
cp .env.example .env              # then fill in your values
```

## Common commands

```bash
source .venv/bin/activate

# (re)build the raw landing zone from the public dataset (~91 GB scanned, idempotent)
python -m ingest.transfer --dry-run   # estimate first (step 01/05 only; 02-04 depend on 01)
python -m ingest.transfer             # execute

# dbt
DBT_PROFILES_DIR=$(pwd)/dbt dbt debug --project-dir dbt
DBT_PROFILES_DIR=$(pwd)/dbt dbt build --project-dir dbt
```

## Notes

- `.env` and `secure/` hold credentials and are gitignored.
- Python **3.12** is required (dbt-core 1.11 does not support 3.13/3.14).
- The "SQL family" filter also matches `nosql`/`apache-spark-sql`; see the comment
  in `sql/transfer/01_questions.sql` to tighten it.
