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


def search_index(query: str, index: list[dict], limit: int = 3) -> list[dict]:
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


def first_source_link(result: dict) -> str:
    links = result.get("source_links") or []
    return links[0] if links else "原始链接暂缺"


def clean_clause(value: object, fallback: str) -> str:
    text = str(value or fallback).strip()
    return text.rstrip("。；;，, ")


def story_paragraph(result: dict) -> str:
    name = result.get("protagonist_name") or "这位主人公"
    title = result.get("case_title") or "一段相似经历"
    scene = clean_clause(result.get("decision_scene"), "一个没有标准答案的路口")
    choice = clean_clause(result.get("final_choice"), "原文没有明确写出最后选择")
    cost = clean_clause(result.get("cost"), "原文没有明确写出代价")
    summary = clean_clause(result_summary(result), "原文没有明确写出后来的结果")
    matched_dimensions = "、".join(result.get("matched_dimensions", []))
    if matched_dimensions:
        similarity = f"我把它放在这里，是因为它和你的处境有这些相近处：{matched_dimensions}。"
    else:
        similarity = "我把它放在这里，是因为它至少有一些处境关键词和你相近。"
    return (
        f"{title}里，{name}也走到过一个不太容易立刻说清楚的阶段。"
        f"对方当时面对的是{scene}，真正难的地方不只是做选择本身，"
        f"也是要承受选择前那种摇摆和不确定。{similarity}"
        f"后来对方选择了{choice}，这个选择的代价是{cost}。"
        f"再往后看，{summary}。"
    )


def render_recommendations(query: str, results: list[dict]) -> str:
    intro = (
        "好哦。我无法真正感同身受你此刻的处境，"
        "但我这里有一些相似的人生片段。它们不是标准答案，"
        "只是一些真实的人在迷茫里做过的尝试，希望能陪你多看见几种可能。"
    )
    if not results:
        return (
            f"{intro}\n\n"
            "我这里暂时没有找到足够相近、又能追到来源的案例。"
            "与其硬凑几个看起来相关的故事，我更愿意先停在这里；"
            "如果你愿意补一句你最纠结的点，我再帮你重新找。"
        )
    lines = [
        intro,
        "",
        "你可以先看看这几段经历：",
        "",
    ]
    for idx, result in enumerate(results, 1):
        lines.extend(
            [
                f"{idx}. {result.get('case_title')}｜{result.get('protagonist_name')}",
                story_paragraph(result),
                f"来源：{first_source_link(result)}",
                "",
            ]
        )
    lines.append("你不用把这些经历当成要复制的路线，先把它们当成几面镜子就好。")
    return "\n".join(lines)


def render_database_unavailable() -> str:
    return (
        "我这里暂时连不上奥德赛案例库，也没有可以继续使用的本地缓存。\n\n"
        "所以这次我不会临时编造案例。你可以稍后再试；如果你愿意，"
        "也可以先聊聊你现在最卡住的地方，我会只基于你说的内容陪你梳理。"
    )


def search_remote(query: str, limit: int = 3, remote_base_url: str | None = None) -> str:
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
    parser.add_argument("--limit", type=int, default=3)
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
