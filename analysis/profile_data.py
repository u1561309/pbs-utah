"""Read-only profiling of the eight source exports. Run from the project folder."""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
tables = {}
for path in sorted(ROOT.iterdir()):
    if path.suffix not in {'.csv', '.txt'}:
        continue
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    tables[path.stem] = df
    columns = {}
    for col in df:
        s = df[col]
        stripped = s.str.strip()
        nonempty = stripped[stripped.ne('')]
        info = {'blank': int(stripped.eq('').sum()), 'unique_nonblank': int(nonempty.nunique()),
                'outer_whitespace': int(s.ne(stripped).sum())}
        if nonempty.nunique() <= 20:
            info['values'] = nonempty.value_counts().to_dict()
        if any(x in col.lower() for x in ['amount', 'percent', 'titles_viewed', 'age', 'capacity']):
            num = pd.to_numeric(nonempty, errors='coerce')
            info['numeric'] = {'invalid': int(num.isna().sum()), 'min': num.min(), 'max': num.max(),
                               'negative': int(num.lt(0).sum()), 'zero': int(num.eq(0).sum()), 'sum': num.sum()}
        if 'date' in col.lower():
            dates = pd.to_datetime(nonempty, errors='coerce', format='mixed')
            info['dates'] = {'invalid': int(dates.isna().sum()), 'min': str(dates.min()), 'max': str(dates.max())}
        columns[col] = info
    print(json.dumps({'file': path.name, 'rows':len(df), 'columns':len(df.columns),
                      'exact_duplicate_excess':int(df.duplicated().sum()), 'profile':columns}, default=str), flush=True)

master = set(tables['constituents_w_memberships']['Constituent ID']) - {''}
for name, df in tables.items():
    for col in df:
        if col in ['donor_id', 'constituent_id', 'synthetic_id', 'Spouse Constituent ID',
                   'Soft Credit Constituent ID'] or col.startswith('constituent_id_'):
            values = set(df[col]) - {''}
            print(json.dumps({'join':name+'.'+col, 'distinct':len(values),
                              'missing_from_constituents':len(values-master),
                              'unmatched_rows':int((df[col].ne('') & ~df[col].isin(master)).sum())}), flush=True)

checks = {
    'constituents_w_memberships':['Constituent ID'], 'campaign_codes':['Marketing Code'],
    'officer_portfolios':['portfolio_id'], 'cultivation':['synthetic_id','fiscal_year'],
    'passport_viewing':['constituent_id','fiscal_year','genre'], 'unite_payments':['payment_id'],
    'soft_credits':['Credit ID'],
}
for name, key in checks.items():
    df = tables[name]
    print(json.dumps({'key_check':name, 'key':key, 'duplicate_excess':int(df.duplicated(key).sum()),
                      'blank_key_rows':int(df[key].eq('').any(axis=1).sum())}), flush=True)

df = tables['unite_payments']
codes = set(tables['campaign_codes']['Marketing Code']) - {''}
print(json.dumps({'campaign_join_unmatched_rows':int((df.marketing_code.ne('') & ~df.marketing_code.isin(codes)).sum()),
                  'campaign_join_nonblank_rows':int(df.marketing_code.ne('').sum())}))
legacy = tables['team_approach_legacy_payments']
idcols = [c for c in legacy if c.startswith('constituent_id_')]
counts = legacy[idcols].ne('').sum(axis=1)
print(json.dumps({'legacy_constituents_per_row':counts.value_counts().sort_index().to_dict()}))
for name in ['cultivation','passport_viewing']:
    df=tables[name]
    print(json.dumps({'year_counts':name,'counts':df.fiscal_year.value_counts().sort_index().to_dict()}))
