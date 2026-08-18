# ImmunoVision

A predictive analytics and decision-support dashboard for child immunization coverage, built for the Rural Health Unit (RHU) of San Jacinto, Pangasinan — implementing the system described in the *ImmunoVision* capstone proposal and matching the accompanying Figma prototype.

## What it does

- Ingests and cleans the RHU's own registry exports (`data/raw/*.csv`) — mixed date formats, "MOVE OUT" / "NULL" sentinels, missing names, inconsistent barangay spelling — into a unified dataset, per the proposal's Obtain/Scrub methodology.
- Tracks child immunization records (0–12 months) against the DOH Expanded Program on Immunization schedule (15 doses across 7 antigens: BCG, Hepatitis B, DPT-Hib-HepB ×3, OPV ×3, PCV ×3, IPV ×2, MMR ×2), plus Vitamin A / MNP supplementation.
- Classifies each child as **At-Risk** / **Not At-Risk** of incomplete immunization using a trained ML classifier (Logistic Regression / Random Forest / XGBoost — the best of the three is selected automatically by recall), trained on the real registry data augmented with a statistically realistic synthetic population, with per-child explainability ("top risk factors").
- Presents coverage analytics, a barangay-level geospatial risk/coverage map, vaccine inventory management, and a barangay ↔ RHU vaccine request/distribution workflow.
- Three role-based portals sharing one codebase: **RHU Personnel**, **Barangay Health Worker (BHW)**, and **System Administrator**.

## Stack

Flask + SQLAlchemy + Flask-Login (backend), server-rendered Jinja templates + vanilla JS + Chart.js (frontend, vendored locally — no CDN required), scikit-learn / XGBoost / pandas / numpy (ML). SQLite by default for zero-setup local use; set `DATABASE_URL` to a MySQL DSN for RHU deployment.

## Setup

```bash
pip install -r requirements.txt

# 0. Vendor Chart.js locally (zero CDN dependency at runtime; requires npm)
bash scripts/fetch_vendor_js.sh

# 1. Train the risk classifier on the real + synthetic data (writes data/risk_model.joblib)
python -c "import data_processor as dp; dp.train_and_save_model()"

# 2. Seed the database: real registry children (data/raw/*.csv) + a simulated
#    population for the remaining barangays, demo users, inventory, sample requests
python seed.py

# 3. Run
python app.py
```

Then open http://localhost:5000.

**Demo accounts** (password `password123` for all):

| Role | Username | Scope |
|---|---|---|
| System Administrator | `jdelacruz` | All barangays |
| RHU Personnel | `msantos` | All barangays |
| Barangay Health Worker | `areyes` | Guibal (real registry data) |
| Barangay Health Worker | `mtorres` | Macayug (real registry data) |

To reset and reseed: `python seed.py --reset`.

## Project layout

```
app.py               # Flask app factory, all routes (auth/RHU/BHW/Admin/API), live analytics & notifications
data_processor.py    # CSV ingestion/cleaning, feature engineering, ML training & inference (the OSEMN pipeline)
models.py            # SQLAlchemy models
seed.py              # database seed script
templates/           # flat Jinja templates, prefixed by role (rhu_*.html / bhw_*.html / admin_*.html)
static/              # CSS design system, JS, vendored Chart.js
data/
  raw/                # RHU registry CSV exports (Obtain)
  immunovision.db     # SQLite database (generated)
  risk_model.joblib   # trained model artifact (generated)
```

## Notes on the data

Two of San Jacinto's 19 barangays (Guibal and Macayug) have real RHU registry exports in `data/raw/`; `data_processor.py` cleans and merges them (handling mixed date formats, "MOVE OUT" relocations, missing child names, and inconsistent barangay-name variants like "Guibal (Centro)"). The remaining 17 barangays — for which no export was available — use a statistically realistic synthetic population instead, built with the same feature/label logic so the two are directly comparable. The ML model trains on the real data augmented with the synthetic corpus. All dashboard numbers, risk scores, and charts are computed live from the database — nothing is hardcoded — so dropping in more real registry CSVs (named `Data_SJ_<Barangay>...csv`) and re-seeding immediately reflects in every screen.
