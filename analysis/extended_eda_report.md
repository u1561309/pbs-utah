# Extended EDA findings

Scope: supplied synthetic exports, all Unite cash for channel/payment-method totals, and resolved individual donors for segment and subsequent-giving comparisons. No model was fitted or tuned. Pilot work is deferred.

| Finding | Evidence | Modeling implication |
| --- | --- | --- |
| Broad channel labels dominate | Legacy 59.23%, Miscellaneous 26.65%, Digital 10.25% of recorded Unite cash | Clarify category semantics before modeling actionable channel behavior |
| Current sustainers dominate individual cash | 86.37% of latest active individual cash; median 74 units/12 positive payments versus 10 units/1 payment for non-sustainers | Examine dated recurring-payment history; do not use current labels as historical facts |
| June payment volume is unusually low | 35,662 June rows versus 148,061 May rows, pooled across six years; June is lower in each year | Verify export/generation behavior before interpreting calendar effects |
| Large Third Party tender averages reflect payer mix | 733 payments: 719 organization records and 14 unresolved; only two payer IDs | Separate organizational funding from individual prospect analysis |
| Small channel groups give unstable rates | Phone: 3 upgrades among 28 baseline donors; Digital retention 3,330/4,149 (80.26%); Legacy 12,490/15,834 (78.88%) | Use denominators and donor-composition checks; avoid causal channel ranking |
| Viewing alignment changes interpretation | Latest baseline cohorts produce different retention patterns under two hypothetical July–June FY-label mappings | Confirm calendar semantics before using engagement as a historical predictor |
| Cultivation has a structured synthetic pattern | Every source year has 1,000 selected, 752 contacted, 248 holdouts; every portfolio-year selects 125 | Describe coverage, but do not infer causal outreach effects or staff hours |

Campaign-reference communication channel and payment tender are different fields. Positive donor counts overlap across channel cash totals. Unmapped campaign rows account for 14,297 source units (0.071% of cash) and are retained. Channel totals are not response rates or ROI because exposures and costs are absent.

Viewing absence means no record, not confirmed non-viewing. Title totals sum genre-level counts, not validated distinct titles; median row watch fractions are not pooled completion rates. Neither calendar scenario is confirmed. Current segment attributes are snapshot descriptions rather than dated historical features. All subsequent giving outcomes mean recorded giving within supplied exports.

Results are in `analysis.ipynb` and `data/extended_eda/20261011T060942Z_29117690`. Forty-two checks passed. The reproduction command rebuilt the initial donor panel and this EDA; all thirteen aggregate tables match exactly across runs. The four-panel chart was visually checked for clipping and readable labels.

Next source questions: what Legacy/Miscellaneous labels encode, why June payment volume is low, what FY labels mean, and whether missing viewing represents coverage differences. These can inform further EDA without live contact permissions, assignments or staff budgets. Post-test EDA is not new independent validation of altered models.
