"""Descriptive channel, segment, viewing and cultivation EDA; no model fitting."""
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
import argparse
import hashlib
import json
import uuid

import numpy as np
import pandas as pd


def run_extended_eda(root, cleaned_run, donor_run):
    root = Path(root).resolve()
    cleaned_run, donor_run = Path(cleaned_run).resolve(), Path(donor_run).resolve()
    for run in [cleaned_run, donor_run]:
        if not (run / '_SUCCESS').exists():
            raise ValueError(f'Validated source run required: {run}')
    source = cleaned_run / 'curated'
    donor_manifest = json.loads((donor_run / 'manifest.json').read_text())
    if (root / donor_manifest['cleaned_run']).resolve() != cleaned_run:
        raise ValueError('Donor EDA and cleaned inputs must refer to the same source run.')
    payments = pd.read_parquet(source / 'unite_payments.parquet')
    campaigns = pd.read_parquet(source / 'campaigns.parquet')
    people = pd.read_parquet(source / 'constituents.parquet')
    viewing = pd.read_parquet(source / 'viewing_annual_genre.parquet')
    cultivation = pd.read_parquet(source / 'cultivation_assignments.parquet')
    portfolios = pd.read_parquet(source / 'portfolios.parquet')
    panel = pd.read_parquet(donor_run / 'constituent_period.parquet')
    features = pd.read_parquet(donor_run / 'donor_features.parquet')
    checks = []

    def check(name, value):
        if not bool(value):
            raise AssertionError(name)
        checks.append({'check': name, 'passed': True})

    def hundredths(value):
        scaled = value * Decimal(100)
        if scaled != scaled.to_integral_value():
            raise ValueError('More than two decimals in source amount.')
        return int(scaled)

    payments['amount_hundredths'] = payments.payment_amount.map(hundredths).astype('int64')
    before_rows, before_total = len(payments), int(payments.amount_hundredths.sum())
    payments = payments.merge(campaigns[['marketing_code', 'communication_method']],
                              on='marketing_code', how='left', validate='many_to_one', indicator=True)
    payments['channel'] = payments.communication_method.fillna('Unmapped')
    payments['window_end'] = (payments.credit_date.dt.year + payments.credit_date.dt.month.gt(6).astype(int)).astype(str) + '-06-30'
    payments['window_end'] = pd.to_datetime(payments.window_end)
    payments['positive_donor'] = payments.donor_id.where(payments.amount_hundredths.gt(0))
    check('Campaign join preserves rows', len(payments) == before_rows)
    check('Campaign join preserves exact amount', int(payments.amount_hundredths.sum()) == before_total)
    check('Panel constituent-period keys unique', not panel.duplicated(['constituent_id', 'period_end']).any())
    check('Viewing constituent-year-genre keys unique', not viewing.duplicated(['constituent_id', 'fiscal_year', 'genre']).any())
    individual_ids = set(people.loc[people.constituent_type.ne('Organization'), 'constituent_id'])

    def payment_summary(frame, keys):
        summary = frame.groupby(keys, dropna=False).agg(
            payments=('payment_id', 'size'), giving_hundredths=('amount_hundredths', 'sum'),
            positive_donors=('positive_donor', 'nunique'),
            median_payment_hundredths=('amount_hundredths', 'median')).reset_index()
        summary['giving_source_units'] = summary.giving_hundredths / 100
        summary['median_payment_source_units'] = summary.median_payment_hundredths / 100
        summary['mean_payment_source_units'] = summary.giving_hundredths / summary.payments / 100
        return summary

    channel_totals = payment_summary(payments, ['channel'])
    channel_totals['cash_share'] = channel_totals.giving_hundredths / before_total
    check('Channel totals reconcile', int(channel_totals.giving_hundredths.sum()) == before_total)
    channel_windows = payment_summary(payments, ['window_end', 'channel'])
    tender_totals = payment_summary(payments, ['tender_type'])
    check('Tender totals reconcile', int(tender_totals.giving_hundredths.sum()) == before_total)
    campaign_totals = payment_summary(payments, ['marketing_code', 'campaign_name', 'channel'])
    campaign_totals = campaign_totals.sort_values(['giving_hundredths', 'marketing_code'], ascending=[False, True])
    check('Campaign totals reconcile', int(campaign_totals.giving_hundredths.sum()) == before_total)
    seasonality = payment_summary(payments, [payments.credit_date.dt.month.rename('calendar_month')])
    check('Month totals reconcile', int(seasonality.giving_hundredths.sum()) == before_total)
    calendar_months = payment_summary(payments, [payments.credit_date.dt.to_period('M').astype(str).rename('calendar_month')])
    check('Year-month totals reconcile', int(calendar_months.giving_hundredths.sum()) == before_total)
    payments['recorded_constituent_type'] = payments.donor_id.map(people.set_index('constituent_id').constituent_type).fillna('Unresolved')
    tender_segments = payment_summary(payments, ['tender_type', 'recorded_constituent_type'])
    check('Tender-type constituent mix reconciles', int(tender_segments.giving_hundredths.sum()) == before_total)

    # Segments are current-snapshot descriptions, never historical predictors.
    latest = features.loc[features.is_individual & features.giving_hundredths.gt(0)].copy()
    segment_tables = []
    for col in ['sustainer_pbs_utah', 'major_donor_class_pbs_utah', 'constituent_type', 'giving_pattern']:
        frame = latest.copy()
        frame['segment_value'] = frame[col].astype('string').fillna('Not recorded')
        summary = frame.groupby('segment_value').agg(
            donors=('constituent_id', 'size'), giving_hundredths=('giving_hundredths', 'sum'),
            median_giving_hundredths=('giving_hundredths', 'median'),
            median_positive_payments=('positive_payment_count', 'median')).reset_index()
        summary['segment'] = col
        summary['giving_source_units'] = summary.giving_hundredths / 100
        summary['median_giving_source_units'] = summary.median_giving_hundredths / 100
        check(col + ': segment donors reconcile', int(summary.donors.sum()) == len(latest))
        check(col + ': segment cash reconciles', int(summary.giving_hundredths.sum()) == int(latest.giving_hundredths.sum()))
        segment_tables.append(summary)
    segments = pd.concat(segment_tables, ignore_index=True)

    # Assign channel at baseline, never using next-window payments.
    individual_payments = payments.loc[payments.constituent_resolved & payments.donor_id.isin(individual_ids)]
    channel_donor = individual_payments.groupby(['donor_id', 'window_end', 'channel']).amount_hundredths.sum().reset_index()
    channel_donor = channel_donor.loc[channel_donor.amount_hundredths.gt(0)].copy()
    channel_donor['max_channel_amount'] = channel_donor.groupby(['donor_id', 'window_end']).amount_hundredths.transform('max')
    dominant = channel_donor.loc[channel_donor.amount_hundredths.eq(channel_donor.max_channel_amount)].copy()
    dominant['ties'] = dominant.groupby(['donor_id', 'window_end']).channel.transform('size')
    dominant.loc[dominant.ties.gt(1), 'channel'] = 'Tied dominant channels'
    dominant = dominant.drop_duplicates(['donor_id', 'window_end']).rename(
        columns={'donor_id': 'constituent_id', 'window_end': 'period_end'})
    baseline = panel.loc[panel.constituent_id.isin(individual_ids) & panel.giving_hundredths.gt(0),
                         ['constituent_id', 'period_end', 'giving_hundredths']].copy()
    baseline = baseline.merge(dominant[['constituent_id', 'period_end', 'channel']],
                              on=['constituent_id', 'period_end'], how='left', validate='one_to_one')
    check('Baseline channel coverage', baseline.channel.notna().all())
    baseline['next_period_end'] = baseline.period_end + pd.DateOffset(years=1)
    future = panel[['constituent_id', 'period_end', 'giving_hundredths']].rename(
        columns={'period_end': 'next_period_end', 'giving_hundredths': 'next_giving_hundredths'})
    pairs = baseline.merge(future, on=['constituent_id', 'next_period_end'], how='inner', validate='one_to_one')
    pairs['retained'] = pairs.next_giving_hundredths.gt(0)
    pairs['upgraded'] = ((pairs.next_giving_hundredths * 4 >= pairs.giving_hundredths * 5) &
                         (pairs.next_giving_hundredths - pairs.giving_hundredths >= 2500))
    transition_summary = pairs.groupby(['period_end', 'next_period_end', 'channel']).agg(
        baseline_donors=('constituent_id', 'size'), retained=('retained', 'sum'),
        upgrades=('upgraded', 'sum'), baseline_cash_hundredths=('giving_hundredths', 'sum')).reset_index()
    transition_summary['retention_fraction'] = transition_summary.retained / transition_summary.baseline_donors
    transition_summary['upgrade_fraction'] = transition_summary.upgrades / transition_summary.baseline_donors
    check('Baseline cohorts do not duplicate donors', not pairs.duplicated(['constituent_id', 'period_end']).any())
    check('Transition summaries reconcile donors', int(transition_summary.baseline_donors.sum()) == len(pairs))

    viewing_years = viewing.groupby('fiscal_year').agg(
        viewing_rows=('constituent_id', 'size'), recorded_viewers=('constituent_id', 'nunique'),
        summed_genre_title_counts=('titles_viewed', 'sum'),
        median_row_watch_fraction=('mean_watch_fraction', 'median')).reset_index()
    viewing_genres = viewing.groupby(['fiscal_year', 'genre']).agg(
        recorded_viewers=('constituent_id', 'nunique'), summed_genre_title_counts=('titles_viewed', 'sum'),
        median_row_watch_fraction=('mean_watch_fraction', 'median')).reset_index()
    check('Viewing title count summaries reconcile', int(viewing_years.summed_genre_title_counts.sum()) == int(viewing.titles_viewed.sum()))
    view_person = viewing.groupby(['constituent_id', 'fiscal_year']).agg(
        summed_genre_title_counts=('titles_viewed', 'sum'), recorded_genres=('genre', 'nunique')).reset_index()
    # Conditional sensitivity, not a validated fiscal-calendar crosswalk.
    view_associations = []
    for interpretation in ['FY_label_is_June_end_year', 'FY_label_is_July_start_year']:
        frame = view_person.copy()
        end_year = frame.fiscal_year + (1 if interpretation.endswith('start_year') else 0)
        frame['period_end'] = pd.to_datetime(end_year.astype(str) + '-06-30')
        joined = pairs.merge(frame.drop(columns='fiscal_year'), on=['constituent_id', 'period_end'],
                             how='left', validate='one_to_one')
        check(interpretation + ': viewing join preserves cohort', len(joined) == len(pairs))
        joined['viewing_group'] = np.select([
            joined.summed_genre_title_counts.isna().to_numpy(dtype=bool),
            joined.summed_genre_title_counts.lt(10).fillna(False).to_numpy(dtype=bool),
            joined.summed_genre_title_counts.lt(30).fillna(False).to_numpy(dtype=bool)],
            ['No viewing record', 'Recorded 1-9', 'Recorded 10-29'], default='Recorded 30+')
        summary = joined.groupby(['period_end', 'next_period_end', 'viewing_group']).agg(
            baseline_donors=('constituent_id', 'size'), retained=('retained', 'sum'), upgrades=('upgraded', 'sum')).reset_index()
        summary['calendar_assumption'] = interpretation
        summary['retention_fraction'] = summary.retained / summary.baseline_donors
        summary['upgrade_fraction'] = summary.upgrades / summary.baseline_donors
        view_associations.append(summary)
    viewing_sensitivity = pd.concat(view_associations, ignore_index=True)

    cultivation_detail = cultivation.merge(portfolios[['portfolio_id', 'officer_id', 'capacity', 'rollout_fy']],
                                            on='portfolio_id', how='left', validate='many_to_one')
    check('Portfolio join preserves cultivation rows', len(cultivation_detail) == len(cultivation))
    check('Portfolio reference coverage', cultivation_detail.officer_id.notna().all())
    cultivation_summary = cultivation_detail.groupby(['fiscal_year', 'portfolio_id', 'officer_id'], dropna=False).agg(
        selected=('selected', 'sum'), contacted=('contacted', 'sum'), holdout=('holdout', 'sum'),
        adopted=('program_adopted', 'sum'), stated_capacity=('capacity', 'first')).reset_index()
    cultivation_summary['selected_to_capacity_ratio'] = cultivation_summary.selected / cultivation_summary.stated_capacity
    cultivation_summary['contact_fraction'] = cultivation_summary.contacted / cultivation_summary.selected
    check('Cultivation flags are complementary', cultivation_detail.contacted.ne(cultivation_detail.holdout).all())
    check('Selected cohort coverage', cultivation_detail.selected.all())
    check('Cultivation summaries reconcile', int(cultivation_summary.selected.sum()) == len(cultivation))

    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8]
    out = root / 'data' / 'extended_eda' / run_id
    out.mkdir(parents=True, exist_ok=False)
    outputs = {
        'channel_totals': channel_totals.sort_values('giving_hundredths', ascending=False),
        'channel_windows': channel_windows, 'tender_totals': tender_totals,
        'campaign_totals': campaign_totals, 'seasonality': seasonality,
        'calendar_months': calendar_months, 'tender_constituent_mix': tender_segments,
        'latest_individual_segments': segments, 'channel_transitions': transition_summary,
        'viewing_years': viewing_years, 'viewing_genres': viewing_genres,
        'viewing_calendar_sensitivity': viewing_sensitivity, 'cultivation_portfolio_summary': cultivation_summary,
    }
    for name, table in outputs.items():
        table.to_csv(out / (name + '.csv'), index=False)
        check(name + ': saved rows', len(pd.read_csv(out / (name + '.csv'))) == len(table))
    pd.DataFrame(checks).to_csv(out / 'validation_checks.csv', index=False)
    unmapped = payments.loc[payments.channel.eq('Unmapped')]
    notes = [
        'Synthetic data: these patterns generate hypotheses, not station-level operational conclusions.',
        'Channels are campaign-reference communication methods, not payment tender or proven solicitation exposure.',
        'Payment channel totals include unresolved donors and organizations; transition/segment cohorts include resolved individuals only.',
        'A donor can appear in multiple payment channel totals; donor counts cannot be added across channels.',
        'No exposure, costs or staff effort: channel cash shares are not response rates, ROI or incremental effects.',
        'Current segment labels are snapshot descriptions; no historical status or causal effect is inferred.',
        'Viewing counts sum genre-level title counts; they are not confirmed distinct titles. Missing records are not zero viewing.',
        'Viewing/giving joins are explicitly conditional on two hypothetical July-June mappings; neither is confirmed.',
        'Annual contact/holdout flags do not establish randomization, detailed outreach effort or causality.',
        'Period zeros mean no recorded giving in supplied exports; completeness outside those exports is unknown.',
        'This is post-test descriptive EDA. It does not tune or revalidate the frozen upgrade model.',
    ]
    manifest = {
        'cleaned_run': str(cleaned_run.relative_to(root)), 'donor_run': str(donor_run.relative_to(root)),
        'source_manifest_hashes': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in [cleaned_run / 'metadata' / 'manifest.json', donor_run / 'manifest.json']},
        'latest_window_end': str(panel.period_end.max().date()), 'payment_rows': len(payments),
        'payment_amount_source_units': before_total / 100,
        'unmapped_channel_rows': len(unmapped), 'unmapped_amount_source_units': int(unmapped.amount_hundredths.sum()) / 100,
        'validation_checks': len(checks), 'outputs': list(outputs), 'notes': notes,
    }
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (out / '_SUCCESS').write_text('Descriptive EDA and saved aggregate checks passed.\n')
    return {'output': out, 'manifest': manifest, **outputs}


