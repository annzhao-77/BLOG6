# BLOG6: Does the Age We Measure Income Change the Story?

This post is a SQL-in-Python tutorial on matching biological fathers and adult
children and estimating intergenerational income elasticities (IGE). It compares
single-year income with multi-year averages, and children's income near ages
25 and 40. The article uses results from the author's local run: 439 pairs and
331 distinct fathers.

## Files

```text
BLOG6/
├── README.md
├── BLOG6.Rproj
├── requirements.txt
├── index.qmd
├── code/
│   ├── analysis.py        # Excel reading, cleaning, SQL, regressions, figures
│   ├── download_cpi.py    # download/cache BLS CPI and calculate annual means
│   ├── variables.csv     # PSID variable codes for each survey wave
│   └── sync_website.py   # copy the article and figures to the website
├── data/
│   ├── raw/              # original inputs and CPI responses
│   └── processed/        # generated person-level matched sample; local only
├── results/
│   ├── tables/
│   └── figures/
└── archive/              # superseded code and preliminary checks
```

`analysis.py` contains the full analysis, including SQL as multi-line strings.
The former separate scripts are retained in `archive/split_workflow/` as an
old version. They are not part of the current workflow. The website receives
only the QMD and figure files. BLOG6 is not a separate Quarto website.

## Data

The PSID inputs are `J366544.xlsx`, its labels and codebook, and
`fim16212_gid_BO_2_BAL.xlsx`, stored in `data/raw/`. The extract provides
individual identifiers with annual family variables. The FIMS table supplies
the biological father-child links (`PTYPE = F`). A permanent person ID combines
the 1968 family ID and person number; the annual family interview ID is not
used as a permanent person identifier.

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

The BLS CPI-U series is CUUR0000SA0: U.S. city average, all items,
not seasonally adjusted. The three original API responses cover 1993–2002,
2003–2012, and 2013–2022 and are saved in `data/raw/`. `cpi_sources.json`
records their URLs and the October 21, 2026 retrieval date. The annual index
is the unrounded mean of twelve monthly observations. All incomes are converted
to 2022 dollars before averaging.

## Income measures and SQL

The analysis uses 17 survey waves from 1994 through 2023, reporting income for
1993–2022. `variables.csv` records the variable mapping. The selected personal
labor income variables exclude farm and unincorporated business income.

Income is assigned to the current reference person (sequence 1, relationship
10) or spouse/partner (sequence 2, relationship 20/22). These fields measure
the person's own income; they are not added to form family income. Income for
other household members is not reconstructed. Age in the income year is
approximated as survey age minus one.

| Measure | Rule |
|---|---|
| Young single year | Closest to 25 within ages 23–27 |
| Mature single year | Closest to 40 within ages 38–42 |
| Multi-year average | Mean at ages 35–45, at least three valid observations |
| Ties | Earlier income year |
| Zeros | Included in averages; not replaced by another positive single year |
| High codes | Nominal amounts at or above 9,999,997 are excluded |
| Common sample | All five selected income measures must be positive |

SQL `JOIN` connects the generations, `CASE` assigns the correct income field,
`GROUP BY` and `AVG()` construct individual averages, and `ROW_NUMBER()`
selects the closest-age records. Missing incomes are not filled with zeros.
The averages use available observations, not a complete eleven-year history.

## Regressions

All four models use the same matched sample and an intercept:

```text
log(child income) = intercept + beta × log(father income) + error
```

| Model | Father income | Child income | Reported beta |
|---|---|---|---:|
| Young | Ages 35–45 average | Single year near 25 | 0.154 |
| Mature | Same average | Single year near 40 | 0.220 |
| Average | Ages 35–45 average | Ages 35–45 average | 0.191 |
| Single | Single year near 40 | Single year near 40 | 0.384 |

Income is averaged before taking logs. OLS is unweighted; standard errors are
clustered by father because siblings share a parent. The figures retain 95%
confidence intervals. The age difference is uncertain, so the article describes
point estimates and possible measurement mechanisms rather than claiming to
prove life-cycle bias. The supplementary age-difference calculation remains
in the code and `age_difference.csv`; it is not a central result in the post.

The sample is selected, the regressions are descriptive, and multi-year income
is only a proxy for long-run status. Age and calendar time change together.
Averaging can reduce temporary fluctuations without necessarily increasing IGE.

## Reproduction

The author's split-script run used Python 3.14.7. Package requirements are in
`requirements.txt`. With the local inputs available, the combined entry point
from the repository root is:

```bash
python -m pip install -r requirements.txt
python code/analysis.py
```

The script reads the CPI snapshots, prepares the income records, matches pairs
using SQLite, estimates the models, and saves tables and figures. It uses a
temporary database and leaves the original workbooks unchanged. Existing CPI
responses are reused; only missing responses require a download. The separate
`download_cpi.py` can also rebuild the annual CPI table.

The combined script preserves the original analysis functions and SQL queries.
Its syntax and consolidation were checked without rerunning PSID records or
creating simulated sample tests. The reported results and current figures come
from the author's completed run of the original split workflow.

| Output | Contents |
|---|---|
| `data/processed/matched_sample.csv` | Person-level matched data; local only |
| `results/tables/cpi_annual.csv` | Annual CPI and conversion factors |
| `results/tables/sample_flow.csv` | Counts through the selection stages |
| `results/tables/income_coverage.csv` | Eligible income observations by year |
| `results/tables/sample_summary.csv` | Ages, dates, counts, and zero years |
| `results/tables/regressions.csv` | Four regression estimates and intervals |
| `results/tables/age_difference.csv` | Supplementary age-difference estimate |
| `results/tables/results_summary.md` | Readable regression output |
| `results/tables/plot_bins.csv` | Group means for the relationship figure |
| `results/figures/income_relationships.png` | Child income at two ages |
| `results/figures/regression_comparison.png` | Four coefficients and intervals |

## Article and website

`index.qmd` contains the English SQL tutorial and interpretation. Its code blocks
are displayed, not executed on rendering. The file remains marked `draft: true`
for review. It references the website's `figures/` directory.
`python code/sync_website.py` copies the article and generated PNGs to
`website1/blog/posts/post6/`. Editing the BLOG6 copy and syncing keeps one
canonical article. Syncing does not publish or push the site.

## Sources

- [Panel Study of Income Dynamics](https://psidonline.isr.umich.edu/), public use
  dataset, Survey Research Center, Institute for Social Research, University of
  Michigan (2026). Extract J366544 and FIMS; supplied codebook and
  [identifier guidance](https://psidonline.isr.umich.edu/Guide/FAQ.aspx).
- [BLS Public Data API](https://www.bls.gov/developers/), CPI-U CUUR0000SA0.
  Request URLs and retrieval date are saved with the raw responses.
- Gouskova, Chiteji, and Stafford (2010),
  [Estimating Intergenerational Persistence of Lifetime Earnings with Life Course Matching: Evidence from PSID](https://doi.org/10.1016/j.labeco.2009.04.009),
  Labour Economics 17(3), 592–597. Background motivation, not a replication.
