#!/usr/bin/env python3
"""Validate Odyssey Skill cloud database files."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


def sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def source_node_ids(cases: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    ids = set()
    for case in cases:
        case_id = case.get("case_id")
        for protagonist in case.get("protagonists", []):
            protagonist_id = protagonist.get("protagonist_id")
            for node in protagonist.get("decision_nodes", []):
                ids.add((case_id, protagonist_id, node.get("node_id")))
    return ids


def validate_data(
    manifest: dict[str, Any],
    search_index: list[dict[str, Any]],
    source_index: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    verify_sha: bool = True,
) -> list[str]:
    errors: list[str] = []
    file_info = manifest.get("files", {})
    search_info = file_info.get("odyssey_search_index", {})
    source_info = file_info.get("source_index", {})

    if search_info.get("record_count") != len(search_index):
        errors.append("manifest odyssey_search_index record_count mismatch")
    if source_info.get("record_count") != len(source_index):
        errors.append("manifest source_index record_count mismatch")
    if verify_sha:
        if search_info.get("sha256") != sha256_json(search_index):
            errors.append("manifest odyssey_search_index sha256 mismatch")
        if source_info.get("sha256") != sha256_json(source_index):
            errors.append("manifest source_index sha256 mismatch")

    known_nodes = source_node_ids(cases)
    seen_nodes: set[str] = set()
    source_urls = {item.get("url") for item in source_index}
    for record in search_index:
        node_id = record.get("node_id")
        if node_id in seen_nodes:
            errors.append(f"duplicate search node_id {node_id}")
        seen_nodes.add(node_id)
        trace_key = (record.get("case_id"), record.get("protagonist_id"), node_id)
        if trace_key not in known_nodes:
            errors.append(f"search record {node_id} does not trace back to source data")
        if not record.get("searchable_text"):
            errors.append(f"search record {node_id} has empty searchable_text")
        links = record.get("source_links") or []
        if record.get("is_podcast_recommendable") and not links:
            errors.append(f"podcast recommendable record {node_id} has no source link")
        for link in links:
            if source_index and link not in source_urls:
                errors.append(f"search record {node_id} source link is not present in source_index: {link}")

    seen_sources: set[str] = set()
    for source in source_index:
        source_id = source.get("source_id")
        if source_id in seen_sources:
            errors.append(f"duplicate source_id {source_id}")
        seen_sources.add(source_id)
        if source.get("is_recommendable_for_skill") and not source.get("url"):
            errors.append(f"recommendable source {source_id} has no url")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Odyssey Skill data files.")
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    search_index = json.loads((data_dir / "odyssey_search_index.json").read_text(encoding="utf-8"))
    source_index = json.loads((data_dir / "source_index.json").read_text(encoding="utf-8"))
    cases = json.loads((data_dir / "decision_storylines_v2.json").read_text(encoding="utf-8"))
    errors = validate_data(manifest, search_index, source_index, cases)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Odyssey Skill data validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
