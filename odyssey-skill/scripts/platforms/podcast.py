from __future__ import annotations

import html
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests

from scripts.asr import transcribe_audio
from scripts.completeness import evaluate_text_completeness
from scripts.text_normalize import normalize_chinese_text, normalize_record_text


def _apply_transcription_result(record: dict, result: dict) -> None:
    record["assets"]["transcripts"].extend(result.get("assets", []))
    record["fetch_errors"].extend(result.get("errors", []))
    record["correction_log"].extend(result.get("correction_log", []))
    if result.get("speaker_segments"):
        record["speaker_segments"] = result["speaker_segments"]
        record["speaker_count"] = result.get("speaker_count", 0)
        record["speaker_role_map"] = result.get("speaker_role_map", {})
        record["speaker_label_status"] = result.get("speaker_label_status", "diarized")
    if result.get("text"):
        record["transcript_text"] = result["text"]
        record["merged_text"] = result["text"]


def extract_episode_id(url: str) -> str | None:
    return parse_qs(urlparse(url).query).get("i", [None])[0]


def extract_show_id(url: str) -> str | None:
    match = re.search(r"/id(\d+)", url)
    return match.group(1) if match else None


def _find_rss_audio(feed_url: str, episode_id: str | None, title: str) -> str | None:
    response = requests.get(feed_url, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    root = ET.fromstring(response.content)
    title_norm = re.sub(r"\s+", "", title or "")
    for item in root.findall(".//item"):
        guid = "".join(item.findtext("guid") or "")
        item_title = item.findtext("title") or ""
        item_title_norm = re.sub(r"\s+", "", item_title)
        enclosure = item.find("enclosure")
        enclosure_url = enclosure.attrib.get("url") if enclosure is not None else None
        if not enclosure_url:
            continue
        if episode_id and episode_id in guid:
            return enclosure_url
        if title_norm and (title_norm in item_title_norm or item_title_norm in title_norm):
            return enclosure_url
    return None


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _find_meta(html_text: str, name: str) -> str:
    patterns = [
        rf'<meta[^>]+property=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']*)["\']',
        rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+property=["\']{re.escape(name)}["\']',
        rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']*)["\']',
        rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']{re.escape(name)}["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, re.I | re.S)
        if match:
            return html.unescape(match.group(1)).strip()
    return ""


def _find_rss_link(page_url: str, html_text: str) -> str:
    match = re.search(
        r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]+href=["\']([^"\']+)["\']',
        html_text,
        re.I | re.S,
    )
    if not match:
        match = re.search(
            r'<link[^>]+href=["\']([^"\']+)["\'][^>]+type=["\']application/(?:rss|atom)\+xml["\']',
            html_text,
            re.I | re.S,
        )
    if match:
        return urljoin(page_url, html.unescape(match.group(1)).strip())
    parsed = urlparse(page_url)
    if parsed.netloc.endswith("fireside.fm"):
        return f"{parsed.scheme}://{parsed.netloc}/rss"
    return ""


def _clean_url(value: str) -> str:
    return html.unescape(value).replace("\\u0026", "&").replace("\\/", "/").rstrip("\\")


def _find_inline_audio_url(html_text: str) -> str:
    for match in re.finditer(r"https?://[^\"'<> ]+\.(?:mp3|m4a)(?:\?[^\"'<> ]*)?", html_text, re.I):
        return _clean_url(match.group(0))
    return ""


def _item_text(item: ET.Element, name: str) -> str:
    value = item.findtext(name)
    if value:
        return _strip_html(value)
    for child in item:
        if child.tag.endswith("}" + name) or child.tag == name:
            return _strip_html(child.text or "")
    return ""


def _item_matches_url(item: ET.Element, page_url: str, page_title: str) -> bool:
    parsed = urlparse(page_url)
    path = parsed.path.rstrip("/")
    candidates = [
        _item_text(item, "link"),
        _item_text(item, "guid"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        candidate_path = urlparse(candidate).path.rstrip("/")
        if candidate.rstrip("/") == page_url.rstrip("/") or (path and candidate_path == path):
            return True
    item_title = re.sub(r"\s+", "", _item_text(item, "title"))
    title = re.sub(r"\s+", "", page_title or "")
    return bool(title and item_title and (title in item_title or item_title in title))


def _metadata_from_rss(feed_url: str, page_url: str, page_title: str) -> dict:
    response = requests.get(feed_url, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    root = ET.fromstring(response.content)
    item = next((candidate for candidate in root.findall(".//item") if _item_matches_url(candidate, page_url, page_title)), None)
    if item is None:
        item = next(iter(root.findall(".//item")), None)
    if item is None:
        return {}
    enclosure = item.find("enclosure")
    audio_url = enclosure.attrib.get("url") if enclosure is not None else ""
    duration = ""
    for child in item:
        if child.tag.endswith("}duration") or child.tag == "duration":
            duration = _strip_html(child.text or "")
            break
    description = _item_text(item, "description") or _item_text(item, "summary")
    return {
        "title": _item_text(item, "title"),
        "description": description,
        "description_source": "rss_description" if description else "",
        "description_completeness": "完整" if description else "缺失",
        "audio_url": audio_url,
        "published_at": _item_text(item, "pubDate"),
        "duration": duration,
        "feed_url": feed_url,
    }


def discover_generic_episode(url: str) -> dict:
    response = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    html_text = response.text
    metadata = {
        "title": _find_meta(html_text, "og:title") or _find_meta(html_text, "twitter:title"),
        "description": _find_meta(html_text, "og:description") or _find_meta(html_text, "description"),
        "description_source": "page_meta",
        "description_completeness": "部分",
        "audio_url": _find_meta(html_text, "og:audio") or _find_meta(html_text, "twitter:player:stream") or _find_inline_audio_url(html_text),
        "published_at": "",
        "duration": "",
        "feed_url": "",
    }
    rss_url = _find_rss_link(url, html_text)
    if rss_url:
        try:
            rss_metadata = _metadata_from_rss(rss_url, url, metadata.get("title", ""))
            metadata.update({key: value for key, value in rss_metadata.items() if value})
        except Exception as exc:
            metadata["rss_error"] = str(exc)
            metadata["feed_url"] = rss_url
    if not metadata.get("description"):
        metadata["description_source"] = ""
        metadata["description_completeness"] = "缺失"
    return metadata


def _download_audio(audio_url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(audio_url, stream=True, timeout=60, headers={"User-Agent": "Mozilla/5.0"}) as response:
        response.raise_for_status()
        with path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)


def collect_podcast(
    record: dict,
    output_dir: Path,
    fetch_media: bool = True,
    asr_timeout_seconds: int = 900,
    asr_engine: str = "auto",
    asr_model: str = "base",
) -> dict:
    episode_id = extract_episode_id(record["url"])
    show_id = extract_show_id(record["url"])
    record["platform_ids"]["episode_id"] = episode_id
    record["platform_ids"]["show_id"] = show_id
    record["content_type"] = "audio"
    record["is_multi_speaker"] = True
    record["speaker_label_status"] = "unknown"
    record["text_source"] = "播客音频转写"
    if record.get("seed_title") and not record.get("title"):
        record["title"] = normalize_chinese_text(record["seed_title"])
    if record.get("seed_person_or_guest") and not record.get("author"):
        record["author"] = normalize_chinese_text(record["seed_person_or_guest"])

    try:
        if "podcasts.apple.com" in record["url"]:
            lookup = requests.get(
                "https://itunes.apple.com/lookup",
                params={"id": show_id or episode_id, "entity": "podcastEpisode", "limit": 200},
                timeout=25,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            lookup.raise_for_status()
            results = lookup.json().get("results", [])
            episode = next(
                (
                    item
                    for item in results
                    if item.get("wrapperType") == "podcastEpisode"
                    and str(item.get("trackId")) == str(episode_id)
                ),
                None,
            )
            if not episode:
                episode = next((item for item in results if item.get("wrapperType") == "podcastEpisode"), None)
            show = next((item for item in results if item.get("wrapperType") == "track"), None)
            if not episode:
                record["fetch_errors"].append("itunes_episode_missing")
                audio_url = None
            else:
                record["title"] = normalize_chinese_text(episode.get("trackName", "")) or record.get("title", "")
                record["author"] = normalize_chinese_text(episode.get("collectionName") or episode.get("artistName", "")) or record.get("author", "")
                record["published_at"] = episode.get("releaseDate")
                record["duration"] = episode.get("trackTimeMillis")
                description = html.unescape(episode.get("description") or episode.get("shortDescription") or "")
                if description:
                    record["platform_description"] = normalize_chinese_text(description)
                    record["description_source"] = "itunes_description"
                    record["description_completeness"] = "完整"
                else:
                    record["description_completeness"] = "缺失"
                    record["notes"].append("description_missing")
                audio_url = episode.get("episodeUrl")
                if not audio_url and show and show.get("feedUrl"):
                    audio_url = _find_rss_audio(show["feedUrl"], episode_id, record["title"])
        else:
            metadata = discover_generic_episode(record["url"])
            record["title"] = normalize_chinese_text(metadata.get("title", "")) or record.get("title", "")
            record["author"] = record.get("author", "")
            record["published_at"] = metadata.get("published_at", "")
            record["duration"] = metadata.get("duration")
            if metadata.get("description"):
                record["platform_description"] = normalize_chinese_text(metadata["description"])
                record["description_source"] = metadata.get("description_source", "page_meta")
                record["description_completeness"] = metadata.get("description_completeness", "部分")
            else:
                record["description_completeness"] = "缺失"
                record["notes"].append("description_missing")
            if metadata.get("feed_url"):
                record["platform_ids"]["feed_url"] = metadata["feed_url"]
            if metadata.get("rss_error"):
                record["fetch_errors"].append(f"rss_fetch_failed:{metadata['rss_error']}")
            audio_url = metadata.get("audio_url")

        if audio_url:
            record["resolved_url"] = audio_url
            record["assets"]["remote_audio"].append(audio_url)
            if fetch_media and record.get("transcript_text"):
                record["notes"].append("existing_transcript_reused")
            elif fetch_media:
                existing_audio = [
                    Path(path)
                    for path in record.get("assets", {}).get("audio", [])
                    if Path(path).exists()
                ]
                if existing_audio:
                    audio_path = existing_audio[0]
                else:
                    suffix = Path(urlparse(audio_url).path).suffix or ".mp3"
                    audio_path = output_dir / "assets" / record["id"] / f"audio{suffix}"
                    _download_audio(audio_url, audio_path)
                    record["assets"]["audio"].append(str(audio_path))
                result = transcribe_audio(
                    audio_path,
                    audio_path.parent,
                    language="zh",
                    timeout_seconds=asr_timeout_seconds,
                    engine=asr_engine,
                    model=asr_model,
                )
                _apply_transcription_result(record, result)
            else:
                record["notes"].append("media_fetch_disabled")
        else:
            record["fetch_errors"].append("audio_url_missing")
    except Exception as exc:
        record["fetch_errors"].append(f"podcast_fetch_failed:{exc}")

    record["text_completeness"] = evaluate_text_completeness(record)
    return normalize_record_text(record)
