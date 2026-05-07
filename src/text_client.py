"""Text generation: Groq primary (free, fast), Gemini fallback.

Strategy:
  - If GROQ_API_KEY is set, use Groq (Llama 3.3 70B by default).
    Saves Gemini quota for what only Gemini can do (Nano Banana images).
  - On Groq rate-limit / network error, automatically retry on Gemini if its key is set.
  - If only one provider's key is set, use it directly.

Both clients are lazy-initialized so missing optional deps never break import.
"""
from __future__ import annotations

import time

from . import config

_groq_client = None
_gemini_client = None


def _groq():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq(api_key=config.GROQ_API_KEY)
    return _groq_client


def _gemini():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _gemini_client


def _is_rate_limit_error(err: Exception) -> bool:
    msg = str(err).lower()
    return any(s in msg for s in ("429", "rate", "quota", "resource_exhausted"))


def _generate_groq(prompt: str, *, json_mode: bool = False, max_retries: int = 3) -> str:
    delay = 2.0
    kwargs: dict = {
        "model": config.GROQ_TEXT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.85,
    }
    if json_mode:
        # Forces strict JSON output — eliminates unescaped-quote bugs that break our extractor.
        # Requires the prompt to contain the word "JSON" (Groq enforces this).
        kwargs["response_format"] = {"type": "json_object"}
    for attempt in range(max_retries):
        try:
            resp = _groq().chat.completions.create(**kwargs)
            return (resp.choices[0].message.content or "").strip()
        except Exception as err:
            if _is_rate_limit_error(err) and attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise


def _generate_gemini(prompt: str, *, json_mode: bool = False, max_retries: int = 5) -> str:
    delay = 2.0
    for attempt in range(max_retries):
        try:
            kwargs: dict = {
                "model": config.GEMINI_TEXT_MODEL,
                "contents": prompt,
            }
            if json_mode:
                from google.genai import types
                kwargs["config"] = types.GenerateContentConfig(response_mime_type="application/json")
            resp = _gemini().models.generate_content(**kwargs)
            return (resp.text or "").strip()
        except Exception as err:
            if _is_rate_limit_error(err) and attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise


def active_provider() -> str:
    """Which provider would be tried first."""
    if config.GROQ_API_KEY:
        return f"groq ({config.GROQ_TEXT_MODEL})"
    if config.GEMINI_API_KEY:
        return f"gemini ({config.GEMINI_TEXT_MODEL})"
    return "none"


def generate_text(prompt: str, *, json_mode: bool = False) -> str:
    """Try Groq first, fall back to Gemini if Groq fails or is unavailable.

    Pass `json_mode=True` when you need strict JSON output. This forces
    the underlying provider to return valid JSON (no unescaped quotes,
    no markdown fences, no trailing prose). Requires the prompt to
    contain the word "JSON" or providers may reject it.
    """
    config.assert_text_provider()

    if config.GROQ_API_KEY:
        try:
            return _generate_groq(prompt, json_mode=json_mode)
        except Exception as groq_err:
            if not config.GEMINI_API_KEY:
                raise
            try:
                return _generate_gemini(prompt, json_mode=json_mode)
            except Exception as gemini_err:
                raise RuntimeError(
                    f"Both providers failed.\nGroq: {groq_err}\nGemini: {gemini_err}"
                ) from gemini_err

    return _generate_gemini(prompt, json_mode=json_mode)
