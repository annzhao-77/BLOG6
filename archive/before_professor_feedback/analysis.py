from pathlib import Path
import re
import sqlite3
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from statsmodels.regression.linear_model import OLS
from statsmodels.tools.tools import add_constant

from download_cpi import main as prepare_cpi

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw'
PROCESSED = ROOT / 'data/processed'
TABLES = ROOT / 'results/tables'
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
BLUE = '#236B8E'
ORANGE = '#C16839'
INK = '#263746'

MODELS = [
    ('young', 'Child near 25; father average', 'father_average', 'child_young'),
    ('mature', 'Child near 40; father average', 'father_average', 'child_mature'),
    ('average', 'Both generations: averages', 'father_average', 'child_average'),
    ('single', 'Both generations: near 40', 'father_mature', 'child_mature')
]


INCOME_SQL = """
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
"""

MEASURES_SQL = """
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
"""

PAIRS_SQL = """
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
"""


# Read the Excel exports.
def read_excel_export(path, wanted=None):
    # PSID exports can contain sheet attributes that ordinary Excel readers reject.
    with zipfile.ZipFile(Path(path)) as archive:
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(e.itertext()).strip()
                       for e in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
        columns, records = {}, []
        for _, row in ET.iterparse(archive.open('xl/worksheets/sheet1.xml'), events=('end',)):
            if row.tag != NS + 'row':
                continue
            record = {}
            header = row.get('r') == '1'
            for cell in row:
                letter = re.sub(r'\d+', '', cell.get('r', ''))
                if not header and letter not in columns:
                    continue
                value = cell.find(NS + 'v')
                text = value.text if value is not None else ''
                if cell.get('t') == 's' and text:
                    text = strings[int(text)]
                elif cell.get('t') == 'inlineStr':
                    text = ''.join(cell.itertext()).strip()
                if header:
                    if wanted is None or text in wanted:
                        columns[letter] = text
                else:
                    record[columns[letter]] = text
            if not header:
                records.append(record)
            row.clear()
    result = pd.DataFrame.from_records(records, columns=list(columns.values()))
    if wanted is not None:
        missing = sorted(set(wanted) - set(result.columns))
        if missing:
            raise ValueError(f'Missing variables in {path}: {missing}')
    return result

# Prepare income records and match the two generations.
def prepare_inputs(connection):
    mapping = pd.read_csv(ROOT / 'code/variables.csv')
    wanted = {'ER30001', 'ER30002'} | set(mapping.iloc[:, 1:].values.ravel())
    print('Reading the local income workbook. This can take a few minutes.', flush=True)
    data = read_excel_export(RAW / 'J366544.xlsx', wanted)
    data = data.apply(pd.to_numeric, errors='coerce')
    if data[['ER30001', 'ER30002']].isna().any().any():
        raise ValueError('Missing permanent identifiers.')
    data['person_id'] = (data.ER30001 * 1000 + data.ER30002).astype('int64')
    assert data.person_id.is_unique
    data[['person_id']].to_sql('people', connection, index=False, if_exists='replace')

    family = read_excel_export(RAW / 'fim16212_gid_BO_2_BAL.xlsx')
    family = family.loc[family.PTYPE.str.strip().eq('F')].copy()
    for column in ['ID68', 'PN', 'ID68P', 'PNP']:
        family[column] = pd.to_numeric(family[column], errors='raise')
    links = pd.DataFrame({
        'child_id': (family.ID68 * 1000 + family.PN).astype('int64'),
        'father_id': (family.ID68P * 1000 + family.PNP).astype('int64')
    }).drop_duplicates()
    assert links.groupby('child_id').father_id.nunique().le(1).all()
    assert links.child_id.ne(links.father_id).all()
    links.to_sql('relationships', connection, index=False, if_exists='replace')

    for i, row in mapping.iterrows():
        names = {'family_id': row.family_id, 'sequence_number': row.sequence,
                 'relationship': row.relationship, 'survey_age': row.age,
                 'head_income': row.head_income, 'spouse_income': row.spouse_income}
        wave = data[['person_id', *names.values()]].rename(
            columns={value: key for key, value in names.items()})
        wave['survey_year'] = int(row.survey_year)
        wave.to_sql('person_year', connection, index=False,
                    if_exists='replace' if i == 0 else 'append', chunksize=5000)
    cpi = pd.read_csv(TABLES / 'cpi_annual.csv')
    assert set(mapping.survey_year - 1).issubset(set(cpi.year))
    cpi[['year', 'cpi']].to_sql('cpi', connection, index=False, if_exists='replace')


