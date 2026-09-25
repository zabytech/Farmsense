"""FarmSense Decision Engine  -  DETERMINISTIC, RULE-BASED, EXPLAINABLE.

No machine learning and no randomness here: the same inputs always give the same
output. All thresholds / weights live in rules.json so they can be edited without
touching code.

HOW IT WORKS (say this to the judges)
--------------------------------------
1. GROWTH STAGE  : crop type + planting date -> sowing / vegetative / flowering / maturity
                   (lookup table in rules.json). Each stage has a water-sensitivity weight.
2. SIGNALS       : soil moisture (now + 3-day trend), rain in next 48h/72h, heat, humidity.
3. THREE DECISION AREAS, each scored 0-100 for urgency:
     a) IRRIGATION  - weighted points: dry soil, falling trend, no rain, heat, watering history.
                      Positive points are multiplied by the stage weight (flowering = 1.4x),
                      rain/rising moisture subtract points. A COMPOUND bonus is added when
                      heat + dry soil + a sensitive stage happen together.
     b) PEST/DISEASE - from the latest photo result or the farmer's symptom choice. Severity is
                      raised when the weather helps the problem spread (humid -> fungus,
                      hot+dry -> pests).
     c) FERTILIZER   - from fertilizer history + growth stage (+ yellowing leaves).
4. PICK ONE      : the actionable area with the highest urgency becomes the headline action.
                   If nothing needs doing, the irrigation verdict (wait / no_action) is used.
5. CONFIDENCE    : based on how far the score is from a decision boundary, minus penalties when
                   data is missing, estimated (mock) or contradictory  (SRS "data honesty").
6. OUTPUT        : action, time window, confidence, reasoning factors, consequence if ignored,
                   fertilizer tip, pest/disease advice. The LLM only rephrases this afterwards.
"""
import json
import os
from datetime import date

_RULES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.json")
with open(_RULES_PATH, "r", encoding="utf-8") as _f:
    RULES = json.load(_f)

ACTIONABLE = {"irrigate", "pest_action", "apply_fertilizer"}
AREA_PRIORITY = ["irrigation", "pest", "fertilizer"]   # tie-break order


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


# --------------------------------------------------------------------------- #
# Step 1: crop + growth stage lookup
# --------------------------------------------------------------------------- #
def _get_crop(crop_type: str):
    key = (crop_type or "").strip().lower()
    if key in RULES["crops"]:
        return key, RULES["crops"][key], RULES["crops"][key]["display"]
    return key, RULES["default_crop"], (key or "crop")


def get_growth_stage(crop: dict, planting_date: date, today: date):
    """Days since planting -> stage name using the crop's stage table."""
    days = max(0, (today - planting_date).days)
    for st in crop["stages"]:
        if days <= st["until_day"]:
            return st["name"], days
    return "maturity", days                           # past the table = harvest-ready


# --------------------------------------------------------------------------- #
# Step 2: signals derived from environment data
# --------------------------------------------------------------------------- #
def _signals(env: dict) -> dict:
    fc = env.get("forecast_7day") or []
    trend = env.get("soil_trend") or []
    cur = env["current"]
    change = None
    if len(trend) >= 4:                               # change over the last 3 days
        change = trend[-1]["value"] - trend[-4]["value"]
    temps = [cur["temperature_c"]] + [f["temperature_c"] for f in fc[:2]]
    hums = [f["humidity_pct"] for f in fc[:3]] or [cur["humidity_pct"]]
    return {
        "sm": cur["soil_moisture_pct"],
        "trend_change": change,
        "trend_len": len(trend),
        "rain_48h": sum(f["rain_mm"] for f in fc[:2]),
        "rain_72h": sum(f["rain_mm"] for f in fc[:3]),
        "humidity_72h": sum(hums) / len(hums),
        "peak_temp": max(temps),
    }


def _condition_info(condition: dict | None):
    """Normalise the latest pest/disease input (photo or manual)."""
    if not condition:
        return None
    name = condition.get("condition", "unknown")
    if name == "unknown":
        return None
    info = RULES["conditions"].get(name, {"category": "unknown", "severity": 1, "label": "a problem on the crop"})
    return {"name": name, "category": info["category"], "severity": info.get("severity", 0),
            "label": info.get("label", name), "confidence": float(condition.get("confidence") or 0),
            "source": condition.get("source", "manual")}


