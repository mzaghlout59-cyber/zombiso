"""Claude for the city: the one place that calls the Anthropic API.

Agents ask for structured JSON and get a dict back. If Claude is unavailable for
any reason (no ANTHROPIC_API_KEY, the SDK can't load, network/API error, or the
request is declined), ask_json raises LLMUnavailable and the calling agent falls
back to a neutral answer, so the city keeps running without Claude.
"""
import json

from config import settings

MODEL = "claude-opus-5-5"
# Refusal fallback: if the model declines, the API retries on a fallback model
# picked by refusal category, inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMUnavailable(RuntimeError):
    pass


def _sdk():
    try:
        import anthropic
        return anthropic
    except Exception as e:  # e.g. a blocked native module, not just ImportError
        raise LLMUnavailable(f"Anthropic SDK could not load: {e}") from e


def make_client():
    if not settings.ANTHROPIC_API_KEY:
        raise LLMUnavailable("ANTHROPIC_API_KEY is not set in .env")
    return _sdk().Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def ask_json(system, prompt, schema, effort="low", max_tokens=4000, client=None):
    """Ask Claude for JSON matching `schema`. Returns the parsed dict.

    effort: "low" for quick classification, "medium"/"high" for writing that needs thought.
    client: inject a fake in tests; by default a real client is built from .env.
    """
    real = client is None
    client = client or make_client()
    api_errors = ()
    if real:
        sdk = _sdk()
        api_errors = (sdk.APIStatusError, sdk.APIConnectionError)
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": effort,
                           "format": {"type": "json_schema", "schema": schema}},
        )
    except api_errors as e:
        raise LLMUnavailable(f"Claude API error: {e}") from e

    if response.stop_reason == "refusal":
        raise LLMUnavailable("Claude declined the request")
    if response.stop_reason == "max_tokens":
        raise LLMUnavailable("Claude's answer was cut off (max_tokens)")
    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise LLMUnavailable("Claude returned no text")
    return json.loads(text)
