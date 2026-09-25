# FarmSense Backend (PS-01, AgriTech)

FastAPI backend for FarmSense. It combines farmer profile data, weather/soil data (Open-Meteo),
a pretrained pest/disease classifier, a **deterministic rule-based decision engine**, and an LLM
that only rephrases the engine's output. SMS delivery goes through Twilio.

**Everything has a mock fallback**: with zero API keys the whole pipeline still runs end-to-end.

## Quick start

Requires **Python 3.10+**.

```bash
cd farmsense-backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # optional - only needed to plug in real keys

uvicorn main:app --host 0.0.0.0 --port 8000
```

- API base URL: `http://localhost:8000/api`
- Interactive docs: `http://localhost:8000/docs`
- Health / mode check: `http://localhost:8000/health` (shows which services are live vs mock)
- `python main.py` also starts it on port 8000.
- Self-test (offline, mock mode): `python test_smoke.py`

## Endpoints (exact contract)

| # | Method + path | Purpose |
|---|---------------|---------|
| 1 | `POST /api/farmer/profile` | Create profile -> `{farmer_id, status:"created"}` |
| 2 | `POST /api/farmer/{id}/photo` | multipart field `photo` -> `{condition, confidence}`; on any failure `{"condition":"unknown","confidence":0}` (HTTP 200) |
| 3 | `POST /api/farmer/{id}/leaf-condition` | `{condition: normal\|spotted\|yellowing\|wilting}` -> `{status:"recorded"}` |
| 4 | `GET /api/farmer/{id}/environment` | current, 7-day forecast, since-planting summary |
| 5 | `GET /api/farmer/{id}/recommendation` | runs the decision engine + LLM phrasing |
| 6 | `GET /api/farmer/{id}/history` | soil-moisture trend + past recommendations (oldest -> newest) |
| 7 | `POST /api/farmer/{id}/sms` | sends condensed recommendation -> `{status:"sent"\|"failed", message_preview}` |

Extras (not used by the frontend, handy for the demo):

- `GET /api/farmer/{id}/recommendation?debug=true` adds a `debug` object: growth stage, signals, and the
  score of every decision area. Use it when judges ask "why?".
- `POST /api/farmer/{id}/sms?phone=+919876543210` overrides the destination number. Otherwise it uses the
  optional `phone` field sent in the profile, then `DEFAULT_SMS_TO` from `.env`.
- `POST /api/farmer/profile` also accepts an optional `"phone"` field.
- `GET/POST /api/dev/scenario` switches the **mock** weather situation live.

Errors are always JSON: `{"error": "..."}` (404 unknown farmer, 422 invalid input, 500 unexpected), and CORS
is open for all origins, including on error responses.

## Mock mode and live-demo tricks

| Service | Goes live when... | Otherwise |
|---------|-------------------|-----------|
| Weather/soil | Open-Meteo is reachable (no key needed) | Auto-falls back to mock data. The engine lowers confidence and says the figures are estimates. |
| Pest model | `HF_API_TOKEN` set | Deterministic mock. Put `blight`, `spot`, `pest`, `virus` or `healthy` in the **filename** to force that result. |
| LLM | `LLM_API_KEY` set | Template sentences built from the engine's output |
| SMS | all three `TWILIO_*` vars set | Message is printed to the server console and reported as `sent` |

Force any of them off with `FORCE_MOCK_WEATHER / PEST / LLM / SMS=true`.

Switch the mock weather during the demo without restarting (only affects mock weather, i.e.
`FORCE_MOCK_WEATHER=true` or no internet):

```bash
curl -X POST localhost:8000/api/dev/scenario -H 'Content-Type: application/json' -d '{"scenario":"rain_soon"}'
# scenarios: dry | hot | rain_soon | wet | ok
```

Then refresh the recommendation screen: e.g. `dry` -> irrigate, `rain_soon` -> no action, `wet` -> hold off watering.
(Which verdict you get also depends on crop and growth stage - that is the engine working as designed.)

## Plugging in real keys (`.env`)

```
HF_API_TOKEN=hf_xxx                         # pest/disease model (HuggingFace)
LLM_PROVIDER=openai                         # or: anthropic
LLM_API_KEY=xxx
LLM_API_URL=                                # optional (e.g. https://api.groq.com/openai/v1/chat/completions)
LLM_MODEL=                                  # optional; defaults: gpt-4o-mini / claude-haiku-4-5-20251001
TWILIO_ACCOUNT_SID=ACxxx
TWILIO_AUTH_TOKEN=xxx
TWILIO_FROM_NUMBER=+1xxxxxxxxxx
DEFAULT_SMS_TO=+91xxxxxxxxxx
```

If a real service is configured but fails, the app logs a warning and falls back to the mock
(check the server console if you expected live output). Twilio trial accounts can only text verified numbers.

## How the decision engine works (for the judges)

`decision_engine.py` is pure if/else + weighted points. There is no ML and no randomness, so the same
inputs always give the same output. All thresholds live in `rules.json`, so they can be edited without touching code.

1. **Growth stage**: crop + planting date -> sowing / vegetative / flowering / maturity (lookup table). Each stage has a water-sensitivity weight (flowering 1.4x, ripening 0.5x).
2. **Signals**: soil moisture now and 3-day trend, rain in the next 48h/72h, heat, humidity.
3. **Three areas scored 0-100**: irrigation (weighted points and a compound-risk bonus for heat + dry soil + sensitive stage), pest/disease (photo or symptom, escalated by weather), fertilizer (history + stage).
4. **Pick one**: the actionable area with the highest score becomes the headline.
5. **Confidence**: distance from a decision boundary, minus penalties for estimated/missing/contradictory data.
6. **LLM**: receives the finished decision and only rewrites it in plain words (see `llm_service.py`).

## Behaviour notes

- A photo/symptom report older than **7 days** is ignored as stale (`CONDITION_MAX_AGE_DAYS` in `main.py`).
- If the photo model fails (`unknown`), nothing is stored, so an earlier manual symptom still counts.
- One history row per farmer per day; today's row is refreshed on every recommendation call.
- With mock weather, `SEED_DEMO_HISTORY=true` adds up to 4 demo rows so the History screen isn't empty (flagged `is_seed` in the DB).
- `crop_height_cm`, `irrigation_type`, `avg_watering_minutes` and `fertilizer_amount` are stored but not used by the current rules (the SRS only requires them to be collected).
- The SQLite DB file `farmsense.db` is created next to `main.py`. Delete it to reset all data.

## Files

```
main.py             FastAPI app: all 7 endpoints, error handling, CORS
decision_engine.py  deterministic rule engine       rules.json   editable thresholds/tables
weather_service.py  Open-Meteo client + mock        pest_service.py  HF classifier + mock
llm_service.py      LLM phrasing + template fallback
sms_service.py      Twilio SMS + condensed text + mock
database.py         SQLAlchemy models (SQLite)      config.py    env-var settings
test_smoke.py       end-to-end self-test            .env.example config template
```
