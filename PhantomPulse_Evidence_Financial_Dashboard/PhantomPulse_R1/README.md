# PhantomPulse AI — R1 Phantom Stock-Out Detector

## Overview

PhantomPulse helps store teams decide which inventory records are worth checking in person. It looks for SKU, store and date combinations where the recorded stock may not match what is happening on the shelf, especially when sales have stayed unusually low or stopped altogether.

The model is a supervised binary classifier built with scikit-learn's `HistGradientBoostingClassifier`. It gives each candidate a score and ranks the candidates for each store-day. The competition metric is mean Precision@20 per store-day. A high-ranked alert is a reason to investigate; it is not proof of theft, missing stock or an empty shelf.

The pipeline combines recent sales patterns, zero-sales streaks, inventory changes, promotions, calendar details and SKU/store information. The Streamlit dashboard shows the evidence behind an alert and lets a manager record the result of a physical check. Any estimated sales or recovery amounts are assumptions for prioritising work, not confirmed revenue.

## Project layout

```text
PhantomPulse_R1/
├── README.md
├── .gitignore
├── LICENSE
├── submission/
│   └── R1_predictions.csv
└── FULL_CODE/
    ├── .env.example
    ├── config.yaml
    ├── requirements.txt
    ├── pyproject.toml
    ├── phantompulse.py
    ├── dashboard.py
    ├── evaluate.py
    └── tests/
        └── test_phantompulse.py
```

The application, model, evaluation script and tests are kept in `FULL_CODE/`. Dataset files, downloaded models, local outputs, virtual environments, caches and secrets are not included in the submission. If you need to run the project locally, place the organiser-provided data in a `data/` folder at the project root. That folder is ignored by Git.

## Set up the environment

Use Python 3.11 or 3.12 and create a virtual environment from the project root.

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r FULL_CODE/requirements.txt
```

Copy the relevant organiser-provided files into `data/` without committing them:

- `daily_sales_inventory.parquet`
- `daily_sales_inventory_sample_2stores.csv` (a smaller file for quick experiments)
- `dev_truth.csv`
- `sku_master.csv`
- `store_master.csv`
- `holiday_calendar.csv`
- `promotion_calendar.csv` (included in the data pack; the current feature builder reads promotion flags from the panel)

The Parquet file needs `pyarrow`. For a smaller temporal experiment, you can start with the sample CSV.

## Run the pipeline

Run these commands from the project root.

```bash
# Try temporal validation with the two-store sample
python FULL_CODE/phantompulse.py --mode temporal-validate --input-file data/daily_sales_inventory_sample_2stores.csv

# Score the validation output
python FULL_CODE/evaluate.py --submission outputs/validation_predictions.csv --truth outputs/validation_truth.csv --out outputs/validation_score.json

# Validate with a grouped-store holdout (requires the full development data)
python FULL_CODE/phantompulse.py --mode validate
python FULL_CODE/evaluate.py --submission outputs/validation_predictions.csv --truth outputs/validation_truth.csv --out outputs/validation_score.json

# Create the submission for the official test window (requires the full 25-store panel)
python FULL_CODE/phantompulse.py --mode submit

