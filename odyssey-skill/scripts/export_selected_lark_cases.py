#!/usr/bin/env python3
"""Normalize selected Odyssey 3.0 Lark Base records for repeatable ingestion."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


FIELDS = [
    "标题",
    "人物/嘉宾",
    "平台",
    "URL",
    "来源类型",
    "主题标签",
    "可能决策场景",
    "原文可得性",
    "优先级",
    "备注",
]


def first_value(value: Any) -> str:
    if isinstance(value, list):
        if not value:
            return ""
        return first_value(value[0])
    if value is None:
        return ""
    return str(value).strip()


def list_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def normalize_url(value: Any) -> str:
    text = first_value(value)
    match = re.match(r"^\[([^\]]+)\]\(([^)]+)\)$", text)
    if match and match.group(1) == match.group(2):
        return match.group(2).strip()
    if match:
        return match.group(2).strip()
    return text


def slugify(value: str) -> str:
    text = re.sub(r"\s+", "_", value.strip())
    text = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:48] or "untitled"


def source_prefix(source_type: str) -> str:
    if source_type == "podcast":
        return "podcast"
    if source_type == "bilibili":
        return "bilibili"
    if source_type == "xiaohongshu":
        return "xiaohongshu"
    return source_type or "other"


def normalize_selected_records(raw: dict[str, Any], start_case_number: int = 21) -> list[dict[str, Any]]:
    if not raw.get("ok", False):
        raise ValueError("Lark export envelope is not ok")
    payload = raw.get("data", {})
    fields = payload.get("fields", [])
    missing_fields = [field for field in FIELDS if field not in fields]
    if missing_fields:
        raise ValueError(f"Lark export missing fields: {', '.join(missing_fields)}")

    rows = payload.get("data", [])
    record_ids = payload.get("record_id_list", [])
    if len(record_ids) != len(rows):
        raise ValueError("record_id_list length does not match data row length")

    field_positions = {field: fields.index(field) for field in FIELDS}
    records: list[dict[str, Any]] = []
    for offset, (record_id, row) in enumerate(zip(record_ids, rows)):
        case_number = start_case_number + offset
        item = {field: row[field_positions[field]] if field_positions[field] < len(row) else "" for field in FIELDS}
        title = first_value(item["标题"])
        url = normalize_url(item["URL"])
        source_type = first_value(item["来源类型"])
        if not title:
            raise ValueError(f"{record_id} missing 标题")
        if not url:
            raise ValueError(f"{record_id} missing URL")
        if not source_type:
            raise ValueError(f"{record_id} missing 来源类型")
        records.append(
            {
                "case_id": f"case_{case_number:02d}",
                "case_number": case_number,
                "record_id": record_id,
                "title": title,
                "person_or_guest": first_value(item["人物/嘉宾"]),
                "platform": first_value(item["平台"]),
                "url": url,
                "source_type": source_type,
                "topic_tags": list_values(item["主题标签"]),
                "possible_decision_scene": first_value(item["可能决策场景"]),
                "text_availability": first_value(item["原文可得性"]),
                "priority": first_value(item["优先级"]),
                "notes": first_value(item["备注"]),
                "source_id": f"case3:{source_prefix(source_type)}_{case_number:02d}",
                "slug": slugify(title),
            }
        )
    return records


def write_outputs(
    raw: dict[str, Any],
    raw_out: str | Path,
    normalized_out: str | Path,
    start_case_number: int = 21,
) -> dict[str, Any]:
    records = normalize_selected_records(raw, start_case_number=start_case_number)
    raw_path = Path(raw_out)
    normalized_path = Path(normalized_out)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    normalized_path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "record_count": len(records),
        "unique_url_count": len({record["url"] for record in records}),
        "has_more": bool(raw.get("data", {}).get("has_more")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize selected Odyssey Lark Base records.")
    parser.add_argument("--input", required=True, help="Raw lark-cli +record-list JSON file")
    parser.add_argument("--raw-out", required=True, help="Backup path for raw JSON")
    parser.add_argument("--out", required=True, help="Normalized selected cases JSON path")
    parser.add_argument("--start-case-number", type=int, default=21)
    args = parser.parse_args()

    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    report = write_outputs(raw, args.raw_out, args.out, args.start_case_number)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
