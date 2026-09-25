"""SMS delivery (Twilio REST API) with a mock fallback.

condense(recommendation) -> str    short SMS text: action + time window + one-line reason (FR-7.3)
send_sms(to, body)       -> bool   True = sent (or mocked), False = failed. NEVER raises.

Mock mode (no Twilio credentials, or FORCE_MOCK_SMS=true): the message is only logged to the
console and send_sms returns True, so the demo flow completes end-to-end.
"""
import logging
import re

import httpx

import config

log = logging.getLogger("farmsense.sms")

SMS_LIMIT = 160   # one standard SMS segment

_ACTION_PHRASE = {
    "irrigate": "Water your crop",
    "wait": "Do not water yet",
    "apply_fertilizer": "Apply fertilizer",
    "pest_action": "Treat the crop problem",
    "no_action": "No action needed",
}


def condense(rec: dict) -> str:
    """Build the SMS text from the structured recommendation (deterministic, no LLM needed)."""
    head = f"FarmSense: {_ACTION_PHRASE.get(rec.get('action'), 'Check your crop')} - {rec.get('time_window', '')}."
    reasons = [r.strip().rstrip(".") for r in (rec.get("reasoning_factors") or []) if r and r.strip()]
    room = SMS_LIMIT - len(head) - 1
    reason = next((r for r in reasons[:3] if len(r) + 1 <= room), None)   # first reason that fits
    if reason is None and reasons and room > 15:
        reason = reasons[0][: room - 4].rsplit(" ", 1)[0] + "..."
    if reason:
        return f"{head} {reason[:1].upper() + reason[1:]}."
    return head


def send_sms(to: str, body: str) -> bool:
    try:
        if config.FORCE_MOCK_SMS or not (config.TWILIO_ACCOUNT_SID and config.TWILIO_AUTH_TOKEN
                                         and config.TWILIO_FROM_NUMBER):
            log.info("[MOCK SMS] to=%s | %s", to or "(no number)", body)
            return True
        number = re.sub(r"[^\d+]", "", to or "")
        if not number:
            log.warning("SMS not sent: no phone number (set DEFAULT_SMS_TO or pass ?phone=...)")
            return False
        resp = httpx.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{config.TWILIO_ACCOUNT_SID}/Messages.json",
            data={"To": number, "From": config.TWILIO_FROM_NUMBER, "Body": body},
            auth=(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN),
            timeout=config.HTTP_TIMEOUT * 2,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        log.warning("SMS send failed: %s", exc)
        return False
