# First upgrade-model comparison

This is a historical validation assessment, not a current outreach recommendation or a measurement of outreach effectiveness.

## Scope

- Working target: next 12-month giving at least 25% and 25 source units above prior 12-month giving.
- Eligible population: individuals with positive recorded giving in the preceding 12 months.
- Training: 95,025 donor-cutoff rows, including 4,862 upgrade outcomes.
- Validation: cutoff 2024-06-30, outcomes through 2025-06-30; 32,731 donors and 1,563 upgrades (4.78%).
- Final test: excluded from model-comparison reads and not scored.
- Inputs: past payment features only; current donor classes, snapshot lifetime values, cultivation, viewing and outcomes are excluded.

## Validation results at an illustrative capacity of 500

| Approach | Upgrades in list | Precision | Lift over random |
| --- | ---: | ---: | ---: |
| Logistic regression | 77.0 | 15.40% | 3.22x |
| Depth-3 decision tree | 67.6 | 13.52% | 2.83x |
| Lower prior giving rule | 62.9 | 12.57% | 2.63x |
| Higher prior giving rule | 24.8 | 4.95% | 1.04x |
| Random selection expectation | 23.9 | 4.78% | 1.00x |

Rules and tree leaves can assign equal scores to many donors. These results average uniformly over tied candidates at the list boundary; fractional counts are expected counts, not fractional donors. Raw ID-ordered metrics are also saved for traceability. Donor IDs are not model features.

Logistic regression has validation average precision 0.1091 and ROC AUC 0.7183. The best simple rule has average precision 0.0991. At 500, logistic regression captures 4.9% of all validation upgrades. At capacity 100, the tree does better; logistic regression leads at 250, 500 and 1,000. Capacity 500 is a comparison setting, not confirmed staff availability.

## Interpretation and limits

The working upgrade target has enough historical examples for a first model. Lower baseline giving is a strong signal, partly because percentage-based growth is easier from a small starting amount. This model estimates upgrade propensity, not donor wealth, major-gift capacity, gift size, net revenue or the added benefit of outreach.

The candidates are fixed first-pass models: L2 logistic regression and a decision tree with maximum depth 3 and minimum leaf size 500. Log transforms, median imputation, missing indicators and scaling are documented in the implementation. Learned preprocessing uses training only. The source dataset is hashed and package versions recorded. Fourteen checks passed, including timing, logistic convergence and saved-model reload equivalence; a separate notebook check confirms predictors are unchanged when outcome columns are modified.

Validation selects the provisional candidate and therefore is not an unbiased final performance estimate. Probability calibration and ranking uncertainty have not been established. The exports include synthetic values, historical coverage is incomplete, and current eligibility/assignments are unavailable. Do not use the historical score table as a live contact list.

## Artifacts and reproduction

Selected comparison run: `data/models/20261011T045412Z_a1281ec2/`.

- `manifest.json`: definitions, selection rule, software versions, source hash and limits.
- `validation_capacity_metrics.csv` and `validation_overall_metrics.csv`: comparative metrics.
- `historical_validation_scores.parquet`: retrospective scores and labels.
- `logistic_regression.joblib` and `shallow_tree.joblib`: fitted pipelines expecting the derived feature matrix.
- `logistic_coefficients.csv` and `tree_rules.txt`: model explanations.
- `validation_checks.csv` and `validation_precision.png`: verification and comparison figure.

Use `modeling.ipynb`. Default behavior reloads this run. The final test is now consumed; do not select new models using it. The reusable implementation is `analysis/upgrade_model.py`; saved pipelines must receive its `feature_matrix()` output. Development dependencies are recorded in `analysis/requirements-modeling.txt` and the run manifest.

## Next step

Freeze the target, candidate and capacity policy before evaluating the reserved test cohort. Use logistic regression as the provisional candidate at capacity 500, compared with the lower-prior-giving rule and random expectation. If test performance holds, obtain current assignments and eligibility and review a fresh shortlist with officers. Measure incremental gifts and staff effort in a subsequent outreach pilot.
