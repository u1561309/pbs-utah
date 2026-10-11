"""Reproducible donor EDA using validated Unite payments; invoked by analysis.ipynb."""
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
import json
import uuid

import numpy as np
import pandas as pd


def run_donor_eda(root, cleaned_run):
    root, cleaned_run = Path(root), Path(cleaned_run)
    assert (cleaned_run / '_SUCCESS').exists(), 'Choose a validated cleaning run.'
    source = cleaned_run / 'curated'
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8]
    out = root / 'data' / 'marts' / run_id
    out.mkdir(parents=True, exist_ok=False)
    payments = pd.read_parquet(source / 'unite_payments.parquet')
    people = pd.read_parquet(source / 'constituents.parquet')
    cultivation = pd.read_parquet(source / 'cultivation_assignments.parquet')
    checks = []

    def check(name, actual, expected):
        assert actual == expected, f'{name}: {actual} != {expected}'
        checks.append({'check': name, 'actual': str(actual), 'expected': str(expected), 'passed': True})

    # Exact integer hundredths of source units, without asserting a currency.
    def hundredths(value):
        scaled = value * Decimal(100)
        assert scaled == scaled.to_integral_value(), 'Amount requires more than two decimal places.'
        return int(scaled)

    payments['amount_hundredths'] = payments.payment_amount.map(hundredths).astype('int64')
    resolved = payments.loc[payments.constituent_resolved].copy()
    excluded = payments.loc[~payments.constituent_resolved].copy()
    check('Source count reconciliation', len(resolved) + len(excluded), len(payments))
    check('Source amount reconciliation', int(resolved.amount_hundredths.sum() + excluded.amount_hundredths.sum()), int(payments.amount_hundredths.sum()))
    check('Resolved donor coverage', bool(resolved.donor_id.isin(people.constituent_id).all()), True)
    check('Resolved payment IDs unique', int(resolved.payment_id.duplicated().sum()), 0)
    check('Nonnegative source amounts', bool(payments.amount_hundredths.ge(0).all()), True)

    # Windows are described by exact dates, not assigned fiscal-year names.
    as_of = payments.credit_date.max().normalize()
    earliest = payments.credit_date.min().normalize()
    ends = []
    end = as_of
    while end >= earliest:
        ends.append(end)
        end = end - pd.DateOffset(years=1)
    ends = pd.DatetimeIndex(sorted(ends))
    windows = pd.DataFrame({'period_end': ends})
    windows['period_start'] = windows.period_end.map(lambda x: x - pd.DateOffset(years=1) + pd.Timedelta(days=1))
    windows['label'] = windows.period_start.dt.strftime('%Y-%m-%d') + ' to ' + windows.period_end.dt.strftime('%Y-%m-%d')
    resolved['period_end'] = ends[ends.searchsorted(resolved.credit_date)]
    resolved['positive_payment'] = resolved.amount_hundredths.gt(0)
    resolved['positive_date'] = resolved.credit_date.where(resolved.positive_payment)
    agg = resolved.groupby(['donor_id', 'period_end']).agg(
        giving_hundredths=('amount_hundredths', 'sum'),
        payment_count=('payment_id', 'size'),
        positive_payment_count=('positive_payment', 'sum'),
        largest_payment_hundredths=('amount_hundredths', 'max'),
        first_positive_date=('positive_date', 'min'),
        last_positive_date=('positive_date', 'max'),
    ).reset_index().rename(columns={'donor_id': 'constituent_id'})
    ids = sorted(resolved.donor_id.unique())
    grid = pd.MultiIndex.from_product([ids, ends], names=['constituent_id', 'period_end']).to_frame(index=False)
    panel = grid.merge(agg, on=['constituent_id', 'period_end'], how='left', validate='one_to_one')
    for col in ['giving_hundredths', 'payment_count', 'positive_payment_count', 'largest_payment_hundredths']:
        panel[col] = panel[col].fillna(0).astype('int64')
    panel['donated_in_export'] = panel.giving_hundredths.gt(0)
    panel = panel.merge(windows, on='period_end', validate='many_to_one')
    check('Period panel amount reconciliation', int(panel.giving_hundredths.sum()), int(resolved.amount_hundredths.sum()))
    check('Period panel payment reconciliation', int(panel.payment_count.sum()), len(resolved))
    check('Period panel unique key', int(panel.duplicated(['constituent_id', 'period_end']).sum()), 0)

    monthly = resolved.groupby([resolved.credit_date.dt.to_period('M'), 'donor_id']).agg(
        giving_hundredths=('amount_hundredths', 'sum'),
        payment_count=('payment_id', 'size'), positive_payment_count=('positive_payment', 'sum'),
    ).reset_index().rename(columns={'credit_date': 'month', 'donor_id': 'constituent_id'})
    monthly['month'] = monthly.month.astype(str)
    check('Monthly amount reconciliation', int(monthly.giving_hundredths.sum()), int(resolved.amount_hundredths.sum()))

    features = panel.loc[panel.period_end.eq(as_of)].copy()
    prior_end = ends[-2]
    previous = panel.loc[panel.period_end.eq(prior_end), ['constituent_id', 'giving_hundredths']].rename(columns={'giving_hundredths': 'previous_giving_hundredths'})
    features = features.merge(previous, on='constituent_id', validate='one_to_one')
    history = resolved.groupby('donor_id').agg(
        observed_total_hundredths=('amount_hundredths', 'sum'),
        first_observed_positive_date=('positive_date', 'min'),
        last_observed_positive_date=('positive_date', 'max'),
    ).reset_index().rename(columns={'donor_id': 'constituent_id'})
    features = features.merge(history, on='constituent_id', validate='one_to_one')
    features['recency_days'] = (as_of - features.last_observed_positive_date).dt.days.astype('Int64')
    features['giving_change_hundredths'] = features.giving_hundredths - features.previous_giving_hundredths
    features['giving_change_fraction'] = (features.giving_change_hundredths / features.previous_giving_hundredths.replace(0, np.nan))
    features['giving_pattern'] = np.select([
        features.giving_hundredths.gt(0) & features.previous_giving_hundredths.gt(0),
        features.giving_hundredths.eq(0) & features.previous_giving_hundredths.gt(0),
        features.giving_hundredths.gt(0) & features.previous_giving_hundredths.eq(0),
    ], ['gave_in_both_windows', 'gave_previous_not_latest', 'gave_latest_not_previous'], default='gave_in_neither_window')
    # Current snapshot attributes are descriptive only, not historical predictors.
    features = features.merge(people[['constituent_id', 'constituent_type', 'major_donor_class_pbs_utah', 'sustainer_pbs_utah']], on='constituent_id', validate='one_to_one')
    latest_assignment_year = int(cultivation.fiscal_year.max())
    selected_ids = set(cultivation.loc[cultivation.fiscal_year.eq(latest_assignment_year), 'constituent_id'])
    features['in_latest_recorded_cultivation'] = features.constituent_id.isin(selected_ids)
    features['latest_recorded_cultivation_fy'] = latest_assignment_year
    features['cultivation_scope_note'] = 'Absence is not proof of current unassigned status.'
    features['is_individual'] = features.constituent_type.ne('Organization')

    # No major-donor label or predictive score is manufactured.
    active = features.loc[features.is_individual & features.giving_hundredths.gt(0)].copy()
    cutoff = float(active.giving_hundredths.quantile(.9))
    features['exploratory_top_decile_giving'] = features.is_individual & features.giving_hundredths.gt(0) & features.giving_hundredths.ge(cutoff)
    features['increased_giving_from_positive_base'] = features.previous_giving_hundredths.gt(0) & features.giving_change_hundredths.gt(0)
    review = features.loc[features.exploratory_top_decile_giving].sort_values(
        ['giving_hundredths', 'giving_change_hundredths', 'constituent_id'], ascending=[False, False, True])
    gap_review = review.loc[~review.in_latest_recorded_cultivation].copy()

    summaries = []
    previous_ids = None
    for window in windows.itertuples(index=False):
        part = panel.loc[panel.period_end.eq(window.period_end)]
        active_ids = set(part.loc[part.donated_in_export, 'constituent_id'])
        eligible = len(previous_ids) if previous_ids is not None else None
        retained = len(active_ids & previous_ids) if previous_ids is not None else None
        summaries.append({'period_start': window.period_start, 'period_end': window.period_end,
                          'active_constituents': len(active_ids), 'giving_hundredths': int(part.giving_hundredths.sum()),
                          'prior_active_constituents': eligible, 'retained_constituents': retained,
                          'retention_fraction': retained / eligible if eligible else None})
        previous_ids = active_ids
    period_summary = pd.DataFrame(summaries)
    sensitivity = []
    for threshold in [1000, 2500, 5000, 10000]:
        selected = active.loc[active.giving_hundredths.ge(threshold * 100)]
        sensitivity.append({'illustrative_threshold_source_units': threshold, 'individuals': len(selected),
                            'giving_hundredths': int(selected.giving_hundredths.sum()),
                            'not_in_latest_recorded_cultivation': int((~selected.in_latest_recorded_cultivation).sum())})
    thresholds = pd.DataFrame(sensitivity)
    major_class_summary = features.groupby(features.major_donor_class_pbs_utah.fillna('No recorded class')).agg(
        constituent_count=('constituent_id', 'size'), latest_giving_hundredths=('giving_hundredths', 'sum'),
        active_constituents=('donated_in_export', 'sum')).reset_index()

    outputs = {'constituent_period': panel, 'constituent_month': monthly, 'donor_features': features,
               'exploratory_review_cohort': review, 'cultivation_coverage_review': gap_review}
    for name, frame in outputs.items():
        path = out / (name + '.parquet')
        frame.to_parquet(path, index=False)
        import pyarrow.parquet as pq
        check(name + ': saved rows', pq.ParquetFile(path).metadata.num_rows, len(frame))
    period_summary.to_csv(out / 'period_summary.csv', index=False)
    thresholds.to_csv(out / 'threshold_sensitivity.csv', index=False)
    major_class_summary.to_csv(out / 'major_class_summary.csv', index=False)
    pd.DataFrame(checks).to_csv(out / 'validation_checks.csv', index=False)
    stats = {
        'cleaned_run': str(cleaned_run.relative_to(root)), 'as_of_date': str(as_of.date()),
        'latest_window': windows.iloc[-1].label, 'resolved_payment_rows': len(resolved),
        'excluded_unresolved_rows': len(excluded), 'excluded_unresolved_amount_source_units': str(Decimal(int(excluded.amount_hundredths.sum())) / 100),
        'resolved_amount_source_units': str(Decimal(int(resolved.amount_hundredths.sum())) / 100),
        'observed_resolved_constituents': len(features), 'latest_active_individuals': len(active),
        'top_decile_cutoff_source_units': cutoff / 100, 'review_cohort_individuals': len(review),
        'review_cohort_not_in_latest_recorded_cultivation': len(gap_review),
        'latest_recorded_cultivation_fy': latest_assignment_year, 'validation_checks': len(checks),
        'notes': [
            'Unite payments only. Legacy attribution and soft credits are excluded from these donor cash features.',
            'Periods are explicit trailing 12-month date windows; fiscal-year convention remains unconfirmed.',
            'Zeros in the panel mean no recorded giving in this export, not proof of no giving elsewhere.',
            'Top decile and amount thresholds are exploratory review criteria, not major-donor definitions or predictions.',
            'Current donor classes are descriptive only; Former is not treated as a current major-donor label.',
            'Latest cultivation data is FY2025, so absence does not establish current assignment status.',
            'Viewing is not joined until fiscal-year alignment is confirmed. No unvalidated weighted watch mean is computed.',
            'Cost savings, return on outreach, and specific new funding sources require additional data or research.',
            'Source data contains synthetic placeholders; patterns require validation before operational use.',
        ],
    }
    (out / 'manifest.json').write_text(json.dumps(stats, indent=2) + '\n')
    (out / '_SUCCESS').write_text('All donor EDA validation checks passed.\n')
    return {'output': out, 'stats': stats, 'period_summary': period_summary,
            'thresholds': thresholds, 'major_class_summary': major_class_summary,
            'features': features, 'review': review, 'windows': windows}


