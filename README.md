# Bellhaven CRM Sync

A local, human-in-the-loop reconciliation workflow for the Clipboard Health Analyst Assessment. It compares Bellhaven's published facility roster with the CRM snapshot, produces evidence-backed change proposals, lets a reviewer approve or reject each proposal, and applies **only approved** changes through the CRM API.

> Bellhaven is a fictional operator used for the assessment. Do not commit CRM tokens, account snapshots, review decisions, or execution ledgers to a public repository.

## Project layout

```text
bellhaven-crm-sync/
├── .github/workflows/daily_sync.yml   # optional daily detection configuration
├── data/
│   ├── scraped_locations.json         # local website snapshot
│   └── crm_snapshot.json             # local CRM snapshot
├── reconcile_output/                 # generated locally; not committed
│   ├── facilities_reconciliation.csv
│   ├── crm_cleanup.csv
│   ├── review_proposals.json
│   ├── summary.json
│   ├── reconcile_report.md
│   ├── review_states.json
│   └── execution_states.json
├── src/
│   ├── scraper.py                    # if stored under src/
│   └── crm_client.py                # CRM API wrapper
├── tests/
│   ├── conftest.py
│   ├── test_matching.py
│   ├── test_chow.py
│   └── test_idempotency.py
├── save_snapshot.py
├── match.py
├── app.py
├── apply_proposals.py
├── requirements.txt
├── .env.example
└── .gitignore
```

If your scraper has a different file path, use its actual path in the commands below.

## Setup

Requires Python 3.11 or newer (tested Python version should be recorded after running locally).

```bash
python3 -m venv .venv
source .venv/bin/activate           # macOS / Linux
python3 -m pip install -r requirements.txt
```

Set your personal CRM token in the terminal; **do not put the real token in source code**:

```bash
export CRM_API_TOKEN='YOUR_PRIVATE_TOKEN'
export CRM_BASE_URL='https://analyst-assessment-production.up.railway.app'
```

`.env.example` documents these variables but is not loaded automatically by the scripts.

## Run locally

From the repository root:

```bash
# 1. Collect fresh snapshots (adjust scraper path if needed)
python3 src/scraper.py
python3 save_snapshot.py

# 2. Reconcile website vs CRM; generates local reports and proposals
python3 match.py

# 3. Review proposals in the browser
python3 -m streamlit run app.py

# 4. Preview valid approved proposals without writing
python3 apply_proposals.py

# 5. Explicitly execute approved changes (requires confirmation)
python3 apply_proposals.py --apply
```

The review app records decisions in `reconcile_output/review_states.json`. The executor writes execution status to `reconcile_output/execution_states.json`. **Approving a proposal in the app does not itself modify CRM data.**

## Matching and decisions

- Normalize facility names, street abbreviations, cities and states; anchor candidate selection to location evidence rather than name alone.
- **A — Match / No Change:** already correct; no API write.
- **B — Minor Field Update:** targeted name, contact, or address adjustments.
- **C — Re-parent Existing:** wrong parent and CHOW conditions do not apply.
- **D — CHOW:** if both `lifetime_revenue > 0` **and** `outstanding_ar > 0`, preserve the old account and parent, create a new account under Bellhaven, then set `chow_current_account` on the old account to the new ID.
- **E — Rename or Re-parent:** identity matched but material change requires reviewer consideration.
- **F — Create New:** no suitable existing CRM account.
- **CRM cleanup:** separately surface duplicates, website-absent facilities, and same-address competing accounts. Ambiguous cases remain for manual review.

A matching street address is evidence, not automatic permission to inactivate another operator's account. A billing PO box is not necessarily the facility's physical street address.

## Safety and reruns

- Every CRM mutation requires an explicit approval and an explicit executor confirmation.
- Proposal identity/content should be checked against its recorded review decision; changed proposals must be reviewed again.
- The execution ledger is essential to resuming multi-step CHOW operations and skipping applied changes. **Do not delete it while running the assessment.**
- Refresh the CRM snapshot after applying changes; the local `data/crm_snapshot.json` is otherwise stale.
- The daily workflow should detect changes without automatically running the mutation executor. GitHub Actions runs on ephemeral machines and does not have access to a reviewer's local state files.
- For production-grade cross-run idempotency, use a durable shared approval/execution store and unique external identifiers, especially to handle uncertain network outcomes after POST.

## Tests

```bash
python3 -m pytest tests/ -v
```

Tests should mock API writes and verify matching, the CHOW billing condition, and safe reruns. Run them locally after copying the `tests/` directory into this repository.

## Results and submission

The initial provided dataset contained **35 website facilities** and **121 CRM accounts**. Earlier local reconciliation produced **29 change proposals**, with remaining matched facilities requiring no write. These are baseline figures, not a guarantee after new snapshots or approved changes. Use `reconcile_output/summary.json` for current results.

Before submission, verify the CRM browser end state, save the demo video, and document actual time spent and any judgment calls. The assessment's evaluation includes **the corrected CRM data**, not only the source code.

## Limitations / future improvements

Add an authenticated durable review store, richer record-linkage confidence, transaction-aware CHOW recovery, additional API integration tests, and daily alerting when new human review is required.
