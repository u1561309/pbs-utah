"""Evaluate the frozen upgrade policy without fitting or selecting on test data."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import uuid

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss

from analysis.upgrade_model import feature_matrix, baseline_scores


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evaluate_frozen_policy(root, model_run):
    root, model_run = Path(root).resolve(), Path(model_run).resolve()
    assert (model_run / '_SUCCESS').exists()
    source = json.loads((model_run / 'manifest.json').read_text())
    readiness = root / source['source_readiness_run']
    dataset = readiness / 'historical_donor_cohorts.parquet'
    assert sha256(dataset) == source['source_dataset_sha256']
    selected = source['selected_method']
    assert selected == 'logistic_regression', 'Review a changed model selection before evaluation.'
    # Freeze the benchmark using validation only, before reading test data.
    validation = pd.read_csv(model_run / 'validation_capacity_metrics.csv')
    overall = pd.read_csv(model_run / 'validation_overall_metrics.csv')
    primary = validation.loc[validation.capacity.eq(source['primary_capacity'])]
    benchmark = primary.loc[~primary.method.isin(['logistic_regression', 'shallow_tree'])].merge(
        overall[['method', 'average_precision']], on='method').sort_values(
        ['tie_adjusted_upgrades', 'average_precision', 'method'], ascending=[False, False, True]).iloc[0].method
    model_path = model_run / (selected + '.joblib')
    run = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8]
    out = root / 'data' / 'final_evaluation' / run
    out.mkdir(parents=True, exist_ok=False)
    policy = {
        'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
        'source_model_run': str(model_run.relative_to(root)),
        'model_sha256': sha256(model_path), 'dataset_sha256': sha256(dataset),
        'feature_code_sha256': sha256(root / 'analysis' / 'upgrade_model.py'),
        'target': source['target'], 'definition': source['upgrade_definition'],
        'selected_method': selected, 'benchmark': benchmark,
        'primary_capacity': source['primary_capacity'], 'secondary_capacities': source['capacities'],
        'tie_policy': 'Uniform expected selection among equal scores at boundary; IDs order saved lists only.',
        'model_policy': 'Use saved training-only model and preprocessing unchanged; no refit or tuning.',
        'test_policy': '12-month horizon and suggested_split=test only.',
        'status': 'Historical evaluation of an illustrative policy, not an approved outreach plan.',
    }
    (out / 'frozen_policy.json').write_text(json.dumps(policy, indent=2) + '\n')
    test = pd.read_parquet(dataset, filters=[('horizon_months', '=', 12), ('suggested_split', '=', 'test')])
    checks = []

    def check(name, value):
        if not bool(value):
            raise AssertionError(name)
        checks.append({'check': name, 'passed': True})

    check('One test row per donor', not test.constituent_id.duplicated().any())
    check('One prediction cutoff', test.cutoff_date.nunique() == 1)
    check('Validation labels precede test cutoff', pd.Timestamp(source['validation_outcome_end']) <= test.cutoff_date.min())
    check('Test history precedes prediction cutoff', test.last_observed_payment_date.le(test.cutoff_date).all())
    check('Future outcomes follow cutoff', test.outcome_end.gt(test.cutoff_date).all())
    X = feature_matrix(test)
    check('Frozen predictor order', list(X.columns) == source['feature_names'])
    model = joblib.load(model_path)
    scores = {
        selected: model.predict_proba(X)[:, 1],
        benchmark: baseline_scores(test)[benchmark],
    }
    check('Bounded finite model scores', np.isfinite(scores[selected]).all() and
          ((scores[selected] >= 0) & (scores[selected] <= 1)).all())
    sample = test.head(100).copy()
    changed = sample.copy()
    for col in changed:
        if col.startswith('target_'):
            changed[col] = False
        elif col.startswith('outcome_') and col.endswith('_hundredths'):
            changed[col] = 999999999
    check('Outcome changes cannot alter predictors', feature_matrix(sample).equals(feature_matrix(changed)))
    y = test[source['target']].astype(int).to_numpy()
    check('Both test classes present', len(np.unique(y)) == 2)
    prevalence = float(y.mean())
    rows, totals = [], []
    historical = test[['constituent_id', 'cutoff_date', 'outcome_end', source['target']]].copy()
    for method, score in scores.items():
        historical[method] = score
        order = pd.DataFrame({'id': test.constituent_id.to_numpy(), 'score': score, 'label': y}).sort_values(
            ['score', 'id'], ascending=[False, True], kind='stable')
        for capacity in source['capacities']:
            top = order.head(min(capacity, len(order)))
            boundary = top.score.iloc[-1]
            above, tied = order.loc[order.score.gt(boundary)], order.loc[order.score.eq(boundary)]
            expected = float(above.label.sum() + (len(top) - len(above)) * tied.label.mean())
            rows.append({'method': method, 'capacity': len(top), 'deterministic_upgrades': int(top.label.sum()),
                         'tie_adjusted_upgrades': expected, 'precision': expected / len(top),
                         'recall': expected / y.sum(), 'lift': expected / len(top) / prevalence,
                         'random_expected_upgrades': len(top) * prevalence, 'boundary_tie_count': len(tied)})
        totals.append({'method': method, 'average_precision': average_precision_score(y, score),
                       'roc_auc': roc_auc_score(y, score),
                       'brier_score': brier_score_loss(y, score) if method == selected else np.nan})
    metrics, overall_test = pd.DataFrame(rows), pd.DataFrame(totals)
    primary_test = metrics.loc[metrics.capacity.eq(source['primary_capacity'])]
    check('Only frozen methods evaluated', set(metrics.method) == {selected, benchmark})
    check('Saved model unchanged', sha256(model_path) == policy['model_sha256'])
    metrics.to_csv(out / 'test_capacity_metrics.csv', index=False)
    overall_test.to_csv(out / 'test_overall_metrics.csv', index=False)
    historical.to_parquet(out / 'historical_test_scores.parquet', index=False)
    check('Persisted test scores retain cohort', len(pd.read_parquet(out / 'historical_test_scores.parquet')) == len(test))
    pd.DataFrame(checks).to_csv(out / 'validation_checks.csv', index=False)
    manifest = {**policy, 'output': str(out.relative_to(root)), 'test_rows': len(test),
                'test_positive_outcomes': int(y.sum()), 'test_prevalence': prevalence,
                'cutoff_date': str(test.cutoff_date.min().date()),
                'outcome_end': str(test.outcome_end.max().date()),
                'validation_checks': len(checks), 'test_scored': True,
                'limitations': ['Test is now consumed; further selection on it would invalidate its holdout role.',
                                'Synthetic data; historical propensity is not incremental outreach impact.',
                                'Capacity remains illustrative; current eligibility and assignments are unavailable.',
                                'No significance claim, calibrated probabilities or current prospect scores.']}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (out / '_SUCCESS').write_text('Frozen policy, temporal and persisted score checks passed.\n')
    return {'output': out, 'manifest': manifest, 'metrics': metrics, 'overall': overall_test,
            'primary': primary_test}
