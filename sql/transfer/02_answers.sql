-- Transfer 02: answers to the SQL-family questions selected in 01_questions.sql.
-- Joined by parent_id so the raw answer set stays consistent with the question set.
CREATE OR REPLACE TABLE `sql-analysis-500017.raw.answers`
PARTITION BY DATE(creation_date)
CLUSTER BY owner_user_id AS
SELECT a.*
FROM `bigquery-public-data.stackoverflow.posts_answers` AS a
WHERE a.parent_id IN (
  SELECT id FROM `sql-analysis-500017.raw.questions`
);
