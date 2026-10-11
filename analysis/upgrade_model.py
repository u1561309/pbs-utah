"""Fixed first-pass upgrade models and ranking baselines; test labels stay reserved."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import uuid

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text


TARGET = 'target_upgrade_25pct_and_25units'
CAPACITIES = [100, 250, 500, 1000]
PRIMARY_CAPACITY = 500  # Illustrative comparison capacity, not an approved outreach budget.


def feature_matrix(frame):
    """Payment-only predictors; no outcome or current-snapshot columns."""
    units = {
        'prior_12m_giving_hundredths': 100,
        'prior_12m_positive_payment_count': 1,
        'prior_12m_largest_payment_hundredths': 100,
        'observed_past_total_hundredths': 100,
        'observed_past_largest_payment_hundredths': 100,
        'recency_days_at_cutoff': 1,
        'observed_tenure_days_at_cutoff': 1,
        'prior_previous_12m_giving_hundredths': 100,
    }
    out = pd.DataFrame(index=frame.index)
    for col, divisor in units.items():
        values = frame[col].astype(float) / divisor
        assert values.dropna().ge(0).all(), col
        out['log1p_' + col.removesuffix('_hundredths')] = np.log1p(values)
    previous = frame.prior_previous_12m_giving_hundredths.astype(float)
    out['past_giving_growth_clipped'] = (
        (frame.prior_12m_giving_hundredths - previous) / previous.clip(lower=100)
    ).clip(-10, 10)
    assert not np.isinf(out.to_numpy()).any()
    return out


def baseline_scores(frame):
    previous = frame.prior_previous_12m_giving_hundredths.astype(float)
    growth = ((frame.prior_12m_giving_hundredths - previous) / previous.clip(lower=100)).clip(-10, 10)
    return {
        'higher_prior_giving': frame.prior_12m_giving_hundredths.astype(float).to_numpy(),
        'lower_prior_giving': -frame.prior_12m_giving_hundredths.astype(float).to_numpy(),
        'more_frequent_payments': frame.prior_12m_positive_payment_count.astype(float).to_numpy(),
        'more_recent_giving': -frame.recency_days_at_cutoff.astype(float).to_numpy(),
        'past_giving_growth': growth.fillna(-np.inf).to_numpy(),
    }


def assess_upgrade_models(root, readiness_run):
    root, readiness_run = Path(root), Path(readiness_run)
    assert (readiness_run / '_SUCCESS').exists()
    data_path = readiness_run / 'historical_donor_cohorts.parquet'
    # Predicate filtering deliberately excludes the final test cohort.
    data = pd.read_parquet(data_path, filters=[
        ('horizon_months', '=', 12), ('suggested_split', 'in', ['train', 'validation'])])
    train = data.loc[data.suggested_split.eq('train')].copy()
    validation = data.loc[data.suggested_split.eq('validation')].copy()
    checks = []

    def check(name, value):
        assert bool(value), name
        checks.append({'check': name, 'passed': True})

    check('No test cohort read for model comparison', set(data.suggested_split) == {'train', 'validation'})
    check('Training labels known by validation cutoff', train.outcome_end.max() <= validation.cutoff_date.min())
    check('Validation donor IDs unique', not validation.constituent_id.duplicated().any())
    check('Payment history precedes each cutoff', data.last_observed_payment_date.le(data.cutoff_date).all())
    X_train, X_val = feature_matrix(train), feature_matrix(validation)
    check('Predictor columns match', list(X_train.columns) == list(X_val.columns))
    check('Outcome names absent from predictors', not any(c.startswith(('target_', 'outcome_')) for c in X_train))
    y_train, y_val = train[TARGET].astype(int), validation[TARGET].astype(int)
    check('Training and validation contain both outcomes', y_train.nunique() == 2 and y_val.nunique() == 2)

    # Fixed choices for a first comparison; no search on test outcomes.
    models = {
        'logistic_regression': Pipeline([
            ('imputer', SimpleImputer(strategy='median', add_indicator=True)),
            ('scale', StandardScaler()),
            ('classifier', LogisticRegression(C=1.0, max_iter=2000, random_state=42)),
        ]),
        'shallow_tree': Pipeline([
            ('imputer', SimpleImputer(strategy='median', add_indicator=True)),
            ('classifier', DecisionTreeClassifier(max_depth=3, min_samples_leaf=500, random_state=42)),
        ]),
    }
    scores = baseline_scores(validation)
    for name, model in models.items():
        model.fit(X_train, y_train)
        check(name + ': fitted preprocessing uses only train', model.named_steps['imputer'].n_features_in_ == X_train.shape[1])
        if name == 'logistic_regression':
            check('Logistic regression converged', int(model.named_steps['classifier'].n_iter_.max()) < 2000)
        scores[name] = model.predict_proba(X_val)[:, 1]
        check(name + ': finite bounded scores', np.isfinite(scores[name]).all() and ((scores[name] >= 0) & (scores[name] <= 1)).all())

    population_rate = float(y_val.mean())
    metric_rows, overall_rows = [], []
    rankings = validation[['constituent_id', 'cutoff_date', 'outcome_end', TARGET]].copy()
    for name, score in scores.items():
        rankings[name] = score
        order = pd.DataFrame({'id': validation.constituent_id.to_numpy(), 'score': score, 'label': y_val.to_numpy()}).sort_values(
            ['score', 'id'], ascending=[False, True], kind='stable')
        for capacity in CAPACITIES:
            top = order.head(min(capacity, len(order)))
            hits = int(top.label.sum())
            precision = hits / len(top)
            boundary = top.score.iloc[-1]
            above = order.loc[order.score.gt(boundary)]
            tied = order.loc[order.score.eq(boundary)]
            slots = len(top) - len(above)
            # Fair comparison when rules/tree leaves give many donors equal scores.
            expected_hits = float(above.label.sum() + slots * tied.label.mean())
            metric_rows.append({'method': name, 'capacity': len(top), 'upgrades_found': hits,
                                'precision': precision, 'recall': hits / int(y_val.sum()),
                                'lift_over_random': precision / population_rate,
                                'tie_adjusted_upgrades': expected_hits,
                                'tie_adjusted_precision': expected_hits / len(top),
                                'tie_adjusted_lift': expected_hits / len(top) / population_rate,
                                'random_expected_upgrades': len(top) * population_rate,
                                'ties_at_boundary': int(order.score.eq(top.score.iloc[-1]).sum())})
        # -inf denotes missing historical-growth information for a ranking rule.
        finite_score = np.where(np.isfinite(score), score, -1e12)
        overall_rows.append({'method': name, 'average_precision': average_precision_score(y_val, finite_score),
                             'roc_auc': roc_auc_score(y_val, finite_score),
                             'brier_score': brier_score_loss(y_val, score) if name in models else np.nan})
    metrics = pd.DataFrame(metric_rows)
    overall = pd.DataFrame(overall_rows)
    primary = metrics.loc[metrics.capacity.eq(PRIMARY_CAPACITY)].merge(overall, on='method')
    primary = primary.sort_values(['tie_adjusted_upgrades', 'average_precision', 'method'], ascending=[False, False, True])
    selected = primary.iloc[0].method

    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8]
    out = root / 'data' / 'models' / run_id
    out.mkdir(parents=True, exist_ok=False)
    metrics.to_csv(out / 'validation_capacity_metrics.csv', index=False)
    overall.to_csv(out / 'validation_overall_metrics.csv', index=False)
    rankings.to_parquet(out / 'historical_validation_scores.parquet', index=False)
    for name, model in models.items():
        joblib.dump(model, out / (name + '.joblib'))
        restored = joblib.load(out / (name + '.joblib'))
        check(name + ': saved model scores match', np.allclose(restored.predict_proba(X_val.iloc[:100])[:, 1], scores[name][:100]))

    logistic = models['logistic_regression']
    names = logistic.named_steps['imputer'].get_feature_names_out(X_train.columns)
    coefficients = pd.DataFrame({'feature': names, 'standardized_coefficient': logistic.named_steps['classifier'].coef_[0]})
    coefficients['odds_ratio_per_standard_deviation'] = np.exp(coefficients.standardized_coefficient)
    coefficients.sort_values('standardized_coefficient', ascending=False).to_csv(out / 'logistic_coefficients.csv', index=False)
    tree = models['shallow_tree']
    tree_names = tree.named_steps['imputer'].get_feature_names_out(X_train.columns)
    (out / 'tree_rules.txt').write_text(export_text(tree.named_steps['classifier'], feature_names=list(tree_names)))
    pd.DataFrame(checks).to_csv(out / 'validation_checks.csv', index=False)
    manifest = {
        'source_readiness_run': str(readiness_run.relative_to(root)),
        'source_dataset_sha256': hashlib.sha256(data_path.read_bytes()).hexdigest(),
        'target': TARGET, 'upgrade_definition': 'At least 25% and 25 source units more than prior 12m giving.',
        'training_rows': len(train), 'training_positive_outcomes': int(y_train.sum()),
        'validation_rows': len(validation), 'validation_positive_outcomes': int(y_val.sum()),
        'validation_prevalence': population_rate,
        'validation_cutoff': str(validation.cutoff_date.min().date()),
        'validation_outcome_end': str(validation.outcome_end.max().date()),
        'capacities': CAPACITIES, 'primary_capacity': PRIMARY_CAPACITY,
        'selected_method': selected,
        'selection_rule': 'Most tie-adjusted expected validation upgrades in top 500; average precision breaks ties, then method name.',
        'feature_names': list(X_train.columns), 'validation_checks': len(checks),
        'software_versions': {'pandas': pd.__version__, 'numpy': np.__version__, 'sklearn': sklearn.__version__, 'joblib': joblib.__version__},
        'test_scored': False,
        'notes': [
            'Fixed L2 logistic regression and a depth-3 decision tree are first-pass candidates, not an exhaustive search.',
            'Median imputation, missingness indicators, and scaling are fitted on training only.',
            'Scores are ranking estimates; probability calibration has not been validated separately.',
            'Tied scores use constituent ID for deterministic ordering; this ID is not a predictor.',
            'Selection and plotted precision average uniformly over tied candidates at the capacity boundary, rather than depending on ID order.',
            'Training includes repeated donor-cutoff observations; validation has one row per donor.',
            'Top-500 is an illustrative capacity; staff availability has not been supplied.',
            'Validation results are used for selection and are not unbiased final performance estimates.',
            'Lower prior giving can make percentage-based upgrades easier; upgrade propensity is not gift size or wealth.',
            'Historical score files are retrospective, not current outreach instructions.',
            'Synthetic data limits operational validity; likelihood of upgrade does not estimate an outreach effect.',
        ],
    }
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (out / '_SUCCESS').write_text('Training, temporal separation, scoring and model reload checks passed.\n')
    return {'output': out, 'manifest': manifest, 'metrics': metrics, 'overall': overall,
            'primary_comparison': primary, 'coefficients': coefficients}


def plot_upgrade_comparison(result):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 5))
    metrics = result['metrics']
    for method, group in metrics.groupby('method'):
        ax.plot(group.capacity, group.tie_adjusted_precision * 100, marker='o', label=method.replace('_', ' '))
    ax.axhline(result['manifest']['validation_prevalence'] * 100, color='gray', linestyle='--', label='random expectation')
    ax.set(xlabel='Illustrative outreach-list capacity', ylabel='Observed upgrades in list (%)',
           title='Historical validation: tie-adjusted precision at capacity')
    ax.set_xticks(CAPACITIES)
    ax.spines[['top', 'right']].set_visible(False)
    ax.legend(fontsize=8, loc='best')
    fig.tight_layout()
    path = result['output'] / 'validation_precision.png'
    fig.savefig(path, dpi=150, bbox_inches='tight')
    return fig, path
