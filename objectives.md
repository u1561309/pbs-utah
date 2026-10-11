
## Project objectives

- Prepare the structure of the project data using AI tools.
- Look for insights that will inform the model-building phase of the project.
- Practice reproducible, collaborative data science with GitHub.

## Business goals

Use data to strengthen fundraising and make better use of staff time and resources:

1. Identify existing major donors and recognize high-potential donors more quickly.
2. Identify opportunities to cut costs and improve fundraising efficiency.
3. Seek new funding sources.
4. Use staff time more efficiently.
5. Improve donor outreach and prioritization.
6. Increase opportunities for major gifts.

## EDA questions aligned with the goals

| Goal | Questions to investigate | Candidate measures of success |
| --- | --- | --- |
| Identify major and high-potential donors | Who gives the most? Which donors show sustained giving, upgrades, or increasing engagement? Which promising donors are outside current portfolios? | Prospect identification time; precision among the highest-priority prospects; subsequent major-gift conversion |
| Cut costs | Which outreach activities produce low returns? Where are staff effort or outreach duplicated? | Cost per donor acquired or retained; net fundraising revenue; staff hours per successful outcome |
| Find new funding sources | Which existing funding channels are underused? What additional foundation, corporate, or partnership opportunities could be researched? | Qualified new opportunities; funding-source diversity; revenue from new sources |
| Use staff time efficiently | Are portfolios balanced? Which outreach activities and prospect groups merit more attention? | Portfolio workload; time spent qualifying prospects; qualified opportunities per staff hour |
| Improve outreach and prioritization | How do donor history, engagement, and previous contact relate to response and future giving? | Response rate; retention; conversion among prioritized donors |
| Increase major-gift opportunities | Which donors show readiness for cultivation or an upgrade? Where does the cultivation process lose prospects? | Qualified major-gift opportunities; proposals; conversion; major-gift revenue |

These are proposed questions and measures, not findings or agreed performance targets. Observed associations do not establish that outreach caused a donation.

## EDA workflow

1. Define the decision, population, observation period, and intended outcome.
2. Understand each table's row meaning, keys, units, time coverage, and relationships.
3. Check missingness, duplicates, invalid values, outliers, and unmatched identifiers.
4. Clean and validate while preserving raw data and reconciling counts and amounts.
5. Explore individual distributions, including donation amounts, frequency, recency, and engagement.
6. Compare donor segments and investigate relationships between giving, engagement, and cultivation.
7. Examine time trends, retention, upgrades, seasonality, and cohorts using comparable periods.
8. Assess modeling readiness: outcome definitions, leakage, selection bias, class imbalance, and information available at prediction time.
9. Document supported insights, limitations, hypotheses, and next actions in reproducible code.

## Definitions and data needed

- Agree on what counts as a major donor and a major gift, including amount thresholds and time windows. Keep current major-donor status separate from predicted future potential.
- Define high potential using an observable future outcome, such as a major gift within an agreed horizon. Confirm historical coverage before choosing that horizon.
- Confirm fiscal-year boundaries and whether each period is complete.
- Obtain outreach costs, campaign expenditure, and staff effort or time records before estimating cost savings or fundraising return. Payment totals alone cannot establish cost efficiency.
- Confirm whether contact dates, outreach channels, responses, proposals, and outcomes are available. Annual contact flags alone cannot support a detailed outreach funnel.
- Assess available funding-source categories. External foundation, corporate, and grant research will be needed to identify specific new opportunities beyond the supplied donor data.
- Establish legacy payment attribution rules and resolve ambiguous soft-credit links before using them in donor-level totals. Keep soft credits separate from cash revenue.
- Use dated attributes and past information for historical prediction. Do not assume current donor status or lifetime totals were known in earlier years.

## Recommended first analytical step

Build a constituent-period analysis table from validated, attributable payments. After confirming the fiscal calendar, use constituent-year as the initial grain and aggregate viewing and cultivation separately before joining them.

Start by profiling giving recency, frequency, amount, retention, and upgrades. Compare current major donors with other donors and examine which high-giving or growing donors are outside cultivation portfolios. Use the results to define a practical first prospect-prioritization task and the information it needs. A historical propensity score would estimate likelihood of giving, not the additional benefit caused by contacting someone.

## Maintenance

Keep this file as the shared record of project goals, proposed success measures, unresolved definitions, and agreed priorities. Update it when decisions are made; retain a clear distinction between confirmed requirements, proposed analyses, and measured findings.

## Progress and next decision

