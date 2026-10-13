"""Claude for the city: the one place that calls the Anthropic API.

Calls the Messages API over plain HTTPS with `requests` rather than the official
`anthropic` SDK: on this PC, Windows Smart App Control blocks one of the SDK's
compiled dependencies (pydantic_core), while `requests` is allowed. Same API, same
model, same features.

Agents ask for structured JSON and get a dict back. If Claude is unavailable for
any reason (no ANTHROPIC_API_KEY, network/API error, or the request is declined),
ask_json raises LLMUnavailable and the calling agent falls back to a neutral
answer, so the city keeps running without Claude.
"""
import json
import time

import requests

from config import settings

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
MODEL = "claude-opus-5-5"
# Refusal fallback: if the model declines, the API retries on a fallback model
# picked by refusal category, inside the same call (sent with fallbacks="default").
FALLBACK_BETA = "server-side-fallback-2026-07-01"
RETRIES = 3          # attempts for rate limits (429), overload (529) and server errors
TIMEOUT_S = 120


class LLMUnavailable(RuntimeError):
    pass


def check_ready():
    """Raise LLMUnavailable if Claude can't be called at all (no key)."""
    if not settings.ANTHROPIC_API_KEY:
        raise LLMUnavailable("ANTHROPIC_API_KEY is not set in .env")


def _error_message(r):
    try:
        return r.json()["error"]["message"]
    except (ValueError, KeyError, TypeError):
        return r.text[:200]


def _post(payload, session=None):
    check_ready()
    headers = {
        "x-api-key": settings.ANTHROPIC_API_KEY,
        "anthropic-version": API_VERSION,
        "anthropic-beta": FALLBACK_BETA,
        "content-type": "application/json",
    }
    http = session or requests
    problem = "no attempt made"
    for attempt in range(RETRIES):
        if attempt:
            time.sleep(2 ** attempt)  # 2s, then 4s
        try:
            r = http.post(API_URL, headers=headers, json=payload, timeout=TIMEOUT_S)
        except requests.RequestException as e:
            problem = f"network error: {e}"
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429 or r.status_code >= 500:  # worth retrying
            problem = f"HTTP {r.status_code}: {_error_message(r)}"
            continue
        raise LLMUnavailable(f"Claude API error {r.status_code}: {_error_message(r)}")
    raise LLMUnavailable(f"Claude API unavailable after {RETRIES} tries ({problem})")


def ask_json(system, prompt, schema, effort="low", max_tokens=4000, session=None):
    """Ask Claude for JSON matching `schema`. Returns the parsed dict.

    effort: "low" for quick classification, "medium"/"high" for writing that needs thought.
    session: inject a fake in tests; by default a real HTTPS request is made.
    """
    data = _post({
        "model": MODEL,
        "max_tokens": max_tokens,
        "fallbacks": "default",
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
        "output_config": {"effort": effort,
                          "format": {"type": "json_schema", "schema": schema}},
    }, session)

    stop = data.get("stop_reason")
    if stop == "refusal":
        raise LLMUnavailable("Claude declined the request")
    if stop == "max_tokens":
        raise LLMUnavailable("Claude's answer was cut off (max_tokens)")
    text = next((b.get("text") for b in data.get("content", []) if b.get("type") == "text"), None)
    if text is None:
        raise LLMUnavailable("Claude returned no text")
    try:
        return json.loads(text)
    except ValueError as e:
        raise LLMUnavailable(f"Claude's answer was not valid JSON: {e}") from e
