from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
# Nano Banana graduated from -preview to GA in late 2025. Try in order; first that works wins.
GEMINI_IMAGE_MODEL_CANDIDATES = [
    os.getenv("GEMINI_IMAGE_MODEL"),  # explicit override wins if set
    "gemini-2.5-flash-image",                    # current GA Nano Banana
    "gemini-2.0-flash-preview-image-generation", # fallback for older API keys
    "gemini-2.0-flash-exp-image-generation",     # very old fallback
]
GEMINI_IMAGE_MODEL_CANDIDATES = [m for m in GEMINI_IMAGE_MODEL_CANDIDATES if m]
GEMINI_IMAGE_MODEL = GEMINI_IMAGE_MODEL_CANDIDATES[0]  # for display only

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_TEXT_MODEL = os.getenv("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile")

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base.en")
UI_PORT = int(os.getenv("UI_PORT", "5173"))

# Optional shared password for public deploys (HF Spaces). Empty = no auth (local mode).
APP_PASSWORD = os.getenv("APP_PASSWORD", "").strip()

# Auto-mode: paid Veo 3 video generation via Kie.ai. Empty = manual paste flow.
KIE_AI_API_KEY = os.getenv("KIE_AI_API_KEY", "").strip()
KIE_AI_BASE_URL = os.getenv("KIE_AI_BASE_URL", "https://api.kie.ai").rstrip("/")
KIE_AI_MODEL = os.getenv("KIE_AI_MODEL", "veo3_fast")  # cheapest tier; 'veo3' for higher quality

# Public base URL of this app (so Kie.ai can fetch the scene images we send it).
# On HF Spaces we can derive it from SPACE_ID; locally it's not reachable from external services.
def public_base_url() -> str:
    explicit = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    if explicit:
        return explicit
    space_id = os.getenv("SPACE_ID", "").strip()
    if space_id and "/" in space_id:
        owner, name = space_id.split("/", 1)
        return f"https://{owner.lower()}-{name.lower()}.hf.space"
    return ""

PROMPTS_DIR = ROOT / "prompts"
PROJECTS_DIR = ROOT / "projects"
MUSIC_DIR = ROOT / "library" / "music"

PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
MUSIC_DIR.mkdir(parents=True, exist_ok=True)


def load_style_presets() -> dict:
    return json.loads((PROMPTS_DIR / "style_presets.json").read_text(encoding="utf-8"))


def load_voiceover_prefix() -> str:
    return (PROMPTS_DIR / "voiceover_prefix.txt").read_text(encoding="utf-8").strip()


def slugify(text: str, max_len: int = 60) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s[:max_len] or "untitled"


def project_dir(slug: str) -> Path:
    p = PROJECTS_DIR / slug
    (p / "images").mkdir(parents=True, exist_ok=True)
    (p / "videos").mkdir(parents=True, exist_ok=True)
    return p


def assert_gemini_key() -> None:
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Copy .env.example to .env and paste your key "
            "from https://aistudio.google.com/app/apikey (required for image generation)"
        )


def assert_text_provider() -> None:
    if not GROQ_API_KEY and not GEMINI_API_KEY:
        raise RuntimeError(
            "No text-generation provider configured. Set either GROQ_API_KEY "
            "(https://console.groq.com/keys, free) or GEMINI_API_KEY in .env"
        )


# Backwards-compat alias
assert_api_key = assert_gemini_key
