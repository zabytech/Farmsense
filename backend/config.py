"""Central configuration. Everything is read from environment variables (or a .env file).

Leave keys empty and the matching service automatically runs in MOCK mode,
so the whole pipeline works end-to-end for a demo with zero keys.
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # dotenv is optional
    pass


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# ---- Database ----
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./farmsense.db")

# ---- Global mock switches (force mock even if keys/network exist) ----
FORCE_MOCK_WEATHER = _bool("FORCE_MOCK_WEATHER", False)
FORCE_MOCK_PEST = _bool("FORCE_MOCK_PEST", False)
FORCE_MOCK_LLM = _bool("FORCE_MOCK_LLM", False)
FORCE_MOCK_SMS = _bool("FORCE_MOCK_SMS", False)

# Which fake weather situation to simulate in mock mode:
# dry | hot | rain_soon | wet | ok
MOCK_SCENARIO = os.getenv("MOCK_SCENARIO", "dry").strip().lower()

# In mock-weather mode, pre-fill a few past recommendations so the History screen isn't empty.
SEED_DEMO_HISTORY = _bool("SEED_DEMO_HISTORY", True)

HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "6"))

# ---- Pest/disease model (HuggingFace Inference API) ----
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "").strip()
HF_MODEL = os.getenv("HF_MODEL", "linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification")
HF_API_URL = os.getenv("HF_API_URL", "").strip() or f"https://router.huggingface.co/hf-inference/models/{HF_MODEL}"

# ---- LLM phrasing layer ----
# LLM_PROVIDER: "openai" (any OpenAI-compatible endpoint) or "anthropic"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_API_URL = os.getenv("LLM_API_URL", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()

# ---- SMS (Twilio) ----
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "").strip()
DEFAULT_SMS_TO = os.getenv("DEFAULT_SMS_TO", "").strip()  # used if the farmer has no phone on file
