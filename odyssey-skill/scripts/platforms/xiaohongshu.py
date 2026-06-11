from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from scripts.completeness import evaluate_text_completeness
from scripts.ocr import ocr_images
from scripts.text_normalize import normalize_chinese_text, normalize_record_text


def _decode_js_string(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except Exception:
        return value.replace("\\u002F", "/")


def _extract_image_urls(html_text: str) -> list[str]:
    urls: list[str] = []
    for key in ("urlDefault", "urlPre"):
        pattern = rf'"{key}"\s*:\s*"([^"]+)"'
        for match in re.finditer(pattern, html_text):
            url = _decode_js_string(match.group(1))
            if url.startswith("http"):
                urls.append(url)
    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    # Prefer full-size urlDefault images. urlPre values are previews and only act as fallback.
    default_urls = [
        _decode_js_string(match.group(1))
        for match in re.finditer(r'"urlDefault"\s*:\s*"([^"]+)"', html_text)
    ]
    default_urls = [url for url in default_urls if url.startswith("http")]
    return default_urls or deduped


def _download_images(image_urls: list[str], output_dir: Path, record_id: str) -> tuple[list[str], list[str]]:
    image_dir = output_dir / "assets" / record_id / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    errors: list[str] = []
    for index, image_url in enumerate(image_urls, start=1):
        path = image_dir / f"image_{index:03d}.jpg"
        try:
            with requests.get(
                image_url,
                stream=True,
                timeout=45,
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.xiaohongshu.com/"},
            ) as response:
                response.raise_for_status()
                with path.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 512):
                        if chunk:
                            handle.write(chunk)
            paths.append(str(path))
        except Exception as exc:
            errors.append(f"xhs_image_download_failed:{index}:{exc}")
    return paths, errors


def collect_xiaohongshu(record: dict, output_dir: Path, fetch_media: bool = True) -> dict:
    record["content_type"] = "note"
    record["is_multi_speaker"] = False
    record["speaker_label_status"] = "not_applicable"
    record["text_source"] = "正文+OCR"

    try:
        response = requests.get(
            record["url"],
            allow_redirects=True,
            timeout=25,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        record["resolved_url"] = response.url
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        meta_desc = soup.find("meta", attrs={"name": "description"})
        body = meta_desc.get("content", "").strip() if meta_desc else ""
        record["title"] = normalize_chinese_text(title)
        if body:
            description = normalize_chinese_text(body)
            record["platform_description"] = description
            record["description_source"] = "xhs_desc"
            record["description_completeness"] = "完整"
            record["body_text"] = description
        else:
            record["description_completeness"] = "缺失"
            record["notes"].append("description_missing")
        image_urls = _extract_image_urls(response.text)
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src and "http" in src:
                image_urls.append(src)
        record["assets"]["remote_images"] = list(dict.fromkeys(image_urls))
        if record["assets"]["remote_images"] and fetch_media:
            image_paths, image_errors = _download_images(record["assets"]["remote_images"], output_dir, record["id"])
            record["assets"]["images"].extend(image_paths)
            record["fetch_errors"].extend(image_errors)
            if image_paths:
                ocr_text, ocr_errors = ocr_images(
                    [Path(path) for path in image_paths],
                    output_dir / "assets" / record["id"] / "images_ocr.txt",
                )
                record["ocr_text"] = ocr_text
                record["fetch_errors"].extend(ocr_errors)
        if not body or "登录" in body or "打开小红书" in body:
            record["notes"].append("manual_computer_use_required")
            record["fetch_errors"].append("public_page_incomplete")
    except Exception as exc:
        record["fetch_errors"].append(f"xhs_public_fetch_failed:{exc}")
        record["notes"].append("manual_computer_use_required")

    if record["assets"].get("remote_images") and not record.get("ocr_text"):
        record["notes"].append("image_ocr_pending")

    if record.get("body_text") or record.get("ocr_text"):
        record["merged_text"] = "\n\n".join(
            part for part in [record.get("body_text", ""), record.get("ocr_text", "")] if part
        )
    record["text_completeness"] = evaluate_text_completeness(record)
    return normalize_record_text(record)


def looks_like_xiaohongshu(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return "xiaohongshu.com" in host or "xhslink.com" in host
