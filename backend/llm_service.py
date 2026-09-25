"""LLM phrasing layer  -  the LLM ONLY REPHRASES, it never decides.

phrase(decision) -> str      (1-3 plain-language sentences; NEVER raises)

The decision engine has already chosen the action, time window, confidence, reasons and
consequence. We hand those to the LLM and tell it to rewrite them in simple words without
changing the substance (SRS FR-5.3).

Providers (set in .env):
  LLM_PROVIDER=openai     -> any OpenAI-compatible /chat/completions endpoint (OpenAI, Groq, Together, ...)
  LLM_PROVIDER=anthropic  -> Anthropic Messages API
If LLM_API_KEY is empty, FORCE_MOCK_LLM=true, the call fails, or the reply looks unusable,
we fall back to a deterministic template so the demo never breaks.
"""
import json
import logging
import re
import time

import httpx

import config

log = logging.getLogger("farmsense.llm")

DEFAULT_URLS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "anthropic": "https://api.anthropic.com/v1/messages",
}
DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
}

SYSTEM_PROMPT = (
    "You help smallholder farmers who may have low reading ability. You will receive a farming "
    "decision that has ALREADY been made by a rule-based system. Your only job is to rewrite it in "
    "very simple, warm, everyday English, in 1 to 3 short sentences.\n"
    "Rules:\n"
    "- Do NOT change, add to, or contradict the action, the time window, or the reasons.\n"
    "- Do NOT invent new advice, products, doses or numbers.\n"
    "- Keep the time window exactly as given.\n"
    "- Briefly say why (using the given reasons) and, if it fits, what may happen if the farmer does nothing.\n"
    "- No technical terms, no percentages, no bullet points, no markdown, no emojis.\n"
    "- Reply with the message text only."
)

# Fields that are passed to the LLM (everything else stays out of the prompt)
_LLM_FIELDS = ("action", "time_window", "confidence_pct", "reasoning_factors", "consequence_if_ignored")

_CACHE: dict = {}          # key -> (timestamp, text); avoids re-calling the LLM for identical decisions
_CACHE_TTL = 3600
_CACHE_MAX = 200


# --------------------------------------------------------------------------- #
# Public
# --------------------------------------------------------------------------- #
def phrase(decision: dict) -> str:
    key = json.dumps({k: decision.get(k) for k in _LLM_FIELDS}, sort_keys=True)
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < _CACHE_TTL:
        return hit[1]

    if not config.FORCE_MOCK_LLM and config.LLM_API_KEY:
        try:
            text = _clean(_call_llm(decision))
            if text:
                if len(_CACHE) >= _CACHE_MAX:
                    _CACHE.clear()
                _CACHE[key] = (time.time(), text)
                return text
            log.warning("LLM reply was empty/unusable - using template")
        except Exception as exc:
            log.warning("LLM call failed (%s) - using template", exc)
    return _mock_phrase(decision)


# --------------------------------------------------------------------------- #
# Real LLM call
# --------------------------------------------------------------------------- #
def _call_llm(decision: dict) -> str:
    provider = config.LLM_PROVIDER if config.LLM_PROVIDER in DEFAULT_URLS else "openai"
    url = config.LLM_API_URL or DEFAULT_URLS[provider]
    model = config.LLM_MODEL or DEFAULT_MODELS[provider]
    payload = {k: decision.get(k) for k in _LLM_FIELDS}
    user_msg = ("Decision (already made - do not change it):\n"
                + json.dumps(payload, indent=2)
                + "\n\nWrite the farmer-facing message now.")

    if provider == "anthropic":
        resp = httpx.post(
            url,
            headers={"x-api-key": config.LLM_API_KEY, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": "allam-2-7b", "max_tokens": 600, "system": SYSTEM_PROMPT,
                  "messages": [{"role": "user", "content": user_msg}],"reasoning_effort": "low"},
            timeout=config.HTTP_TIMEOUT * 3,
        )
        resp.raise_for_status()
        return "".join(b.get("text", "") for b in resp.json().get("content", []) if b.get("type") == "text")

    # OpenAI-compatible
    resp = httpx.post(
        url,
        headers={"Authorization": f"Bearer {config.LLM_API_KEY}", "Content-Type": "application/json"},
        json={"model": model,
              "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                           {"role": "user", "content": user_msg}],
              "max_tokens": 250},
        timeout=config.HTTP_TIMEOUT * 3,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _clean(text: str) -> str:
    """Sanity-check the LLM output: single paragraph, no markdown, sensible length."""
    if not text:
        return ""
    text = re.sub(r"[*_#`>]+", "", text)
    text = re.sub(r"\s+", " ", text).strip().strip('"').strip()
    if len(text) < 10 or len(text) > 600:
        return ""
    return text


# --------------------------------------------------------------------------- #
# Deterministic fallback (no LLM needed)
# --------------------------------------------------------------------------- #
def _cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def _mock_phrase(d: dict) -> str:
    action = d.get("action", "")
    tw = d.get("time_window", "")
    reasons = d.get("reasoning_factors") or []
    consequence = d.get("consequence_if_ignored", "")

    lead = {
        "irrigate": f"Please water your field {tw}.",
        "wait": f"You do not need to water right now - {tw}.",
        "no_action": "You do not need to do anything today.",
        "pest_action": f"Please treat the problem on your crop {tw}.",
        "apply_fertilizer": f"Please apply fertilizer {tw}.",
    }.get(action, f"Your next step: {tw}.")

    parts = [lead]
    if reasons:
        parts.append(_cap(reasons[0]).rstrip(".") + ".")
    if consequence and action != "no_action":
        parts.append(consequence)
    return " ".join(parts)
