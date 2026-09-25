"""Weather + modeled soil data (Open-Meteo, free, no API key) with a mock fallback.

Public function: get_environment(...). It NEVER raises - if the live API fails
(or FORCE_MOCK_WEATHER=true) it returns realistic mock data with source="mock".

Returned dict:
{
  "source": "live" | "mock",
  "current": {temperature_c, humidity_pct, soil_moisture_pct, soil_temperature_c},
  "forecast_7day": [{date, temperature_c (day's HIGH), rain_mm, humidity_pct}],
  "since_planting_summary": {avg_temperature_c, total_rain_mm, days_tracked},
  "soil_trend": [{date, value}]      # last 7 days incl. today (used by /history and the engine)
}
"""
import hashlib
import logging
import random
import time
from datetime import date, datetime, timedelta

import httpx

import config

log = logging.getLogger("farmsense.weather")

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
CACHE_TTL_SECONDS = 600
_CACHE: dict = {}


def _cache_get(key, ttl=CACHE_TTL_SECONDS):
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    return None


def _cache_set(key, value):
    _CACHE[key] = (time.time(), value)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def get_environment(farmer_id: str, lat: float, lng: float, planting_date: date,
                    scenario: str | None = None) -> dict:
    """Return environment data. Falls back to mock data on any failure."""
    if not config.FORCE_MOCK_WEATHER:
        try:
            return _fetch_live(farmer_id, lat, lng, planting_date)
        except Exception as exc:  # network error, bad JSON, missing soil data, ...
            log.warning("Live weather failed (%s) - using mock data", exc)
    return _build_mock(lat, lng, planting_date, scenario or config.MOCK_SCENARIO)


# --------------------------------------------------------------------------- #
# Live (Open-Meteo)
# --------------------------------------------------------------------------- #
def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _aggregate_hourly(hourly: dict) -> dict:
    """Group hourly arrays into per-date aggregates."""
    times = hourly["time"]
    fields = {"t": "temperature_2m", "h": "relative_humidity_2m", "p": "precipitation",
              "sm": "soil_moisture_3_to_9cm", "st": "soil_temperature_6cm"}
    days: dict = {}
    for i, stamp in enumerate(times):
        bucket = days.setdefault(stamp[:10], {k: [] for k in fields})
        for key, name in fields.items():
            series = hourly.get(name)
            if series and series[i] is not None:
                bucket[key].append(series[i])
    return days


