-- Transfer 04: comments on any question or answer in the raw set.
CREATE OR REPLACE TABLE `sql-analysis-500017.raw.comments`
PARTITION BY DATE(creation_date)
CLUSTER BY post_id AS
SELECT c.*
FROM `bigquery-public-data.stackoverflow.comments` AS c
WHERE c.post_id IN (
  SELECT id FROM `sql-analysis-500017.raw.questions`
  UNION DISTINCT
  SELECT id FROM `sql-analysis-500017.raw.answers`
);
