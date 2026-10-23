from pathlib import Path
import pandas as pd
from figures import make_figures

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    sample = pd.read_csv(ROOT / 'data/processed/matched_sample.csv')
    estimates = pd.read_csv(ROOT / 'results/tables/regressions.csv')
    make_figures(sample, estimates, ROOT)
    print('Saved both figures in results/figures/.')
