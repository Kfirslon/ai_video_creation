"""Word-by-word burned-in captions, viral-reel style.

Pipeline:
1. Run faster-whisper on the assembled audio to get word-level timestamps.
2. Emit an ASS subtitle file where each line is a small group of words and the
   currently-spoken word is highlighted (yellow) via inline override codes.
3. ffmpeg burns the ASS file into the final video via the `subtitles` filter.
"""
from __future__ import annotations

from pathlib import Path

from .. import config

# Visual style — tuned for the viral TikTok/Reels look at 1080x1920
PRIMARY_COLOR = "&H00FFFFFF"     # white text (ASS uses BBGGRR with leading alpha)
HIGHLIGHT_COLOR = "&H0000FFFF"   # bright yellow on the active word
OUTLINE_COLOR = "&H00000000"     # solid black outline
BACK_COLOR = "&H80000000"        # 50% black shadow
FONT_NAME = "Arial Black"
FONT_SIZE = 30                   # bigger — was 14, looked tiny in the screenshot
OUTLINE_WIDTH = 5                # thicker outline so text reads on busy backgrounds
SHADOW_DEPTH = 2
WORDS_PER_LINE = 3               # fewer words on screen = each one is bigger
MARGIN_V = 540                   # ~28% from bottom, the classic viral position


def _format_ts(seconds: float) -> str:
    """ASS timestamp: H:MM:SS.cc (centiseconds)."""
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _ass_header() -> str:
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{FONT_NAME},{FONT_SIZE},{PRIMARY_COLOR},{PRIMARY_COLOR},{OUTLINE_COLOR},{BACK_COLOR},1,0,0,0,100,100,0,0,1,{OUTLINE_WIDTH},{SHADOW_DEPTH},2,40,40,{MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _line_text(group: list[dict], active_index: int) -> str:
    """Return ASS dialogue text where the active word is highlighted yellow."""
    parts = []
    for i, w in enumerate(group):
        word = w["word"].strip()
        if not word:
            continue
        if i == active_index:
            parts.append(f"{{\\c{HIGHLIGHT_COLOR}}}{word}{{\\c{PRIMARY_COLOR}}}")
        else:
            parts.append(word)
    return " ".join(parts)


def _build_ass(words: list[dict]) -> str:
    """Group words into rolling lines and emit one Dialogue per word-highlight window."""
    out = [_ass_header()]
    if not words:
        return out[0]

    for i, w in enumerate(words):
        group_start = (i // WORDS_PER_LINE) * WORDS_PER_LINE
        group = words[group_start : group_start + WORDS_PER_LINE]
        active = i - group_start
        start_ts = _format_ts(w["start"])
        end_ts = _format_ts(w["end"])
        text = _line_text(group, active)
        out.append(
            f"Dialogue: 0,{start_ts},{end_ts},Caption,,0,0,0,,{text}"
        )

    return "\n".join(out)


def transcribe_words(audio_or_video: Path) -> list[dict]:
    """Return word-level dicts: [{word, start, end}, ...]."""
    from faster_whisper import WhisperModel  # lazy: ~1s import + downloads model on first call
    model = WhisperModel(config.WHISPER_MODEL, compute_type="int8")
    segments, _info = model.transcribe(
        str(audio_or_video),
        word_timestamps=True,
        vad_filter=True,
    )
    out: list[dict] = []
    for seg in segments:
        for w in seg.words or []:
            if w.word and w.word.strip():
                out.append({"word": w.word, "start": w.start, "end": w.end})
    return out


def write_ass(words: list[dict], out_path: Path) -> Path:
    out_path.write_text(_build_ass(words), encoding="utf-8")
    return out_path


def generate_subtitles(audio_or_video: Path, out_path: Path) -> Path:
    """Convenience: transcribe + write ASS in one call."""
    words = transcribe_words(audio_or_video)
    return write_ass(words, out_path)
