# BLOG6: Matching Fathers and Children: A SQL Tutorial in Python

A SQL-in-Python tutorial on matching biological fathers and adult children and
comparing two estimates of intergenerational income elasticity (IGE). The focus
is on using repeated income observations for both generations. Comparing similar
ages helps with age mismatch but does not remove temporary income fluctuations.

**Status:** the code and article have been revised following instructor feedback.
The author ran the revised design locally: age 36 was selected, with 143 pairs
and 123 fathers. The single-year IGE is 0.220; the ages 29–43 average-income IGE
is 0.297. Old four-model estimates are not used for this design. No formal statistical inference is
required or reported in the current tutorial.

## Structure

```text
BLOG6/
├── README.md
├── BLOG6.Rproj
├── requirements.txt
├── index.qmd
├── code/
│   ├── analysis.py         # cleaning, SQL, two regressions, figures
│   ├── download_cpi.py     # BLS download/cache and annual CPI
│   ├── variables.csv      # annual variable mapping
│   └── sync_website.py    # article and figure copies
├── data/
│   ├── raw/               # original inputs
│   └── processed/         # matched person-level data; local only
├── results/
│   ├── tables/
│   └── figures/
└── archive/               # superseded designs and results
```

All analysis is in `code/analysis.py`, including the SQL statements. The website
receives only the QMD and figures. BLOG6 is not a separate Quarto website.

## Sources and access

The local PSID inputs are `J366544.xlsx`, its labels and codebook, and
`fim16212_gid_BO_2_BAL.xlsx` in `data/raw/`. FIMS provides biological links;
`PTYPE = F` selects fathers. The permanent identifier combines the 1968 family
ID with the person number. Annual household identifiers are not permanent IDs.

