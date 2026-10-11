# Frozen upgrade-policy test evaluation

The saved training-only logistic model and strongest validation-selected simple rule were evaluated without refitting, using the existing working upgrade definition and illustrative capacity 500. A policy file with model/data hashes was written before test loading. The source model-comparison artifacts were preserved.

Prediction cutoff: June 30, 2025. Outcome window ends June 30, 2026. Test population: 32,817 individuals with positive prior-year giving; 1,910 upgraded by at least 25% and 25 source units. Twelve validation checks passed.

| Method | Top-500 upgrades | Precision | Lift over random | Average precision |
| --- | ---: | ---: | ---: | ---: |
| Frozen logistic regression | 87 | 17.40% | 2.99 | 0.1174 |
| Lower prior giving benchmark | 61.40 expected | 12.28% | 2.11 | 0.0977 |
| Random selection | 29.10 expected | 5.82% | 1.00 | — |

The benchmark expectation averages uniformly over ties at the cutoff; its deterministic donor-ID-ordered list contains 59 upgrades. The model has no boundary tie. The model captures 4.55% of all test upgrades. No significance or calibrated-probability claim is made.

Outputs: `data/final_evaluation/20261011T055348Z_689b5d06`. Reloadable cells and results are in `modeling.ipynb`. Implementation: `analysis/final_evaluation.py`.

The test is now consumed. Do not select additional features, models or capacity using its outcomes. Later development needs a new untouched period or evaluation design. These synthetic-data results do not establish that outreach causes additional gifts or that capacity 500 is appropriate.

Next: define a pilot with actual capacity, current assignments/eligibility, costs and staff effort, and measurable outreach outcomes. No current prospect scores or outreach messages were generated.
