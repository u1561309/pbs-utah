# PBS Utah data exploration

Python/pandas review of all eight exports on October 9, 2026. Original files were not modified. Counts below cover full files, not samples. Amounts are in source units; currency is not explicitly documented.

## Inventory and observed grain

| File | Rows | Columns | Observed grain / key |
| --- | ---: | ---: | --- |
| constituents_w_memberships.csv | 196,167 | 22 | One constituent; Constituent ID unique |
| campaign_codes.csv | 29,249 | 17 | One marketing code; Marketing Code unique |
| officer_portfolios.csv | 8 | 4 | One portfolio; portfolio_id unique |
| cultivation.csv | 4,000 | 7 | One selected constituent per fiscal year; synthetic_id + fiscal_year unique |
| passport_viewing.txt | 444,741 | 5 | Constituent + fiscal year + genre unique |
| soft_credits.csv | 4,145 | 9 | Credit ID, with 79 exact duplicate excess rows |
| team_approach_legacy_payments.txt | 1,202,857 | 44 | Payment-like source row; no explicit transaction ID supplied |
| unite_payments.txt | 1,722,698 | 13 | One payment; payment_id unique |

All three .txt files are comma-delimited tables. Legacy gift dates span 1983-07-26 through 2020-06-28. Unite credit dates span 2020-07-01 through 2026-06-30. Viewing covers FY2021–FY2026; cultivation covers FY2022–FY2025. Date ranges do not overlap between payment systems, but do not establish completeness or rule out migration artifacts.

## Priority cleanup

1. **Deduplicate soft credits in a derived clean table.** There are 79 exact duplicate excess rows, also 79 excess Credit IDs. They contribute 23,624 source amount units. Raw soft-credit total is 1,856,827; deduplicated total is 1,833,203. Retain originals and log excluded source rows. Other files have no exact duplicate rows.
2. **Resolve explicit orphan records.** Unite has 33,733 payment rows with donor_id `SYN-ORPHAN`. Deduplicated soft credits have 79 rows with the same unmatched constituent ID. Preserve their amounts and flag the missing relationship rather than discard them or assign them to another donor. All nonblank legacy constituent IDs, viewing IDs, cultivation IDs, and spouse IDs match the constituent master.
3. **Repair the campaign mapping.** 1,225 Unite payments have marketing codes absent from campaign_codes. All marketing codes are populated. Campaign names match the reference for matched codes; the 1,225 name comparison failures arise from missing reference rows. Add an explicit unmapped category and review the source before adding mappings.
4. **Normalize legacy constituent links.** 216,128 legacy rows have no constituent link (18.0%); 977,289 have one; 9,440 have two. Columns constituent_id_3 through constituent_id_7 are entirely empty. Create a separate row-to-constituent bridge. Retain payment value once in the payment table; establish attribution rules before calculating donor totals from multi-person links.
5. **Standardize schema and types.** Use snake_case, canonical constituent_id, string identifiers and ZIP codes, nullable booleans, nullable integer years/counts, typed dates, and exact decimal amounts or integer minor currency units after confirming currency/precision. rollout_fy currently contains values such as `2023.0` plus one missing value; normalize to nullable integer. mean_percent_watched is a fraction (observed 0.005518–1), so document its 0–1 scale or rename mean_watch_fraction.
6. **Remove redundant fields from analytical views.** Constituent Type exactly equals Primary Constituent Type throughout. UofU Degree Info, Latest UofU Degree Year, and UofU Employment Status are entirely blank. Legacy source_description, county, program, all 12 premium fields, and five trailing constituent-ID fields are entirely blank. Campaign Description is entirely blank. Preserve these fields in raw exports; omit from core views unless the upstream schema requires them.
7. **Document synthetic placeholders.** Every nonblank constituent city and every legacy city is `Synthetic City`; numerous source/campaign attributes are constant synthetic codes. Degree count is uniformly zero where present despite alumni categories. These are not usable signals for geography, education, or campaign segmentation without clarification. Constant synthetic fields can remain provenance metadata rather than predictors.

Other observed conditions: 1,086 Unite payments and 34 soft credits have zero amounts; no negative payment/credit amounts or invalid nonblank payment/credit dates were found. Review zeros by business meaning rather than deleting automatically. Two constituent rows are organizations, and many person-specific fields are blank on two rows; validate applicability before imputing. Major Donor Class is blank on 195,608 rows (99.7%); spouse and marital status are blank on 178,807 (91.2%). Missing class does not automatically mean non-donor, and missing marital status does not mean unmarried. No outer whitespace was found in the profiled fields. All nonblank constituent ZIP values have five characters; this is a format observation, not geographic validation.

## Joins that need care

**Soft credits are attribution, not additional cash.** Unite payment_amount sums to 20,079,042 source units. Do not add soft-credit amounts to this as revenue. Both hard-credit organization IDs in soft_credits occur among Unite donors, but this alone does not prove individual payment matches.

