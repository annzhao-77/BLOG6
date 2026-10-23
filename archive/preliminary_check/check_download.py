from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
import re
import json
import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

def read_psid(path):
    # Read PSID's Excel XML directly; some exports contain unusual sheet settings.
    with zipfile.ZipFile(path) as z:
        strings = [''.join(e.itertext()).strip() for e in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        records = []
        for _, row in ET.iterparse(z.open('xl/worksheets/sheet1.xml'), events=('end',)):
            if row.tag != NS + 'row':
                continue
            values = []
            for cell in row:
                value = cell.find(NS + 'v')
                text = value.text if value is not None else ''
                values.append(strings[int(text)] if cell.get('t') == 's' else text)
            records.append(values)
            row.clear()
    return pd.DataFrame(records[1:], columns=records[0])

if __name__ == '__main__':
    out = ROOT / 'results' / 'checks'
    out.mkdir(parents=True, exist_ok=True)
    text = '\n'.join(p.extract_text() for p in PdfReader(Path.home() / 'Desktop/J366544_codebook.pdf').pages)
    (out / 'codebook_text.txt').write_text(text, encoding='utf-8')
    d = read_psid(Path.home() / 'Downloads/J366544.xlsx').apply(pd.to_numeric, errors='coerce')
    f = read_psid(ROOT / 'data/fim16212_gid_BO_2_BAL.xlsx')
    print('Loaded', d.shape, f.shape, flush=True)
    d.to_pickle(out / 'download_cache.pkl')
    f.to_pickle(out / 'fims_cache.pkl')
    print(d.columns.tolist(), flush=True)
