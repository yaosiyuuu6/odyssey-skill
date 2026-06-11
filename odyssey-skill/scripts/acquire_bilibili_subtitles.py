#!/usr/bin/env python3
"""Acquire official Bilibili subtitles for selected Odyssey cases."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import requests


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}


def extract_bvid(url: str) -> str:
    match = re.search(r"/video/(BV[0-9A-Za-z]+)", url)
    if not match:
        raise ValueError(f"Cannot extract BVID from URL: {url}")
    return match.group(1)


def pick_subtitle(subtitles: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not subtitles:
        return None
    for subtitle in subtitles:
        if str(subtitle.get("lan", "")).lower() in {"zh-cn", "zh-hans", "ai-zh"}:
            return subtitle
    return subtitles[0]


def subtitle_json_to_text(subtitle_json: dict[str, Any]) -> str:
    lines = []
    for item in subtitle_json.get("body", []):
        content = str(item.get("content", "")).strip()
        if content:
            lines.append(content)
    return "\n".join(lines).rstrip() + ("\n" if lines else "")


def get_json(session: requests.Session, url: str, **params: Any) -> dict[str, Any]:
    response = session.get(url, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    data = response.json()
    if data.get("code", 0) != 0:
        raise RuntimeError(f"Bilibili API error {data.get('code')}: {data.get('message')}")
    return data.get("data", data)


def fetch_case_subtitle(record: dict[str, Any], text_dir: Path, clean_dir: Path, meta_dir: Path) -> dict[str, Any]:
    session = requests.Session()
    bvid = extract_bvid(record["url"])
    view = get_json(session, "https://api.bilibili.com/x/web-interface/view", bvid=bvid)
    cid = view["cid"]
    player = get_json(session, "https://api.bilibili.com/x/player/v2", bvid=bvid, cid=cid)
    subtitles = player.get("subtitle", {}).get("subtitles", [])
    subtitle = pick_subtitle(subtitles)
    slug = record["slug"]
    case_id = record["case_id"]
    meta_dir.mkdir(parents=True, exist_ok=True)
    meta_path = meta_dir / f"{case_id}_{slug}.bilibili.json"
    meta_path.write_text(
        json.dumps(
            {
                "record": record,
                "bvid": bvid,
                "cid": cid,
                "view": {"title": view.get("title"), "owner": view.get("owner"), "desc": view.get("desc")},
                "subtitles": subtitles,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if not subtitle:
        return {
            "case_id": case_id,
            "url": record["url"],
            "status": "needs_asr",
            "reason": "no_official_subtitle",
            "metadata_path": str(meta_path),
        }

    subtitle_url = subtitle.get("subtitle_url")
    if subtitle_url and subtitle_url.startswith("//"):
        subtitle_url = "https:" + subtitle_url
    subtitle_response = session.get(subtitle_url, headers=HEADERS, timeout=30)
    subtitle_response.raise_for_status()
    subtitle_json = subtitle_response.json()
    text = subtitle_json_to_text(subtitle_json)
    if not text.strip():
        return {
            "case_id": case_id,
            "url": record["url"],
            "status": "needs_asr",
            "reason": "empty_official_subtitle",
            "metadata_path": str(meta_path),
        }

    text_dir.mkdir(parents=True, exist_ok=True)
    clean_dir.mkdir(parents=True, exist_ok=True)
    raw_path = text_dir / f"{case_id}_{slug}.txt"
    clean_path = clean_dir / f"{case_id}_{slug}.txt"
    raw_path.write_text(text, encoding="utf-8")
    clean_path.write_text(text, encoding="utf-8")
    return {
        "case_id": case_id,
        "url": record["url"],
        "status": "complete_subtitle",
        "source_text_path": str(raw_path),
        "source_text_clean_path": str(clean_path),
        "metadata_path": str(meta_path),
        "line_count": len([line for line in text.splitlines() if line.strip()]),
    }


def acquire(records: list[dict[str, Any]], text_dir: Path, clean_dir: Path, meta_dir: Path) -> list[dict[str, Any]]:
    report = []
    for record in records:
        if record.get("source_type") != "bilibili":
            continue
        try:
            report.append(fetch_case_subtitle(record, text_dir, clean_dir, meta_dir))
        except Exception as exc:  # noqa: BLE001 - acquisition report should preserve per-record failures.
            report.append(
                {
                    "case_id": record.get("case_id"),
                    "url": record.get("url"),
                    "status": "failed",
                    "reason": str(exc),
                }
            )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Acquire official Bilibili subtitles for selected cases.")
    parser.add_argument("--selected", required=True)
    parser.add_argument("--text-dir", required=True)
    parser.add_argument("--clean-dir", required=True)
    parser.add_argument("--meta-dir", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    records = json.loads(Path(args.selected).read_text(encoding="utf-8"))
    report = acquire(records, Path(args.text_dir), Path(args.clean_dir), Path(args.meta_dir))
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(report), "complete_subtitle": sum(1 for item in report if item["status"] == "complete_subtitle")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