def run_sql(connection):
    for query in [INCOME_SQL, MEASURES_SQL, PAIRS_SQL]:
        connection.executescript(query)
    checks = [
        ('Unique downloaded people', 'SELECT COUNT(*) FROM people'),
        ('Unique biological father-child links', 'SELECT COUNT(*) FROM relationships'),
        ('Both people found in download', 'SELECT COUNT(*) FROM father_child'),
        ('All required age measures available', 'SELECT COUNT(*) FROM eligible'),
        ('Common positive-log sample', 'SELECT COUNT(*) FROM matched_sample')
    ]
    flow = pd.DataFrame([{'stage': label, 'count': connection.execute(query).fetchone()[0]}
                         for label, query in checks])
    flow.to_csv(TABLES / 'sample_flow.csv', index=False)
    coverage = pd.read_sql_query('''
        SELECT survey_year, income_year, COUNT(*) AS observations,
               SUM(CASE WHEN nominal_income = 0 THEN 1 ELSE 0 END) AS zero_incomes
        FROM income GROUP BY survey_year, income_year ORDER BY survey_year
    ''', connection)
    coverage.to_csv(TABLES / 'income_coverage.csv', index=False)
    sample = pd.read_sql_query('SELECT * FROM matched_sample ORDER BY child_id', connection)
    assert sample.child_id.is_unique
    assert sample.father_n_years.ge(3).all() and sample.child_n_years.ge(3).all()
    assert sample.child_young_age.between(23, 27).all()
    assert sample.child_mature_age.between(38, 42).all()
    if len(sample) < 10 or sample.father_id.nunique() < 2:
        raise ValueError('Too few observations or father clusters for the planned comparison.')
    sample.to_csv(PROCESSED / 'matched_sample.csv', index=False)
    return sample



# Estimate the four income regressions.
def fit_model(sample, x, y):
    design = add_constant(np.log(sample[x]).rename('log_father'))
    return OLS(np.log(sample[y]), design).fit(
        cov_type='cluster', cov_kwds={'groups': sample.father_id,
                                    'use_correction': True, 'df_correction': True},
        use_t=True)