# --------------------------------------------------------------------------- #
# Data-honesty penalties (FR-5.4)
# --------------------------------------------------------------------------- #
def _data_quality(env: dict, sig: dict, cond):
    Q = RULES["data_quality"]
    pen, notes = 0, []
    if env.get("source") == "mock":
        pen += Q["estimated_weather_penalty"]
        notes.append("weather and soil figures are estimates right now, so confidence is lower")
    if sig["trend_len"] < 4:
        pen += Q["short_trend_penalty"]
        notes.append("only a few days of soil history are available, so confidence is lower")
    if cond is None:
        pen += Q["no_crop_check_penalty"]
        notes.append("no photo or crop description was given, so confidence is a little lower")
    return pen, notes


# --------------------------------------------------------------------------- #
# Step 3a: IRRIGATION  (weighted-points model)
# --------------------------------------------------------------------------- #
def _irrigation(profile, sig, stage, stage_label, crop, crop_name, cond, dq_pen, dq_notes):
    I = RULES["irrigation"]
    P, T = I["points"], I["thresholds"]
    TW = RULES["time_windows"]
    sens = RULES["stage_irrigation_sensitivity"][stage]     # how much water shortage hurts NOW
    sm, low, high = sig["sm"], crop["moisture_low"], crop["moisture_high"]

    pos = 0.0        # points that RAISE urgency (later scaled by stage sensitivity)
    neg = 0.0        # points that LOWER urgency (rain, wet soil) - not scaled
    reasons = []

    # (a) How dry is the soil compared with this crop's comfort range?
    dry = overwet = False
    if sm < low * I["critical_factor"]:
        pos += P["critical_dry"]; dry = True
        reasons.append(f"soil is very dry for your {crop_name}")
    elif sm < low:
        pos += P["dry"]; dry = True
        reasons.append(f"soil is getting dry for your {crop_name}")
    elif sm < low * I["borderline_factor"]:
        pos += P["borderline"]
        reasons.append("soil moisture is close to the dry limit")
    elif sm > high:
        neg += P["wet_soil"]; overwet = True
        reasons.append(f"soil is already wet enough for your {crop_name}")
    else:
        reasons.append(f"soil moisture is comfortable for your {crop_name}")

    # (b) Is soil moisture falling or rising over the last 3 days?
    ch = sig["trend_change"]
    if ch is not None and not overwet:
        if ch <= -I["trend_change_points"]:
            pos += P["falling_trend"]
            reasons.append("soil has been drying out over the last few days")
        elif ch >= I["trend_change_points"]:
            neg += P["rising_trend"]
            reasons.append("soil moisture has been rising")

    # (c) Rain forecast: coming rain will water the crop for free, so it reduces urgency.
    if sig["rain_48h"] >= I["rain_heavy_mm"]:
        neg += P["rain_heavy"]
        reasons.append("good rain is expected in the next 2 days")
    elif sig["rain_48h"] >= I["rain_light_mm"]:
        neg += P["rain_light"]
        reasons.append("a little rain is expected soon")
    elif sig["rain_72h"] < I["no_rain_mm"]:
        pos += P["no_rain"]
        reasons.append("no rain is expected in the next 3 days")

    # (d) Heat speeds up water loss.
    if sig["peak_temp"] >= I["very_hot_c"]:
        pos += P["very_hot"]
        reasons.append("very hot weather is drying the soil faster")
    elif sig["peak_temp"] >= I["hot_c"]:
        pos += P["hot"]
        reasons.append("hot weather is drying the soil faster")

    # (e) Watering history: watering less often than the crop needs while soil is dry.
    wdays = profile["watering_days_per_week"] or 0
    if dry and wdays < crop["min_watering_days"]:
        pos += P["low_watering_history"]
        reasons.append("you have been watering less often than this crop usually needs")
    if overwet and wdays >= 6:
        reasons.append("frequent watering has kept the soil wet")

    # (f) Crop already showing thirst symptoms while soil is dry -> agrees with the soil signal.
    if cond and cond["category"] == "wilting" and dry:
        pos += P["wilting_and_dry"]
        reasons.append("your crop is already wilting")

    # (g) STAGE WEIGHT: multiply the 'raise urgency' points. Flowering = 1.4x, ripening = 0.5x.
    risk = pos * sens + neg
    if sens >= 1.3 and dry:
        reasons.append(f"{stage_label} is the stage when water shortage hurts most")

    # (h) COMPOUND RISK (FR-4.3): heat + dry soil + sensitive stage together is worse than the sum.
    if dry and sig["peak_temp"] >= I["compound_hot_c"] and sens >= 1.3:
        risk += P["compound_bonus"]
        reasons.append("heat, dry soil and a sensitive stage together make the risk much higher")

    risk = _clamp(risk, 0, 100)

    # (i) Convert risk score to an action + time window using the thresholds.
    if overwet:
        action, tw, consequence = "wait", TW["wait_wet"], RULES["wet_consequence"]
    elif risk >= T["irrigate_now"]:
        action, tw, consequence = "irrigate", TW["irrigate_now"], RULES["irrigation_consequences"][stage]
    elif risk >= T["irrigate_soon"]:
        action, tw, consequence = "irrigate", TW["irrigate_soon"], RULES["irrigation_consequences"][stage]
    elif risk >= T["watch"]:
        rain_helping = sig["rain_48h"] >= I["rain_light_mm"] and sm < low * I["borderline_factor"]
        action = "wait"
        tw = TW["wait_rain"] if rain_helping else TW["wait"]
        consequence = RULES["wait_consequence"]
    else:
        action, tw, consequence = "no_action", TW["no_action"], RULES["no_action_consequence"]

    # (j) Confidence = distance from nearest decision boundary, minus data-honesty penalties.
    if overwet:
        conf = 80.0
    else:
        dist = min(abs(risk - t) for t in T.values())
        conf = 55 + min(35, dist * 1.2)
    pen, notes = dq_pen, list(dq_notes)
    if cond and cond["category"] == "wilting" and not dry and not overwet:
        pen += RULES["data_quality"]["conflict_penalty"]
        notes.append("the crop looks wilted but the soil is not dry, so the signals disagree")
    conf = _clamp(round(conf - pen), 35, 95)

    return {"area": "irrigation", "action": action, "time_window": tw, "score": round(risk, 1),
            "confidence": conf, "reasons": reasons, "notes": notes, "consequence": consequence,
            "dry": dry, "overwet": overwet}


