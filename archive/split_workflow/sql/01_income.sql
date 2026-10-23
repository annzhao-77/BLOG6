CREATE TABLE income AS
WITH assigned AS (
    SELECT person_id, survey_year, family_id,
           survey_year - 1 AS income_year,
           survey_age - 1 AS age,
           CASE
               WHEN sequence_number = 1 AND relationship = 10
                   THEN head_income
               WHEN sequence_number = 2 AND relationship IN (20, 22)
                   THEN spouse_income
           END AS nominal_income
    FROM person_year
    WHERE family_id > 0
)
SELECT a.*,
       a.nominal_income * base.cpi / c.cpi AS real_income
FROM assigned AS a
JOIN cpi AS c ON a.income_year = c.year
CROSS JOIN (SELECT cpi FROM cpi WHERE year = 2022) AS base
WHERE a.age BETWEEN 18 AND 90
  AND a.nominal_income >= 0
  AND a.nominal_income < 9999997;

CREATE UNIQUE INDEX income_key ON income(person_id, income_year);
