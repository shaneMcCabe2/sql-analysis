-- Transfer 03: users who authored any question or answer in the raw set.
-- Filtered (rather than copying all 18M users) to keep the landing zone lean.
CREATE OR REPLACE TABLE `sql-analysis-500017.raw.users` AS
SELECT u.*
FROM `bigquery-public-data.stackoverflow.users` AS u
WHERE u.id IN (
  SELECT owner_user_id FROM `sql-analysis-500017.raw.questions` WHERE owner_user_id IS NOT NULL
  UNION DISTINCT
  SELECT owner_user_id FROM `sql-analysis-500017.raw.answers`   WHERE owner_user_id IS NOT NULL
);
