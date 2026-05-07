"""Story idea generation — Step 1 of the master prompt."""
from __future__ import annotations

import json
import re

from jinja2 import Environment, FileSystemLoader

from .. import config, text_client


def _render_template(
    style_key: str,
    *,
    mode: str,
    theme: str | None = None,
    theme_hint: str | None = None,
    chosen_idea: str | None = None,
    runtime_seconds: int = 25,
    scene_count: int = 8,
) -> str:
    presets = config.load_style_presets()
    if style_key not in presets:
        raise ValueError(f"Unknown style '{style_key}'. Available: {list(presets)}")
    env = Environment(loader=FileSystemLoader(str(config.PROMPTS_DIR)))
    tmpl = env.get_template("master_prompt.md.j2")
    return tmpl.render(
        style=presets[style_key],
        mode=mode,
        theme=theme,
        theme_hint=theme_hint or "",
        chosen_idea=chosen_idea,
        runtime_seconds=runtime_seconds,
        scene_count=scene_count,
    )


def _extract_json(text: str) -> object:
    """Robustly pull the largest balanced JSON value out of a model response.

    Handles: ```json fences, leading prose, trailing prose, embedded `{...}`
    examples earlier in the text, and string literals that contain brackets.
    Picks the LARGEST successfully-parsed value so that small inline examples
    in the prompt or in prose don't outrank the real answer.
    """
    if not text or not text.strip():
        raise ValueError("Empty response from model")

    # Strip a fenced block if present (most common Gemini wrapping)
    fence = re.search(r"```(?:json|JSON)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence:
        text = fence.group(1)

    candidates: list[tuple[int, object]] = []
    i = 0
    while i < len(text):
        if text[i] in "[{":
            try:
                span = _slice_balanced(text, i)
                parsed = json.loads(span)
                candidates.append((len(span), parsed))
                i += len(span)
                continue
            except (ValueError, json.JSONDecodeError):
                pass
        i += 1

    if not candidates:
        raise ValueError(f"No parseable JSON found in:\n{text[:600]}")
    # Largest balanced value wins
    candidates.sort(key=lambda c: c[0], reverse=True)
    return candidates[0][1]


def _slice_balanced(text: str, start: int) -> str:
    """Return text[start : end+1] where end matches the bracket at `start`,
    respecting strings + escapes. Raises ValueError if unbalanced.
    """
    open_ch = text[start]
    close_ch = "]" if open_ch == "[" else "}"
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == "\\" and in_string:
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError(f"Unbalanced JSON starting at offset {start}")


def generate_ideas(
    style_key: str = "fruit_head",
    theme: str | None = None,
    theme_hint: str | None = None,
    runtime_seconds: int = 25,
    scene_count: int = 8,
) -> list[str]:
    """Return 10 story idea sentences for the chosen style."""
    prompt = _render_template(
        style_key,
        mode="ideas",
        theme=theme,
        theme_hint=theme_hint,
        runtime_seconds=runtime_seconds,
        scene_count=scene_count,
    )
    raw = text_client.generate_text(prompt, json_mode=True)
    parsed = _extract_json(raw)
    # JSON mode requires top-level object; we ask for {"ideas": [...]}
    ideas = parsed.get("ideas") if isinstance(parsed, dict) else parsed
    if not isinstance(ideas, list) or not all(isinstance(x, str) for x in ideas):
        raise ValueError(
            f"Expected list of 10 idea strings, got: {type(ideas).__name__}\n"
            f"Raw response:\n{raw[:600]}"
        )
    return ideas[:10]
