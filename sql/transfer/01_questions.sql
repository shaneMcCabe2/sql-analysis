-- Transfer 01: SQL-family Stack Overflow questions, 2020-2022 -> raw landing zone.
--
-- Source : bigquery-public-data.stackoverflow (a public, FROZEN snapshot,
--          last refreshed ~Nov 2022 -- so 2022 is a partial year).
-- Scope  : "SQL family" = any tag containing the substring "sql"
--          (sql, mysql, postgresql, sql-server, tsql, plsql, sqlite, ...).
--          NOTE: this also matches "nosql" and "apache-spark-sql"; add
--          `AND NOT REGEXP_CONTAINS(tags, r'(^|\|)nosql(\||$)')` to exclude.
-- Output : ~298k rows. Partitioned by day, clustered by author for cheap
--          downstream scans.
CREATE OR REPLACE TABLE `sql-analysis-500017.raw.questions`
PARTITION BY DATE(creation_date)
CLUSTER BY owner_user_id AS
SELECT *
FROM `bigquery-public-data.stackoverflow.posts_questions`
WHERE creation_date >= TIMESTAMP('2020-01-01')
  AND creation_date <  TIMESTAMP('2023-01-01')
  AND tags LIKE '%sql%';
