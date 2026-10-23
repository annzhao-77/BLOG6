from pathlib import Path
import json
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/checks'
d = pd.read_pickle(OUT / 'download_cache.pkl')
f = pd.read_pickle(OUT / 'fims_cache.pkl')
for c in ['ID68', 'PN', 'ID68P', 'PNP']:
    f[c] = pd.to_numeric(f[c], errors='coerce')
d['pid'] = d.ER30001 * 1000 + d.ER30002
f['child'] = f.ID68 * 1000 + f.PN
f['father'] = f.ID68P * 1000 + f.PNP
pairs = f[f.PTYPE.str.strip().eq('F')][['child', 'father']].drop_duplicates()
matched = pairs[pairs.child.isin(d.pid) & pairs.father.isin(d.pid)].copy()

years = [1994,1995,1996,1997,1999,2001,2003,2005,2007,2009,2011,2013,2015,2017,2019,2021,2023]
prefix = ['331','332','333','334','335','336','337','338','339','340','341','342','343','345','347','349','351']
heads = 'ER4140 ER6980 ER9231 ER12080 ER16463 ER20443 ER24116 ER27931 ER40921 ER46829 ER52237 ER58038 ER65216 ER71293 ER77315 ER81642 ER85496'.split()
spouses = 'ER4144 ER6984 ER9235 ER12082 ER16465 ER20447 ER24135 ER27943 ER40933 ER46841 ER52249 ER58050 ER65244 ER71321 ER77343 ER81670 ER85524'.split()
panels = []
coverage = []
for year, pre, head, spouse in zip(years,prefix,heads,spouses):
    seq, rel = d['ER'+pre+'02'], d['ER'+pre+'03']
    age = d['ER'+pre+('05' if year==2015 else '04')] - 1
    income = pd.Series(np.nan, index=d.index)
    income.loc[seq.eq(1) & rel.eq(10)] = d.loc[seq.eq(1) & rel.eq(10), head]
    income.loc[seq.eq(2) & rel.isin([20,22])] = d.loc[seq.eq(2) & rel.isin([20,22]), spouse]
    # This is an eligibility check, not the final treatment of zero incomes/topcodes.
    valid = income.gt(0) & income.lt(9999997) & age.between(18,90)
    panels.append(pd.DataFrame({'pid':d.pid[valid], 'year':year-1, 'age':age[valid], 'income':income[valid]}))
    coverage.append({'survey_year':year, 'positive_income_people':int(valid.sum())})
p = pd.concat(panels, ignore_index=True)
counts = p[p.age.between(35,45)].groupby('pid').size()
young = set(p.loc[p.age.between(23,27),'pid'])
mature = set(p.loc[p.age.between(38,42),'pid'])
avg = set(counts[counts.ge(3)].index)
matched['father_average'] = matched.father.isin(avg)
matched['child_young'] = matched.child.isin(young)
matched['child_mature'] = matched.child.isin(mature)
matched['child_average'] = matched.child.isin(avg)
common = matched[matched[['father_average','child_young','child_mature','child_average']].all(axis=1)]
summary = {
 'data_rows':len(d), 'data_columns':len(d.columns)-1,
 'duplicate_person_ids':int(d.pid.duplicated().sum()),
 'fims_rows':len(f), 'unique_father_child_pairs':len(pairs),
 'pairs_with_both_ids_in_download':len(matched),
 'children_with_multiple_fathers':int(pairs.groupby('child').father.nunique().gt(1).sum()),
 'father_average_pairs':int(matched.father_average.sum()),
 'father_average_and_child_young':int((matched.father_average & matched.child_young).sum()),
 'father_average_and_child_mature':int((matched.father_average & matched.child_mature).sum()),
 'both_averages':int((matched.father_average & matched.child_average).sum()),
 'common_three_comparisons':len(common),
 'common_distinct_fathers':int(common.father.nunique()),
 'common_also_father_single_near40':int(common.father.isin(mature).sum()),
 'notes':'Preliminary positive-income coverage only. Survey age minus one approximates income-year age. 1994-2023 survey waves. Average windows 35-45, >=3 positive observations; young23-27, mature38-42. No CPI adjustment or final regression yet.'
}
(OUT/'eligibility_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
pd.DataFrame(coverage).to_csv(OUT/'coverage.csv',index=False)
print(json.dumps(summary,indent=2))
