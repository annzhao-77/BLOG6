# Matching Fathers and Children: A SQL Tutorial in Python

This project asks: **Do higher-income fathers tend to have higher-income children?**
It demonstrates how SQL within Python connects father-child records, selects each
person's income, and aggregates repeated income observations. Python then estimates
two log-income regressions and produces one figure.

The blog source is [index.qmd](index.qmd). All data preparation, SQL queries,
regressions, and plotting are in [code/analysis.py](code/analysis.py).

## Project structure

```text
BLOG6/
├── README.md
├── index.qmd
├── requirements.txt
├── BLOG6.Rproj
├── code/
│   ├── analysis.py
│   ├── download_cpi.py
│   └── variables.csv
├── data/
│   ├── raw/               # downloaded inputs and CPI snapshots
│   └── processed/         # generated matched analysis sample
└── results/
    ├── tables/            # regression results and coverage summaries
    └── figures/
        └── single_vs_average.png
```

## Data and required inputs

The source is the [Panel Study of Income Dynamics (PSID)](https://psidonline.isr.umich.edu/).
Its Family Identification Mapping System (FIMS) supplies biological parent-child
links. The analysis selects fathers (`PTYPE = F`) and includes both adult sons and
daughters.

The code uses 17 survey waves from **1994–2023**, reporting income for **1993–2022**.
The selected personal labor-income variables exclude farm and unincorporated
business income. Earlier Head income totals included those components, so this
project restricts the years to avoid combining different definitions.

Place these files in `data/raw/`:

| File expected by the script | Purpose |
|---|---|
| `J366544.xlsx` | Income extract with permanent IDs and annual variables |
| `fim16212_gid_BO_2_BAL.xlsx` | FIMS biological parent-child links |
| `J366544_labels.txt` and `J366544_codebook.pdf` | Variable documentation; not read by the analysis script |

Readers obtaining their own extracts should select `ER30001` and `ER30002`, plus
the variables listed in [code/variables.csv](code/variables.csv). The FIMS export
must include `PTYPE`, `ID68`, `PN`, `ID68P`, and `PNP`. Extract filenames may differ:
rename the equivalent files to the expected names or update the paths in
`prepare_inputs()` in `analysis.py`. Obtain data through PSID and follow its
[Conditions of Use](https://simba.isr.umich.edu/U/CondUse.aspx).

Inflation adjustment uses the BLS CPI-U series **CUUR0000SA0**, U.S. city average,
all items, not seasonally adjusted. [code/download_cpi.py](code/download_cpi.py)
uses the [BLS Public Data API](https://www.bls.gov/developers/) and stores the original
JSON responses and source metadata in `data/raw/`. Existing snapshots are reused;
only missing snapshots are downloaded. Annual CPI is the mean of twelve monthly
observations. Income is converted to 2022 dollars before averaging.

## Reproduce the analysis

Open a terminal in the **BLOG6 project root**, not in `code/`. In RStudio, use the
**Terminal** tab rather than the R Console.

Install the packages once:

```bash
python -m pip install -r requirements.txt
```

Then run the complete workflow:

```bash
python code/analysis.py
```

No separate cleaning, regression, or plotting commands are needed. Reading the
income workbook can take several minutes. The script:

1. Loads or downloads CPI and calculates annual adjustment factors.
2. Reads the PSID and FIMS files and reshapes income data into person-wave records.
3. Uses SQL to select personal income and build father-child pairs.
4. Counts eligible pairs at each candidate age and selects the age with the largest common sample.
5. Runs the single-year and average-income regressions on the same pairs.
6. Saves the matched sample, summary tables, and relationship figure.
7. Updates the marked results block in `index.qmd`.

The results block is between `<!-- RESULTS_START -->` and `<!-- RESULTS_END -->`.
A rerun replaces edits inside that block. Text outside it remains unchanged, so
review the methodology and interpretation if a new extract changes the selected
age, sample, or results. Raw input files are not modified.

## How the matching works

Python prepares four SQLite tables:

| Table | Contents |
|---|---|
| `people` | One row per individual with a permanent person ID |
| `relationships` | Biological father-child ID pairs from FIMS |
| `person_year` | Person ID, survey year, age, family ID, household role, and income fields |
| `cpi` | Annual CPI values |

The permanent person ID combines the 1968 family ID and person number. The annual
family interview ID identifies a household in a particular wave; it is not a
permanent individual identifier.

SQL joins FIMS links to the downloaded people. It uses relationship and sequence
codes to select each person's own Head/Reference Person or Spouse/Partner income.
For the selected waves, sequence 1 with relationship 10 identifies the current
reference person; sequence 2 with relationship 20 or 22 identifies the current
spouse or partner. Income for other household members is not reconstructed.

`GROUP BY`, `AVG()`, and `COUNT()` create average income and observation counts for
each person. Separate joins attach the father's and child's measures to the same
pair. Each child has one row; multiple children may share a father.

## Regression design

| Choice | Rule |
|---|---|
| Income-year age | Survey age minus one, because income refers to the preceding year |
| Candidate ages | 30–45 |
| Age selection | Largest number of pairs eligible for both models; ties go closest to 40, then younger |
| Single-year income | Income at the selected approximate age for each generation; earlier year breaks repeated-age ties |
| Average income | Mean real income within seven years on either side of the selected age |
| Minimum coverage | At least three valid income observations per person for the average |
| Log sample | Both single-year incomes and both averages must be positive |
| Recorded zeros | Retained in averages; a selected single-year zero is not replaced with another year |
| Invalid amounts | Missing, negative, and values at or above 9,999,997 are excluded |

Age selection uses sample counts, not estimated coefficients. Both regressions use
the same pairs and unweighted OLS with an intercept. There are no additional
regression controls. The slope of log child income on log father income is the
**intergenerational income elasticity (IGE)**. For the average-income model,
calculate the arithmetic mean of real incomes first, then take its logarithm.
The tutorial reports point estimates without formal statistical inference.

## Current results

The author's local run selected **age 36**, giving **143 pairs and 123 fathers**.

| Income measure for both generations | IGE |
|---|---:|
| Single year at age 36 | 0.220 |
| Average at ages 29–43 | 0.297 |

Fathers contribute an average of 6.4 observations and children 5.1. The mean elapsed
span between first and last records is about eight years. A fifteen-age window
is not fifteen observations or complete coverage of that window.

In `single_vs_average.png`, dots are group means formed by sorting on fathers'
log income within each model. Lines are OLS fits using individual pairs, not fits
to those group means. The two panels need not contain identical group membership.

The larger average-income estimate is consistent with reducing noise from
single-year measurements. It does not isolate the amount of life-cycle bias:
both generations' income measures change, and complete lifetime income is not observed.

## Outputs

The retained tables document the results and main selection choices:

| File | Contents |
|---|---|
| `results/tables/regressions.csv` | IGE, intercept, R squared, pair and father counts |
| `results/tables/age_coverage.csv` | Candidate-age counts and selected age |
| `results/tables/sample_summary.csv` | Observation counts, ages, income years, elapsed spans, and zeros |
| `results/tables/sample_flow.csv` | Counts through the matching and selection stages |
| `results/tables/cpi_annual.csv` | Annual CPI and conversion factors |
| `results/figures/single_vs_average.png` | Single-year and average-income relationship panels |
| `data/processed/matched_sample.csv` | Generated pair-level analysis data |

Rerunning also creates supporting outputs: `income_coverage.csv`, `plot_bins.csv`,
`results_summary.md`, and `blog_results.md` in `results/tables/`. These are generated
summaries rather than additional inputs. They may be omitted from a compact
repository; rerunning recreates them. The obsolete bar chart is not needed.

## Render the blog

With Quarto installed, render a local preview from BLOG6:

```bash
quarto render index.qmd -M draft:false
```

This creates `index.html` and its supporting resources. They are preview outputs,
not inputs to the analysis. Keep them together if using that local HTML preview.
The figure path in BLOG6 is `results/figures/single_vs_average.png`.

For the author's separate website, copy `index.qmd` to `website1/blog/posts/post6/`
and the figure to that post's `figures/` folder. In the website copy of the QMD,
change the image link from `results/figures/single_vs_average.png` to
`figures/single_vs_average.png`, then render the website. The previous automatic
synchronization script has been removed. Analysis results do not automatically
update the website copy.

## Limitations

- Restricting survey years for consistent income definitions reduces the number
  of pairs observed at the same age and the history available for averaging.
- Later biennial interviews also reduce observation counts. Average incomes are
  proxies for lifetime income, covering only part of each person's working life.
- Age is approximate. The selected, unweighted sample requires particular
  household roles and positive log-income measures; recorded zeros and imputed
  income also require care when interpreting results.
- CPI adjusts purchasing power, not labor-market conditions in different periods.

## References

- Panel Study of Income Dynamics, public use dataset. Produced and distributed by
  the Survey Research Center, Institute for Social Research, University of Michigan,
  Ann Arbor, MI (2026). [PSID](https://psidonline.isr.umich.edu/) and
  [identifier and household-role FAQ](https://psidonline.isr.umich.edu/Guide/FAQ.aspx).
- U.S. Bureau of Labor Statistics. CPI-U, series CUUR0000SA0.
  [Public Data API](https://www.bls.gov/developers/).
- Mazumder, B. (2018). [Intergenerational Mobility in the United States: What We Have
  Learned from the PSID](https://pmc.ncbi.nlm.nih.gov/articles/PMC6820674/).
  *The ANNALS*, 680(1), 213–234.
