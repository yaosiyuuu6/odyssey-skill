from __future__ import annotations

import re


URL_RE = re.compile(r"https?://\S+")

FALLBACK_TRADITIONAL_TO_SIMPLIFIED = str.maketrans(
    {
        "這": "这",
        "個": "个",
        "選": "选",
        "擇": "择",
        "發": "发",
        "與": "与",
        "為": "为",
        "學": "学",
        "會": "会",
        "後": "后",
        "說": "说",
        "國": "国",
        "過": "过",
        "時": "时",
        "間": "间",
        "長": "长",
        "視": "视",
        "頻": "频",
        "聲": "声",
        "錄": "录",
        "寫": "写",
        "標": "标",
        "題": "题",
        "簡": "简",
        "體": "体",
        "臺": "台",
        "台": "台",
        "萬": "万",
        "億": "亿",
        "職": "职",
        "業": "业",
        "轉": "转",
        "復": "复",
        "盤": "盘",
        "圖": "图",
        "說": "说",
        "話": "话",
        "員": "员",
        "獲": "获",
        "取": "取",
        "錯": "错",
        "誤": "误",
    }
)


def _convert_segment(segment: str) -> str:
    try:
        from opencc import OpenCC  # type: ignore

        return OpenCC("t2s").convert(segment)
    except Exception:
        return segment.translate(FALLBACK_TRADITIONAL_TO_SIMPLIFIED)


def normalize_chinese_text(text: str | None) -> str:
    """Normalize Chinese text to simplified Chinese while preserving URLs."""
    if not text:
        return ""

    parts: list[str] = []
    cursor = 0
    for match in URL_RE.finditer(text):
        parts.append(_convert_segment(text[cursor : match.start()]))
        parts.append(match.group(0))
        cursor = match.end()
    parts.append(_convert_segment(text[cursor:]))
    return "".join(parts)


def normalize_record_text(record: dict) -> dict:
    for key in (
        "title",
        "author",
        "platform_description",
        "body_text",
        "ocr_text",
        "transcript_text",
        "merged_text",
        "notes_text",
    ):
        if isinstance(record.get(key), str):
            record[key] = normalize_chinese_text(record[key])
    if isinstance(record.get("notes"), list):
        record["notes"] = [normalize_chinese_text(str(note)) for note in record["notes"]]
    return record
