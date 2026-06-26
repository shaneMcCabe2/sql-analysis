-- SQL dialect frequency: question volume and answer rates per dialect family (2020-2022).
-- Maps 40+ SO tags to 12 named dialect families. A question can match multiple dialects.
-- To materialise: run dbt run --select analysis_dialect_frequency
-- or execute as a BQ query with a destination table set.

with dialect_tags as (
    select dialect, tag from unnest([
        struct('MySQL / MariaDB' as dialect, 'mysql'                       as tag),
        struct('MySQL / MariaDB',             'mysql-5.6'                      ),
        struct('MySQL / MariaDB',             'mysql-5.7'                      ),
        struct('MySQL / MariaDB',             'mysql-8.0'                      ),
        struct('MySQL / MariaDB',             'mariadb'                        ),
        struct('PostgreSQL',                  'postgresql'                     ),
        struct('PostgreSQL',                  'psql'                           ),
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
        struct('Oracle',                      'oracle'                         ),
        struct('Oracle',                      'oracle-database'                ),
        struct('Oracle',                      'oracle-11g'                     ),
        struct('Oracle',                      'oracle-12c'                     ),
        struct('Oracle',                      'oracle-xe'                      ),
        struct('Oracle',                      'plsql'                          ),
        struct('Oracle',                      'pl-sql'                         ),
        struct('SQLite',                      'sqlite'                         ),
        struct('Snowflake',                   'snowflake'                      ),
        struct('Snowflake',                   'snowflake-cloud-data-platform'  ),
        struct('Google BigQuery',             'google-bigquery'                ),
        struct('Google BigQuery',             'bigquery'                       ),
        struct('Amazon Redshift',             'amazon-redshift'                ),
        struct('Amazon Redshift',             'redshift'                       ),
        struct('Databricks',                  'databricks'                     ),
        struct('Apache Hive',                 'hive'                           ),
        struct('Apache Hive',                 'apache-hive'                    ),
        struct('IBM DB2',                     'db2'                            ),
        struct('IBM DB2',                     'ibm-db2'                        ),
        struct('Microsoft Access',            'access'                         ),
        struct('Microsoft Access',            'ms-access'                      )
    ])
),

matched as (
    select distinct
        dt.dialect,
        q.question_id,
        q.creation_year,
        q.score,
        q.view_count,
        q.is_answered,
        q.has_accepted_answer
    from `sql-analysis-500017`.`dbt_dev_marts`.`dim_questions` as q
    cross join dialect_tags as dt
    where dt.tag in unnest(q.tags)
)

select
    dialect,
    creation_year,
    count(*)                                                        as num_questions,
    countif(is_answered)                                            as num_answered,
    round(safe_divide(countif(is_answered), count(*)), 4)          as pct_answered,
    countif(has_accepted_answer)                                    as num_accepted,
    round(safe_divide(countif(has_accepted_answer), count(*)), 4)  as pct_accepted,
    round(avg(score), 2)                                           as avg_score,
    sum(view_count)                                                 as total_views,
    round(avg(view_count), 0)                                      as avg_views
from matched
group by dialect, creation_year
order by sum(count(*)) over (partition by dialect) desc, creation_year
;
