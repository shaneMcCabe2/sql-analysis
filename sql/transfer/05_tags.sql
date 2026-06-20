-- Transfer 05: full tag dictionary (tiny). Useful for tag metadata / joins.
CREATE OR REPLACE TABLE `sql-analysis-500017.raw.tags` AS
SELECT *
FROM `bigquery-public-data.stackoverflow.tags`;