# --------------------------------------------------------------------------- #
# Step 3b: PEST / DISEASE
# --------------------------------------------------------------------------- #
def _pest(cond, sig, irr, crop_name):
    """Returns (decision_or_None, advice_text). Advice exists whenever a condition is detected."""
    if cond is None or cond["category"] == "healthy":
        return None, ""                                # FR-4.6: no condition -> no pest guidance
    PC, A, TW = RULES["pest"], RULES["condition_advice"], RULES["time_windows"]
    cat = cond["category"]

    # Symptoms that are really a WATER or NUTRIENT problem are handled by those areas.
    if cat == "nutrient":
        return None, A["nutrient_wet"] if irr["overwet"] else A["nutrient_dry_or_ok"]
    if cat == "wilting" and irr["dry"]:
        return None, A["wilting_dry"]                  # thirst: irrigation decision already boosted

    sev = cond["severity"] if cat != "unknown" else 1
    if cat == "wilting":
        sev = 2                                        # wilting with wet/normal soil: suspect disease/roots
    advice = {"fungal": A["fungal"], "pest": A["pest"], "viral": A["viral"],
              "wilting": A["wilting_wet"]}.get(cat, A["unknown"])
    who = "the photo suggests" if cond["source"] == "photo" else "you reported"
    reasons = [f"{who} {cond['label']}"]
    weather_escalated = False

    # WEATHER ESCALATION (compound risk): weather that helps the problem spread raises severity.
    if cat == "fungal" and (sig["humidity_72h"] >= PC["humid_pct"] or sig["rain_72h"] >= RULES["irrigation"]["rain_light_mm"]):
        sev += 1; weather_escalated = True
        reasons.append("humid or rainy weather helps this disease spread")
    if cat == "pest" and sig["peak_temp"] >= PC["hot_dry_c"] and sig["rain_72h"] < RULES["irrigation"]["no_rain_mm"]:
        sev += 1; weather_escalated = True
        reasons.append("hot, dry weather lets pests multiply faster")
    sev = min(3, sev)

    # Confidence: photo -> trust the model's own confidence (x0.9); manual -> fixed moderate value.
    if cond["source"] == "photo":
        conf = cond["confidence"] * 0.9
        if cond["confidence"] < PC["low_photo_confidence"]:
            sev -= 1                                   # weak model result -> do not over-react
            conf -= RULES["data_quality"]["low_photo_penalty"]
            reasons.append("the photo result is uncertain, so retake it in clear daylight")
            advice = "The photo result is uncertain. " + advice
    else:
        conf = PC["manual_confidence"]
    if weather_escalated:
        conf += 8
    conf = _clamp(round(conf), 35, 95)

    if sev <= 0:
        return None, advice
    return {"area": "pest", "action": "pest_action", "time_window": TW[f"pest_sev{sev}"],
            "score": PC["score_by_severity"][str(sev)], "confidence": conf, "reasons": reasons, "notes": [],
            "consequence": RULES["pest_consequences"].get(cat, RULES["pest_consequences"]["unknown"])}, advice


