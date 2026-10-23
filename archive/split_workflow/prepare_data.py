from pathlib import Path
import sqlite3
import pandas as pd

from download_cpi import main as prepare_cpi
from psid_reader import read_excel_export

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw'
PROCESSED = ROOT / 'data/processed'
TABLES = ROOT / 'results/tables'


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
    for filename in ['01_income.sql', '02_measures.sql', '03_pairs.sql']:
        connection.executescript((ROOT / 'code/sql' / filename).read_text())
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


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    prepare_cpi()
    with sqlite3.connect('') as connection:
        prepare_inputs(connection)
        sample = run_sql(connection)
    print(f'Saved {len(sample)} matched pairs to data/processed/matched_sample.csv')
    print('Next: run code/02_regressions.py')


if __name__ == '__main__':
    main()
