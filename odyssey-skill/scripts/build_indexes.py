#!/usr/bin/env python3
"""Build Odyssey Skill search/source indexes from decision storyline JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
UNKNOWN = "原文未提及"


TAG_RULES = {
    "裸辞": ["裸辞", "离职", "辞职", "空窗"],
    "转行": ["转行", "转型", "跨界", "换行业"],
    "留学": ["留学", "硕士", "海外学历", "出国"],
    "大厂": ["大厂", "华为", "微软", "阿里", "百度", "字节", "腾讯"],
    "创业": ["创业", "公司", "业务", "客户", "融资"],
    "海外生活": ["海外", "澳洲", "德国", "芬兰", "香港", "国外"],
    "职业倦怠": ["倦怠", "疲惫", "加班", "不适配", "压力"],
    "收入下降": ["收入下降", "收入不稳定", "放弃稳定收入", "薪资", "存款"],
    "家庭约束": ["家庭", "配偶", "父母", "孩子", "房贷"],
    "城市选择": ["城市", "北京", "上海", "深圳", "悉尼", "德国"],
}


def clean_text(value: Any) -> str:
    if value is None:
        return UNKNOWN
    if isinstance(value, str):
        text = " ".join(value.split())
        return text or UNKNOWN
    if isinstance(value, list):
        return " ".join(clean_text(item) for item in value if item is not None)
    if isinstance(value, dict):
        return " ".join(f"{key} {clean_text(val)}" for key, val in value.items())
    return str(value)


def is_podcast(source_links: list[str], source_ids: list[str]) -> bool:
    text = " ".join(source_links + source_ids).lower()
    return "podcast" in text or "podcasts.apple.com" in text


def platform_for_url(url: str) -> str:
    lowered = url.lower()
    if "podcasts.apple.com" in lowered:
        return "Apple Podcasts"
    if "bilibili.com" in lowered:
        return "Bilibili"
    if "xhslink.com" in lowered or "xiaohongshu" in lowered:
        return "Xiaohongshu"
    return "Other"


def source_type_for(source_id: str, url: str) -> str:
    text = f"{source_id} {url}".lower()
    if "podcast" in text or "podcasts.apple.com" in text:
        return "podcast"
    if "bilibili" in text or "bilibili.com" in text:
        return "bilibili"
    if "xiaohongshu" in text or "xhslink.com" in text:
        return "xiaohongshu"
    return "other"


def infer_tags(text: str) -> list[str]:
    tags = []
    for tag, keywords in TAG_RULES.items():
        if any(keyword.lower() in text.lower() for keyword in keywords):
            tags.append(tag)
    return tags


def infer_dimensions(node: dict[str, Any], tags: list[str]) -> list[str]:
    dimensions = ["决策场景相似"]
    if clean_text(node.get("当时约束")) != UNKNOWN:
        dimensions.append("资源约束相似")
    if clean_text(node.get("代价")) != UNKNOWN:
        dimensions.append("风险代价相似")
    if clean_text(node.get("行动路径")) != UNKNOWN:
        dimensions.append("行动路径相似")
    if any(tag in tags for tag in ["大厂", "留学", "创业", "海外生活"]):
        dimensions.append("职业阶段相似")
    return dimensions


def sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_indexes(
    cases: list[dict[str, Any]],
    database_version: str | None = None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    search_index: list[dict[str, Any]] = []
    source_records: dict[str, dict[str, Any]] = {}

    for case in cases:
        case_id = clean_text(case.get("case_id"))
        case_title = clean_text(case.get("case_title"))
        source_links = [clean_text(link) for link in case.get("source_links", [])]
        source_ids = [clean_text(source_id) for source_id in case.get("source_ids", [])]
        podcast_recommendable = is_podcast(source_links, source_ids)

        source_pairs = list(zip(source_ids, source_links))
        if source_links and not source_pairs:
            source_pairs = [(f"{case_id}:source_01", source_links[0])]
        for idx, url in enumerate(source_links):
            source_id = source_ids[idx] if idx < len(source_ids) else f"{case_id}:source_{idx + 1:02d}"
            record = {
                "source_id": source_id,
                "case_id": case_id,
                "source_type": source_type_for(source_id, url),
                "platform": platform_for_url(url),
                "title": case_title,
                "url": url,
                "is_podcast": source_type_for(source_id, url) == "podcast",
                "is_recommendable_for_skill": source_type_for(source_id, url) == "podcast",
            }
            source_records[source_id] = record

        for protagonist in case.get("protagonists", []):
            protagonist_id = clean_text(protagonist.get("protagonist_id"))
            protagonist_name = clean_text(protagonist.get("name"))
            identity = clean_text(protagonist.get("identity"))
            profile = protagonist.get("profile", {})
            for node in protagonist.get("decision_nodes", []):
                node_id = clean_text(node.get("node_id"))
                searchable_parts = [
                    case_title,
                    protagonist_name,
                    identity,
                    clean_text(profile),
                    clean_text(node.get("decision_scene")),
                    clean_text(node.get("stage_at_decision")),
                    clean_text(node.get("age_at_decision")),
                    clean_text(node.get("location_at_decision")),
                    clean_text(node.get("人物背景")),
                    clean_text(node.get("当时约束")),
                    clean_text(node.get("备选项")),
                    clean_text(node.get("最终选择")),
                    clean_text(node.get("行动路径")),
                    clean_text(node.get("结果")),
                    clean_text(node.get("代价")),
                    clean_text(node.get("关键变量")),
                    clean_text(node.get("可参考人群")),
                    clean_text(source_ids),
                    clean_text(source_links),
                ]
                searchable_text = " ".join(part for part in searchable_parts if part)
                tags = infer_tags(searchable_text)
                search_index.append(
                    {
                        "case_id": case_id,
                        "case_title": case_title,
                        "protagonist_id": protagonist_id,
                        "protagonist_name": protagonist_name,
                        "identity": identity,
                        "node_id": node_id,
                        "timeline_order": node.get("timeline_order", 0),
                        "decision_scene": clean_text(node.get("decision_scene")),
                        "stage_at_decision": clean_text(node.get("stage_at_decision")),
                        "constraints": node.get("当时约束", []),
                        "options": node.get("备选项", {}),
                        "final_choice": clean_text(node.get("最终选择")),
                        "action_path": node.get("行动路径", []),
                        "cost": clean_text(node.get("代价")),
                        "result": node.get("结果", {}),
                        "reference_group": clean_text(node.get("可参考人群")),
                        "source_ids": source_ids,
                        "source_links": source_links,
                        "is_podcast_recommendable": podcast_recommendable,
                        "searchable_text": searchable_text,
                        "search_tags": tags,
                        "match_dimensions": infer_dimensions(node, tags),
                    }
                )

    source_index = sorted(source_records.values(), key=lambda item: (item["case_id"], item["source_id"]))
    updated_at = updated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    database_version = database_version or updated_at[:10] + ".1"
    manifest = {
        "database_version": database_version,
        "updated_at": updated_at,
        "files": {
            "odyssey_search_index": {
                "path": "data/odyssey_search_index.json",
                "sha256": sha256_json(search_index),
                "record_count": len(search_index),
            },
            "source_index": {
                "path": "data/source_index.json",
                "sha256": sha256_json(source_index),
                "record_count": len(source_index),
            },
        },
    }
    return {
        "odyssey_search_index": search_index,
        "source_index": source_index,
        "manifest": manifest,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Odyssey Skill GitHub database indexes.")
    parser.add_argument("--source", default=str(DATA_DIR / "decision_storylines_v2.json"))
    parser.add_argument("--out-dir", default=str(DATA_DIR))
    parser.add_argument("--database-version", default=None)
    args = parser.parse_args()

    source = Path(args.source)
    out_dir = Path(args.out_dir)
    cases = json.loads(source.read_text(encoding="utf-8"))
    result = build_indexes(cases, database_version=args.database_version)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "odyssey_search_index.json").write_text(
        json.dumps(result["odyssey_search_index"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "source_index.json").write_text(
        json.dumps(result["source_index"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "manifest.json").write_text(
        json.dumps(result["manifest"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(result['odyssey_search_index'])} search records")
    print(f"wrote {len(result['source_index'])} source records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