def plot_extended_eda(result):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    channels = result['channel_totals'].sort_values('giving_hundredths')
    axes[0, 0].barh(channels.channel, channels.cash_share * 100)
    axes[0, 0].set(title='Campaign-reference channel: recorded cash share', xlabel='Percent of all Unite cash')
    season = result['seasonality']
    axes[0, 1].bar(season.calendar_month, season.giving_source_units)
    axes[0, 1].set(title='Calendar-month cash, pooled across six years', xlabel='Calendar month', ylabel='Source units')
    axes[0, 1].set_xticks(range(1, 13))
    views = result['viewing_years']
    axes[1, 0].plot(views.fiscal_year, views.recorded_viewers, marker='o')
    axes[1, 0].set(title='Recorded viewers by source FY label', xlabel='Source FY label', ylabel='Distinct recorded viewers')
    port = result['cultivation_portfolio_summary'].groupby('portfolio_id').contact_fraction.mean()
    axes[1, 1].bar(port.index, port * 100)
    axes[1, 1].set(title='Contact fraction within selected cultivation cohort', xlabel='Portfolio', ylabel='Percent', ylim=(0, 100))
    for ax in axes.flat:
        ax.spines[['top', 'right']].set_visible(False)
    fig.tight_layout()
    path = result['output'] / 'extended_eda.png'
    fig.savefig(path, dpi=150, bbox_inches='tight')
    return fig, path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cleaned-run', required=True)
    parser.add_argument('--donor-run', required=True)
    args = parser.parse_args()
    result = run_extended_eda(Path.cwd(), args.cleaned_run, args.donor_run)
    plot_extended_eda(result)
    print(result['output'])
    print('Validation checks:', result['manifest']['validation_checks'])
