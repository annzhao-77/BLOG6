"""Copy the draft and any locally generated figures to the existing website."""

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT.parent / 'website1/blog/posts/post6'
DESTINATION.mkdir(parents=True, exist_ok=True)
(DESTINATION / 'figures').mkdir(exist_ok=True)
shutil.copy2(ROOT / 'index.qmd', DESTINATION / 'index.qmd')
for name in ['single_vs_average.png']:
    source = ROOT / 'results/figures' / name
    if source.exists():
        shutil.copy2(source, DESTINATION / 'figures' / name)
print('Copied the QMD and available figures. No data or analysis code were copied.')