Designation Detail ID is not a transaction key. Joining the raw soft-credit table to Unite on designation alone would yield 1,335,286,326 rows. Some designation IDs occur on as many as 733,658 payments. After deduplicating soft credits, matching on hard-credit organization ID + designation + date + amount gives one candidate payment for 3,971 credits, multiple candidates for 61, and no candidates for 34. Treat this as a diagnostic candidate match, not an approved allocation rule. Request a source payment_id on soft-credit exports; quarantine ambiguous matches until resolved.

**Viewing is already aggregated.** Keep constituent + fiscal year + genre as its key. Aggregate to constituent-year before joining annual giving or cultivation outcomes, otherwise each donor's giving repeats across genres. A titles_viewed-weighted mean watch fraction is appropriate only if each row's mean uses that same title denominator; confirm before aggregating. Summed genre counts may not equal distinct titles across genres.

**Cultivation is a selected cohort.** selected is True on all 4,000 rows. Each of 32 portfolio-year groups contains exactly 125 rows, matching the stated portfolio capacity. contacted and holdout are exact opposites. program_adopted exactly matches fiscal_year >= rollout_fy, with missing rollout treated as not adopted for this diagnostic. These relationships suggest a structured synthetic rollout, not evidence that the intervention caused giving changes. Missing rollout could mean never treated or unknown; document it. Do not infer that absent constituent-year records were eligible or in a control group. Donor annual features can form a panel, but selection and timing rules must be explicit. Do not backfill historical years with current age, sustainer status, giving class, or lifetime totals without dated snapshots.

## Proposed data model

| Table | Grain / key | Purpose |
| --- | --- | --- |
| constituents | constituent_id | Current attributes with snapshot_date; keep organization/person type |
| constituent_relationships | constituent_id + related_constituent_id + relationship_type | Spouse and other validated relationships; do not assume a household definition |
| payments | source_system + source_payment_id | Unified cash facts with dates, amounts, campaign key, original identifiers and provenance |
| legacy_payment_constituents | legacy_payment_id + constituent_id | Multiple constituent links, original slot and attribution rule if approved |
| campaigns | marketing_code | Validated campaign reference plus unmapped status |
| soft_credits | credit_id | Deduplicated recognition facts; payment_id only when resolved |
| viewing_annual_genre | constituent_id + fiscal_year + genre | Existing viewing grain |
| cultivation_assignments | constituent_id + fiscal_year | Selected cohort, portfolio, contacted, holdout, adoption status |
| portfolios | portfolio_id | Officer, capacity, nullable rollout year |
| constituent_year | constituent_id + fiscal_year | Derived giving, engagement and cultivation features for analysis |

For legacy payments, use an immutable import-batch ID plus source-row number as a traceable technical key until a real transaction ID is available. ta_account_id repeats across payments and must not be used as a payment key. Confirm source meanings before mapping gift_date and credit_date to a shared accounting date. Keep original categories, and use explicit crosswalks for payment_method versus tender_type and each system's gift classifications.

## Proposed folder structure

```text
data/
  raw/<source>/<extract_date>/   # immutable original exports + manifest/checksums
  staging/                     # parsed, typed, consistently named files
  curated/                     # validated entities/facts, preferably Parquet
  marts/                       # constituent_year and report-ready aggregates
  exceptions/                  # duplicates, orphan keys, unmatched/ambiguous links
analysis/                      # reusable Python and exploration reports
docs/                          # data dictionary, fiscal calendar, mapping decisions
```

This structure is a proposal; source files have not been moved or rewritten. Parquet plus DuckDB would suit these millions of rows and preserve types without forcing everything into Excel. Use explicit schemas and a manifest recording source filename, extraction date when known, row count, encoding, delimiter and source checksum. Do not invent extraction dates from file modification timestamps.

## Implementation order and acceptance checks

Start with typed staging and the data dictionary; then soft-credit deduplication and exception tables; then campaign/identity mapping and the legacy bridge; finally unified payments and annual analytical marts. Confirm fiscal-year boundaries and whether each year is complete before deriving annual outcomes. Unite dates are compatible with a July–June calendar, but the convention should be confirmed.

Require unique/nonblank entity keys, expected foreign-key coverage, date parsing, boolean/category validation, nonnegative integral viewing counts, and watch fractions within 0–1. Reconcile payment counts and exact amounts by source before and after transformation. Deduplication must explain the 79-row / 23,624-unit soft-credit difference. Joining descriptive tables must preserve payment counts and amounts. For bridges and attribution tables, test that cash totals remain unchanged and any approved allocation weights sum to one per payment. Track unresolved exceptions rather than quietly dropping them.

The Python profiler in this directory can be rerun with `python3 analysis/profile_data.py`. It reads IDs as strings, retains literal values rather than treating strings such as NA as null, and prints full-file column profiles and relationship checks. It loads all tables into memory; use chunking or DuckDB for larger future extracts. This review does not establish source business definitions or historical snapshot dates.