PSID microdata and person-level derived files are local inputs, not intended
GitHub contents. The [PSID Conditions of Use](https://simba.isr.umich.edu/U/CondUse.aspx)
restrict redistribution and currently prohibit AI/LLM use in conjunction with
PSID data. Writing code for a local run does not itself establish an exception.
Any applicable permission must be resolved by the data user. This draft does
not claim that permission has been obtained. Independent replication requires
authorized access to PSID and the corresponding variables, rather than obtaining
another user's microdata from this repository. Public-facing outputs should be
limited to permitted aggregate reporting and code; `data/processed/` contains
individual identifiers and must not be uploaded as an aggregate result.

The public BLS CPI-U series CUUR0000SA0 covers 1993–2022. Original JSON
responses and source metadata are saved in `data/raw/`; the retrieval date is
October 21, 2026. Each annual CPI is the mean of all twelve monthly values.
`download_cpi.py` reuses these snapshots and downloads only missing files.

## Design

The extract supplies 17 survey waves from 1994–2023, corresponding to income
years 1993–2022. Individual labor income excludes farm and unincorporated business
income. `CASE` chooses Head/Reference Person income for sequence 1 and relationship
10, or Spouse income for sequence 2 and relationship 20/22. Income for other family
members is not reconstructed. Income-year age is approximated as survey age minus one.

Income is converted to 2022 dollars using CPI before averages are calculated.

| Measure | Definition |
|---|---|
| Single-year income | Exact approximate age A, chosen among 30–45 by maximum common-pair count; earlier year breaks repeated-age ties |
| Multi-year income | All valid real incomes at ages A−7 through A+7; at least three observations |
| Zero income | Included in averages; selected single-year zero is not substituted |
| Invalid/high codes | Missing, negative, and amounts at or above 9,999,997 excluded |
| Common sample | Both single-year incomes and both averages must be available and positive |

There is no age-25 eligibility condition. Both regressions use exactly the same
pairs. `AVG()` is applied before the natural logarithm; it is not an average of logs.

| Regression | Father X | Child Y |
|---|---|---|
| Single | Log of single-year income at A | Log of single-year income at A |
| Average | Log of mean income at A−7 through A+7 | Log of mean income at A−7 through A+7 |

The models are unweighted OLS with an intercept. Outputs contain the slopes,
intercepts, R squared, and counts. No p-values, confidence intervals, significance
stars, or age-difference tests are produced.

The fifteen-age window does not require fifteen observations or complete coverage.
It is not a replication of a fifteen-observation average. The code reports observation counts and elapsed spans for fathers and
children separately. The current averages are limited proxies for long-run income;
they do not guarantee elimination of life-cycle or transitory-income bias. The
literature's estimates around 0.5 or higher are not a calibration target.

## Reproduction

With the locally obtained inputs present, the entry point from BLOG6 is:

```bash
python -m pip install -r requirements.txt
python code/analysis.py
```

The script rebuilds the matched sample, runs both regressions, creates the figures,
and updates only the marked results section of `index.qmd`. It also saves that
section as `results/tables/blog_results.md`. Re-running replaces that results block,
so personal edits outside the block are preserved. The narrative interpretation
should be reviewed after the local run. The raw files remain unchanged.

The revised script has been checked for Python syntax. It has not been executed
on PSID records here, and no simulated-sample tests were created. The author runs
the analysis locally. Package requirements are in `requirements.txt`.

| Output | Contents |
|---|---|
| `data/processed/matched_sample.csv` | Current pair-level analysis table; local only |
| `results/tables/cpi_annual.csv` | Annual CPI and conversion factors |
| `results/tables/sample_flow.csv` | Counts through selection stages |
| `results/tables/income_coverage.csv` | Income records by survey/income year |
| `results/tables/age_coverage.csv` | Candidate-age counts and selected age |
| `results/tables/sample_summary.csv` | Number of observations, ages, dates, elapsed spans, zeros |
| `results/tables/regressions.csv` | Two OLS point estimates and sample counts |
| `results/tables/results_summary.md` | Readable coefficient table |
| `results/tables/plot_bins.csv` | Group means used in the relationship figure |
| `results/tables/blog_results.md` | Results section produced from the run |
| `results/figures/single_vs_average.png` | Two relationship panels |

The prior four-model outputs are archived under `archive/before_professor_feedback/`.
The current matched sample was rebuilt by the author. A subsequent run replaces
it and regenerates the marked results section in the article.

## Website and article

`index.qmd` is the canonical English tutorial. Code blocks are displayed rather
than executed when rendering. It remains `draft: true` for review. After the
analysis runs, `python code/sync_website.py` copies it and the relationship PNG to
`website1/blog/posts/post6/`. No raw data or processed individual records are copied.
The scripts do not publish, commit, or push the website.

## Limitations

This is a selected and unweighted sample. The required roles, observation coverage,
and positive incomes limit representativeness. Age is approximate, calendar years
differ across generations, income can be imputed, and averages contain different
numbers of observations. Inflation adjustment does not remove labor-market period
effects. These regressions describe associations rather than causal effects or
verified estimates of complete lifetime-income persistence.

## References

- [PSID](https://psidonline.isr.umich.edu/), Survey Research Center, Institute for Social
  Research, University of Michigan (2026). Extract J366544, FIMS, and supplied codebook.
- [BLS Public Data API](https://www.bls.gov/developers/), CPI-U CUUR0000SA0.
- Mazumder, B. (2018). [Intergenerational Mobility in the United States: What We Have Learned from the PSID](https://pmc.ncbi.nlm.nih.gov/articles/PMC6820674/).
  The ANNALS, 680(1), 213–234. DOI: 10.1177/0002716218794129.

## Age selection in the current design

Before estimating any slopes, the code evaluates ages 30–45. Each candidate uses
exactly the same approximate income-year age for father and child. It chooses the
age with the largest sample eligible for BOTH regressions, including the average
income requirements. Ties go closest to 40, then younger. No coefficient or
significance result is used for selection. `results/tables/age_coverage.csv`
reports both single-year-only and common-sample counts for every candidate.

The average window is A−7 to A+7 for both generations, with at least three valid
observations. Actual observation counts, ages and spans must be reported. This
coverage-based choice does not identify an optimal age for lifetime income and
may select a different cohort from a fixed-age design. Both sons and daughters
remain eligible as before; 'child' describes the relationship, not sex.

Run `python code/analysis.py` in the RStudio Terminal from BLOG6. This rebuilds
the sample, selects the age, estimates both models and regenerates figures and
the article's marked results section. Then run `python code/sync_website.py`.
The current local run uses age 36 and the ages 29–43 averaging window. The older
four-model results remain superseded.

## Short tutorial format

The article has about 796 words excluding displayed code and the equation. It
uses one two-panel relationship figure and a coefficient table. The redundant
bar chart is no longer generated or embedded. The results writer preserves this
compact format. Detailed replication information remains in this README and code.
