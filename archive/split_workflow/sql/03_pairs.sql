CREATE TABLE father_child AS
SELECT DISTINCT r.child_id, r.father_id
FROM relationships AS r
JOIN people AS c ON r.child_id = c.person_id
JOIN people AS p ON r.father_id = p.person_id;

CREATE TABLE eligible AS
SELECT f.child_id, f.father_id,
       pa.mean_income AS father_average,
       ca.mean_income AS child_average,
       cy.real_income AS child_young,
       cm.real_income AS child_mature,
       pm.real_income AS father_mature,
       pa.n_years AS father_n_years,
       ca.n_years AS child_n_years,
       pa.mean_age AS father_mean_age,
       ca.mean_age AS child_mean_age,
       pa.zero_years AS father_zero_years,
       ca.zero_years AS child_zero_years,
       cy.age AS child_young_age,
       cm.age AS child_mature_age,
       pm.age AS father_mature_age,
       cy.income_year AS child_young_year,
       cm.income_year AS child_mature_year,
       pm.income_year AS father_mature_year
FROM father_child AS f
JOIN averages AS pa ON f.father_id = pa.person_id
JOIN averages AS ca ON f.child_id = ca.person_id
JOIN young AS cy ON f.child_id = cy.person_id
JOIN mature AS cm ON f.child_id = cm.person_id
JOIN mature AS pm ON f.father_id = pm.person_id;

CREATE TABLE matched_sample AS
SELECT * FROM eligible
WHERE father_average > 0 AND child_average > 0
  AND child_young > 0 AND child_mature > 0 AND father_mature > 0;