def plot_donor_eda(result):
    import matplotlib.pyplot as plt
    summary = result['period_summary']
    features = result['features']
    active = features.loc[features.is_individual & features.giving_hundredths.gt(0)]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    axes[0].plot(summary.period_end, summary.giving_hundredths / 100, marker='o')
    axes[0].set(title='Recorded giving by dated 12-month window', ylabel='Source amount units', xlabel='Window end')
    axes[1].plot(summary.period_end, summary.retention_fraction * 100, marker='o')
    axes[1].set(title='Retention among prior-window donors', ylabel='Percent', xlabel='Window end', ylim=(0, 100))
    axes[2].hist(active.giving_hundredths / 100, bins=np.geomspace(max(.01, active.giving_hundredths.min() / 100), active.giving_hundredths.max() / 100, 40))
    axes[2].set_xscale('log')
    axes[2].set(title='Latest-window individual giving', xlabel='Source amount units (log scale)', ylabel='Individuals')
    for ax in axes[:2]:
        ax.set_xticks(summary.period_end)
        ax.set_xticklabels(summary.period_end.dt.strftime('%Y-%m'), rotation=30, ha='right')
    for ax in axes:
        ax.spines[['top', 'right']].set_visible(False)
    fig.tight_layout()
    path = result['output'] / 'donor_eda.png'
    fig.savefig(path, dpi=150, bbox_inches='tight')
    return fig, path
