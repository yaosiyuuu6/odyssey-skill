#!/usr/bin/env python3
"""Search public metadata for Odyssey 3.0 candidate cases."""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


DEFAULT_QUERIES = [
    "裸辞 转行 创业",
    "大厂 产品经理 职业 访谈",
    "留学 海外工作 创业 访谈",
    "城市选择 回国 海外 工作",
    "职业倦怠 自由职业 副业",
    "创业 现金流 合伙人 产品",
]

BILIBILI_QUERIES = [
    "裸辞 转行",
    "大厂 裸辞 创业",
    "留学 海外工作",
    "城市选择 定居",
    "自由职业 副业",
    "产品经理 转行",
    "回国 海外 去留",
]

XIAOHONGSHU_QUERIES = [
    "裸辞 转行",
    "大厂 裸辞 创业",
    "留学 海外工作",
    "城市选择 定居",
    "自由职业 副业",
    "职业倦怠 离职",
    "回国 海外 去留",
    "产品经理 转行",
    "一人公司 副业",
    "考研 留学 工作选择",
    "裸辞 开咖啡馆",
    "大厂离职 自由职业",
    "海外定居 职业选择",
    "转码 转行 复盘",
    "gap year 裸辞",
]

TAG_RULES = {
    "选校/专业": ["选校", "专业", "高考", "大学", "学校", "志愿"],
    "第一份工作": ["毕业", "校招", "第一份工作", "实习", "入职", "职场新人"],
    "考研/读研": ["考研", "读研", "研究生", "硕士", "博士"],
    "裸辞": ["裸辞", "辞职", "离职", "空窗"],
    "转行": ["转行", "转型", "换行业", "跨界"],
    "创业": ["创业", "创始人", "公司", "融资", "现金流"],
    "海外生活": ["海外", "澳洲", "美国", "欧洲", "新加坡", "回国", "留学"],
    "留学": ["留学", "读研", "硕士", "博士", "申请"],
    "大厂": ["大厂", "阿里", "腾讯", "字节", "华为", "微软", "Google", "Meta"],
    "产品": ["产品经理", "产品", "PM"],
    "城市选择": ["城市", "北上广深", "上海", "北京", "深圳", "杭州"],
    "职业倦怠": ["倦怠", "焦虑", "压力", "停下来"],
    "副业": ["副业", "自由职业", "一人公司"],
    "组织/管理": ["管理", "组织", "团队", "领导力", "合伙人"],
    "内容创作": ["创作", "写作", "播客", "视频", "脱口秀", "表达"],
    "长期主义": ["长期主义", "长期", "复利", "耐心"],
}


def infer_tags(text: str) -> list[str]:
    tags: list[str] = []
    lowered = text.lower()
    for tag, keywords in TAG_RULES.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            tags.append(tag)
    return tags


def infer_scene(tags: list[str]) -> str:
    if "选校/专业" in tags:
        return "如何选择学校或专业方向"
    if "第一份工作" in tags:
        return "毕业后如何选择第一份工作"
    if "考研/读研" in tags:
        return "是否继续读研或深造"
    if "裸辞" in tags and "创业" in tags:
        return "离开稳定工作后是否创业"
    if "转行" in tags:
        return "是否转换职业方向"
    if "留学" in tags or "海外生活" in tags:
        return "是否出国、回国或留在海外发展"
    if "城市选择" in tags:
        return "是否更换工作和生活城市"
    if "副业" in tags:
        return "是否把副业发展成主业"
    if "组织/管理" in tags:
        return "是否承担管理、合伙或组织责任"
    if "内容创作" in tags:
        return "是否进入内容创作或表达型职业"
    return "人生或职业关键选择"


def normalize_url(url: object) -> str:
    return str(url or "").split("#", 1)[0].rstrip("/")


def normalize_itunes_episode(item: dict[str, Any], query: str) -> dict[str, Any] | None:
    url = normalize_url(item.get("trackViewUrl") or item.get("collectionViewUrl"))
    title = str(item.get("trackName") or item.get("collectionName") or "").strip()
    if not url or not title:
        return None
    description = str(item.get("description") or item.get("shortDescription") or "").strip()
    haystack = " ".join(
        [
            query,
            title,
            str(item.get("collectionName") or ""),
            str(item.get("artistName") or ""),
            description,
        ]
    )
    tags = infer_tags(haystack)
    return {
        "title": title,
        "person": str(item.get("artistName") or "").strip(),
        "platform": "Apple Podcasts",
        "url": url,
        "source_type": "podcast",
        "topic_tags": tags,
        "decision_scene": infer_scene(tags),
        "fit_reason": "播客访谈通常包含完整叙事，可提取选择背景、约束、路径、代价和结果。",
        "text_availability": "需音频 ASR",
        "notes": f"query={query}; show={item.get('collectionName', '')}; release={item.get('releaseDate', '')}",
    }


