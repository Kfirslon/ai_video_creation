"""Generate posting metadata: title, description, hashtags."""
from __future__ import annotations

import json
from pathlib import Path

from .. import text_client
from .story import _extract_json


def generate_metadata(pack: dict) -> dict:
    """Return {title, description, hashtags: list[str]}."""
    prompt = (
        "You are writing the TikTok / Instagram Reels post copy for a 25-second cinematic AI short.\n\n"
        f"Story title: {pack.get('title', '')}\n"
        f"Logline: {pack.get('logline', '')}\n"
        f"Style: {pack.get('style_key', '')}\n\n"
        "Return ONLY a JSON object with these exact fields:\n"
        "- `title`: a punchy 60-char-max hook for the post (no emoji at start)\n"
        "- `description`: 1-2 sentences that tease the story without spoiling the twist\n"
        "- `hashtags`: array of 8-12 hashtags (no `#` prefix, no spaces). Mix 2-3 niche tags "
        "(e.g. aiart, aishorts, pixarstyle), 4-6 mid-popularity (e.g. shortsfeed, viralreels), "
        "and 2-3 broad (fyp, foryou, reels). Lowercase only.\n\n"
        "Format:\n"
        '{\"title\": \"...\", \"description\": \"...\", \"hashtags\": [\"...\", ...]}\n'
    )
    raw = text_client.generate_text(prompt, json_mode=True)
    obj = _extract_json(raw)
    if not isinstance(obj, dict):
        raise ValueError(f"Expected metadata object, got: {obj!r}")
    obj.setdefault("title", pack.get("title", ""))
    obj.setdefault("description", pack.get("logline", ""))
    obj.setdefault("hashtags", ["aishorts", "fyp", "viralreels"])
    return obj


def save_metadata(meta: dict, project_path: Path) -> Path:
    out = project_path / "metadata.json"
    out.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return out
