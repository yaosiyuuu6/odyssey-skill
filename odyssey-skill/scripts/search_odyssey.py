#!/usr/bin/env python3
"""Search Odyssey decision-node index and render warm recommendations."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


KEYWORD_ALIASES = {
    "裸辞": ["裸辞", "辞职", "离职", "空窗"],
    "大厂": ["大厂", "华为", "微软", "阿里", "百度", "字节", "腾讯"],
    "产品": ["产品", "产品经理", "PM"],
    "转行": ["转行", "转型", "跨界"],
    "留学": ["留学", "出国", "硕士", "海外学历"],
    "创业": ["创业", "客户", "融资", "业务"],
    "海外": ["海外", "澳洲", "德国", "芬兰", "香港"],
    "城市": ["城市", "北京", "上海", "深圳", "悉尼"],
    "家庭": ["家庭", "配偶", "父母", "孩子", "房贷"],
}


def load_fetch_indexes():
    path = SCRIPT_DIR / "fetch_indexes.py"
    spec = importlib.util.spec_from_file_location("fetch_indexes", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tokenize(query: str) -> list[str]:
    lowered = query.lower()
    terms: list[str] = []
    for canonical, aliases in KEYWORD_ALIASES.items():
        if any(alias.lower() in lowered for alias in aliases):
            terms.append(canonical)
    terms.extend(re.findall(r"[A-Za-z0-9]{2,}", query))
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", query):
        if chunk not in terms:
            terms.append(chunk)
    return terms


def matched_terms_for(query_terms: list[str], record: dict) -> list[str]:
    haystack = " ".join(
        [
            str(record.get("searchable_text", "")),
            " ".join(record.get("search_tags", [])),
            str(record.get("decision_scene", "")),
        ]
    ).lower()
    matched = []
    for term in query_terms:
        aliases = KEYWORD_ALIASES.get(term, [term])
        if any(alias.lower() in haystack for alias in aliases):
            matched.append(term)
    return matched


def score_record(query_terms: list[str], record: dict) -> tuple[int, list[str]]:
    matched = matched_terms_for(query_terms, record)
    score = len(matched) * 10
    if record.get("is_podcast_recommendable"):
        score += 5
    scene = str(record.get("decision_scene", "")).lower()
    if any(term.lower() in scene for term in matched):
        score += 4
    cost = str(record.get("cost", "")).lower()
    if any(term in matched for term in ["裸辞", "创业", "留学", "海外"]) and cost:
        score += 2
    return score, matched


def search_index(query: str, index: list[dict], limit: int = 5) -> list[dict]:
    query_terms = tokenize(query)
    scored = []
    for record in index:
        score, matched = score_record(query_terms, record)
        if score <= 0:
            continue
        item = dict(record)
        item["match_score"] = score
        item["matched_terms"] = matched
        item["matched_dimensions"] = record.get("match_dimensions", [])[:3]
        scored.append(item)
    scored.sort(
        key=lambda item: (
            item["match_score"],
            bool(item.get("is_podcast_recommendable")),
            len(item.get("source_links", [])),
        ),
        reverse=True,
    )
    return scored[:limit]


def result_summary(result: dict) -> str:
    result_value = result.get("result", "原文未提及")
    if isinstance(result_value, dict):
        return "；".join(f"{key}：{value}" for key, value in result_value.items())
    if isinstance(result_value, list):
        return "；".join(str(item) for item in result_value)
    return str(result_value)


def render_recommendations(query: str, results: list[dict]) -> str:
    intro = "听起来你现在站在一个需要认真比较代价和可能性的位置。"
    if not results:
        return (
            f"{intro}\n\n"
            "我目前在库内没有找到足够相似、且可追溯到来源的案例。"
            "我不想为了给出推荐而编造播客；你可以补充行业、储蓄周期、裸辞目的和家庭约束后再试一次。"
        )
    lines = [
        intro,
        "",
        "你不妨看看这几个人生，希望对你有帮助。",
        "",
    ]
    for idx, result in enumerate(results, 1):
        links = result.get("source_links") or ["原始链接暂缺"]
        lines.extend(
            [
                f"{idx}. {result.get('case_title')}｜{result.get('protagonist_name')}",
                f"   - 决策节点：{result.get('decision_scene')} ({result.get('node_id')})",
                f"   - 相似点：{', '.join(result.get('matched_terms', [])) or '处境关键词相近'}；{', '.join(result.get('matched_dimensions', [])) or '可作为低置信参考'}",
                f"   - 当时选择：{result.get('final_choice', '原文未提及')}",
                f"   - 代价：{result.get('cost', '原文未提及')}",
                f"   - 后来结果：{result_summary(result)}",
                f"   - 来源：{links[0]}",
                f"   - 追溯 ID：{result.get('case_id')} / {result.get('protagonist_id')} / {result.get('node_id')}",
                "",
            ]
        )
    lines.append("这不是建议你复制他们的选择，而是帮你比较处境、代价和结果。")
    return "\n".join(lines)


def render_database_unavailable() -> str:
    return (
        "暂时无法检索奥德赛数据库：远程 GitHub 数据不可用，且本地还没有可用缓存。\n\n"
        "我不会为了给出推荐而编造播客或人生案例。你可以稍后重试，"
        "或先确认网络连接和 ODYSSEY_SKILL_REMOTE_BASE_URL 配置。"
    )


def search_remote(query: str, limit: int = 5, remote_base_url: str | None = None) -> str:
    fetch_indexes = load_fetch_indexes()
    kwargs = {}
    if remote_base_url:
        kwargs["remote_base_url"] = remote_base_url
    try:
        indexes = fetch_indexes.get_indexes(**kwargs)
    except Exception:
        return render_database_unavailable()
    results = search_index(query, indexes.search_index, limit=limit)
    rendered = render_recommendations(query, results)
    if indexes.warning:
        rendered = f"{indexes.warning}\n\n{rendered}"
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(description="Search Odyssey Skill cloud index.")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--remote-base-url", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    fetch_indexes = load_fetch_indexes()
    kwargs = {}
    if args.remote_base_url:
        kwargs["remote_base_url"] = args.remote_base_url
    try:
        indexes = fetch_indexes.get_indexes(**kwargs)
    except Exception:
        print(render_database_unavailable())
        return 2
    results = search_index(args.query, indexes.search_index, args.limit)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        if indexes.warning:
            print(indexes.warning)
            print()
        print(render_recommendations(args.query, results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
