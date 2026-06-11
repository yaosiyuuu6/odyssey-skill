#!/usr/bin/env python3
"""Prepare Odyssey 3.0 candidate records for Lark Base review."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REVIEW_STATUS_DEFAULT = "待审阅"
PRIORITY_DEFAULT = "P2"

REVIEW_FIELDS = [
    "标题",
    "人物/嘉宾",
    "平台",
    "URL",
    "来源类型",
    "主题标签",
    "可能决策场景",
    "适合原因",
    "原文可得性",
    "去重状态",
    "审阅状态",
    "优先级",
    "备注",
]


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalize_url(url: object) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    return text.split("#", 1)[0].rstrip("/")


def normalize_title(value: object) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)
    return text


def extract_bvid(value: object) -> str:
    match = re.search(r"(BV[0-9A-Za-z]{10,})", str(value or ""))
    return match.group(1) if match else ""


def normalize_tags(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw_tags = value
    else:
        raw_tags = str(value).replace("，", ",").split(",")
    tags: list[str] = []
    for tag in raw_tags:
        text = str(tag).strip()
        if text and text not in tags:
            tags.append(text)
    return tags


def existing_urls(source_index: list[dict[str, Any]]) -> set[str]:
    return {normalize_url(item.get("url")) for item in source_index if normalize_url(item.get("url"))}


def existing_bvids(source_index: list[dict[str, Any]]) -> dict[str, str]:
    result = {}
    for item in source_index:
        bvid = extract_bvid(item.get("url"))
        if bvid:
            result[bvid] = str(item.get("title") or item.get("case_id") or bvid)
    return result


def existing_titles(source_index: list[dict[str, Any]]) -> dict[str, str]:
    titles = {}
    for item in source_index:
        title = str(item.get("title") or "").strip()
        normalized = normalize_title(title)
        has_cjk = bool(re.search(r"[\u4e00-\u9fff]", normalized))
        if (has_cjk and len(normalized) >= 2) or len(normalized) >= 3:
            titles[normalized] = title
    return titles


STOP_TITLE_TOKENS = {
    "工作",
    "创业",
    "长期主义",
    "大厂",
    "出国",
    "案例",
}


def title_tokens(value: object) -> list[str]:
    text = str(value or "")
    raw_tokens = re.findall(r"[A-Za-z][A-Za-z0-9]+|[\u4e00-\u9fff]{2,}", text)
    tokens: list[str] = []
    for token in raw_tokens:
        token_text = token.strip()
        pieces = [token_text]
        if re.fullmatch(r"[\u4e00-\u9fff]{4,}", token_text):
            pieces = [token_text[index : index + 2] for index in range(0, len(token_text), 2)]
        for piece in pieces:
            lowered = piece.lower()
            if piece in STOP_TITLE_TOKENS:
                continue
            if lowered not in tokens:
                tokens.append(lowered)
    return tokens


def token_title_match(candidate_title: str, known_titles: dict[str, str]) -> str:
    candidate_norm = normalize_title(candidate_title)
    for original in known_titles.values():
        tokens = title_tokens(original)
        if len(tokens) >= 2 and all(token in candidate_norm for token in tokens):
            return f"existing_title_tokens={original}"
        if len(tokens) == 1:
            token = tokens[0]
            if (len(token) >= 4 or re.fullmatch(r"[\u4e00-\u9fff]{2,}", token)) and token in candidate_norm:
                return f"existing_title_token={original}"
    return ""


def candidate_url(candidate: dict[str, Any]) -> str:
    return normalize_url(candidate.get("url") or candidate.get("URL") or candidate.get("source_url"))


def candidate_value(candidate: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = candidate.get(key)
        if value is not None:
            return str(value).strip()
    return ""


def existing_match_reason(
    candidate: dict[str, Any],
    known_urls: set[str],
    known_bvids: dict[str, str],
    known_titles: dict[str, str],
) -> str:
    url = candidate_url(candidate)
    if url in known_urls:
        return "existing_url"
    bvid = extract_bvid(url)
    if bvid and bvid in known_bvids:
        return f"existing_bvid={bvid}"
    candidate_title = normalize_title(candidate_value(candidate, "title", "标题"))
    for normalized, original in known_titles.items():
        if normalized and candidate_title and (normalized in candidate_title or candidate_title in normalized):
            return f"existing_title={original}"
    token_reason = token_title_match(candidate_value(candidate, "title", "标题"), known_titles)
    if token_reason:
        return token_reason
    return ""


def build_review_rows(
    candidates: list[dict[str, Any]],
    source_index: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    known_urls = existing_urls(source_index)
    known_bvids = existing_bvids(source_index)
    known_titles = existing_titles(source_index)
    seen_urls: set[str] = set()
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        url = candidate_url(candidate)
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        tags = normalize_tags(candidate.get("topic_tags") or candidate.get("主题标签"))
        match_reason = existing_match_reason(candidate, known_urls, known_bvids, known_titles)
        notes = candidate_value(candidate, "notes", "备注")
        if match_reason and match_reason not in notes:
            notes = f"{notes}; {match_reason}".strip("; ")
        row = {
            "标题": candidate_value(candidate, "title", "标题"),
            "人物/嘉宾": candidate_value(candidate, "person", "guest", "人物/嘉宾"),
            "平台": candidate_value(candidate, "platform", "平台"),
            "URL": url,
            "来源类型": candidate_value(candidate, "source_type", "来源类型"),
            "主题标签": tags,
            "可能决策场景": candidate_value(candidate, "decision_scene", "可能决策场景"),
            "适合原因": candidate_value(candidate, "fit_reason", "适合原因"),
            "原文可得性": candidate_value(candidate, "text_availability", "原文可得性"),
            "去重状态": "已在 Odyssey" if match_reason else "新候选",
            "审阅状态": candidate_value(candidate, "review_status", "审阅状态") or REVIEW_STATUS_DEFAULT,
            "优先级": candidate_value(candidate, "priority", "优先级") or PRIORITY_DEFAULT,
            "备注": notes,
        }
        rows.append(row)
    return rows


def write_lark_records_jsonl(
    candidates_path: str | Path,
    source_index_path: str | Path,
    output_path: str | Path,
) -> int:
    candidates = load_json(candidates_path)
    source_index = load_json(source_index_path)
    rows = build_review_rows(candidates, source_index)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare Odyssey 3.0 candidate records for Lark Base.")
    parser.add_argument("--candidates", required=True, help="Candidate JSON array.")
    parser.add_argument("--source-index", default="data/source_index.json", help="Existing Odyssey source index JSON.")
    parser.add_argument("--out", required=True, help="Output JSONL path for lark-cli record upserts.")
    args = parser.parse_args()
    count = write_lark_records_jsonl(args.candidates, args.source_index, args.out)
    print(json.dumps({"records": count, "out": args.out}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
