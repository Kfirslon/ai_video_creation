"""Scene pack generation — Step 2 of the master prompt.

Produces a structured 8-scene JSON. Auto-prepends the anti-music tag
to every voiceover dialogue (the fix for Veo's tendency to inject background music).
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import config, text_client
from .story import _extract_json, _render_template


def generate_scene_pack(
    chosen_idea: str,
    style_key: str = "fruit_head",
    runtime_seconds: int = 25,
    scene_count: int = 8,
) -> dict:
    """Generate the full scene pack for a chosen story idea."""
    if scene_count not in (4, 6, 8):
        raise ValueError(f"scene_count must be 4, 6, or 8 — got {scene_count}")
    prompt = _render_template(
        style_key,
        mode="scene_pack",
        chosen_idea=chosen_idea,
        runtime_seconds=runtime_seconds,
        scene_count=scene_count,
    )
    raw = text_client.generate_text(prompt, json_mode=True)
    pack = _extract_json(raw)
    if not isinstance(pack, dict) or "scenes" not in pack:
        raise ValueError(
            f"Expected scene pack object with 'scenes' key, got: {str(pack)[:300]}\n"
            f"Raw response:\n{raw[:600]}"
        )

    scenes = pack["scenes"]
    if len(scenes) != scene_count:
        # Trim or pad — but warn loud. Some models occasionally return one off.
        if len(scenes) > scene_count:
            scenes[:] = scenes[:scene_count]
        else:
            raise ValueError(
                f"Expected {scene_count} scenes, got {len(scenes)} — model under-delivered"
            )

    voiceover_prefix = config.load_voiceover_prefix()
    for s in scenes:
        vo = s.get("voiceover_script", {}) or {}
        vo.setdefault("speaker", "")
        vo.setdefault("direction", "")
        vo.setdefault("dialogue", "")
        if vo["dialogue"]:
            vo["veo_prompt"] = (
                f"{voiceover_prefix}\n"
                f"{vo['speaker']}:\n"
                f"{vo['direction']}\n"
                f"\"{vo['dialogue']}\""
            ).strip()
        else:
            vo["veo_prompt"] = vo["direction"] or ""
        s["voiceover_script"] = vo

    pack.setdefault("title", chosen_idea[:60])
    pack.setdefault("logline", chosen_idea)
    pack["chosen_idea"] = chosen_idea
    pack["style_key"] = style_key
    pack["runtime_seconds"] = runtime_seconds
    pack["scene_count"] = scene_count
    return pack


def save_scene_pack(pack: dict, project_path: Path) -> None:
    (project_path / "scene_pack.json").write_text(
        json.dumps(pack, indent=2), encoding="utf-8"
    )
    (project_path / "scene_pack.md").write_text(
        _render_human_readable(pack), encoding="utf-8"
    )


def _render_human_readable(pack: dict) -> str:
    lines = [f"# {pack.get('title', 'Untitled')}", ""]
    if pack.get("logline"):
        lines += [f"*{pack['logline']}*", ""]
    lines += ["---", ""]
    for s in pack["scenes"]:
        lines += [
            f"## SCENE {s['scene_number']}",
            "",
            "**IMAGE PROMPT**",
            "",
            s["image_prompt"],
            "",
            "**ANIMATION PROMPT**",
            "",
            s["animation_prompt"],
            "",
            "**VOICEOVER (paste into Google Flow alongside animation prompt):**",
            "",
            "```",
            s["voiceover_script"]["veo_prompt"],
            "```",
            "",
            "---",
            "",
        ]
    return "\n".join(lines)


def combined_video_prompt(scene: dict) -> str:
    """Return the single text block to paste into Google Flow for one scene."""
    return f"{scene['animation_prompt']}\n\n{scene['voiceover_script']['veo_prompt']}".strip()
