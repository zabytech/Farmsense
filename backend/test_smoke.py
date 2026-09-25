"""End-to-end smoke test (runs fully offline in mock mode).  Run:  python test_smoke.py"""
import os
import tempfile
from datetime import date, timedelta

# Force everything to mock BEFORE importing the app
_tmp = tempfile.mkdtemp()
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_tmp}/test.db",
    "FORCE_MOCK_WEATHER": "true", "FORCE_MOCK_PEST": "true",
    "FORCE_MOCK_LLM": "true", "FORCE_MOCK_SMS": "true",
})

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

FIELDS_REC = {"action", "time_window", "confidence_pct", "reasoning_factors", "consequence_if_ignored",
              "plain_language_message", "fertilizer_tip", "pest_disease_advice"}


def profile(crop="tomato", days_ago=60, **kw):
    body = {"location": {"lat": 12.97, "lng": 77.59}, "crop_type": crop,
            "planting_date": (date.today() - timedelta(days=days_ago)).isoformat(),
            "crop_height_cm": 45, "watering_days_per_week": 3, "irrigation_type": "Drip",
            "avg_watering_minutes": 30, "fertilizer_used": True, "fertilizer_amount": "50 kg/acre"}
    body.update(kw)
    return body


def run():
    with TestClient(main.app) as c:
        # 1. profile
        r = c.post("/api/farmer/profile", json=profile())
        assert r.status_code == 200 and r.json()["status"] == "created", r.text
        fid = r.json()["farmer_id"]

        # 4. environment (exact shape)
        env = c.get(f"/api/farmer/{fid}/environment").json()
        assert set(env) == {"current", "forecast_7day", "since_planting_summary"}
        assert set(env["current"]) == {"temperature_c", "humidity_pct", "soil_moisture_pct", "soil_temperature_c"}
        assert len(env["forecast_7day"]) == 7

        # 5. recommendation (no photo yet)
        rec = c.get(f"/api/farmer/{fid}/recommendation").json()
        assert set(rec) == FIELDS_REC, set(rec) ^ FIELDS_REC
        print("dry/tomato/flowering ->", rec["action"], "|", rec["time_window"], "|", rec["confidence_pct"])
        print("   msg:", rec["plain_language_message"])

        # 2. photo (filename hint forces a result in mock mode)
        r = c.post(f"/api/farmer/{fid}/photo", files={"photo": ("leaf_blight.jpg", b"fakeimage", "image/jpeg")})
        assert r.status_code == 200 and set(r.json()) == {"condition", "confidence"}, r.text
        print("photo ->", r.json())
        rec = c.get(f"/api/farmer/{fid}/recommendation?debug=true").json()
        assert rec["pest_disease_advice"], "photo blight should give advice"
        print("after photo ->", rec["action"], rec["time_window"], "| chosen:", rec["debug"]["chosen_area"])

        # photo with no file / empty file -> 200 unknown/0 (never an error)
        r = c.post(f"/api/farmer/{fid}/photo")
        assert r.status_code == 200 and r.json() == {"condition": "unknown", "confidence": 0}, r.text
        r = c.post(f"/api/farmer/{fid}/photo", files={"photo": ("x.jpg", b"", "image/jpeg")})
        assert r.json() == {"condition": "unknown", "confidence": 0}

        # 3. leaf-condition (most recent input wins)
        r = c.post(f"/api/farmer/{fid}/leaf-condition", json={"condition": "yellowing"})
        assert r.json() == {"status": "recorded"}
        assert c.post(f"/api/farmer/{fid}/leaf-condition", json={"condition": "bogus"}).status_code == 422

        # 6. history
        h = c.get(f"/api/farmer/{fid}/history").json()
        assert set(h) == {"soil_moisture_trend", "past_recommendations"}
        assert h["soil_moisture_trend"] and h["past_recommendations"]
        print("history:", [(p["date"], p["action"]) for p in h["past_recommendations"]])

        # 7. sms
        s = c.post(f"/api/farmer/{fid}/sms").json()
        assert s["status"] == "sent" and 0 < len(s["message_preview"]) <= 160, s
        print("sms ->", s["message_preview"])

        # error handling: always JSON + CORS
        r = c.get("/api/farmer/nope/recommendation", headers={"Origin": "http://localhost:5173"})
        assert r.status_code == 404 and "error" in r.json()
        assert r.headers.get("access-control-allow-origin") == "*"
        r = c.post("/api/farmer/profile", json={"crop_type": "rice"})
        assert r.status_code == 422 and "error" in r.json()

        # scenarios through the whole pipeline
        print("\n--- mock scenarios (rice, flowering, no photo) ---")
        for sc in ("dry", "hot", "rain_soon", "wet", "ok"):
            assert c.post("/api/dev/scenario", json={"scenario": sc}).status_code == 200
            f2 = c.post("/api/farmer/profile", json=profile("rice", 100, fertilizer_used=True)).json()["farmer_id"]
            rr = c.get(f"/api/farmer/{f2}/recommendation").json()
            print(f"{sc:10s} -> {rr['action']:16s} {rr['time_window']:34s} {rr['confidence_pct']}%")
        assert c.post("/api/dev/scenario", json={"scenario": "nope"}).status_code == 422

        # unhandled exception -> JSON 500 with CORS
        import decision_engine
        original = main.decide
        main.decide = lambda *a, **k: 1 / 0
        try:
            c2 = TestClient(main.app, raise_server_exceptions=False)
            r = c2.get(f"/api/farmer/{fid}/recommendation", headers={"Origin": "http://x.com"})
            assert r.status_code == 500 and "error" in r.json()
            assert r.headers.get("access-control-allow-origin") == "*"
        finally:
            main.decide = original
    print("\nALL SMOKE TESTS PASSED")


if __name__ == "__main__":
    run()
