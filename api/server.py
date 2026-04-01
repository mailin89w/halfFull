"""
Railway HTTP API server
-----------------------
Wraps score_answers.py and bayesian/run_bayesian.py as HTTP endpoints so that
the Vercel Next.js frontend can reach them via fetch() instead of spawn().

Endpoints
---------
POST /score
    Body:  raw quiz answers dict (same as score_answers.py stdin)
    Returns: { "anemia": 0.31, "thyroid": 0.55, ... }

POST /bayesian/questions
    Body:  { mode: "questions", ml_scores, patient_sex?, existing_answers? }
    Returns: { confounder_questions: [...], condition_questions: [...] }

POST /bayesian/update
    Body:  { mode: "update", ml_scores, confounder_answers, answers_by_condition,
             patient_sex?, existing_answers? }
    Returns: { posterior_scores: {...}, details: {...} }

Start with:
    uvicorn api.server:app --host 0.0.0.0 --port 8000
"""

import logging
import os
import sys
import warnings

# Suppress noisy model-loading output (warnings only — do NOT disable logging
# globally here, it would silence uvicorn's startup and crash messages too)
warnings.filterwarnings("ignore")

# Ensure project root is on sys.path so models_normalized/ and bayesian/ are importable
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

log = logging.getLogger("railway_api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")

app = FastAPI(title="HalfFull ML API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# ── Lazy-loaded singletons ───────────────────────────────────────────────────

_model_runner = None
_bayesian_updater = None
_knn_scorer = None


def get_model_runner():
    global _model_runner
    if _model_runner is None:
        from models_normalized.model_runner import ModelRunner
        _model_runner = ModelRunner()
        if _model_runner.failed_models:
            log.warning("Failed to load models: %s", _model_runner.failed_models)
    return _model_runner


def get_bayesian_updater():
    global _bayesian_updater
    if _bayesian_updater is None:
        from bayesian.bayesian_updater import BayesianUpdater
        _bayesian_updater = BayesianUpdater()
    return _bayesian_updater


def get_knn_scorer():
    global _knn_scorer
    if _knn_scorer is None:
        from scripts.knn_scorer import KNNScorer
        _knn_scorer = KNNScorer()
    return _knn_scorer


# ── /score ───────────────────────────────────────────────────────────────────

@app.post("/score")
async def score(answers: dict):
    """
    Accept raw quiz answers, run preprocessing + all 11 ML models,
    return legacy-key probability dict plus a `confirmed` list of already-diagnosed conditions.
    """
    from scripts.score_answers import _preprocess, _patient_context, _remap_scores, _get_confirmed_models

    try:
        flat = _preprocess(answers)
        confirmed_models = _get_confirmed_models(flat)
        runner = get_model_runner()
        normalizer = runner._get_normalizer()
        feature_vectors = normalizer.build_feature_vectors(flat)
        raw_scores = runner.run_all_with_context(
            feature_vectors,
            patient_context=_patient_context(flat),
            skip_conditions=set(confirmed_models),
        )
        return {**_remap_scores(raw_scores), "confirmed": confirmed_models}
    except Exception as exc:
        log.exception("Error in /score")
        raise HTTPException(status_code=500, detail=str(exc))


# ── /bayesian/questions ──────────────────────────────────────────────────────

@app.post("/bayesian/questions")
async def bayesian_questions(payload: dict):
    """
    Return structured clarification questions for conditions that cleared
    the ML trigger threshold.
    """
    from bayesian.run_bayesian import handle_questions

    try:
        updater = get_bayesian_updater()
        return handle_questions(payload, updater)
    except Exception as exc:
        log.exception("Error in /bayesian/questions")
        raise HTTPException(status_code=500, detail=str(exc))


# ── /bayesian/update ─────────────────────────────────────────────────────────

@app.post("/bayesian/update")
async def bayesian_update(payload: dict):
    """
    Run Bayesian posterior update and return updated probabilities.
    """
    from bayesian.run_bayesian import handle_update

    try:
        updater = get_bayesian_updater()
        return handle_update(payload, updater)
    except Exception as exc:
        log.exception("Error in /bayesian/update")
        raise HTTPException(status_code=500, detail=str(exc))


# ── /knn-score ───────────────────────────────────────────────────────────────

@app.post("/knn-score")
async def knn_score(answers: dict):
    """
    Accept raw quiz answers, find the 50 nearest NHANES neighbours by cosine
    distance, and return lab signals that are disproportionately abnormal in
    that neighbourhood (vs. population baseline).

    Toggle on only by setting USE_KNN=true in the environment.

    Returns:
        { lab_signals: [...], n_signals: int, k_neighbours: int }
        or { lab_signals: [], n_signals: 0, k_neighbours: 50, disabled: true }
    """
    if os.environ.get("USE_KNN", "false").lower() != "true":
        return {"lab_signals": [], "n_signals": 0, "k_neighbours": 50, "disabled": True}

    try:
        scorer = get_knn_scorer()
        return scorer.score(answers)
    except Exception as exc:
        log.exception("Error in /knn-score")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Startup: pre-warm models so first user request is fast ───────────────────

@app.on_event("startup")
async def startup_preload():
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, get_model_runner)
        log.info("ModelRunner pre-loaded")
    except Exception as exc:
        log.warning("ModelRunner pre-load failed (will retry on first request): %s", exc)
    try:
        await loop.run_in_executor(None, get_bayesian_updater)
        log.info("BayesianUpdater pre-loaded")
    except Exception as exc:
        log.warning("BayesianUpdater pre-load failed (will retry on first request): %s", exc)


# ── Health check ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}
