#!/usr/bin/env python3
"""Historical migration helper for copying old OdysseyMap final data."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ODYSSEY_MAP = Path("/Users/chenkai/Desktop/CodeX/OdysseyMap")
DEFAULT_SKILL_DATA = ROOT / "data"
FINAL_JSON = "data/final/decision_storylines_v2.json"


def load_build_indexes():
    path = Path(__file__).resolve().parent / "build_indexes.py"
    spec = importlib.util.spec_from_file_location("build_indexes", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def count_storylines(cases: list[dict[str, Any]]) -> dict[str, int]:
    protagonists = sum(len(case.get("protagonists", [])) for case in cases)
    nodes = sum(
        len(protagonist.get("decision_nodes", []))
        for case in cases
        for protagonist in case.get("protagonists", [])
    )
    return {"cases": len(cases), "protagonists": protagonists, "decision_nodes": nodes}


def sync_final_json(odyssey_map_root: str | Path, skill_data_dir: str | Path) -> dict[str, Any]:
    source = Path(odyssey_map_root) / FINAL_JSON
    target = Path(skill_data_dir) / "decision_storylines_v2.json"
    cases = json.loads(source.read_text(encoding="utf-8"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report: dict[str, Any] = {"source": str(source), "target": str(target)}
    report.update(count_storylines(cases))
    return report


def rebuild_indexes(skill_data_dir: str | Path, database_version: str | None = None) -> dict[str, Any]:
    build_indexes = load_build_indexes()
    data_dir = Path(skill_data_dir)
    source = data_dir / "decision_storylines_v2.json"
    cases = json.loads(source.read_text(encoding="utf-8"))
    result = build_indexes.build_indexes(cases, database_version=database_version)
    (data_dir / "odyssey_search_index.json").write_text(
        json.dumps(result["odyssey_search_index"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (data_dir / "source_index.json").write_text(
        json.dumps(result["source_index"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (data_dir / "manifest.json").write_text(
        json.dumps(result["manifest"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "search_records": len(result["odyssey_search_index"]),
        "source_records": len(result["source_index"]),
        "database_version": result["manifest"]["database_version"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Historical migration only. New ingestion writes and generates final data inside odyssey-skill/data."
    )
    parser.add_argument("--odyssey-map-root", default=str(DEFAULT_ODYSSEY_MAP))
    parser.add_argument("--skill-data-dir", default=str(DEFAULT_SKILL_DATA))
    parser.add_argument("--database-version", default=None)
    parser.add_argument("--skip-indexes", action="store_true")
    args = parser.parse_args()
    report = sync_final_json(args.odyssey_map_root, args.skill_data_dir)
    if not args.skip_indexes:
        report.update(rebuild_indexes(args.skill_data_dir, args.database_version))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
