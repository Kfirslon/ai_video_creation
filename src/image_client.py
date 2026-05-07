"""Image generation via Gemini's Nano Banana family.

Auto-discovers the working model name on first call by trying each candidate
in `config.GEMINI_IMAGE_MODEL_CANDIDATES` until one succeeds. Caches the winner
so subsequent calls hit the right model immediately.

This is needed because Google has renamed the model name several times
(`-preview` → GA → various `imagen-*` variants), and a hardcoded name breaks
silently with a 404 whenever they ship a new alias.
"""
from __future__ import annotations

import io
import time
from pathlib import Path

from PIL import Image

from . import config

_client = None
_resolved_model: str | None = None


def _gemini():
    global _client
    if _client is None:
        from google import genai
        config.assert_gemini_key()
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _is_rate_limit_error(err: Exception) -> bool:
    msg = str(err).lower()
    return any(s in msg for s in ("429", "rate", "quota", "resource_exhausted"))


def _is_model_not_found(err: Exception) -> bool:
    msg = str(err).lower()
    return "404" in msg or "not_found" in msg or "is not found" in msg


def _try_generate(model_name: str, contents: list) -> Image.Image:
    """Single attempt against a specific model. Returns PIL image or raises."""
    resp = _gemini().models.generate_content(model=model_name, contents=contents)
    for cand in resp.candidates or []:
        for part in cand.content.parts or []:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                return Image.open(io.BytesIO(inline.data))
    raise RuntimeError(
        f"Model '{model_name}' returned no image (safety filter may have blocked the prompt)."
    )


def _resolve_model(contents: list) -> tuple[str, Image.Image]:
    """Try each candidate until one works. Returns (model_name, first_image)."""
    global _resolved_model
    last_err: Exception | None = None

    if _resolved_model:
        try:
            return _resolved_model, _try_generate(_resolved_model, contents)
        except Exception as err:
            if not _is_model_not_found(err):
                raise
            # Model went away mid-session; reset and re-discover
            _resolved_model = None
            last_err = err

    for name in config.GEMINI_IMAGE_MODEL_CANDIDATES:
        try:
            img = _try_generate(name, contents)
            _resolved_model = name
            return name, img
        except Exception as err:
            last_err = err
            if _is_model_not_found(err):
                continue  # try next candidate
            # Real error — surface it
            raise

    tried = ", ".join(config.GEMINI_IMAGE_MODEL_CANDIDATES)
    raise RuntimeError(
        f"None of the candidate image models work on this API key.\n"
        f"Tried: {tried}\n"
        f"Last error: {last_err}\n\n"
        f"Visit https://aistudio.google.com/app/apikey and check that your key has "
        f"image-generation access. You can override the model name by setting "
        f"GEMINI_IMAGE_MODEL=<name> in .env"
    )


def active_model() -> str:
    """Best guess at which model will be used (resolved if known, else first candidate)."""
    return _resolved_model or config.GEMINI_IMAGE_MODEL_CANDIDATES[0]


def generate_image(
    prompt: str,
    *,
    reference_images: list[Path] | None = None,
    max_retries: int = 5,
) -> Image.Image:
    """Generate an image. Uses the first working candidate model and caches it."""
    from google.genai import types

    contents: list = [prompt]
    if reference_images:
        for ref in reference_images:
            with open(ref, "rb") as f:
                contents.append(
                    types.Part.from_bytes(data=f.read(), mime_type="image/png")
                )

    delay = 2.0
    for attempt in range(max_retries):
        try:
            _name, img = _resolve_model(contents)
            return img
        except Exception as err:
            if _is_rate_limit_error(err) and attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise

    raise RuntimeError("Image generation exhausted retries")
