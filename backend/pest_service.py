"""Pest / disease image classification.

classify_photo(image_bytes, filename) -> {"condition": str, "confidence": 0-100, "source": "model"|"mock"|"error"}

* HF_API_TOKEN set  -> calls a pretrained PlantVillage-based model on HuggingFace.
                       If that call fails, returns {"condition": "unknown", "confidence": 0}
                       (the frontend then shows the manual fallback).
* No token / FORCE_MOCK_PEST -> deterministic mock result so demos always work.

To swap the model: change HF_MODEL / HF_API_URL in .env, or rewrite _call_model().
Labels are normalised to: healthy, leaf_blight, leaf_spot, fungal_disease, pest_infestation, viral_disease.
"""
import hashlib
import logging
import time

import httpx

import config

log = logging.getLogger("farmsense.pest")

UNKNOWN = {"condition": "unknown", "confidence": 0.0, "source": "error"}


def classify_photo(image_bytes: bytes, filename: str = "") -> dict:
    if config.FORCE_MOCK_PEST or not config.HF_API_TOKEN:
        return _mock(image_bytes, filename)
    try:
        return _call_model(image_bytes)
    except Exception as exc:
        log.warning("Pest model failed: %s", exc)
        return dict(UNKNOWN)


# --------------------------------------------------------------------------- #
def _call_model(image_bytes: bytes) -> dict:
    headers = {"Authorization": f"Bearer {config.HF_API_TOKEN}", "Content-Type": "application/octet-stream"}
    resp = None
    for attempt in range(2):                       # HF models can be "loading" (503) on first call
        resp = httpx.post(config.HF_API_URL, headers=headers, content=image_bytes, timeout=25)
        if resp.status_code == 503 and attempt == 0:
            time.sleep(4)
            continue
        break
    resp.raise_for_status()
    out = resp.json()
    if out and isinstance(out[0], list):           # some endpoints nest the list
        out = out[0]
    best = max(out, key=lambda r: r["score"])
    return {"condition": map_label(best["label"]),
            "confidence": round(float(best["score"]) * 100, 1),
            "source": "model"}


def map_label(label: str) -> str:
    """Map a PlantVillage label like 'Tomato___Late_blight' to our small vocabulary."""
    s = label.lower().replace("___", " ").replace("_", " ")
    if "healthy" in s:
        return "healthy"
    if any(w in s for w in ("virus", "curl", "mosaic")):
        return "viral_disease"
    if "blight" in s:
        return "leaf_blight"
    if any(w in s for w in ("mite", "pest", "insect", "aphid")):
        return "pest_infestation"
    if any(w in s for w in ("mold", "mildew", "rust", "scorch", "rot")):
        return "fungal_disease"
    return "leaf_spot"                              # spot, scab, bacterial, anything else unhealthy


# --------------------------------------------------------------------------- #
_MOCK_RESULTS = [("healthy", 93.4), ("leaf_blight", 87.6), ("leaf_spot", 81.3),
                 ("pest_infestation", 78.9), ("healthy", 95.1)]
_FILENAME_HINTS = {"healthy": "healthy", "blight": "leaf_blight", "spot": "leaf_spot",
                   "pest": "pest_infestation", "virus": "viral_disease"}


def _mock(image_bytes: bytes, filename: str) -> dict:
    """Deterministic: same image -> same answer. Put 'blight', 'pest', 'healthy'... in the
    filename to force a specific result during a live demo."""
    name = (filename or "").lower()
    for hint, cond in _FILENAME_HINTS.items():
        if hint in name:
            return {"condition": cond, "confidence": 95.0 if cond == "healthy" else 88.0, "source": "mock"}
    h = int(hashlib.md5(image_bytes or b"").hexdigest()[:8], 16)
    cond, conf = _MOCK_RESULTS[h % len(_MOCK_RESULTS)]
    return {"condition": cond, "confidence": conf, "source": "mock"}
