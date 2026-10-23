"""Read the downloaded Excel files without changing the originals."""

from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

import pandas as pd

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


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