# --------------------------------------------------------------------------- #
# Step 3c: FERTILIZER  (history + growth stage; hormone advice is a static tip only - FR-4.5)
# --------------------------------------------------------------------------- #
def _fertilizer(profile, cond, sig, irr, crop, stage, stage_label, crop_name):
    F = RULES["fertilizer"]
    used = bool(profile["fertilizer_used"])
    yellowing = bool(cond and cond["name"] == "yellowing")
    in_topup = stage in crop["topup_stages"]

    # Static generic tip - shown only when fertilizer is relevant right now.
    relevant = in_topup or yellowing or stage == "maturity"
    tip = (F["tips_by_stage"][stage] + " " + F["hormone_tip"]) if relevant else ""

    # Gates: never fertilize a water-stressed crop (water first), into heavy rain (runoff),
    # near harvest, or when yellowing is really over-watering.
    if (stage == "maturity" or irr["score"] >= F["water_first_risk"]
            or sig["rain_48h"] >= F["heavy_rain_skip_mm"] or (yellowing and irr["overwet"])):
        return None, tip

    if yellowing and in_topup:
        return {"area": "fertilizer", "action": "apply_fertilizer", "time_window": RULES["time_windows"]["fertilizer"],
                "score": F["score_yellowing_topup"], "confidence": 65,
                "reasons": ["leaves are yellowing, a sign of nutrient shortage",
                            f"the {stage_label} stage needs extra nutrients"],
                "notes": [], "consequence": F["consequence_yellowing"]}, tip
    if in_topup and not used:
        return {"area": "fertilizer", "action": "apply_fertilizer", "time_window": RULES["time_windows"]["fertilizer"],
                "score": F["score_topup_never_used"], "confidence": 60,
                "reasons": [f"your {crop_name} is in the {stage_label} stage, when it needs extra nutrients",
                            "no fertilizer has been used so far"],
                "notes": [], "consequence": F["consequence_never_used"]}, tip
    if yellowing:
        reasons = ["leaves are yellowing, which often means a nutrient shortage"]
        if not used:
            reasons.append("no fertilizer has been used so far")
        return {"area": "fertilizer", "action": "apply_fertilizer", "time_window": RULES["time_windows"]["fertilizer"],
                "score": F["score_yellowing_other"], "confidence": 55, "reasons": reasons,
                "notes": [], "consequence": F["consequence_yellowing"]}, tip
    return None, tip


# --------------------------------------------------------------------------- #
# Step 4-6: combine everything into ONE recommendation
# --------------------------------------------------------------------------- #
def decide(profile: dict, env: dict, condition: dict | None, today: date | None = None) -> dict:
    """
    profile   : dict with crop_type, planting_date (date), watering_days_per_week, fertilizer_used, ...
    env       : output of weather_service.get_environment()
    condition : {"condition", "confidence", "source"} or None (latest photo/manual result)
    Returns the 7 contract fields plus a "_debug" dict (stripped by the API layer).
    """
    today = today or date.today()
    crop_key, crop, crop_name = _get_crop(profile["crop_type"])
    stage, days = get_growth_stage(crop, profile["planting_date"], today)
    stage_label = RULES["stage_labels"][stage]
    sig = _signals(env)
    cond = _condition_info(condition)
    dq_pen, dq_notes = _data_quality(env, sig, cond)

    irr = _irrigation(profile, sig, stage, stage_label, crop, crop_name, cond, dq_pen, dq_notes)
    pest, pest_advice = _pest(cond, sig, irr, crop_name)
    fert, fert_tip = _fertilizer(profile, cond, sig, irr, crop, stage, stage_label, crop_name)

    candidates = [d for d in (irr, pest, fert) if d]

    # Headline action = the actionable area with the highest urgency score.
    actionable = [d for d in candidates if d["action"] in ACTIONABLE]
    if actionable:
        primary = max(actionable, key=lambda d: (d["score"], -AREA_PRIORITY.index(d["area"])))
    else:
        primary = irr                                  # nothing to do -> report irrigation verdict

    reasons = list(primary["reasons"])
    if not any("stage" in r for r in reasons):
        reasons.append(f"your {crop_name} is in the {stage_label} stage")
    reasons += primary["notes"]                        # data-honesty notes (missing/estimated data)

    return {
        "action": primary["action"],
        "time_window": primary["time_window"],
        "confidence_pct": int(primary["confidence"]),
        "reasoning_factors": reasons[:7],
        "consequence_if_ignored": primary["consequence"],
        "fertilizer_tip": fert_tip,
        "pest_disease_advice": pest_advice,
        "_debug": {
            "crop": crop_key or "default", "growth_stage": stage, "days_since_planting": days,
            "signals": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in sig.items()},
            "candidates": [{"area": d["area"], "action": d["action"], "score": d["score"],
                            "confidence": d["confidence"]} for d in candidates],
            "chosen_area": primary["area"], "data_source": env.get("source"),
        },
    }
