-- Mart: per-dialect, per-year question aggregates.
-- Maps the long-tail of SQL-family tags to 12 named dialect families,
-- then aggregates engagement metrics at the dialect × year grain.
-- A question can belong to multiple dialects (e.g. tagged both mysql and php).
{{ config(materialized = 'table') }}

with dialect_tags as (
    select dialect, tag from unnest([
        -- MySQL / MariaDB
        struct('MySQL / MariaDB' as dialect, 'mysql'                       as tag),
        struct('MySQL / MariaDB',             'mysql-5.6'                      ),
        struct('MySQL / MariaDB',             'mysql-5.7'                      ),
        struct('MySQL / MariaDB',             'mysql-8.0'                      ),
        struct('MySQL / MariaDB',             'mariadb'                        ),
        -- PostgreSQL
        struct('PostgreSQL',                  'postgresql'                     ),
        struct('PostgreSQL',                  'psql'                           ),
        -- SQL Server / T-SQL
        struct('SQL Server',                  'sql-server'                     ),
        struct('SQL Server',                  't-sql'                          ),
        struct('SQL Server',                  'tsql'                           ),
        struct('SQL Server',                  'sql-server-2008'                ),
        struct('SQL Server',                  'sql-server-2012'                ),
        struct('SQL Server',                  'sql-server-2014'                ),
        struct('SQL Server',                  'sql-server-2016'                ),
        struct('SQL Server',                  'sql-server-2017'                ),
        struct('SQL Server',                  'sql-server-2019'                ),
        struct('SQL Server',                  'azure-sql-database'             ),
        -- Oracle / PL-SQL
        struct('Oracle',                      'oracle'                         ),
        struct('Oracle',                      'oracle-database'                ),
        struct('Oracle',                      'oracle-11g'                     ),
        struct('Oracle',                      'oracle-12c'                     ),
        struct('Oracle',                      'oracle-xe'                      ),
        struct('Oracle',                      'plsql'                          ),
        struct('Oracle',                      'pl-sql'                         ),
        -- SQLite
        struct('SQLite',                      'sqlite'                         ),
        -- Snowflake
        struct('Snowflake',                   'snowflake'                      ),
        struct('Snowflake',                   'snowflake-cloud-data-platform'  ),
        -- Google BigQuery
        struct('Google BigQuery',             'google-bigquery'                ),
        struct('Google BigQuery',             'bigquery'                       ),
        -- Amazon Redshift
        struct('Amazon Redshift',             'amazon-redshift'                ),
        struct('Amazon Redshift',             'redshift'                       ),
        -- Databricks
        struct('Databricks',                  'databricks'                     ),
        -- Apache Hive
        struct('Apache Hive',                 'hive'                           ),
        struct('Apache Hive',                 'apache-hive'                    ),
        -- IBM DB2
        struct('IBM DB2',                     'db2'                            ),
        struct('IBM DB2',                     'ibm-db2'                        ),
        -- Microsoft Access
        struct('Microsoft Access',            'access'                         ),
        struct('Microsoft Access',            'ms-access'                      )
    ])
),

questions as (
    select
        question_id,
        creation_year,
        score,
        view_count,
        is_answered,
        has_accepted_answer,
        tags
    from {{ ref('dim_questions') }}
),

-- One row per (question, dialect) — a question matching multiple dialect tags
-- for the same dialect is collapsed to one row via DISTINCT on question_id.
matched as (
    select distinct
        dt.dialect,
        q.question_id,
        q.creation_year,
        q.score,
        q.view_count,
        q.is_answered,
        q.has_accepted_answer
    from questions          as q
    cross join dialect_tags as dt
    where dt.tag in unnest(q.tags)
)

select
    dialect,
    creation_year,
    count(*)                                                            as num_questions,
    countif(is_answered)                                                as num_answered,
    round(safe_divide(countif(is_answered), count(*)), 4)              as pct_answered,
    countif(has_accepted_answer)                                        as num_accepted,
    round(safe_divide(countif(has_accepted_answer), count(*)), 4)      as pct_accepted,
    round(avg(score), 2)                                               as avg_score,
    sum(view_count)                                                     as total_views,
    round(avg(view_count), 0)                                          as avg_views
from matched
group by dialect, creation_year
order by dialect, creation_year
