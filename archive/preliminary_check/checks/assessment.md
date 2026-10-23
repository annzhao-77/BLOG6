# BLOG6 data feasibility check

Checked on 2026-10-21 using J366544.xlsx, J366544_labels.txt,
J366544_codebook.pdf and data/fim16212_gid_BO_2_BAL.xlsx.

The income download contains 85,536 people and 305 variables. The combined
ER30001/ER30002 identifier has no duplicates. The FIMS file contains 113,450
relationship rows, including 53,437 unique father-child pairs; 29,218 pairs
have both identifiers present in this income download. No child has multiple
distinct father identifiers in this FIMS selection.

## Income definition

The codebook confirms that V23323 (1993 survey, 1992 income) includes farm and
business labor components, whereas ER4140 (1994 survey, 1993 income) excludes
farm and unincorporated business income. The corresponding selected reference
person and spouse series from 1994 onward use the exclusion definition.
Use the 1994-2023 survey waves for this preliminary common-definition screen;
do not concatenate earlier income totals without harmonization.

## Preliminary eligibility

Income is assigned only to current reference persons (sequence 1, relationship
10) and spouses (sequence 2, relationship 20 or 22). Income-year age is
approximated by survey age minus one. The screening retains positive income
below 9,999,997 and ages 18-90. These rules are not a final missing-value,
topcoding, or zero-income policy.

- Father: at least three positive income observations at ages 35-45.
- Child young observation: age 23-27.
- Child mature observation: age 38-42.
- Child average coverage: at least three positive observations at ages 35-45.
- Common sample for these three comparisons: 316 pairs, 241 distinct fathers.
- Also requiring a father observation at age 38-42: 272 pairs.

These counts establish feasibility, not final sample sizes or regression results.
Birth-date precision, role selection, attrition, imputation and genuine zero
incomes require explicit treatment. A genuine zero can be part of a multi-year
average even though an individual zero cannot be logged. Income measurements
must be inflation-adjusted before averaging. No CPI series is in this download.
Sibling observations share fathers; inference should account for that clustering.
No weights were selected, so do not describe these unweighted matched-sample
regressions as nationally representative estimates.

## Tutorial scope

The existing merged individual extract supports SQL joins to the FIMS map,
selection by annual family role and age, GROUP BY/AVG income construction,
and single-year versus multi-year log regressions. No separate family extract
is necessary for this tutorial. Age comparisons illustrate sensitivity to
measurement age, but calendar-period and cohort differences prevent interpreting
all coefficient differences as pure life-cycle bias. No rank analysis is planned.

Checks: code/check_download.py followed by code/check_matches.py; the notebook
code/download_check.ipynb records the aggregate output. Cache files can be deleted
after checking; rerun the first script to reconstruct them.
