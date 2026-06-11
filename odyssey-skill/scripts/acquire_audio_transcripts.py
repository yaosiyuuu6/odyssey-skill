#!/usr/bin/env python3
"""Acquire audio transcripts for selected Odyssey source records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts.asr import find_binary, transcribe_audio
from scripts.text_normalize import normalize_chinese_text


SUPPORTED_SOURCE_TYPES = {"podcast", "bilibili"}


def paths_for_record(record: dict[str, Any], root: Path) -> dict[str, Path]:
    stem = f"{record['case_id']}_{record['slug']}"
    return {
        "media": root / "media" / f"{stem}.m4a",
        "raw_text": root / "text" / f"{stem}.txt",
        "clean_text": root / "text_clean" / f"{stem}.txt",
        "metadata": root / "acquisition" / f"{stem}.audio.json",
    }


def format_timestamp(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def format_segments(segments: list[dict[str, Any]]) -> str:
    lines = []
    for segment in segments:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        start = format_timestamp(float(segment.get("start", 0.0) or 0.0))
        end = format_timestamp(float(segment.get("end", 0.0) or 0.0))
        lines.append(f"[{start} --> {end}] {text}")
    return "\n".join(lines) + ("\n" if lines else "")


def should_process(record: dict[str, Any], source_types: set[str], root: Path, reuse_existing: bool = True) -> bool:
    if record.get("source_type") not in source_types:
        return False
    if reuse_existing and paths_for_record(record, root)["clean_text"].exists():
        return False
    return True


def write_transcript_outputs(record: dict[str, Any], root: Path, text: str, metadata: dict[str, Any]) -> dict[str, Any]:
    paths = paths_for_record(record, root)
    clean = normalize_chinese_text(text)
    for key in ("raw_text", "clean_text", "metadata"):
        paths[key].parent.mkdir(parents=True, exist_ok=True)
    paths["raw_text"].write_text(text, encoding="utf-8")
    paths["clean_text"].write_text(clean, encoding="utf-8")
    paths["metadata"].write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "case_id": record.get("case_id"),
        "url": record.get("url"),
        "status": "complete_transcript" if clean.strip() else "empty_transcript",
        "source_text_path": str(paths["raw_text"]),
        "source_text_clean_path": str(paths["clean_text"]),
        "metadata_path": str(paths["metadata"]),
    }


def acquire_records(
    records: list[dict[str, Any]],
    output_root: Path,
    source_types: set[str] = SUPPORTED_SOURCE_TYPES,
    reuse_existing: bool = True,
    asr_engine: str = "auto",
    asr_model: str = "base",
    asr_timeout_seconds: int = 900,
) -> list[dict[str, Any]]:
    report = []
    for record in records:
        if not should_process(record, source_types, output_root, reuse_existing=reuse_existing):
            continue
        paths = paths_for_record(record, output_root)
        audio_path = paths["media"]
        if not audio_path.exists():
            report.append(
                {
                    "case_id": record.get("case_id"),
                    "url": record.get("url"),
                    "status": "blocked",
                    "reason": f"audio_missing:{audio_path}",
                }
            )
            continue
        result = transcribe_audio(
            audio_path,
            audio_path.parent,
            language="zh",
            timeout_seconds=asr_timeout_seconds,
            engine=asr_engine,
            model=asr_model,
        )
        report.append(write_transcript_outputs(record, output_root, result.get("text", ""), {"record": record, "asr": result}))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe already-downloaded Odyssey audio assets.")
    parser.add_argument("--selected", required=True)
    parser.add_argument("--output-root", default="data/assets")
    parser.add_argument("--source-type", action="append", choices=sorted(SUPPORTED_SOURCE_TYPES))
    parser.add_argument("--no-reuse-existing", action="store_true")
    parser.add_argument("--asr-engine", choices=["auto", "mlx", "faster-whisper", "whisperx"], default="auto")
    parser.add_argument("--asr-model", default="base")
    parser.add_argument("--asr-timeout-seconds", type=int, default=900)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    if not find_binary("ffmpeg"):
        print("warning: ffmpeg not found; ASR engines may fail")

    records = json.loads(Path(args.selected).read_text(encoding="utf-8"))
    report = acquire_records(
        records,
        Path(args.output_root),
        source_types=set(args.source_type or SUPPORTED_SOURCE_TYPES),
        reuse_existing=not args.no_reuse_existing,
        asr_engine=args.asr_engine,
        asr_model=args.asr_model,
        asr_timeout_seconds=args.asr_timeout_seconds,
    )
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(report)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