def clean_html_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_bilibili_html(page_html: str, query: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_bvids: set[str] = set()
    pattern = re.compile(
        r'href=["\'](?:https?:)?//www\.bilibili\.com/video/(BV[0-9A-Za-z]{10,})[^"\']*["\'][^>]*>(.*?)</a>',
        re.S,
    )
    for match in pattern.finditer(page_html):
        bvid = match.group(1)
        if bvid in seen_bvids:
            continue
        seen_bvids.add(bvid)
        title = clean_html_text(match.group(2)) or f"Bilibili 视频 {bvid}"
        haystack = f"{query} {title}"
        tags = infer_tags(haystack)
        candidates.append(
            {
                "title": title,
                "person": "",
                "platform": "Bilibili",
                "url": f"https://www.bilibili.com/video/{bvid}",
                "source_type": "bilibili",
                "topic_tags": tags,
                "decision_scene": infer_scene(tags),
                "fit_reason": "B 站长视频/访谈可能包含完整叙事；后续优先检查官方字幕，缺失时走音频 ASR。",
                "text_availability": "可获取字幕或需音频 ASR",
                "notes": f"query={query}; bvid={bvid}",
            }
        )
    return candidates


def bvid_from_url(url: str) -> str | None:
    match = re.search(r"/video/(BV[0-9A-Za-z]{10,})", url)
    return match.group(1) if match else None


def fetch_bilibili_view_payload(bvid: str) -> dict[str, Any]:
    url = "https://api.bilibili.com/x/web-interface/view?" + urllib.parse.urlencode({"bvid": bvid})
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.bilibili.com/",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def apply_bilibili_view_payload(candidate: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("code") != 0 or not isinstance(payload.get("data"), dict):
        return candidate
    data = payload["data"]
    title = str(data.get("title") or "").strip()
    owner = data.get("owner") if isinstance(data.get("owner"), dict) else {}
    person = str(owner.get("name") or "").strip()
    desc = str(data.get("desc") or "").strip()
    repaired = dict(candidate)
    if title:
        repaired["title"] = title
    if person:
        repaired["person"] = person
    tags = infer_tags(" ".join([repaired.get("title", ""), person, desc]))
    repaired["topic_tags"] = tags
    repaired["decision_scene"] = infer_scene(tags)
    return repaired


def enrich_bilibili_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for candidate in candidates:
        bvid = bvid_from_url(candidate.get("url", ""))
        if not bvid:
            enriched.append(candidate)
            continue
        try:
            enriched.append(apply_bilibili_view_payload(candidate, fetch_bilibili_view_payload(bvid)))
        except Exception as error:
            fallback = dict(candidate)
            fallback["notes"] = f"{fallback.get('notes', '')}; detail_fetch_failed={type(error).__name__}"
            enriched.append(fallback)
    return enriched


def fetch_bilibili_search(query: str) -> str:
    url = "https://search.bilibili.com/all?" + urllib.parse.urlencode({"keyword": query})
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://search.bilibili.com/",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "ignore")


def search_bilibili_candidates(queries: list[str], target_count: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for query in queries:
        candidates.extend(parse_bilibili_html(fetch_bilibili_search(query), query))
        candidates = dedupe_candidates(candidates)
        if len(candidates) >= target_count:
            break
    enriched = enrich_bilibili_candidates(candidates)
    relevant = [candidate for candidate in enriched if candidate.get("topic_tags")]
    return relevant[:target_count]


def bvids_from_sources(sources: list[dict[str, Any]]) -> list[str]:
    bvids: list[str] = []
    for source in sources:
        if source.get("source_type") != "bilibili":
            continue
        match = re.search(r"(BV[0-9A-Za-z]{10,})", str(source.get("url", "")))
        if match and match.group(1) not in bvids:
            bvids.append(match.group(1))
    return bvids


def bilibili_owner_names_from_sources(source_index_path: str | Path) -> list[str]:
    names: list[str] = []
    for bvid in bvids_from_sources(load_source_index(source_index_path)):
        try:
            payload = fetch_bilibili_view_payload(bvid)
            owner = payload.get("data", {}).get("owner", {})
            name = str(owner.get("name") or "").strip()
            if name and name not in names:
                names.append(name)
        except Exception:
            continue
    return names


def search_bilibili_candidates_from_existing_sources(
    source_index_path: str | Path,
    target_count: int,
) -> list[dict[str, Any]]:
    owner_names = bilibili_owner_names_from_sources(source_index_path)
    per_owner_limit = max(3, math.ceil(target_count / max(1, len(owner_names))))
    topics = ["人生", "工作", "选择", "访谈", "转行", "留学", "城市", "创业", "毕业"]
    candidates: list[dict[str, Any]] = []
    for owner_name in owner_names:
        queries = [owner_name] + [f"{owner_name} {topic}" for topic in topics]
        found = search_bilibili_candidates(queries, per_owner_limit)
        candidates.extend([candidate for candidate in found if candidate.get("person") == owner_name])
        candidates = dedupe_candidates(candidates)
    return balanced_select(candidates, "person", target_count)


def xiaohongshu_search_candidate(query: str) -> dict[str, Any]:
    url = "https://www.xiaohongshu.com/search_result?" + urllib.parse.urlencode({"keyword": query})
    tags = infer_tags(query)
    return {
        "title": f"小红书人工复核：{query}",
        "person": "",
        "platform": "Xiaohongshu",
        "url": url,
        "source_type": "xiaohongshu",
        "topic_tags": tags,
        "decision_scene": infer_scene(tags),
        "fit_reason": "小红书公开搜索需要登录态/前端签名才能稳定展开具体笔记；后续按 OdysseyMap 方法人工打开、展开、截图/OCR 后筛入具体案例。",
        "text_availability": "需人工打开确认 / 需 OCR",
        "notes": f"manual_review_query={query}",
    }


def search_xiaohongshu_candidates(queries: list[str], target_count: int) -> list[dict[str, Any]]:
    return [xiaohongshu_search_candidate(query) for query in queries[:target_count]]


def dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    seen_titles: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for candidate in candidates:
        url = normalize_url(candidate.get("url"))
        title_key = (str(candidate.get("platform", "")), re.sub(r"\s+", "", str(candidate.get("title", "")).lower()))
        if not url or url in seen or title_key in seen_titles:
            continue
        seen.add(url)
        seen_titles.add(title_key)
        normalized = dict(candidate)
        normalized["url"] = url
        result.append(normalized)
    return result


def balanced_select(candidates: list[dict[str, Any]], group_key: str, target_count: int) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        group = str(candidate.get(group_key) or candidate.get("platform") or "UNKNOWN")
        grouped.setdefault(group, []).append(candidate)
    selected: list[dict[str, Any]] = []
    while len(selected) < target_count and any(grouped.values()):
        for group in list(grouped):
            if not grouped[group]:
                continue
            selected.append(grouped[group].pop(0))
            if len(selected) >= target_count:
                break
    return dedupe_candidates(selected)[:target_count]


def apple_collection_ids_from_sources(sources: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for source in sources:
        if source.get("source_type") != "podcast":
            continue
        match = re.search(r"/id(\d+)", str(source.get("url", "")))
        if match and match.group(1) not in ids:
            ids.append(match.group(1))
    return ids


def load_source_index(path: str | Path) -> list[dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def lookup_podcast_collection(collection_id: str, country: str = "AU") -> dict[str, Any] | None:
    url = "https://itunes.apple.com/lookup?" + urllib.parse.urlencode({"id": collection_id, "country": country})
    with urllib.request.urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    results = payload.get("results") or []
    return results[0] if results else None


def fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "ignore")


def xml_text(element: ET.Element, name: str) -> str:
    found = element.find(name)
    return "".join(found.itertext()).strip() if found is not None else ""


def parse_podcast_rss(rss_text: str, show_name: str, limit: int = 12) -> list[dict[str, Any]]:
    root = ET.fromstring(rss_text)
    candidates: list[dict[str, Any]] = []
    for item in root.findall(".//item"):
        title = xml_text(item, "title")
        link = xml_text(item, "link")
        description = xml_text(item, "description")
        if not title or not link:
            continue
        tags = infer_tags(f"{show_name} {title} {description}")
        if not tags:
            continue
        candidates.append(
            {
                "title": title,
                "person": show_name,
                "platform": "Podcast RSS",
                "source_show": show_name,
                "url": link,
                "source_type": "podcast",
                "topic_tags": tags,
                "decision_scene": infer_scene(tags),
                "fit_reason": "来自现有 Odyssey 案例已验证的优质播客节目；同一节目内其他长访谈适合继续提取人生选择节点。",
                "text_availability": "需音频 ASR",
                "notes": f"source_show={show_name}",
            }
        )
        if len(candidates) >= limit:
            break
    return candidates


def search_podcast_candidates_from_existing_sources(
    source_index_path: str | Path,
    target_count: int,
    country: str = "AU",
    per_show_limit: int = 10,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    sources = load_source_index(source_index_path)
    collection_ids = apple_collection_ids_from_sources(sources)
    show_limit = max(per_show_limit, math.ceil(target_count / max(1, len(collection_ids))))
    for collection_id in collection_ids:
        try:
            collection = lookup_podcast_collection(collection_id, country=country)
            if not collection or not collection.get("feedUrl"):
                continue
            show_name = collection.get("collectionName") or collection.get("artistName") or collection_id
            rss_text = fetch_text(collection["feedUrl"])
            candidates.extend(parse_podcast_rss(rss_text, str(show_name), limit=show_limit))
            candidates = dedupe_candidates(candidates)
        except Exception:
            continue
    return balanced_select(candidates, "source_show", target_count)


def fetch_itunes_episodes(query: str, limit: int = 50, country: str = "CN") -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "term": query,
            "country": country,
            "media": "podcast",
            "entity": "podcastEpisode",
            "limit": limit,
        }
    )
    url = f"https://itunes.apple.com/search?{params}"
    with urllib.request.urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("results", [])


def search_candidates(queries: list[str], target_count: int, per_query_limit: int, country: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for query in queries:
        for item in fetch_itunes_episodes(query, limit=per_query_limit, country=country):
            candidate = normalize_itunes_episode(item, query)
            if candidate:
                candidates.append(candidate)
        candidates = dedupe_candidates(candidates)
        if len(candidates) >= target_count:
            break
    return candidates[:target_count]


def search_mixed_candidates(
    podcast_count: int,
    bilibili_count: int,
    xiaohongshu_count: int,
    per_query_limit: int,
    country: str,
) -> list[dict[str, Any]]:
    podcast_queries = [
        "裸辞",
        "转行",
        "大厂",
        "产品经理",
        "创业 访谈",
        "留学",
        "海外工作",
        "回国 工作",
        "自由职业",
        "副业",
        "职业倦怠",
        "城市选择",
        "AI 创业",
        "人生选择",
    ]
    candidates: list[dict[str, Any]] = []
    candidates.extend(search_candidates(podcast_queries, podcast_count, per_query_limit, country))
    candidates.extend(search_bilibili_candidates(BILIBILI_QUERIES, bilibili_count))
    candidates.extend(search_xiaohongshu_candidates(XIAOHONGSHU_QUERIES, xiaohongshu_count))
    return dedupe_candidates(candidates)[: podcast_count + bilibili_count + xiaohongshu_count]


def search_from_existing_sources(
    source_index_path: str | Path,
    podcast_count: int,
    bilibili_count: int,
    xiaohongshu_count: int,
    country: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    candidates.extend(
        search_podcast_candidates_from_existing_sources(
            source_index_path,
            target_count=podcast_count,
            country=country,
            per_show_limit=max(4, podcast_count // 6),
        )
    )
    candidates.extend(search_bilibili_candidates_from_existing_sources(source_index_path, bilibili_count))
    candidates.extend(search_xiaohongshu_candidates(XIAOHONGSHU_QUERIES, xiaohongshu_count))
    return dedupe_candidates(candidates)[: podcast_count + bilibili_count + xiaohongshu_count]


def main() -> int:
    parser = argparse.ArgumentParser(description="Search public metadata for Odyssey 3.0 candidates.")
    parser.add_argument("--query", action="append", dest="queries", help="Search query. Can be repeated.")
    parser.add_argument("--target-count", type=int, default=100)
    parser.add_argument("--per-query-limit", type=int, default=100)
    parser.add_argument("--country", default="CN")
    parser.add_argument("--mixed", action="store_true", help="Generate a mixed Podcast/Bilibili/Xiaohongshu candidate pool.")
    parser.add_argument("--from-existing-sources", action="store_true", help="Expand candidates from channels/shows already present in data/source_index.json.")
    parser.add_argument("--source-index", default="data/source_index.json")
    parser.add_argument("--podcast-count", type=int, default=50)
    parser.add_argument("--bilibili-count", type=int, default=35)
    parser.add_argument("--xiaohongshu-count", type=int, default=15)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.from_existing_sources:
        candidates = search_from_existing_sources(
            args.source_index,
            args.podcast_count,
            args.bilibili_count,
            args.xiaohongshu_count,
            args.country,
        )
    elif args.mixed:
        candidates = search_mixed_candidates(
            args.podcast_count,
            args.bilibili_count,
            args.xiaohongshu_count,
            args.per_query_limit,
            args.country,
        )
    else:
        candidates = search_candidates(args.queries or DEFAULT_QUERIES, args.target_count, args.per_query_limit, args.country)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(candidates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidates": len(candidates), "out": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
