# Frictionless Dispute & Chargeback Resolution

An end-to-end system that automates credit card dispute resolution: card members file disputes, both sides submit evidence, an LLM extracts structured facts from that evidence, a rule engine scores evidence completeness, and a trained ML model predicts an outcome (refund / deny / partial) with a full explainability trail (SHAP factors + counterfactual) — routing low- and mid-confidence cases to a human, and letting high-confidence cases resolve automatically.

This repo is a monorepo with three parts:

```
monorepo/
├── frontend/   React + Vite + Tailwind — the web app (card member & merchant views, dashboard)
├── backend/    FastAPI + SQLAlchemy — REST API, database, LLM parsing, rule engine, ML serving
└── ml/         Data generation, model training, and explainability scripts
```

---

## Table of Contents

1. [How It Works](#how-it-works)
2. [Tech Stack](#tech-stack)
3. [Project Structure](#project-structure)
4. [Quick Start](#quick-start)
5. [Frontend — Setup & Usage](#frontend--setup--usage)
6. [Backend — Setup & Usage](#backend--setup--usage)
7. [ML Pipeline — Setup & Usage](#ml-pipeline--setup--usage)
8. [API Reference](#api-reference)
9. [Database Schema](#database-schema)
10. [The Resolve Pipeline, Step by Step](#the-resolve-pipeline-step-by-step)
11. [Confidence Routing](#confidence-routing)
12. [Evidence Requirements by Reason Code](#evidence-requirements-by-reason-code)
13. [Model Details](#model-details)
14. [Environment Variables](#environment-variables)
15. [Known Limitations](#known-limitations)
16. [Troubleshooting](#troubleshooting)

---

## How It Works

1. A **card member** files a dispute against a merchant charge, picking a reason code (not received, not as described, duplicate charge, unauthorized).
2. Both the **card member** and the **merchant** can submit free-text evidence. A role toggle in the UI switches between these two views (no real auth — it's just a view switch for the demo).
3. Each piece of evidence is run through the **Mistral LLM** to extract structured fields (tracking number, delivery status, dates, amounts, signature confirmation, policy compliance, etc.). If no API key is configured, this fails gracefully and the pipeline falls back to keyword-based detection instead of crashing.
4. A **rule engine** checks how complete the submitted evidence is against what's required for that reason code.
5. A **feature vector** is built from all of this (evidence signals + dispute history), and fed into a trained **XGBoost classifier** that predicts `refund` / `deny` / `partial` with a confidence score.
6. **SHAP** explains the top 3 factors behind the prediction, and a **counterfactual** check reports what single input flip would change the outcome.
7. **Confidence-based routing** decides what happens next: auto-approve, auto-reject, or queue for human review.
8. Everything is persisted (dispute, evidence, decision) and surfaced in a **dashboard** with aggregate metrics.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite, Tailwind CSS v4, Recharts, Axios |
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic, Uvicorn |
| Database | SQLite (default, zero-setup) — swappable for Postgres via `DATABASE_URL` |
| ML | XGBoost, SHAP, scikit-learn, pandas, numpy |
| LLM | Mistral API (`mistral-small-latest`), via `requests` + `python-dotenv` |

---

## Project Structure

```
monorepo/
├── .gitignore
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx                    Role toggle, nav, orchestrates the whole flow
│   │   ├── api.js                     Axios client, one function per backend endpoint
│   │   ├── constants.js               REQUIRED_EVIDENCE mirror, confidence thresholds, evidence labels
│   │   ├── index.css                  Tailwind entrypoint
│   │   └── components/
│   │       ├── RoleToggle.jsx         Card Member / Merchant switch
│   │       ├── DisputeForm.jsx        Create a new dispute (card member only)
│   │       ├── EvidenceForm.jsx       Submit evidence (used by both roles)
│   │       ├── StatusTracker.jsx      Polls dispute status every 4s
│   │       ├── DecisionView.jsx       Outcome, confidence bar, SHAP factors, counterfactual
│   │       └── Dashboard.jsx          Aggregate metrics (recharts)
│   ├── package.json
│   └── vite.config.js
│
├── backend/
│   ├── main.py                        FastAPI app, CORS, startup table creation
│   ├── database.py                    SQLAlchemy engine/session (SQLite by default)
│   ├── requirements.txt
│   ├── .env.example                   Template for MISTRAL_API_KEY
│   ├── models/
│   │   ├── db_models.py               SQLAlchemy ORM: Dispute, Evidence, Decision
│   │   └── schemas.py                 Pydantic request/response models
│   ├── routers/
│   │   ├── disputes.py                All dispute lifecycle endpoints + resolve pipeline
│   │   ├── dashboard.py               GET /dashboard/metrics
│   │   ├── health.py, items.py        Scaffold example endpoints
│   └── services/
│       ├── rule_engine.py             REQUIRED_EVIDENCE map + evidence_completeness()
│       ├── llm_parser.py              Mistral API call + JSON-retry logic
│       ├── evidence_signals.py        Keyword fallback detectors (signature, compliance, tracking plausibility)
│       ├── ml_service.py              Loads model.json, predicts, SHAP, counterfactual
│       ├── model.json                 Trained XGBoost model (copied from /ml)
│       └── feature_order.json         Feature column order + class labels (copied from /ml)
│
└── ml/
    ├── generate_data.py                Synthetic dataset generator (1500 rows)
    ├── train_model.py                  Trains XGBoost, prints accuracy + confusion matrix
    ├── explain.py                      SHAP explanation + counterfactual demo
    ├── disputes.csv                    Generated dataset (gitignored)
    ├── model.json                      Trained model (gitignored)
    ├── feature_order.json              Feature order + class labels (gitignored)
    └── requirements.txt
```

---

## Quick Start

**Prerequisites:** Node.js 18+, Python 3.10+, npm.

```bash
unzip monorepo.zip -d monorepo
cd monorepo
```

**1. Frontend**
```bash
cd frontend
npm install
npm run dev
```
Opens at **http://localhost:5173**.

**2. Backend** (in a new terminal)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and add your real MISTRAL_API_KEY (optional — see Known Limitations)

uvicorn main:app --reload --port 8000
```
API docs (Swagger UI) at **http://localhost:8000/docs**. Tables are created automatically on startup — no migrations needed.

With both running, open the frontend and you have the full demo: toggle roles, file a dispute, submit evidence, watch the status tracker poll, resolve it, see the decision breakdown, and check the Dashboard tab.

**3. ML pipeline** (optional — only needed if you want to regenerate data or retrain)
```bash
cd ml
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python generate_data.py     # -> disputes.csv
python train_model.py       # -> model.json, feature_order.json (~71% test accuracy)
python explain.py           # SHAP + counterfactual demo on a sample row
```
If you retrain, **copy the new `model.json` and `feature_order.json` into `backend/services/`** — the backend uses its own copy, not the one in `/ml`, so it doesn't depend on the ML environment being present at runtime.

---

## Frontend — Setup & Usage

```bash
cd frontend
npm install
npm run dev       # dev server, http://localhost:5173
npm run build     # production build -> dist/
npm run preview   # preview the production build
npm run lint      # oxlint
```

**Environment variable:** `VITE_API_URL` — the backend base URL. Defaults to `http://localhost:8000` if not set. To point at a different backend:
```bash
VITE_API_URL=https://your-api.example.com npm run dev
```
or create a `.env` file in `frontend/` with `VITE_API_URL=...`.

**How the UI is organized:**
- **Role toggle** (top right, when on the Disputes tab): switches between Card Member and Merchant views. This is a pure UI state change — there's no real authentication.
- **Card Member view:** create a dispute → submit evidence → watch status poll → click "Resolve Dispute" → see the decision.
- **Merchant view:** enter a Dispute ID (given to them by the card member out-of-band, since there's no lookup/auth) → submit evidence against that dispute.
- **Dashboard tab:** aggregate stats across all resolved disputes (outcome rates, confidence distribution, resolution time, % human-reviewed).

---

## Backend — Setup & Usage

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then edit in your MISTRAL_API_KEY
uvicorn main:app --reload --port 8000
```

- Interactive API docs: `http://localhost:8000/docs`
- Alternative docs: `http://localhost:8000/redoc`
- Root health check: `GET /` → `{"message": "Backend API is running"}`

**Database:** defaults to a local SQLite file at `./dev.db` (relative to wherever you launch `uvicorn` from). All tables are created automatically via a startup event — nothing to run manually. To use Postgres or another DB instead, set `DATABASE_URL` before starting the server, e.g.:
```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/disputes uvicorn main:app --reload
```

---

## ML Pipeline — Setup & Usage

```bash
cd ml
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**`generate_data.py`** — generates 1,500 synthetic disputes with realistic, partially-overlapping (not perfectly separable) outcome labels, plus 5% random label noise. Six weighted rules drive the outcome, in priority order:

| # | Rule | Favors |
|---|---|---|
| 1 | No tracking + no signature | Refund |
| 2 | Merchant policy compliance + signature | Deny |
| 3 | Evidence completeness ≥ 85% + policy compliance | Deny |
| 4 | Evidence completeness ≤ 20% | Refund / Partial |
| 5 | Merchant response time ≥ 150 hours | Refund (away from Deny) |
| 6 | Tracking present, no signature, mid-range evidence (30–75%) | Partial |
| — | Everything else | Soft, feature-weighted randomness |

Run it: `python generate_data.py` → writes `disputes.csv`, prints the class balance.

**`train_model.py`** — one-hot encodes `reason_code`, splits 80/20 stratified by outcome, trains an `XGBClassifier` (`multi:softprob`, 200 trees, depth 4), prints test accuracy + a confusion matrix, and saves:
- `model.json` — the trained model, XGBoost's native JSON format
- `feature_order.json` — the exact post-encoding feature column order **and** the class label order, both of which the backend needs to reconstruct input vectors and interpret predictions identically

Run it: `python train_model.py`. Current result: **71.3% test accuracy** (fully reproducible — both scripts use fixed random seeds).

**`explain.py`** — loads the trained model and demonstrates:
- `get_shap_explanation(model, feature_vector, feature_order, target_classes)` — top 3 features behind a prediction, via SHAP's `TreeExplainer`, each labeled `"pushed toward <class>"` (or `"pushed toward <other class> (away from <predicted>)"` for negative contributions)
- `get_counterfactual(model, feature_vector, feature_order, target_classes)` — flips `has_tracking`, `has_signature_confirmation`, `merchant_policy_compliance` one at a time and reports the first flip that changes the predicted outcome

Run it: `python explain.py` — runs both functions on a sample row from `disputes.csv` and prints readable output.

---

## API Reference

Base URL: `http://localhost:8000` (or your `VITE_API_URL`).

### `POST /disputes`
Create a new dispute.

Request body:
```json
{
  "card_member_id": "cm_123",
  "merchant_id": "merch_456",
  "reason_code": "not_received",
  "amount": 89.99
}
```
`reason_code` must be one of: `not_received`, `not_as_described`, `duplicate_charge`, `unauthorized`. Invalid codes return `400`.

Response: the created dispute (`id`, `status: "open"`, `created_at`, ...).

### `POST /disputes/{id}/evidence`
Submit a piece of evidence. Runs it through the Mistral LLM parser (`services/llm_parser.py`); if that fails (no API key, network issue, or bad JSON after retry), the evidence is still stored with `parsed_fields: {"parse_error": true, "raw_response": "..."}` rather than failing the request.

Request body:
```json
{
  "evidence_type": "tracking_number",
  "raw_text": "Order shipped March 3rd, tracking 1Z999AA10123456784, delivered, recipient signed for it.",
  "submitted_by": "card_member"
}
```
`submitted_by` defaults to `"card_member"` if omitted; use `"merchant"` for merchant-submitted evidence — this matters because `merchant_policy_compliance` is only derived from merchant-submitted evidence.

Response: the stored evidence row, including `parsed_fields`.

### `GET /disputes/{id}/status`
```json
{ "dispute_id": 1, "status": "open", "evidence_count": 2 }
```
`status` is one of `open`, `resolved`, `pending_review`.

### `POST /disputes/{id}/resolve`
Runs the full resolution pipeline (see next section) and returns the resulting Decision:
```json
{
  "id": 1,
  "dispute_id": 1,
  "outcome": "refund",
  "confidence_score": 95.42,
  "shap_explanation": {
    "predicted_class": "refund",
    "top_features": [
      { "feature": "has_tracking", "shap_value": 1.0423, "direction": "pushed toward refund" }
    ]
  },
  "counterfactual_text": "Flipping 'has_tracking' from False to True would change the outcome to 'partial'.",
  "evidence_completeness_pct": 50.0,
  "human_reviewed": false,
  "reasoning_text": "Predicted 'refund' with 95.42% confidence. Evidence completeness: 50.0% (missing: delivery_confirmation). Top factors: ...",
  "created_at": "2026-07-23T07:14:09.510112"
}
```

### `GET /disputes/{id}/decision`
Returns the most recent Decision for a dispute (404 if none exists yet).

### `GET /dashboard/metrics`
```json
{
  "total_decisions": 2,
  "outcome_rates": { "refund": 50.0, "deny": 50.0, "partial": 0.0 },
  "avg_resolution_time_seconds": 0.15,
  "confidence_distribution": { "0-20": 0, "20-40": 0, "40-60": 0, "60-85": 0, "85-100": 2 },
  "pct_human_reviewed": 0.0
}
```

---

## Database Schema

Three tables (SQLite by default, or any SQLAlchemy-supported DB via `DATABASE_URL`):

**`disputes`**
| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| card_member_id | String | |
| merchant_id | String | |
| reason_code | String | one of the four reason codes |
| amount | Float | |
| status | String | `open` / `resolved` / `pending_review` |
| created_at | DateTime | |

**`evidence`**
| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| dispute_id | Integer, FK → disputes.id | |
| submitted_by | String | `"card_member"` or `"merchant"` |
| evidence_type | String | must match rule engine's expected types |
| raw_text | Text | the free-text evidence |
| parsed_fields | JSON | LLM-extracted structured fields (or `parse_error`) |
| uploaded_at | DateTime | |

**`decisions`**
| Column | Type | Notes |
|---|---|---|
| id | Integer, PK | |
| dispute_id | Integer, FK → disputes.id | |
| outcome | String | `refund` / `deny` / `partial` |
| confidence_score | Float | 0–100, the predicted class's probability |
| shap_explanation | JSON | top-3 factors + directions |
| counterfactual_text | Text | human-readable "what would flip it" |
| evidence_completeness_pct | Float | 0–100 |
| human_reviewed | Boolean | see note below |
| reasoning_text | Text | full human-readable summary |
| created_at | DateTime | |

> **Note on `human_reviewed`:** this field means *"flagged as needing human review"*, not *"already reviewed by a human"* — it's `True` only for decisions routed into the 20–85% confidence band. The frontend labels this "Pending Human Review" to avoid the ambiguity.

---

## The Resolve Pipeline, Step by Step

`POST /disputes/{id}/resolve` runs, in order:

1. **Load evidence** — pull every `Evidence` row for the dispute, collect the list of `evidence_type`s submitted.
2. **Score completeness** — `rule_engine.evidence_completeness(reason_code, evidence_types)` compares what was submitted against `REQUIRED_EVIDENCE` for that reason code.
3. **Build the feature vector** — reconstructs the model's raw inputs from stored/parsed evidence:
   - `has_tracking`: **True** only if some evidence has a tracking number that (a) passes a plausibility check (rejects empty/placeholder/garbage values like `"wrong"`, `"123456"`, `"n/a"`, and catches "this tracking number is wrong" language even with natural phrasing) **and** (b) isn't contradicted by a delivery status indicating the package was *not* actually delivered.
   - `has_signature_confirmation`: prefers the LLM's explicit field; falls back to keyword detection (negation-checked first) over the evidence text if the LLM didn't extract it.
   - `merchant_policy_compliance`: same idea, but only evidence submitted by the merchant counts.
   - `card_member_dispute_history_count`: a real count — how many *other* disputes this card member has filed (capped at 10).
   - `merchant_response_time_hours`: not yet tracked end-to-end, defaults to 48.0.
   - `evidence_completeness_pct`: from step 2.
4. **Predict** — `ml_service.predict_outcome()` loads the trained XGBoost model and returns the predicted class + confidence (0–100%).
5. **Explain** — `ml_service.get_shap_explanation()` (top-3 SHAP factors) and `ml_service.get_counterfactual()` (first single-feature flip that would change the outcome).
6. **Route by confidence** — see below.
7. **Persist** — save a `Decision` row, update the `Dispute`'s `status`.

---

## Confidence Routing

| Confidence | Routing | `human_reviewed` | `Dispute.status` |
|---|---|---|---|
| < 20% | Auto-Reject | `False` | `resolved` |
| 20% – 85% | Pending Human Review | `True` | `pending_review` |
| > 85% | Auto-Approve | `False` | `resolved` |

Note: "reject" here means the model's top prediction (whatever class it is) is acted on automatically because confidence is *very low* — it's a routing decision, not a statement that the outcome itself is a denial.

---

## Evidence Requirements by Reason Code

From `backend/services/rule_engine.py`:

| Reason Code | Required Evidence Types |
|---|---|
| `not_received` | `tracking_number`, `delivery_confirmation` |
| `not_as_described` | `product_photos`, `listing_description` |
| `duplicate_charge` | `transaction_records` |
| `unauthorized` | `account_activity_log` |

`evidence_completeness_pct` = (required types submitted) / (required types for that reason code) × 100. Extra/irrelevant evidence types don't count against you, but they don't help completeness either.

---

## Model Details

- **Algorithm:** XGBoost multi-class classifier (`multi:softprob`), 200 trees, max depth 4
- **Features (in exact order, from `feature_order.json`):** `has_tracking`, `has_signature_confirmation`, `merchant_response_time_hours`, `merchant_policy_compliance`, `card_member_dispute_history_count`, `evidence_completeness_pct`, `reason_duplicate_charge`, `reason_not_as_described`, `reason_not_received`, `reason_unauthorized` (the last four are the one-hot encoding of `reason_code`)
- **Classes:** `deny`, `partial`, `refund` (alphabetical order, from `LabelEncoder`)
- **Test accuracy:** 71.3% (80/20 stratified split, fixed random seed)
- **Global feature importance (mean |SHAP|):** signature confirmation and tracking presence are the two strongest signals, followed by evidence completeness, merchant response time, and policy compliance.
- **Explainability:** every prediction comes with the top-3 SHAP factors (with plain-English direction) and a counterfactual ("flipping X would change the outcome to Y").

---

## Environment Variables

| Variable | Where | Default | Purpose |
|---|---|---|---|
| `MISTRAL_API_KEY` | `backend/.env` | — (required for live LLM parsing) | Auth for the Mistral chat completions API |
| `DATABASE_URL` | backend shell env | `sqlite:///./dev.db` | SQLAlchemy connection string |
| `VITE_API_URL` | `frontend/.env` or shell env | `http://localhost:8000` | Backend base URL the frontend calls |

---

## Known Limitations

- **No real authentication.** The role toggle is just a UI state switch; merchants target a dispute by ID with no verification that they actually own it.
- **No live LLM without a key.** Without `MISTRAL_API_KEY` set, evidence parsing fails gracefully (`parse_error: true`) and the pipeline falls back to keyword-based signal detection — the system still works end-to-end, just with less precise field extraction than a live LLM call would give.
- **`merchant_response_time_hours` is a fixed default (48.0).** There's no event in the schema yet tracking when a merchant actually responds, so this feature is currently not informative in production use.
- **Single-process SQLite.** Fine for local dev and demos; switch to Postgres via `DATABASE_URL` for anything concurrent/production-like.
- **Synthetic training data.** The model is trained on a rule-generated synthetic dataset (`ml/generate_data.py`), not real historical dispute outcomes — useful for demonstrating the full pipeline, but would need retraining on real data before any production use.
- **Keyword-fallback heuristics aren't perfect.** `evidence_signals.py`'s negation/co-occurrence detection handles common phrasing well (verified with an extensive test suite) but, like any keyword heuristic, can still be fooled by unusual phrasing or double negatives.

---

## Troubleshooting

**`ModuleNotFoundError` when running any Python script** — you're not in the right virtual environment, or haven't run `pip install -r requirements.txt` in that folder. Each of `backend/`, `ml/` has its own `requirements.txt` and should get its own venv.

**`pip install` fails / complains about "externally managed environment"** — use a virtual environment (`python3 -m venv .venv && source .venv/bin/activate`) rather than installing system-wide; if you must install system-wide, add `--break-system-packages`.

**Frontend can't reach the backend / CORS errors** — confirm the backend is running on port 8000 (or that `VITE_API_URL` matches wherever it's actually running), and that you're accessing the frontend at `http://localhost:5173` (the only origin allowed by the backend's CORS config).

**`dev.db` ends up in an unexpected location** — `DATABASE_URL` defaults to `sqlite:///./dev.db`, which resolves *relative to wherever you launched `uvicorn` from*, not relative to the `backend/` folder specifically. Launch from inside `backend/` for the file to land there.

**Evidence always shows `parse_error: true`** — you haven't set `MISTRAL_API_KEY` (copy `backend/.env.example` to `backend/.env` and fill it in), or the key is invalid/rate-limited. The pipeline still functions via the keyword fallback either way.

**Retrained the model but the backend's predictions didn't change** — the backend loads its *own* copy of `model.json`/`feature_order.json` from `backend/services/`, not the one in `ml/`. Copy the freshly trained files over after retraining.
