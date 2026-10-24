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
TARGET_AGE = None
AGE_MIN, AGE_MAX = 30, 45
HALF_WINDOW = 7

MODELS = [
    ('single', 'Single year at selected age', 'father_mature', 'child_mature'),
    ('average', 'Average within selected age window', 'father_average', 'child_average')
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
WHERE age BETWEEN {age_low} AND {age_high}
GROUP BY person_id
HAVING COUNT(*) >= 3;

CREATE TABLE mature AS
WITH candidates AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY person_id
               ORDER BY income_year
           ) AS choice
    FROM income
    WHERE age = {target_age}
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
       pm.real_income AS father_mature,
       cm.real_income AS child_mature,
       pa.n_years AS father_n_years,
       ca.n_years AS child_n_years,
       pa.mean_age AS father_mean_age,
       ca.mean_age AS child_mean_age,
       pa.zero_years AS father_zero_years,
       ca.zero_years AS child_zero_years,
       pa.first_year AS father_first_year,
       pa.last_year AS father_last_year,
       ca.first_year AS child_first_year,
       ca.last_year AS child_last_year,
       pa.last_year - pa.first_year AS father_span,
       ca.last_year - ca.first_year AS child_span,
       pm.age AS father_mature_age,
       cm.age AS child_mature_age,
       pm.income_year AS father_mature_year,
       cm.income_year AS child_mature_year
FROM father_child AS f
JOIN averages AS pa ON f.father_id = pa.person_id
JOIN averages AS ca ON f.child_id = ca.person_id
JOIN mature AS pm ON f.father_id = pm.person_id
JOIN mature AS cm ON f.child_id = cm.person_id;

CREATE TABLE matched_sample AS
SELECT * FROM eligible
WHERE father_average > 0 AND child_average > 0
  AND father_mature > 0 AND child_mature > 0;
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
    global TARGET_AGE, MODELS
    connection.executescript(INCOME_SQL)
    # Count eligible pairs before fitting any regression.
    def build_sample(age):
        for table in ['averages', 'mature', 'father_child', 'eligible', 'matched_sample']:
            connection.execute(f'DROP TABLE IF EXISTS {table}')
        connection.executescript(MEASURES_SQL.format(
            target_age=age, age_low=age-HALF_WINDOW, age_high=age+HALF_WINDOW))
        connection.executescript(PAIRS_SQL)

    counts = []
    for age in range(AGE_MIN, AGE_MAX + 1):
        build_sample(age)
        single_pairs = connection.execute('''
            SELECT COUNT(*) FROM father_child f
            JOIN mature p ON f.father_id = p.person_id
            JOIN mature c ON f.child_id = c.person_id
            WHERE p.real_income > 0 AND c.real_income > 0
        ''').fetchone()[0]
        common_pairs = connection.execute('SELECT COUNT(*) FROM matched_sample').fetchone()[0]
        counts.append({'age': age, 'single_year_pairs': single_pairs,
                       'common_pairs': common_pairs})
    age_counts = pd.DataFrame(counts)
    # Maximize the sample usable in BOTH models; ties go closest to 40, then younger.
    TARGET_AGE = min(counts, key=lambda r: (-r['common_pairs'], abs(r['age']-40), r['age']))['age']
    age_counts['selected'] = age_counts.age.eq(TARGET_AGE)
    age_counts.to_csv(TABLES / 'age_coverage.csv', index=False)
    build_sample(TARGET_AGE)
    MODELS = [
        ('single', f'Single year at age {TARGET_AGE}', 'father_mature', 'child_mature'),
        ('average', f'Average at ages {TARGET_AGE-7}–{TARGET_AGE+7}', 'father_average', 'child_average')
    ]
    print(f'Selected age {TARGET_AGE} using common-pair counts only. See results/tables/age_coverage.csv.')
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
    assert sample.child_mature_age.eq(TARGET_AGE).all()
    assert sample.father_mature_age.eq(TARGET_AGE).all()
    if len(sample) < 10:
        raise ValueError('Too few matched pairs for this comparison.')
    sample.to_csv(PROCESSED / 'matched_sample.csv', index=False)
    return sample



