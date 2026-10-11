# PBS Utah fundraising EDA

Goal: understand the supplied donor data, prepare validated analytical tables, and document insights useful for later model building. The source data contains synthetic placeholders. Descriptive associations are hypotheses, not estimates of outreach impact or cost savings.

## Environment

Run commands from this folder. The recorded analysis environment is Python 3.14.7; exact package versions are in `analysis/requirements-modeling.txt`.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

For interactive notebook editing, install JupyterLab in your own environment. `analysis.ipynb` is the local working notebook with saved results. The tracked, source-only copy is `notebooks/analysis.ipynb`. The reproduction command uses that copy when the root working notebook is absent. For interactive work on a fresh checkout, copy it into the root as `analysis.ipynb`; do not overwrite an existing working notebook.

## Inputs and reproduction

Obtain the eight original exports separately and place them in the project root: `campaign_codes.csv`, `constituents_w_memberships.csv`, `cultivation.csv`, `officer_portfolios.csv`, `passport_viewing.txt`, `soft_credits.csv`, `team_approach_legacy_payments.txt`, `unite_payments.txt`. Raw exports and all generated `data/` files are excluded from Git. Current operational data, permissions and staffing estimates are not required for this EDA.

Rebuild cleaning and both descriptive EDA phases:

```sh
MPLBACKEND=Agg python -m analysis.reproduce_eda
```

Or reuse a validated cleaning run:

```sh
MPLBACKEND=Agg python -m analysis.reproduce_eda --cleaned-run data/cleaned/<run_id>
```

The command executes the identified cleanup cells from the working notebook and invokes reusable EDA modules. Each run writes a new versioned directory, original-file hashes, checks and aggregate outputs. It prints the new paths. It never trains a model, scores the consumed final test, assigns donors or sends outreach. Cleaning loads the exports into memory; allow several GB of working memory. Notebook reload cells refer to the saved runs from this workspace; on a fresh checkout, replace those paths with the new command outputs.

For only the extended EDA, given both validated inputs:

```sh
MPLBACKEND=Agg python -m analysis.extended_eda --cleaned-run data/cleaned/<run_id> --donor-run data/marts/<run_id>
```

## Analysis scope

- Channels and payment methods: recorded cash mix, campaign concentration, date trends and subsequent giving among baseline donors. Unique donor counts overlap across channels; channel summaries are not acquisition rates or ROI.
- Donor segments: latest-window individual giving by current sustainer, donor-class and constituent-type labels. Current labels do not establish historical state.
- Viewing: recorded viewers, genre counts and row-level completion distributions. Missing records are not zero engagement. Two hypothetical July–June mappings are shown separately; neither is a confirmed fiscal convention.
- Cultivation: selected cohorts, portfolio capacity ratios and contact/holdout composition. Contact flags do not establish randomization or a causal effect.
- Existing model artifacts remain historical. The final test is consumed; new EDA must not be presented as independent validation of newly chosen features.

See `objectives.md` for goals and progress, `analysis/data_review.md` for source issues, and the executed notebook for calculations and findings. Pilot files are optional later work and are separate from the EDA objective.

## Collaboration

Track scripts, objectives, environment requirements, reports and the source-only notebook. Keep raw exports, row-level derived data, local environments and executed notebook outputs out of the repository. Refresh `notebooks/analysis.ipynb` from the working notebook after edits by stripping execution outputs; preserve the working notebook.

The local Git repository can be reviewed with `git status` and `git diff`. No GitHub remote is configured by this workflow. Choose the destination repository and visibility before publishing; collaborators need authorized access to the separate raw exports to reproduce results. Review changes in branches and document assumptions alongside results.
