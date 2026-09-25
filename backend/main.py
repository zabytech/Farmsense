"""FarmSense backend  -  FastAPI app exposing the exact REST contract the React frontend uses.

Run:  uvicorn main:app --host 0.0.0.0 --port 8000
Docs: http://localhost:8000/docs
"""
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Literal, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

import config
import llm_service
import pest_service
import sms_service
import weather_service
from database import CropCondition, Farmer, RecommendationLog, get_db, init_db
from decision_engine import decide

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("farmsense.api")

MAX_PHOTO_BYTES = 8 * 1024 * 1024        # 8 MB upload cap
CONDITION_MAX_AGE_DAYS = 7               # a photo/symptom report older than this is ignored (stale)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="FarmSense API", version="1.0", lifespan=lifespan)

# --------------------------------------------------------------------------- #
# Middleware order matters: the catch-all is added FIRST (inner), CORS LAST (outer), so even
# 500 error responses carry CORS headers and the browser lets the frontend read the JSON.
# --------------------------------------------------------------------------- #


@app.middleware("http")
async def catch_all_errors(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:  # never leak an HTML/empty error page - the frontend expects JSON
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse({"error": "Something went wrong on our side. Please try again."}, status_code=500)


app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException):
    return JSONResponse({"error": str(exc.detail)}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    details = [{"field": ".".join(str(p) for p in e.get("loc", []) if p != "body"), "message": e.get("msg", "")}
               for e in exc.errors()]
    return JSONResponse({"error": "Some of the information sent was not valid.", "details": details},
                        status_code=422)


# --------------------------------------------------------------------------- #
# Request models
# --------------------------------------------------------------------------- #
class Location(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class ProfileIn(BaseModel):
    location: Location
    crop_type: str
    planting_date: date
    crop_height_cm: float = 0
    watering_days_per_week: float = Field(default=0, ge=0, le=7)
    irrigation_type: str = ""
    avg_watering_minutes: float = 0
    fertilizer_used: bool = False
    fertilizer_amount: Optional[str] = ""
    phone: Optional[str] = ""            # optional extra (not in the frontend contract) - used for SMS


class LeafConditionIn(BaseModel):
    condition: Literal["normal", "spotted", "yellowing", "wilting"]


class ScenarioIn(BaseModel):
    scenario: str


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _get_farmer(db: Session, farmer_id: str) -> Farmer:
    farmer = db.get(Farmer, farmer_id)
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer profile not found. Please set up your profile again.")
    return farmer


def _get_env(farmer: Farmer) -> dict:
    """Weather + soil data (live, or mock on any failure - see weather_service)."""
    return weather_service.get_environment(farmer.id, farmer.lat, farmer.lng, farmer.planting_date)


def _latest_condition(db: Session, farmer_id: str) -> Optional[dict]:
    """Most recent pest/disease input from EITHER the photo endpoint or the leaf-condition endpoint."""
    row = (db.query(CropCondition).filter(CropCondition.farmer_id == farmer_id)
           .order_by(CropCondition.created_at.desc(), CropCondition.id.desc()).first())
    if not row or datetime.utcnow() - row.created_at > timedelta(days=CONDITION_MAX_AGE_DAYS):
        return None
    return {"condition": row.condition, "confidence": row.confidence, "source": row.source}


def _log_recommendation(db: Session, farmer_id: str, action: str, confidence: int) -> None:
    """One row per farmer per day - today's row is overwritten on every call."""
    try:
        today = date.today()
        row = (db.query(RecommendationLog)
               .filter(RecommendationLog.farmer_id == farmer_id, RecommendationLog.day == today).first())
        if row:
            row.action, row.confidence_pct, row.is_seed = action, confidence, False
        else:
            db.add(RecommendationLog(farmer_id=farmer_id, day=today, action=action, confidence_pct=confidence))
        db.commit()
    except Exception:
        db.rollback()
        log.exception("Could not log recommendation (continuing)")


def compute_recommendation(db: Session, farmer: Farmer, include_debug: bool = False) -> dict:
    """Shared by endpoint 5 (recommendation) and endpoint 7 (sms)."""
    env = _get_env(farmer)
    condition = _latest_condition(db, farmer.id)
    profile = {
        "crop_type": farmer.crop_type,
        "planting_date": farmer.planting_date,
        "watering_days_per_week": farmer.watering_days_per_week,
        "fertilizer_used": farmer.fertilizer_used,
    }

    decision = decide(profile, env, condition)              # deterministic rule engine
    debug = decision.pop("_debug", None)
    message = llm_service.phrase(decision)                  # LLM only rephrases (fallback: template)

    _log_recommendation(db, farmer.id, decision["action"], decision["confidence_pct"])

    result = {
        "action": decision["action"],
        "time_window": decision["time_window"],
        "confidence_pct": decision["confidence_pct"],
        "reasoning_factors": decision["reasoning_factors"],
        "consequence_if_ignored": decision["consequence_if_ignored"],
        "plain_language_message": message,
        "fertilizer_tip": decision["fertilizer_tip"],
        "pest_disease_advice": decision["pest_disease_advice"],
    }
    if include_debug:
        result["debug"] = debug
    return result


# Demo filler so the History screen isn't empty when running on mock weather.
_SEED_PATTERN = [(4, "no_action", 84), (3, "wait", 71), (2, "irrigate", 76), (1, "wait", 68)]


def _maybe_seed_history(db: Session, farmer: Farmer, env: dict) -> None:
    if not (config.SEED_DEMO_HISTORY and env.get("source") == "mock"):
        return
    try:
        today = date.today()
        exists = (db.query(RecommendationLog.id)
                  .filter(RecommendationLog.farmer_id == farmer.id, RecommendationLog.day < today).first())
        if exists:
            return
        for days_ago, action, conf in _SEED_PATTERN:
            d = today - timedelta(days=days_ago)
            if d >= farmer.planting_date:
                db.add(RecommendationLog(farmer_id=farmer.id, day=d, action=action,
                                         confidence_pct=conf, is_seed=True))
        db.commit()
    except Exception:
        db.rollback()
        log.exception("Could not seed demo history (continuing)")


# --------------------------------------------------------------------------- #
# 1. POST /api/farmer/profile
# --------------------------------------------------------------------------- #
@app.post("/api/farmer/profile")
def create_profile(body: ProfileIn, db: Session = Depends(get_db)):
    farmer = Farmer(
        id=uuid.uuid4().hex[:12],
        lat=body.location.lat, lng=body.location.lng,
        crop_type=body.crop_type.strip(),
        planting_date=body.planting_date,
        crop_height_cm=body.crop_height_cm,
        watering_days_per_week=body.watering_days_per_week,
        irrigation_type=body.irrigation_type or "",
        avg_watering_minutes=body.avg_watering_minutes,
        fertilizer_used=body.fertilizer_used,
        fertilizer_amount=(body.fertilizer_amount or "") if body.fertilizer_used else "",
        phone=(body.phone or "").strip(),
    )
    db.add(farmer)
    db.commit()
    return {"farmer_id": farmer.id, "status": "created"}


# --------------------------------------------------------------------------- #
# 2. POST /api/farmer/{farmer_id}/photo   (multipart, field "photo")
#    Never errors because of the model: on any failure -> {"condition": "unknown", "confidence": 0}
# --------------------------------------------------------------------------- #
@app.post("/api/farmer/{farmer_id}/photo")
def upload_photo(farmer_id: str, photo: Optional[UploadFile] = File(None), db: Session = Depends(get_db)):
    _get_farmer(db, farmer_id)
    result = {"condition": "unknown", "confidence": 0.0}
    try:
        data = photo.file.read(MAX_PHOTO_BYTES + 1) if photo else b""
        if data and len(data) <= MAX_PHOTO_BYTES:
            result = pest_service.classify_photo(data, photo.filename or "")
    except Exception:
        log.exception("Photo classification failed")

    condition = result.get("condition", "unknown")
    confidence = float(result.get("confidence") or 0)
    if condition == "unknown":
        return {"condition": "unknown", "confidence": 0}       # not stored, so an earlier manual input still counts

    try:
        db.add(CropCondition(farmer_id=farmer_id, source="photo", condition=condition, confidence=confidence))
        db.commit()
    except Exception:
        db.rollback()
        log.exception("Could not store photo result")
    return {"condition": condition, "confidence": round(confidence, 1)}


# --------------------------------------------------------------------------- #
# 3. POST /api/farmer/{farmer_id}/leaf-condition   (manual fallback input)
# --------------------------------------------------------------------------- #
@app.post("/api/farmer/{farmer_id}/leaf-condition")
def leaf_condition(farmer_id: str, body: LeafConditionIn, db: Session = Depends(get_db)):
    _get_farmer(db, farmer_id)
    db.add(CropCondition(farmer_id=farmer_id, source="manual", condition=body.condition, confidence=0))
    db.commit()
    return {"status": "recorded"}


# --------------------------------------------------------------------------- #
# 4. GET /api/farmer/{farmer_id}/environment
# --------------------------------------------------------------------------- #
@app.get("/api/farmer/{farmer_id}/environment")
def environment(farmer_id: str, db: Session = Depends(get_db)):
    env = _get_env(_get_farmer(db, farmer_id))
    return {"current": env["current"], "forecast_7day": env["forecast_7day"],
            "since_planting_summary": env["since_planting_summary"]}


# --------------------------------------------------------------------------- #
# 5. GET /api/farmer/{farmer_id}/recommendation   (add ?debug=true to also see the engine's working)
# --------------------------------------------------------------------------- #
@app.get("/api/farmer/{farmer_id}/recommendation")
def recommendation(farmer_id: str, debug: bool = False, db: Session = Depends(get_db)):
    return compute_recommendation(db, _get_farmer(db, farmer_id), include_debug=debug)


# --------------------------------------------------------------------------- #
# 6. GET /api/farmer/{farmer_id}/history
# --------------------------------------------------------------------------- #
@app.get("/api/farmer/{farmer_id}/history")
def history(farmer_id: str, db: Session = Depends(get_db)):
    farmer = _get_farmer(db, farmer_id)
    env = _get_env(farmer)
    _maybe_seed_history(db, farmer, env)
    rows = (db.query(RecommendationLog).filter(RecommendationLog.farmer_id == farmer_id)
            .order_by(RecommendationLog.day.desc(), RecommendationLog.id.desc()).limit(30).all())
    rows.reverse()                                            # oldest -> newest (chronological)
    return {
        "soil_moisture_trend": env.get("soil_trend", []),
        "past_recommendations": [{"date": r.day.isoformat(), "action": r.action,
                                  "confidence_pct": r.confidence_pct} for r in rows],
    }


# --------------------------------------------------------------------------- #
# 7. POST /api/farmer/{farmer_id}/sms     (optional ?phone=+91XXXXXXXXXX overrides the stored number)
# --------------------------------------------------------------------------- #
@app.post("/api/farmer/{farmer_id}/sms")
def send_sms(farmer_id: str, phone: Optional[str] = None, db: Session = Depends(get_db)):
    farmer = _get_farmer(db, farmer_id)
    try:
        rec = compute_recommendation(db, farmer)
        text = sms_service.condense(rec)
    except Exception:
        log.exception("Could not build SMS")
        return {"status": "failed", "message_preview": ""}
    to = (phone or "").strip() or farmer.phone or config.DEFAULT_SMS_TO
    ok = sms_service.send_sms(to, text)
    return {"status": "sent" if ok else "failed", "message_preview": text}


# --------------------------------------------------------------------------- #
# Extras (not part of the frontend contract): health check + demo scenario switch
# --------------------------------------------------------------------------- #
@app.get("/")
def root():
    return {"service": "FarmSense API", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "modes": {
            "weather": "mock (forced)" if config.FORCE_MOCK_WEATHER else "live (auto-falls back to mock)",
            "pest_model": "mock" if (config.FORCE_MOCK_PEST or not config.HF_API_TOKEN) else "huggingface",
            "llm": "mock template" if (config.FORCE_MOCK_LLM or not config.LLM_API_KEY) else config.LLM_PROVIDER,
            "sms": "mock (console log)" if (config.FORCE_MOCK_SMS or not (
                config.TWILIO_ACCOUNT_SID and config.TWILIO_AUTH_TOKEN and config.TWILIO_FROM_NUMBER)) else "twilio",
        },
        "mock_scenario": config.MOCK_SCENARIO,
    }


@app.get("/api/dev/scenario")
def get_scenario():
    return {"scenario": config.MOCK_SCENARIO, "available": list(weather_service.SCENARIOS)}


@app.post("/api/dev/scenario")
def set_scenario(body: ScenarioIn):
    """Live-demo helper: switch the MOCK weather situation (dry|hot|rain_soon|wet|ok) without a restart."""
    name = body.scenario.strip().lower()
    if name not in weather_service.SCENARIOS:
        raise HTTPException(status_code=422, detail=f"Unknown scenario. Choose one of: {', '.join(weather_service.SCENARIOS)}")
    config.MOCK_SCENARIO = name
    return {"scenario": name}


if __name__ == "__main__":       # `python main.py` also works
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