- Completed: raw-data exploration and conservative cleanup, with validated Parquet tables and exception reports.
- Completed: initial donor EDA in `analysis.ipynb`, supported by `analysis/donor_eda.py`. Created monthly and explicitly dated 12-month constituent panels, recency/frequency/amount features, retention summaries, giving-growth features, threshold sensitivity, and an exploratory review cohort.
- Scope: resolved Unite payments only for donor cash profiles. Legacy attribution and soft credits are excluded. Current donor classes are descriptive, and FY2025 cultivation selection is not assumed to represent current assignments. Viewing joins await fiscal-calendar confirmation.
- Initial finding: in 2025-07-01 through 2026-06-30, only 8 individual donors recorded at least 1,000 source units in giving, 5 recorded at least 2,500, and none recorded at least 5,000. These illustrative thresholds are not an agreed major-donor definition.
- Completed: historical outcome feasibility for 12- and 24-month horizons, with separate aggregate-giving and single-payment thresholds. Prepared 288,329 donor-cutoff/horizon rows, past-only payment features, and chronological splits; 32 cohort/timing checks passed. Implementation: `analysis/model_readiness.py`; results are saved in `modeling.ipynb`.
- Historical finding: the 12-month training cohorts contain 21 aggregate-giving outcomes at or above 1,000 source units across 20 donors, versus 4,862 illustrative upgrade outcomes across 4,642 donors. Upgrade means at least 25% and 25 source units more giving than the prior 12-month window. Repeated donor-cutoff outcomes are reported separately from distinct donors.
- Working modeling task: 12-month giving upgrades, with retention as a complementary task. The illustrative upgrade target is not a confirmed major-gift definition.
- Completed: five simple ranking baselines, fixed logistic regression and a depth-3 tree were compared on historical validation data. Fourteen timing/model checks passed; learned preprocessing uses training only. Implementation: `analysis/upgrade_model.py`; results and charts are saved in `modeling.ipynb` and summarized in `analysis/upgrade_model_report.md`.
- Provisional result at an illustrative capacity of 500: logistic regression identifies 77 validation upgrades (15.4% precision, 3.22x random lift), versus 62.9 tie-adjusted expected upgrades for the strongest simple rule and 23.9 for random selection. The tree leads at capacity 100. Staff capacity remains unconfirmed; validation results are not final performance estimates.
- Completed: frozen chronological test evaluation of the existing training-only logistic model, working upgrade target and illustrative top-500 policy, versus the validation-selected lower-prior-giving benchmark. The test contains 32,817 individuals and 1,910 upgrades; prediction cutoff is June 30, 2025, with outcomes through June 30, 2026. Twelve policy, timing, predictor and persisted-score checks passed. Implementation: `analysis/final_evaluation.py`; results: `data/final_evaluation/20261011T055348Z_689b5d06` and `modeling.ipynb`.
- Final historical result: 87 test upgrades among the model's top 500 (17.4% precision, 2.99x random lift), versus 61.4 tie-adjusted expected upgrades for the benchmark and 29.1 under random selection. Average precision is 0.1174 versus 0.0977 for the benchmark. This is a descriptive historical comparison, not a significance test or evidence of incremental outreach impact. The test is now consumed and must not guide further tuning.
- Completed: measured outreach pilot draft in `analysis/pilot_specification.md`, editable assumptions in `analysis/pilot_config.json`, and reproducible planning checks in `analysis/pilot_planning.py`. Pilot notebook material was archived during EDA cleanup; the saved planning run and standalone specification remain available. Proposed design is 1:1 additional outreach versus business-as-usual within an eligible model-prioritized pool. Nine illustrative workload scenarios pass three planning checks; they are not sample-size or power calculations.
- Current priority: complete descriptive EDA and reproducibility using the supplied data. Operational pilot work is deferred and is not a prerequisite for EDA. Current permissions, assignments, staff costs and operational payments are needed only for a later live pilot or cost-efficiency analysis.
- Completed: extended campaign/channel, payment-method, seasonality, latest individual-segment, baseline-channel retention/upgrade, viewing and cultivation EDA. Implementation: `analysis/extended_eda.py`; saved results: `data/extended_eda/20261011T060942Z_29117690`; executed findings/charts are appended to `analysis.ipynb`. Forty-two reconciliation and consistency checks passed. Thirteen aggregate tables reproduce exactly using the end-to-end descriptive workflow.
- Findings informing model-building questions: Legacy and Miscellaneous communication labels cover 85.88% of recorded cash; clarify their meaning before treating them as actionable channels. Current sustainers provide 86.37% of latest-window active individual cash, motivating dated recurring-payment features rather than snapshot labels. June payment counts are much lower than May in every observed year; verify source date-generation/coverage before interpreting seasonality. Viewing associations change with the unconfirmed FY mapping and are not validated predictors. Cultivation selection/contact counts are highly structured and do not establish natural workloads or causal effects.
- Reproducibility: added `README.md`, pinned requirements entry point, `analysis/reproduce_eda.py`, raw/generated-data exclusions, and source-only collaboration copies in `notebooks/`. Executed working notebooks remain local: `analysis.ipynb` for EDA, `data_preparation.ipynb` for cleanup, and `modeling.ipynb` for historical models. A full pre-cleanup notebook is preserved under `data/notebook_archive/`. No model fitting or final-test reuse is part of the descriptive reproduction command.
- Next EDA questions: confirm channel-category definitions, payment-date coverage and FY-label semantics; separate organizational funding from individual donor patterns; examine recurring-payment histories with dated information. These source-definition checks are distinct from operational pilot inputs. Any later changed model requires a new untouched period or evaluation design.
- Additional inputs needed: fiscal-year convention, current portfolio assignments and eligibility, campaign costs, staff effort, and outreach outcomes. These are required for the corresponding engagement, prioritization, and cost-efficiency analyses.
