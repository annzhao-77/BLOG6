from pathlib import Path
import numpy as np
import pandas as pd
from statsmodels.regression.linear_model import OLS
from statsmodels.tools.tools import add_constant

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / 'results/tables'

MODELS = [
    ('young', 'Child near 25; father average', 'father_average', 'child_young'),
    ('mature', 'Child near 40; father average', 'father_average', 'child_mature'),
    ('average', 'Both generations: averages', 'father_average', 'child_average'),
    ('single', 'Both generations: near 40', 'father_mature', 'child_mature')
]


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


def main():
    sample = pd.read_csv(ROOT / 'data/processed/matched_sample.csv')
    TABLES.mkdir(parents=True, exist_ok=True)
    estimates = regressions(sample)
    print(estimates[['label', 'beta', 'ci_low', 'ci_high', 'n_pairs']].to_string(index=False))
    print('Saved results/tables/regressions.csv. Next: run code/03_figures.py')


if __name__ == '__main__':
    main()
