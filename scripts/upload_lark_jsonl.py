#!/usr/bin/env python3
"""Upload JSONL records into a Lark Base table with lark-cli."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any


def load_jsonl_records(jsonl_path: Path) -> list[dict[str, Any]]:
    records = []
    for line_no, line in enumerate(jsonl_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid JSON at line {line_no}: {exc}") from exc
    return records


def run_lark(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def list_record_ids(base_token: str, table_id: str, limit: int = 500) -> list[str]:
    completed = run_lark(
        [
            "lark-cli",
            "base",
            "+record-list",
            "--base-token",
            base_token,
            "--table-id",
            table_id,
            "--field-id",
            "标题",
            "--limit",
            str(limit),
            "--format",
            "json",
        ]
    )
    if completed.returncode != 0:
        raise RuntimeError(f"record list failed: {completed.stderr or completed.stdout}")
    payload = json.loads(completed.stdout)
    return payload.get("data", {}).get("record_id_list", [])


def upsert_record(base_token: str, table_id: str, record: dict[str, Any], record_id: str | None = None) -> None:
    command = [
        "lark-cli",
        "base",
        "+record-upsert",
        "--base-token",
        base_token,
        "--table-id",
        table_id,
    ]
    if record_id:
        command.extend(["--record-id", record_id])
    command.extend(["--json", json.dumps(record, ensure_ascii=False)])
    completed = run_lark(command)
    if completed.returncode != 0:
        raise RuntimeError(f"record upsert failed: {completed.stderr or completed.stdout}")


def upload_records(
    base_token: str,
    table_id: str,
    jsonl_path: Path,
    delay_seconds: float,
    update_existing: bool,
) -> int:
    records = load_jsonl_records(jsonl_path)
    record_ids: list[str | None] = [None] * len(records)
    if update_existing:
        existing_ids = list_record_ids(base_token, table_id, max(500, len(records)))
        if len(existing_ids) != len(records):
            raise RuntimeError(
                f"cannot update existing records: table has {len(existing_ids)} records, JSONL has {len(records)} records"
            )
        record_ids = existing_ids

    count = 0
    for record_id, record in zip(record_ids, records, strict=True):
        upsert_record(base_token, table_id, record, record_id)
        count += 1
        if delay_seconds:
            time.sleep(delay_seconds)
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload JSONL records into a Lark Base table.")
    parser.add_argument("--base-token", required=True)
    parser.add_argument("--table-id", required=True)
    parser.add_argument("--jsonl", required=True, type=Path)
    parser.add_argument("--delay-seconds", type=float, default=0.1)
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Update existing table records in current list order instead of appending.",
    )
    args = parser.parse_args()
    count = upload_records(
        args.base_token,
        args.table_id,
        args.jsonl,
        args.delay_seconds,
        args.update_existing,
    )
    key = "updated" if args.update_existing else "uploaded"
    print(json.dumps({key: count, "table_id": args.table_id}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
