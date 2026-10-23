CREATE TABLE averages AS
SELECT person_id,
       AVG(real_income) AS mean_income,
       COUNT(*) AS n_years,
       AVG(age) AS mean_age,
       MIN(income_year) AS first_year,
       MAX(income_year) AS last_year,
       SUM(CASE WHEN real_income = 0 THEN 1 ELSE 0 END) AS zero_years
FROM income
WHERE age BETWEEN 35 AND 45
GROUP BY person_id
HAVING COUNT(*) >= 3;

CREATE TABLE young AS
WITH candidates AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY person_id
               ORDER BY ABS(age - 25), income_year
           ) AS choice
    FROM income
    WHERE age BETWEEN 23 AND 27
)
SELECT * FROM candidates WHERE choice = 1;

CREATE TABLE mature AS
WITH candidates AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY person_id
               ORDER BY ABS(age - 40), income_year
           ) AS choice
    FROM income
    WHERE age BETWEEN 38 AND 42
)
SELECT * FROM candidates WHERE choice = 1;
