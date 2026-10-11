# Outreach pilot specification

Status: concrete draft for operational review. No assignments, current donor scores or outreach have been generated. The source exports contain synthetic placeholders; historical rankings are not a launch list.

## Decision and design

Test whether additional, standardized outreach increases 12-month giving upgrades among eligible donors prioritized by the frozen logistic model, compared with business-as-usual. This answers the outreach-effect question that historical upgrade prediction cannot answer. It does not test whether model ranking beats every other prioritization policy; that would require a separate design and more capacity.

Use a two-arm, 1:1 randomized pilot within a preselected eligible pool. Rank with the frozen model using only information available before the launch cutoff. Choose the pool size from actual treatment capacity before assigning arms. Record the full eligible population and the ranking cutoff. Randomization occurs after eligibility review, with treatment and control drawn from the same ranked pool. Both arms continue their ordinary service; treatment receives the agreed additional outreach protocol.

Confirm the randomization unit before assignment. Use donors only if interference between related donors is negligible; otherwise randomize households together, account for cluster sizes in workload, and use cluster-aware sample-size planning and analysis. A spouse link alone does not establish a household. Stratification by officer and score band may improve balance, but predefine bands, feasible block sizes and handling of small strata. Never regenerate assignments to obtain preferred groups.

## Population and information cutoff

Working population: individuals with positive recorded giving during the 12 months before a fixed launch date. Require resolved identity, a confirmed eligible contact method, current permission status and assignment ownership. Predefine exclusions for do-not-contact, deceased or invalid records, active sensitive solicitations, existing pilot enrollment, or other officer conflicts. These flags are requested inputs, not facts inferred from current files. Resolve eligibility and household conflicts before scoring or randomization.

Use current operational payment extracts complete through the cutoff, plus dated permission and assignment snapshots. Preserve the denominator and reasons for exclusion. Current demographic labels and lifetime totals must not be substituted for historical model features. Fiscal-year confirmation is not required for explicitly dated rolling windows, but complete date coverage is required. Do not describe the supplied FY2025 cultivation flag as a current assignment.

## Intervention and capacity

Define channel, message/proposition, number and spacing of attempts, officer responsibilities, allowed follow-up and the ordinary service received by controls. Record channel availability for both arms. Do not withhold normal donor service. Track contact attempts and crossovers in both arms; inability to reach a treatment donor is not grounds for removal from analysis.

Treatment capacity is floor((available staff hours minus setup hours) × 60 / minutes budgeted per assigned treatment donor). Budget per assigned donor includes expected unsuccessful attempts, preparation, administration and follow-up, not just successful conversations. At 1:1 allocation, a donor-randomized pool requires approximately twice this many eligible donors. Cluster allocation may change these counts. This formula is workload planning, not evidence that the sample is large enough to detect an effect.

Illustrative scenarios appear in the notebook. Actual hours, time estimates and minimum worthwhile effect remain unset in `analysis/pilot_config.json`. Review sample size and power after defining them; a small pilot can establish feasibility even when it cannot establish a giving effect. The historical 17.4% precision is not an untreated control rate or an estimated treatment effect.

## Outcomes and analysis

Working primary outcome: a donor's cash giving in the 12 months after launch is at least 25% greater and at least 25 source units greater than baseline 12-month giving. Confirm this definition before launch. Keep soft-credit recognition separate from cash. Specify handling of refunds, reversals, organizations and incomplete feeds; the supplied positive-only exports cannot establish all adjustment rules.

Primary estimate: treatment-minus-control difference in upgrade proportions, reported with an appropriate confidence interval and arm counts. Analyze every randomized eligible unit according to assignment, regardless of reach, adherence or crossover. If randomization is clustered, use inference at that level. Do not silently replace missing payment-feed coverage with zero; report missingness and predefine sensitivity analyses. An observed absence of gifts in a complete covered feed is a valid zero outcome.

Secondary outcomes: giving amount, retention, response, completed contacts, attempts and staff minutes. Report giving amount distributions because a few large gifts can dominate averages. Separate exploratory subgroup results from the primary estimate. Net incremental revenue requires compatible monetary units: estimate the difference in per-assigned-donor recorded cash between arms, scale to the treatment-arm size, then subtract additional treatment costs relative to ordinary service. Include uncertainty and measured effort. Do not multiply predicted upgrade probabilities by an assumed gift amount or count all treatment gifts as incremental revenue.

Freeze the policy, eligibility, sample, randomization procedure, primary outcome, follow-up, analysis and stopping rules before assignment. Monitor data completeness, complaints, permission changes and workload during the pilot. Do not stop early for favorable giving results without a preplanned sequential design. Operational stop conditions and escalation owners must be supplied.

## Required input contracts

| Input | Required fields | Grain |
| --- | --- | --- |
| Current roster | constituent_id, snapshot_date, individual/organization status, eligibility, exclusion_reason, permission_status, permitted_channel, portfolio_id, officer_id, household_id if validated | One constituent per dated snapshot |
| Payment feed | source_system, payment_id, constituent_id, payment_date, exact cash amount, currency/unit, adjustment status, feed_complete_through | Attributable cash transaction |
| Capacity | officer_id, available_hours, setup_hours, minutes_per_assigned_treatment_donor, cost_rate, period | Officer per pilot period |
| Assignment registry | pilot_id, randomization_unit_id, constituent_id, arm, stratum, score_at_cutoff, model_hash, assigned_at, seed, eligibility_snapshot_id | Constituent enrollment, with group assignment if clustered |
| Outreach events | pilot_id, event_id, constituent_id, timestamp, arm, officer_id, channel, attempt_number, response, staff_minutes, direct_cost, deviation_reason | One attempt/event |
| Outcome extract | pilot_id, constituent_id, baseline_cash, followup_cash, upgrade, coverage_complete, observation_end | One enrolled constituent |

Validate unique enrollment and event IDs, consistent group assignment, exclusive arms, complete eligibility, no post-cutoff scoring inputs, and exact payment reconciliation. Keep IDs and event timestamps in restricted operational storage rather than a shared Git repository. Version code, configuration, schemas and aggregate reports.

## Deliverables and next handoff

Completed now: pilot design, editable configuration, notebook capacity scenarios and an explicit readiness report. Unset operational fields remain unset rather than inferred.

Before building a live shortlist: provide actual staff hours/time estimates, current assignment and permission/eligibility snapshots, complete operational payments, validated household handling, outreach protocol, owner, costs and minimum meaningful effect. Then finalize sample-size planning and freeze the protocol. Only after that should an assignment generator create the scored eligible pool and randomized registry. External outreach is a separate operational action.