def regressions(sample):
    rows, fitted = [], {}
    for key, label, x, y in MODELS:
        model = fit_model(sample, x, y)
        fitted[key] = model
        low, high = model.conf_int().loc['log_father']
        rows.append({'model': key, 'label': label, 'beta': model.params['log_father'],
                     'se': model.bse['log_father'], 'ci_low': low, 'ci_high': high,
                     'p_value': model.pvalues['log_father'], 'intercept': model.params['const'],
                     'r_squared': model.rsquared, 'n_pairs': len(sample),
                     'n_fathers': sample.father_id.nunique()})
    estimates = pd.DataFrame(rows)
    estimates.to_csv(TABLES / 'regressions.csv', index=False)

    # With the same X and sample, this slope equals beta_mature - beta_young.
    change = np.log(sample.child_mature) - np.log(sample.child_young)
    design = add_constant(np.log(sample.father_average).rename('log_father'))
    difference = OLS(change, design).fit(
        cov_type='cluster', cov_kwds={'groups': sample.father_id,
                                    'use_correction': True, 'df_correction': True}, use_t=True)
    expected = fitted['mature'].params['log_father'] - fitted['young'].params['log_father']
    assert np.isclose(difference.params['log_father'], expected)
    low, high = difference.conf_int().loc['log_father']
    diff = {'comparison': 'mature_minus_young', 'difference': expected,
            'se': difference.bse['log_father'], 'ci_low': low, 'ci_high': high,
            'p_value': difference.pvalues['log_father'], 'n_pairs': len(sample),
            'n_fathers': sample.father_id.nunique()}
    pd.DataFrame([diff]).to_csv(TABLES / 'age_difference.csv', index=False)

    descriptions = []
    for variable in ['child_young_age', 'child_mature_age', 'father_mature_age',
                     'father_mean_age', 'child_mean_age', 'father_n_years', 'child_n_years',
                     'child_young_year', 'child_mature_year', 'father_mature_year',
                     'father_zero_years', 'child_zero_years']:
        descriptions.append({'variable': variable, 'mean': sample[variable].mean(),
                             'min': sample[variable].min(), 'max': sample[variable].max()})
    pd.DataFrame(descriptions).to_csv(TABLES / 'sample_summary.csv', index=False)
    lines = ['# Results from the local run', '',
             'These are estimates from a selected, unweighted matched sample.', '',
             '| Model | Elasticity | 95% CI | Pairs | Fathers |',
             '|---|---:|---|---:|---:|']
    for row in rows:
        lines.append(f"| {row['label']} | {row['beta']:.3f} | [{row['ci_low']:.3f}, {row['ci_high']:.3f}] | {row['n_pairs']} | {row['n_fathers']} |")
    lines += ['', f"Mature minus young: {expected:.3f}; 95% CI [{low:.3f}, {high:.3f}]; p = {diff['p_value']:.4f}.",
              '', 'Intervals use father-clustered standard errors. The difference is estimated directly on the same pairs.',
              'This comparison does not identify pure life-cycle bias: period changes and sample selection remain.',
              'Do not describe a coefficient difference as clear evidence when its interval includes zero.']
    (TABLES / 'results_summary.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return estimates



# Draw the results.
def make_figures(sample, estimates, root):
    root = Path(root)
    output = root / 'results/figures'
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.labelcolor': INK, 'text.color': INK,
                         'axes.titleweight': 'bold', 'savefig.facecolor': 'white'})
    n, fathers = len(sample), sample.father_id.nunique()

    chart = pd.DataFrame({'x': np.log(sample.father_average),
                          'young': np.log(sample.child_young),
                          'mature': np.log(sample.child_mature)})
    # Display group means, not individual income records.
    for bins in [8, 6, 4, 2, 1]:
        chart['bin'] = pd.qcut(chart.x, bins, labels=False, duplicates='drop')
        grouped = chart.groupby('bin').agg(x=('x', 'mean'), young=('young', 'mean'),
                                           mature=('mature', 'mean'), n=('x', 'size'))
        if len(grouped) and grouped.n.min() >= 5:
            break
    if not len(grouped) or grouped.n.min() < 5:
        raise ValueError('Not enough observations for the grouped income figure.')
    grouped.to_csv(root / 'results/tables/plot_bins.csv', index=False)
    all_y = pd.concat([chart.young, chart.mature])
    y_low, y_high = all_y.min() - .25, all_y.max() + .25
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.4), sharex=True, sharey=True)
    for ax, key, title, color in zip(axes, ['young', 'mature'],
                                     ['Child near age 25', 'Child near age 40'], [ORANGE, BLUE]):
        row = estimates.set_index('model').loc[key]
        x = np.linspace(chart.x.min(), chart.x.max(), 100)
        ax.plot(x, row.intercept + row.beta * x, color=color, linewidth=2)
        ax.scatter(grouped.x, grouped[key], s=55, color=color, edgecolor='white', zorder=3)
        ax.set_title(title, loc='left', pad=14)
        ax.set_xlabel('Log of father’s mean real labor income')
        ax.set_ylim(y_low, y_high)
        ax.grid(axis='y', color='#E8ECEF', linewidth=.7)
        ax.text(.03, .96, f"Elasticity = {row.beta:.3f}\n95% CI [{row.ci_low:.3f}, {row.ci_high:.3f}]",
                transform=ax.transAxes, va='top', fontsize=10,
                bbox={'facecolor':'white', 'edgecolor':'none', 'alpha':.9})
    axes[0].set_ylabel('Log of child’s real labor income')
    fig.suptitle('Same families, different ages of income measurement', x=.08, ha='left', fontsize=15)
    fig.text(.08, .02, f'{n} pairs / {fathers} fathers. Dots: group means; lines: OLS on individual pairs.\n'
             'Father income: mean at ages 35–45. Amounts in 2022 dollars. Source: PSID; BLS CPI-U.', fontsize=9)
    fig.subplots_adjust(left=.08, right=.98, bottom=.20, top=.82, wspace=.12)
    fig.savefig(output / 'income_relationships.png', dpi=180)
    plt.close(fig)

    order = ['young', 'mature', 'average', 'single']
    plotted = estimates.set_index('model').loc[order]
    labels = ['Child near 25 / father average', 'Child near 40 / father average',
              'Both generations: ages 35–45 averages', 'Both generations: single year near 40']
    fig, ax = plt.subplots(figsize=(10, 5.8))
    for i, (key, row) in enumerate(plotted.iterrows()):
        color = ORANGE if key == 'young' else BLUE
        ax.errorbar(row.beta, i, xerr=[[row.beta-row.ci_low], [row.ci_high-row.beta]],
                    fmt='o', color=color, capsize=5, markersize=7, linewidth=2)
        ax.annotate(f'{row.beta:.3f}', (row.beta, i), xytext=(0, 12),
                    textcoords='offset points', ha='center', fontsize=10)
    ax.set_yticks(range(4), labels)
    ax.set_ylim(3.55, -.65)
    ax.axvline(0, color='#89949D', linestyle='--', linewidth=1)
    ax.grid(axis='x', color='#E8ECEF', linewidth=.7)
    ax.set_xlabel('Estimated income elasticity (95% confidence interval)')
    ax.set_title('How the income measure changes the estimate', loc='left', fontsize=15, pad=24)
    fig.text(.04, .03, f'All models use the same {n} pairs. Intervals cluster by father ({fathers} clusters).\n'
             'Unweighted OLS; association, not a causal effect. Source: PSID; BLS CPI-U.', fontsize=9)
    fig.subplots_adjust(left=.40, right=.97, bottom=.20, top=.82)
    fig.savefig(output / 'regression_comparison.png', dpi=180)
    plt.close(fig)


def main():
    for folder in [PROCESSED, TABLES, ROOT / 'results/figures']:
        folder.mkdir(parents=True, exist_ok=True)
    prepare_cpi()
    with sqlite3.connect('') as connection:
        prepare_inputs(connection)
        sample = run_sql(connection)
    estimates = regressions(sample)
    make_figures(sample, estimates, ROOT)
    print(f'Finished: {len(sample)} pairs from {sample.father_id.nunique()} fathers.')
    print('Tables: results/tables/. Figures: results/figures/.')


if __name__ == '__main__':
    main()
