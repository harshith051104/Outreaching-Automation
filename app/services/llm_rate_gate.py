"""
Shared LLM rate-limit gate.

When a provider (Groq, Nvidia, etc.) returns 429, every email-generation and
send path must pause until the provider's window resets, then resume — instead
of hammering the limit and dropping emails.

The cooldown is stored on disk so it is honoured across Celery worker processes
(each lead is a separate task/process). No external dependency required.
"""

import json
import logging
import re
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_GATE_FILE = Path(__file__).parent / ".llm_rate_limit.json"
_LOCK = threading.Lock()
_DEFAULT_COOLDOWN = 60.0


class LLMRateLimitError(Exception):
    """Raised when the LLM provider rejects a request due to rate limiting."""

    def __init__(self, retry_after: float = _DEFAULT_COOLDOWN, *args):
        self.retry_after = float(retry_after)
        super().__init__(*args)


def _read_reset_at() -> float:
    try:
        return float(json.loads(_GATE_FILE.read_text()).get("reset_at", 0.0))
    except Exception:
        return 0.0


def _write_reset_at(reset_at: float) -> None:
    try:
        _GATE_FILE.write_text(json.dumps({"reset_at": reset_at}))
    except Exception:
        logger.warning("llm_rate_gate: could not persist cooldown to %s", _GATE_FILE)


def remaining() -> float:
    """Seconds left in the active cooldown (0.0 if none)."""
    return max(0.0, _read_reset_at() - time.time())


def is_rate_limited() -> bool:
    return remaining() > 0.0


def mark_rate_limited(retry_after: float = _DEFAULT_COOLDOWN) -> None:
    """Record a provider-wide cooldown that expires in `retry_after` seconds."""
    reset_at = time.time() + max(float(retry_after), 1.0)
    with _LOCK:
        _write_reset_at(reset_at)
    logger.warning("llm_rate_gate: rate limited — pausing all LLM calls for %.1fs", reset_at - time.time())


def wait_out_llm_rate_limit(step: float = 1.0) -> None:
    """Block (sync) until the shared cooldown expires.

    Used at the start of every LLM call so a single 429 pauses the whole
    email-generation/send batch until the window resets.
    """
    rem = remaining()
    while rem > 0:
        time.sleep(min(step, rem))
        rem = remaining()


def parse_retry_after(response: object = None, error: Exception | None = None) -> float:
    """Best-effort extraction of the wait time from a 429 response/error."""
    # Header / body from an httpx.Response
    resp = getattr(response, "headers", None)
    if resp is not None:
        raw = resp.get("retry-after")
        if raw is not None:
            try:
                return float(raw)
            except (TypeError, ValueError):
                pass
    text = ""
    body = getattr(response, "text", None)
    if body:
        text = str(body).lower()
    if error is not None:
        text += " " + str(error).lower()
    m = re.search(r"retry[_ -]?after[: ]+([\d.]+)", text)
    if m:
        return float(m.group(1))
    # Groq/Nvidia style: "Please try again in 9m52.704s" or "try again in 45s"
    m = re.search(r"try again in (?:(\d+)\s*m)?(?:(\d+(?:\.\d+)?)\s*s)?", text)
    if m and (m.group(1) or m.group(2)):
        minutes = int(m.group(1)) if m.group(1) else 0
        seconds = float(m.group(2)) if m.group(2) else 0.0
        total = minutes * 60 + seconds
        if total > 0:
            return total
    if "429" in text or "rate limit" in text:
        return _DEFAULT_COOLDOWN
    return _DEFAULT_COOLDOWN


if __name__ == "__main__":
    # Self-check: parsing + cooldown pause/reset.
    import time as _t

    class _FakeResp:
        def __init__(self, headers):
            self.headers = headers

    assert parse_retry_after(response=_FakeResp({"retry-after": "12"})) == 12.0
    assert parse_retry_after(error=RuntimeError("HTTP 429 too many requests")) == _DEFAULT_COOLDOWN
    assert parse_retry_after(error=RuntimeError("retry after 7.5s")) == 7.5

    mark_rate_limited(1.0)
    assert is_rate_limited(), "should be limited right after marking"
    assert remaining() > 0
    wait_out_llm_rate_limit()
    assert not is_rate_limited(), "cooldown should have expired"
    # reset so the on-disk gate file is left clean
    _write_reset_at(0.0)
    print("llm_rate_gate self-check OK")

