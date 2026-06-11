from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.text_normalize import normalize_chinese_text


def load_hotwords(path: Path) -> list[str]:
    if not path.exists():
        return []
    words: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            words.append(stripped)
    return words


def hotwords_prompt(hotwords: list[str]) -> str:
    if not hotwords:
        return ""
    return "以下词语应按原样识别：" + "，".join(hotwords)


def apply_corrections(text: str, path: Path) -> tuple[str, list[dict[str, Any]]]:
    if not path.exists() or not text:
        return text, []
    corrections = json.loads(path.read_text(encoding="utf-8"))
    corrected = text
    log: list[dict[str, Any]] = []
    for wrong, right in corrections.items():
        count = corrected.count(wrong)
        if count:
            corrected = corrected.replace(wrong, right)
            log.append({"from": wrong, "to": right, "count": count})
    return normalize_chinese_text(corrected), log


def render_speaker_segments(segments: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for segment in segments:
        text = normalize_chinese_text(str(segment.get("text", "")).strip())
        if not text:
            continue
        start = float(segment.get("start", 0.0) or 0.0)
        end = float(segment.get("end", 0.0) or 0.0)
        speaker = str(segment.get("speaker") or "SPEAKER_UNKNOWN")
        lines.append(f"[{start:.2f}-{end:.2f}] {speaker}: {text}")
    return "\n".join(lines)


def speaker_summary(segments: list[dict[str, Any]]) -> tuple[int, dict[str, str]]:
    speakers = sorted(
        {
            str(segment.get("speaker"))
            for segment in segments
            if segment.get("speaker")
        }
    )
    return len(speakers), {speaker: "" for speaker in speakers}
