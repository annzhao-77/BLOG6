"""Save the BLS responses and calculate annual CPI-U averages."""

from datetime import datetime, timezone
import json
from pathlib import Path
import urllib.request

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'
TABLES = ROOT / 'results' / 'tables'
SERIES = 'CUUR0000SA0'


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    rows = []
    sources = []
    for start, end in [(1993, 2002), (2003, 2012), (2013, 2022)]:
        path = RAW / f'cpi_u_{start}_{end}.json'
        url = (f'https://api.bls.gov/publicAPI/v2/timeseries/data/{SERIES}'
               f'?startyear={start}&endyear={end}')
        if not path.exists():
            with urllib.request.urlopen(url, timeout=60) as response:
                content = response.read()
            payload = json.loads(content)
            if payload.get('status') != 'REQUEST_SUCCEEDED':
                raise ValueError(payload)
            path.write_bytes(content)
        payload = json.loads(path.read_text(encoding='utf-8'))
        if payload['status'] != 'REQUEST_SUCCEEDED':
            raise ValueError(f'BLS request failed: {path.name}')
        series = payload['Results']['series'][0]
        assert series['seriesID'] == SERIES
        for item in series['data']:
            if item['period'] in [f'M{m:02d}' for m in range(1, 13)]:
                rows.append({'year': int(item['year']),
                             'month': int(item['period'][1:]),
                             'cpi': float(item['value'])})
        sources.append({'file': path.name, 'url': url})

    monthly = pd.DataFrame(rows).sort_values(['year', 'month'])
    assert not monthly.duplicated(['year', 'month']).any()
    assert set(monthly.year) == set(range(1993, 2023))
    assert monthly.groupby('year').size().eq(12).all()
    annual = monthly.groupby('year', as_index=False).agg(cpi=('cpi', 'mean'))
    base = annual.loc[annual.year.eq(2022), 'cpi'].iloc[0]
    annual['to_2022_dollars'] = base / annual.cpi
    annual.to_csv(TABLES / 'cpi_annual.csv', index=False)
    metadata_path = RAW / 'cpi_sources.json'
    if not metadata_path.exists():
        metadata = {
            'retrieved_utc': datetime.now(timezone.utc).isoformat(),
            'series_id': SERIES,
            'description': 'CPI-U, U.S. city average, all items, not seasonally adjusted',
            'index_base': '1982-84 = 100',
            'sources': sources,
            'annual_method': 'Arithmetic mean of all 12 monthly observations; not rounded before deflation',
            'income_base_year': 2022
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(f'Saved {len(monthly)} monthly observations and {len(annual)} annual averages.')
    print(annual.iloc[[0, -1]].to_string(index=False))


if __name__ == '__main__':
    main()