def _fetch_forecast(lat: float, lng: float) -> dict:
    key = ("fc", round(lat, 2), round(lng, 2))
    cached = _cache_get(key)
    if cached:
        return cached
    params = {
        "latitude": lat, "longitude": lng, "timezone": "auto",
        "current": "temperature_2m,relative_humidity_2m",
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,soil_moisture_3_to_9cm,soil_temperature_6cm",
        "past_days": 7, "forecast_days": 7,
    }
    resp = httpx.get(FORECAST_URL, params=params, timeout=config.HTTP_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    _cache_set(key, data)
    return data


def _fetch_archive(lat: float, lng: float, start: date, end: date) -> dict:
    """ONE batch request for the whole planting->today range (SRS FR-2.3). Returns {date: (tmean, rain)}."""
    params = {"latitude": lat, "longitude": lng, "start_date": start.isoformat(), "end_date": end.isoformat(),
              "daily": "temperature_2m_mean,precipitation_sum", "timezone": "auto"}
    resp = httpx.get(ARCHIVE_URL, params=params, timeout=config.HTTP_TIMEOUT * 2)
    resp.raise_for_status()
    d = resp.json()["daily"]
    return {t: (tm, p) for t, tm, p in zip(d["time"], d["temperature_2m_mean"], d["precipitation_sum"])}


def _fetch_live(farmer_id: str, lat: float, lng: float, planting: date) -> dict:
    data = _fetch_forecast(lat, lng)
    days = _aggregate_hourly(data["hourly"])
    now_stamp = data["current"]["time"]                # local time, e.g. 2026-09-24T14:15
    today = now_stamp[:10]
    hour_stamp = now_stamp[:13] + ":00"
    times = data["hourly"]["time"]
    idx = times.index(hour_stamp) if hour_stamp in times else None

    def hourly_now(name):
        series = data["hourly"].get(name)
        return series[idx] if (series and idx is not None) else None

    sm_now = hourly_now("soil_moisture_3_to_9cm")
    if sm_now is None:
        sm_now = _mean(days.get(today, {}).get("sm", []))
    if sm_now is None:
        raise ValueError("soil moisture unavailable for this location")   # -> mock fallback
    st_now = hourly_now("soil_temperature_6cm")
    if st_now is None:
        st_now = _mean(days.get(today, {}).get("st", [])) or data["current"]["temperature_2m"]

    ordered = sorted(days)
    future = [d for d in ordered if d >= today][:7]
    forecast = []
    for d in future:
        b = days[d]
        forecast.append({
            "date": d,
            "temperature_c": round(max(b["t"]), 1) if b["t"] else 0.0,     # daily HIGH
            "rain_mm": round(sum(b["p"]), 1),
            "humidity_pct": round(_mean(b["h"]) or 0, 0),
        })

    trend = []
    for d in [x for x in ordered if x <= today][-7:]:
        m = _mean(days[d]["sm"])
        if m is not None:
            trend.append({"date": d, "value": round(m * 100, 1)})          # m3/m3 -> %

    # Since-planting summary: forecast API covers the last 7 days, archive API covers older days.
    per_day = {}                                                           # date -> (tmean, rain)
    for d in ordered:
        if d < today:
            per_day[d] = (_mean(days[d]["t"]), sum(days[d]["p"]))
    today_d = date.fromisoformat(today)
    archive_end = today_d - timedelta(days=8)
    arch_start = max(planting, today_d - timedelta(days=400))
    if arch_start <= archive_end:
        akey = ("arch", farmer_id, planting.isoformat(), today)
        arch = _cache_get(akey, ttl=6 * 3600)
        if arch is None:
            try:
                arch = _fetch_archive(lat, lng, arch_start, archive_end)
                _cache_set(akey, arch)
            except Exception as exc:
                log.warning("Archive fetch failed (%s) - summary uses recent days only", exc)
                arch = {}
        for d, val in arch.items():
            per_day.setdefault(d, val)
    tracked = [(t, p) for d, (t, p) in per_day.items() if d >= planting.isoformat() and t is not None]
    summary = {
        "avg_temperature_c": round(sum(t for t, _ in tracked) / len(tracked), 1) if tracked else 0.0,
        "total_rain_mm": round(sum((p or 0) for _, p in tracked), 1),
        "days_tracked": len(tracked),
    }

    return {
        "source": "live",
        "current": {
            "temperature_c": round(data["current"]["temperature_2m"], 1),
            "humidity_pct": round(data["current"]["relative_humidity_2m"], 0),
            "soil_moisture_pct": round(sm_now * 100, 1),
            "soil_temperature_c": round(st_now, 1),
        },
        "forecast_7day": forecast,
        "since_planting_summary": summary,
        "soil_trend": trend,
    }


# --------------------------------------------------------------------------- #
# Mock (deterministic: same location + scenario => same numbers)
# --------------------------------------------------------------------------- #
# soil_start/soil_end: soil moisture % 6 days ago -> today. rain: {forecast_day_index: mm}
SCENARIOS = {
    "dry":       {"soil_start": 29, "soil_end": 17, "temp_delta": 3, "rain": {}, "hum": 45},
    "hot":       {"soil_start": 26, "soil_end": 19, "temp_delta": 7, "rain": {}, "hum": 35},
    "rain_soon": {"soil_start": 27, "soil_end": 20, "temp_delta": 1, "rain": {1: 14, 2: 9}, "hum": 70},
    "wet":       {"soil_start": 44, "soil_end": 52, "temp_delta": 0, "rain": {0: 6, 1: 12, 3: 8}, "hum": 85},
    "ok":        {"soil_start": 32, "soil_end": 30, "temp_delta": 0, "rain": {4: 5}, "hum": 55},
}


def _build_mock(lat: float, lng: float, planting: date, scenario: str) -> dict:
    sc = SCENARIOS.get(scenario, SCENARIOS["dry"])
    seed = int(hashlib.md5(f"{round(lat, 1)}|{round(lng, 1)}|{scenario}".encode()).hexdigest()[:8], 16)
    rnd = random.Random(seed)
    today = date.today()
    base_t = 30 - min(10, abs(lat - 15) * 0.25) + rnd.uniform(-1.0, 1.0)

    trend = []
    for i in range(7):
        frac = i / 6
        val = sc["soil_start"] + (sc["soil_end"] - sc["soil_start"]) * frac + rnd.uniform(-0.4, 0.4)
        trend.append({"date": (today - timedelta(days=6 - i)).isoformat(), "value": round(val, 1)})
    if len(trend):
        trend[-1]["value"] = float(sc["soil_end"])            # today's value exactly matches the scenario

    forecast = []
    for i in range(7):
        forecast.append({
            "date": (today + timedelta(days=i)).isoformat(),
            "temperature_c": round(base_t + sc["temp_delta"] + rnd.uniform(-1, 1), 1),
            "rain_mm": float(sc["rain"].get(i, 0.0)),
            "humidity_pct": round(sc["hum"] + rnd.uniform(-5, 5), 0),
        })

    days = max(0, (today - planting).days)
    summary = {
        "avg_temperature_c": round(base_t + rnd.uniform(-1, 1), 1),
        "total_rain_mm": round(days * 2.2 * rnd.uniform(0.7, 1.3), 1),
        "days_tracked": days,
    }
    return {
        "source": "mock",
        "current": {
            "temperature_c": round(forecast[0]["temperature_c"] - 2, 1),
            "humidity_pct": float(sc["hum"]),
            "soil_moisture_pct": float(sc["soil_end"]),
            "soil_temperature_c": round(forecast[0]["temperature_c"] - 4, 1),
        },
        "forecast_7day": forecast,
        "since_planting_summary": summary,
        "soil_trend": trend,
    }