# Compare single-year and average income on the same pairs.
def regressions(sample):
    rows = []
    for key, label, x, y in MODELS:
        log_father = np.log(sample[x]).rename('log_father')
        if log_father.nunique() < 2:
            raise ValueError('Father income needs variation to estimate a slope.')
        model = OLS(np.log(sample[y]), add_constant(log_father)).fit()
        rows.append({'model': key, 'label': label,
                     'beta': model.params['log_father'],
                     'intercept': model.params['const'],
                     'r_squared': model.rsquared,
                     'n_pairs': len(sample),
                     'n_fathers': sample.father_id.nunique()})
    estimates = pd.DataFrame(rows)
    estimates.to_csv(TABLES / 'regressions.csv', index=False)

    variables = ['father_n_years', 'child_n_years', 'father_span', 'child_span',
                 'father_mean_age', 'child_mean_age', 'father_mature_age',
                 'child_mature_age', 'father_first_year', 'father_last_year',
                 'child_first_year', 'child_last_year',
                 'father_zero_years', 'child_zero_years']
    summary = sample[variables].agg(['mean', 'min', 'max']).T
    summary.index.name = 'variable'
    summary.to_csv(TABLES / 'sample_summary.csv')
    lines = ['# Single-year and multi-year income', '',
             '| Model | IGE | R squared | Pairs | Fathers |',
             '|---|---:|---:|---:|---:|']
    for row in rows:
        lines.append(f"| {row['label']} | {row['beta']:.3f} | {row['r_squared']:.3f} | {row['n_pairs']} | {row['n_fathers']} |")
    lines += ['', 'Both models use the same pairs. No formal inference is reported.',
              f'Averages use available observations at ages {TARGET_AGE-7}–{TARGET_AGE+7}, not necessarily 15 annual incomes.',
              'See sample_summary.csv for actual counts, ages, and spans.']
    (TABLES / 'results_summary.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return estimates


def make_figures(sample, estimates, root):
    output = root / 'results/figures'
    plt.rcParams.update({'font.size': 11, 'axes.spines.top': False,
                         'axes.spines.right': False, 'savefig.facecolor': 'white'})
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.5), sharex=True, sharey=True)
    ranges_x, ranges_y, bins_output = [], [], []
    for ax, (key, label, x, y), color in zip(axes, MODELS, [ORANGE, BLUE]):
        chart = pd.DataFrame({'x': np.log(sample[x]), 'y': np.log(sample[y])})
        for bins in [8, 6, 4, 2, 1]:
            chart['bin'] = pd.qcut(chart.x, bins, labels=False, duplicates='drop')
            grouped = chart.groupby('bin').agg(x=('x', 'mean'), y=('y', 'mean'), n=('x', 'size'))
            if len(grouped) and grouped.n.min() >= 5:
                break
        if not len(grouped) or grouped.n.min() < 5:
            raise ValueError('Too few observations for grouped figure.')
        grouped['model'] = key
        bins_output.append(grouped)
        row = estimates.set_index('model').loc[key]
        grid = np.linspace(grouped.x.min(), grouped.x.max(), 100)
        fitted = row.intercept + row.beta * grid
        ranges_x.extend(grid)
        ranges_y.extend(grouped.y)
        ranges_y.extend(fitted)
        ax.scatter(grouped.x, grouped.y, color=color, s=45, zorder=3)
        ax.plot(grid, fitted, color=color, linewidth=2)
        ax.set_title(label, loc='left')
        ax.set_xlabel("Log of father's real labor income")
        ax.text(.04, .94, f'IGE = {row.beta:.3f}', transform=ax.transAxes,
                va='top', bbox={'facecolor': 'white', 'edgecolor': 'none', 'alpha': .9})
        ax.grid(axis='y', alpha=.2)
    axes[0].set_xlim(min(ranges_x)-.2, max(ranges_x)+.2)
    axes[0].set_ylim(min(ranges_y)-.3, max(ranges_y)+.5)
    axes[0].set_ylabel("Log of child's real labor income")
    fig.suptitle('One year or several years of income?', x=.08, ha='left', fontsize=16)
    fig.text(.08, .03, f'{len(sample)} pairs. Dots: group means; lines: OLS on individual pairs.\n'
             f'Amounts in 2022 dollars. Average: observed incomes at ages {TARGET_AGE-7}–{TARGET_AGE+7}. Source: PSID; BLS.', fontsize=9)
    fig.subplots_adjust(left=.08, right=.98, bottom=.20, top=.82)
    fig.savefig(output / 'single_vs_average.png', dpi=180)
    plt.close(fig)
    pd.concat(bins_output).to_csv(TABLES / 'plot_bins.csv', index=False)


def write_blog_results(sample, estimates):
    values = estimates.set_index('model').beta
    single, average = values['single'], values['average']
    text = f"""Both models use **{len(sample)} pairs and {sample.father_id.nunique()} fathers**.

| Income measure | IGE |
|---|---:|
| Single year at age {TARGET_AGE} | {single:.3f} |
| Average at ages {TARGET_AGE-7}–{TARGET_AGE+7} | {average:.3f} |

![Income associations. Dots are group means; lines are OLS fits using individual pairs.](results/figures/single_vs_average.png)

"""
    (TABLES / 'blog_results.md').write_text(text, encoding='utf-8')
    article = ROOT / 'index.qmd'
    source = article.read_text(encoding='utf-8')
    start, end = '<!-- RESULTS_START -->', '<!-- RESULTS_END -->'
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError('The article needs one RESULTS_START and RESULTS_END marker.')
    before, remainder = source.split(start, 1)
    _, after = remainder.split(end, 1)
    article.write_text(before+start+'\n\n'+text+'\n'+end+after, encoding='utf-8')


def main():
    for folder in [PROCESSED, TABLES, ROOT / 'results/figures']:
        folder.mkdir(parents=True, exist_ok=True)
    prepare_cpi()
    with sqlite3.connect('') as connection:
        prepare_inputs(connection)
        sample = run_sql(connection)
    estimates = regressions(sample)
    make_figures(sample, estimates, ROOT)
    write_blog_results(sample, estimates)
    print(estimates[['label', 'beta', 'n_pairs']].to_string(index=False))
    print('Saved tables, figures, and the results section in BLOG6/index.qmd.')
    print('Next: python code/sync_website.py')


if __name__ == '__main__':
    main()