# Open the manager dashboard after alert details have been created
streamlit run FULL_CODE/dashboard.py
```

The official run writes predictions to `submission/R1_predictions.csv`, supporting alert details to `outputs/alert_details.csv`, and a local model to `models/`. These generated files stay local and are ignored, except for the required submission CSV.

## How the model works

- **Classifier:** scikit-learn `HistGradientBoostingClassifier`, with median imputation and one-hot encoding in the preprocessing pipeline.
- **Ranking:** candidates are scored and the top 20 are selected for each store-day. Submission mode checks the expected stores, dates and row count.
- **Features:** recent sales over 7, 14, 28 and 56 days; zero-sales streaks and frequency; same-weekday and pre-run demand; sales variability; stock changes and persistence; stock-to-demand coverage; promotions and calendar details; and SKU/store metadata.
- **Date safety:** a prediction for date D uses sales and inventory only through D−1. Promotion and holiday information already known for D can be included.
- **Labels:** `phantom` and `misplaced` are treated as positive cases. `delisted` is treated as a negative/decoy case.
- **Reproducibility:** the seed, model settings, dates, labels and top-K setting are in `FULL_CODE/config.yaml`; package versions are pinned in `FULL_CODE/requirements.txt`.
- **Validation:** run temporal validation and grouped-store holdout, then report the official evaluator's Precision@20 and recall. The approximately 44.93% baseline is a previously observed result, not a promise about this packaged version. Re-run validation after changing the model or features.
- **Inspection feedback:** saved inspection outcomes are operational notes, not automatic training labels. Do not treat uninspected products as negative examples; consider review quality and selection bias before retraining.

## Run the tests and checks

```bash
pip install pytest ruff
pytest FULL_CODE/tests -q
ruff check FULL_CODE
ruff format --check FULL_CODE
```

The tests check deterministic top-20 ranking, fallback behaviour for demand estimates and the arithmetic used for financial estimates. The current pipeline does not call an external AI service or language model, so it does not need external AI API credentials.

## Data handling and security

- Do not commit `.env` files, credentials, private records, organiser data, model binaries, virtual environments, caches or generated output dumps.
- `.env.example` contains placeholders only. The current local model does not require API keys.
- Inputs should follow the CSV/Parquet schema supplied by the organisers. Avoid using real customer or other personal data.
- The dashboard saves inspection notes locally in an ignored output file. Do not enter personal or sensitive information in those notes.

## AI use and originality

The model uses scikit-learn's `HistGradientBoostingClassifier` and does not call a language model or external AI API at runtime. Before submitting, the team should accurately disclose any AI coding assistants used, along with any code, templates or snippets created before Day 1 or reused from elsewhere, including applicable licences. Check the team's actual development history before making that disclosure; this README does not make the disclosure on the team's behalf.

## Limitations

The available validation result comes from a limited temporal holdout. It is not the hidden test score, and final performance should not be claimed until the full-data run and official evaluation are complete. The `confidence` field is a ranking score, not a calibrated probability that a real-world stock-out has occurred. Revenue estimates depend on assumptions and may overstate recoverable sales. Every alert needs physical verification.


## Public saved-predictions dashboard deployment

The Streamlit Community Cloud entry point is `app.py` (in this project folder).
The lightweight `requirements.txt` in this folder installs only the dashboard
runtime. Python 3.12 is selected in `runtime.txt`.

The public dashboard reads only `submission/R1_predictions.csv`. It can display
the manager checklist and download a selected store-day CSV without the source
Parquet data. Historical sales/stock charts appear only if the authorised
`data/daily_sales_inventory.parquet` is present. Development metrics appear only
if `outputs/validation_score.json` is supplied. Do not publish organiser hidden
labels or private data.

The six-column submission file does not contain enough information to calculate
annual recovered rupees. The dashboard deliberately reports this as unavailable
unless the generated alert details include estimated opportunity and observed
period fields. Any annualized amount is labelled illustrative, with arithmetic
and assumptions shown; it is not actual recovered revenue.


## Public dashboard: historical evidence and financial scenario

The public dashboard can display the saved ranked alerts without the source inventory dataset.
To show the sales-versus-stock evidence chart for a selected flagged SKU, use the dashboard's
**Add historical evidence data** uploader and provide an authorised `daily_sales_inventory.parquet`
(or CSV) containing `date`, `store_id`, `sku_id`, `units_sold`, and `on_hand_eod`.
For the rupee scenario, the history file should also contain `unit_price_inr`, or upload
an authorised `sku_master.csv` with `sku_id` and `unit_price_inr`.

The chart shows actual units sold and recorded end-of-day stock for the selected store/SKU.
Its dashed baseline is the average daily sales in up to 28 available rows before the current
zero-sales streak. The annualized scenario is calculated as:

`baseline units/day × unit price (INR) × assumed recovery rate × 365`

The recovery rate defaults to 60% and is adjustable in the dashboard. This is an illustrative
annualized opportunity, not actual recovered cash, a measured uplift, or a guaranteed forecast.
It assumes the historical baseline and recovery rate continue for 365 days. Use only
organiser-authorised data; do not commit private datasets to the public GitHub repository.
