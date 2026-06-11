#!/usr/bin/env python3
"""Create OdysseyMap case3.0 scaffolding from the existing case2.0 workflow."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ODYSSEY_MAP_ROOT = Path("/Users/chenkai/Desktop/CodeX/OdysseyMap")


def copy_case3_dir(root: Path) -> int:
    source = root / "data" / "case2.0"
    target = root / "data" / "case3.0"
    target.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in sorted(source.glob("case_*.md")):
        destination = target / path.name
        if not destination.exists():
            shutil.copy2(path, destination)
            copied += 1
    return copied


def write_case3_generator(root: Path) -> None:
    source = root / "scripts" / "generate_final_from_case2.py"
    target = root / "scripts" / "generate_final_from_case3.py"
    text = source.read_text(encoding="utf-8")
    text = text.replace("from data/case2.0 Markdown cases", "from data/case3.0 Markdown cases")
    text = text.replace('CASE2_DIR = ROOT / "data" / "case2.0"', 'CASE3_DIR = ROOT / "data" / "case3.0"')
    text = text.replace("CASE2_DIR", "CASE3_DIR")
    text = text.replace('story.get("merge_basis", UNKNOWN)', 'story.get("merge_basis") or "case3.0 manual deep-read"')
    target.write_text(text, encoding="utf-8")


def update_file_structure(root: Path) -> None:
    path = root / "docs" / "file-structure.md"
    text = path.read_text(encoding="utf-8")
    if "data/case3.0" not in text:
        text = text.replace(
            "│   ├── case2.0/\n│   │   └── case_*.md\n",
            "│   ├── case2.0/\n│   │   └── case_*.md\n│   ├── case3.0/\n│   │   └── case_*.md\n",
        )
        text = text.replace(
            "- `data/case2.0/`: newer per-case Markdown drafts or revisions.\n",
            "- `data/case2.0/`: v2 per-case Markdown drafts or revisions retained for compatibility.\n"
            "- `data/case3.0/`: Odyssey 3.0 per-case Markdown workspace for newly selected ingestion cases.\n",
        )
        text = text.replace(
            "- `scripts/`: repeatable project maintenance scripts. `generate_final_from_case2.py` regenerates `data/final/` from `data/case2.0/`.\n",
            "- `scripts/`: repeatable project maintenance scripts. `generate_final_from_case2.py` regenerates `data/final/` from `data/case2.0/`; `generate_final_from_case3.py` regenerates `data/final/` from `data/case3.0/` while preserving the downstream v2 filename contract.\n",
        )
        path.write_text(text, encoding="utf-8")


def update_manual_method(root: Path) -> None:
    path = root / "methods" / "manual_extraction_methods.md"
    text = path.read_text(encoding="utf-8")
    addition = (
        "\n## Manual deep-read v3 方法\n\n"
        "- 主工作区：`data/case3.0/`。\n"
        "- 主渲染脚本：`scripts/generate_final_from_case3.py`。\n"
        "- `data/final/decision_storylines_v2.json` 暂时保留下游兼容文件名；内容口径可来自 case3.0。\n"
        "- 内容仍由当前会话逐案阅读原文后手工整理；脚本只负责元数据合并、schema 校验和 Markdown 渲染。\n"
    )
    if "Manual deep-read v3 方法" not in text:
        path.write_text(text.rstrip() + addition, encoding="utf-8")


def main() -> int:
    root = ODYSSEY_MAP_ROOT
    if not root.exists():
        raise SystemExit(f"OdysseyMap root not found: {root}")
    copied = copy_case3_dir(root)
    write_case3_generator(root)
    update_file_structure(root)
    update_manual_method(root)
    print(json.dumps({"odyssey_map_root": str(root), "case3_files_copied": copied}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
