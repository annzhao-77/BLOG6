from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BLUE = '#236B8E'
ORANGE = '#C16839'
INK = '#263746'


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
