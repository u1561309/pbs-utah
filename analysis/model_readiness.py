"""Count prospective donor outcomes and prepare dated, payment-only features."""
from pathlib import Path
from datetime import datetime, timezone
import json
import uuid
import pandas as pd


def assess_model_readiness(root, eda_run):
    root, eda_run = Path(root), Path(eda_run)
    assert (eda_run / '_SUCCESS').exists()
    panel = pd.read_parquet(eda_run / 'constituent_period.parquet')
    features = pd.read_parquet(eda_run / 'donor_features.parquet')
    # Identity/type is used for population filtering, not as a historical predictor.
    individual_ids = set(features.loc[features.is_individual, 'constituent_id'])
    panel = panel.loc[panel.constituent_id.isin(individual_ids)].copy()
    ends = sorted(panel.period_end.unique())
    thresholds = [500, 1000, 2500, 5000, 10000]
    checks, rows, cohorts = [], [], []
    out = root / 'data' / 'model_readiness' / (
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8])
    out.mkdir(parents=True, exist_ok=False)

    def check(name, value):
        assert bool(value), name
        checks.append({'check': name, 'passed': True})

    for horizon_periods in [1, 2]:
        for i in range(len(ends) - horizon_periods):
            cutoff = pd.Timestamp(ends[i])
            outcome_end = pd.Timestamp(ends[i + horizon_periods])
            past = panel.loc[panel.period_end.le(cutoff)]
            base = panel.loc[panel.period_end.eq(cutoff) & panel.giving_hundredths.gt(0)].copy()
            # Eligibility uses only positive giving before the cutoff, not future activity.
            base = base.rename(columns={
                'giving_hundredths': 'prior_12m_giving_hundredths',
                'positive_payment_count': 'prior_12m_positive_payment_count',
                'largest_payment_hundredths': 'prior_12m_largest_payment_hundredths',
            })
            base = base[['constituent_id', 'prior_12m_giving_hundredths',
                         'prior_12m_positive_payment_count', 'prior_12m_largest_payment_hundredths']]
            history = past.groupby('constituent_id').agg(
                observed_past_total_hundredths=('giving_hundredths', 'sum'),
                observed_past_largest_payment_hundredths=('largest_payment_hundredths', 'max'),
                last_observed_payment_date=('last_positive_date', 'max'),
                first_observed_payment_date=('first_positive_date', 'min'),
            ).reset_index()
            base = base.merge(history, on='constituent_id', validate='one_to_one')
            base['recency_days_at_cutoff'] = (cutoff - base.last_observed_payment_date).dt.days
            base['observed_tenure_days_at_cutoff'] = (cutoff - base.first_observed_payment_date).dt.days
            if i:
                previous = panel.loc[panel.period_end.eq(ends[i-1]), ['constituent_id', 'giving_hundredths']].rename(
                    columns={'giving_hundredths': 'prior_previous_12m_giving_hundredths'})
                base = base.merge(previous, on='constituent_id', how='left', validate='one_to_one')
            else:
                # Earlier history is absent, not a known zero.
                base['prior_previous_12m_giving_hundredths'] = pd.NA
            base['prior_previous_12m_giving_hundredths'] = base.prior_previous_12m_giving_hundredths.astype('Int64')
            future = panel.loc[panel.period_end.gt(cutoff) & panel.period_end.le(outcome_end)].groupby('constituent_id').agg(
                outcome_total_hundredths=('giving_hundredths', 'sum'),
                outcome_largest_payment_hundredths=('largest_payment_hundredths', 'max'),
            ).reset_index()
            frame = base.merge(future, on='constituent_id', how='left', validate='one_to_one')
            check(f'{cutoff.date()} {horizon_periods*12}m: complete outcome panel', frame.outcome_total_hundredths.notna().all())
            frame['cutoff_date'] = cutoff
            frame['outcome_start'] = cutoff + pd.Timedelta(days=1)
            frame['outcome_end'] = outcome_end
            frame['horizon_months'] = horizon_periods * 12
            frame['target_retained'] = frame.outcome_total_hundredths.gt(0)
            if horizon_periods == 1:
                # An explicitly illustrative upgrade rule: >=25% and >=25 source units.
                difference = frame.outcome_total_hundredths - frame.prior_12m_giving_hundredths
                frame['target_upgrade_25pct_and_25units'] = (
                    frame.outcome_total_hundredths * 100 >= frame.prior_12m_giving_hundredths * 125
                ) & difference.ge(2500)
            else:
                # Comparing a 24-month total with a 12-month baseline would inflate upgrades.
                frame['target_upgrade_25pct_and_25units'] = pd.NA

            for threshold in thresholds:
                frame[f'target_total_ge_{threshold}'] = frame.outcome_total_hundredths.ge(threshold * 100)
                frame[f'target_single_payment_ge_{threshold}'] = frame.outcome_largest_payment_hundredths.ge(threshold * 100)
            targets = ['target_retained'] + [f'target_{kind}_ge_{t}' for t in thresholds for kind in ['total', 'single_payment']]
            if horizon_periods == 1:
                targets += ['target_upgrade_25pct_and_25units']
            for target in targets:
                positive = int(frame[target].sum())
                rows.append({'cutoff_date': cutoff, 'outcome_start': cutoff + pd.Timedelta(days=1),
                             'outcome_end': outcome_end, 'horizon_months': horizon_periods * 12,
                             'target': target, 'eligible_active_individuals': len(frame),
                             'positive_outcomes': positive, 'negative_outcomes': len(frame)-positive,
                             'positive_fraction': positive/len(frame) if len(frame) else None})
            check(f'{cutoff.date()} {horizon_periods*12}m: historical dates precede cutoff', frame.last_observed_payment_date.le(cutoff).all())
            check(f'{cutoff.date()} {horizon_periods*12}m: eligible baseline positive', frame.prior_12m_giving_hundredths.gt(0).all())
            cohorts.append(frame)

    dataset = pd.concat(cohorts, ignore_index=True)
    check('Unique donor / cutoff / horizon', not dataset.duplicated(['constituent_id', 'cutoff_date', 'horizon_months']).any())
    last_end = pd.Timestamp(ends[-1])
    # 12m: training outcomes end <=2024, validation ends 2025, test ends 2026.
    # 24m: train outcomes end <=2024; final test predicts 2024->2026.
    # A separate 24m validation cohort would leave no temporally valid training cohort.
    dataset['suggested_split'] = 'unused_for_final_split'
    one = dataset.horizon_months.eq(12)
    dataset.loc[one & dataset.outcome_end.le(last_end - pd.DateOffset(years=2)), 'suggested_split'] = 'train'
    dataset.loc[one & dataset.outcome_end.eq(last_end - pd.DateOffset(years=1)), 'suggested_split'] = 'validation'
    dataset.loc[one & dataset.outcome_end.eq(last_end), 'suggested_split'] = 'test'
    two = dataset.horizon_months.eq(24)
    dataset.loc[two & dataset.outcome_end.le(last_end - pd.DateOffset(years=2)), 'suggested_split'] = 'train'
    dataset.loc[two & dataset.outcome_end.eq(last_end), 'suggested_split'] = 'test'
    for horizon in [12, 24]:
        part = dataset.loc[dataset.horizon_months.eq(horizon)]
        train = part.loc[part.suggested_split.eq('train')]
        test = part.loc[part.suggested_split.eq('test')]
        check(f'{horizon}m: train labels known by test cutoff', train.outcome_end.max() <= test.cutoff_date.min())
        if horizon == 12:
            val = part.loc[part.suggested_split.eq('validation')]
            check('12m: train labels known by validation cutoff', train.outcome_end.max() <= val.cutoff_date.min())
            check('12m: validation labels known by test cutoff', val.outcome_end.max() <= test.cutoff_date.min())
    dataset['target_upgrade_25pct_and_25units'] = dataset.target_upgrade_25pct_and_25units.astype('boolean')
    dataset.to_parquet(out / 'historical_donor_cohorts.parquet', index=False)
    counts = pd.DataFrame(rows)
    counts.to_csv(out / 'outcome_counts.csv', index=False)
    split_rows = []
    for (horizon, split), group in dataset.groupby(['horizon_months', 'suggested_split']):
        for target in [c for c in dataset if c.startswith('target_')]:
            valid = group[target].notna()
            if not valid.any():
                continue
            selected = group.loc[valid]
            positive = selected[target].astype(bool)
            split_rows.append({'horizon_months': horizon, 'split': split, 'target': target,
                               'donor_cutoff_rows': len(selected), 'unique_donors': selected.constituent_id.nunique(),
                               'positive_outcomes': int(positive.sum()),
                               'unique_positive_donors': selected.loc[positive, 'constituent_id'].nunique(),
                               'positive_fraction': float(positive.mean())})
    split_summary = pd.DataFrame(split_rows)
    split_summary.to_csv(out / 'split_summary.csv', index=False)
    pd.DataFrame(checks).to_csv(out / 'validation_checks.csv', index=False)
    manifest = {
        'source_eda_run': str(eda_run.relative_to(root)), 'rows': len(dataset), 'validation_checks': len(checks),
        'population': 'Individuals with positive recorded giving in the 12 months before each cutoff.',
        'amount_unit': 'Integer hundredths of source units; currency unconfirmed.',
        'upgrade_rule': '12m future total >=125% of prior 12m giving AND increase >=25 source units; illustrative.',
        'major_rules': 'Separate illustrative future aggregate giving and largest single-payment thresholds. A payment is not necessarily a whole gift or pledge.',
        'features': ['prior_12m_giving_hundredths', 'prior_12m_positive_payment_count',
                     'prior_12m_largest_payment_hundredths', 'observed_past_total_hundredths',
                     'observed_past_largest_payment_hundredths', 'recency_days_at_cutoff',
                     'observed_tenure_days_at_cutoff', 'prior_previous_12m_giving_hundredths'],
        'notes': [
            'Outcome amounts, target_* columns, and outcome dates must not be used as predictive features.',
            'Earlier years of tenure and giving are left-truncated by the export start; they are not lifetime measures.',
            'Repeated donor-cutoff observations are not independent; unique positive donor counts are reported.',
            'No current donor classes, snapshot lifetime values, viewing, or cultivation flags are historical features.',
            '12m has chronological train/validation/test cohorts; 24m has train/test only without a clean separate validation cohort.',
            'Absence of future payments means no observed giving in this export; source completeness is not established.',
            'Counts assess feasibility, not predictive performance or the effect of contacting a donor.',
        ],
    }
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (out / '_SUCCESS').write_text('Historical feature timing and split validation passed.\n')
    return {'output': out, 'counts': counts, 'split_summary': split_summary, 'manifest': manifest}
