from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from scripts.asr import find_binary, transcribe_audio
from scripts.completeness import evaluate_text_completeness
from scripts.text_normalize import normalize_chinese_text, normalize_record_text


BV_RE = re.compile(r"(BV[0-9A-Za-z]+)")


def _apply_transcription_result(record: dict, result: dict, text_source: str) -> None:
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
        record["text_source"] = text_source


def extract_bvid(url: str) -> str | None:
    match = BV_RE.search(url)
    return match.group(1) if match else None


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.bilibili.com/",
    }


def _metadata_description(data: dict) -> tuple[str, str, str]:
    desc = normalize_chinese_text(data.get("desc", ""))
    if desc:
        return desc, "bilibili_desc", "完整"
    dynamic = normalize_chinese_text(data.get("dynamic", ""))
    if dynamic:
        return dynamic, "bilibili_dynamic", "部分"
    title = normalize_chinese_text(data.get("title", ""))
    author = normalize_chinese_text(data.get("owner", {}).get("name", ""))
    parts = []
    if title:
        parts.append(f"视频标题：{title}")
    if author:
        parts.append(f"UP 主：{author}")
    if parts:
        return "；".join(parts), "bilibili_metadata_fallback", "部分"
    return "", "", "缺失"


def _load_subtitle(record: dict, output_dir: Path, cid: int) -> None:
    bvid = extract_bvid(record["url"])
    if not bvid:
        record["fetch_errors"].append("bvid_missing")
        return
    player_url = "https://api.bilibili.com/x/player/v2"
    try:
        response = requests.get(
            player_url,
            params={"bvid": bvid, "cid": cid},
            headers=_headers(),
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        subtitles = (
            data.get("data", {})
            .get("subtitle", {})
            .get("subtitles", [])
        )
        if not subtitles:
            record["notes"].append("official_subtitle_missing")
            return
        subtitle_url = subtitles[0].get("subtitle_url")
        if not subtitle_url:
            record["notes"].append("official_subtitle_url_missing")
            return
        if subtitle_url.startswith("//"):
            subtitle_url = "https:" + subtitle_url
        subtitle_response = requests.get(subtitle_url, headers=_headers(), timeout=20)
        subtitle_response.raise_for_status()
        subtitle_json = subtitle_response.json()
        lines = [
            item.get("content", "").strip()
            for item in subtitle_json.get("body", [])
            if item.get("content", "").strip()
        ]
        transcript = normalize_chinese_text("\n".join(lines))
        subtitle_dir = output_dir / "assets" / record["id"]
        subtitle_dir.mkdir(parents=True, exist_ok=True)
        subtitle_path = subtitle_dir / "official_subtitle.json"
        subtitle_path.write_text(
            json.dumps(subtitle_json, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        text_path = subtitle_dir / "official_subtitle.txt"
        text_path.write_text(transcript, encoding="utf-8")
        record["transcript_text"] = transcript
        record["merged_text"] = transcript
        record["text_source"] = "官方字幕"
        record["assets"]["subtitles"].append(str(subtitle_path))
        record["assets"]["subtitles"].append(str(text_path))
    except Exception as exc:
        record["fetch_errors"].append(f"subtitle_fetch_failed:{exc}")


def _ass_to_text(path: Path) -> str:
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        if len(parts) == 10:
            lines.append(parts[9].replace("\\N", "\n").replace("\\n", "\n").strip())
    return normalize_chinese_text("\n".join(line for line in lines if line))


def _load_subtitle_with_bccdl(record: dict, output_dir: Path) -> None:
    bvid = extract_bvid(record["url"])
    bccdl = find_binary("bccdl")
    if not bvid or not bccdl:
        if not bccdl:
            record["notes"].append("bccdl_unavailable")
        return
    subtitle_dir = output_dir / "assets" / record["id"] / "bccdl"
    subtitle_dir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [bccdl, "-o", str(subtitle_dir), bvid],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        ass_files = sorted(subtitle_dir.glob("*.ass"))
        if not ass_files:
            record["notes"].append("bccdl_subtitle_missing")
            return
        transcript = normalize_chinese_text("\n\n".join(_ass_to_text(path) for path in ass_files))
        text_path = subtitle_dir / "bccdl_subtitle.txt"
        text_path.write_text(transcript, encoding="utf-8")
        record["transcript_text"] = transcript
        record["merged_text"] = transcript
        record["text_source"] = "官方字幕"
        record["assets"]["subtitles"].extend(str(path) for path in ass_files)
        record["assets"]["subtitles"].append(str(text_path))
    except Exception as exc:
        record["fetch_errors"].append(f"bccdl_failed:{exc}")


def _download_and_transcribe(
    record: dict,
    output_dir: Path,
    asr_timeout_seconds: int = 900,
    asr_engine: str = "auto",
    asr_model: str = "base",
) -> None:
    existing_audio = [Path(path) for path in record.get("assets", {}).get("audio", []) if Path(path).exists()]
    if existing_audio:
        asset_dir = existing_audio[0].parent
        result = transcribe_audio(
            existing_audio[0],
            asset_dir,
            language="zh",
            timeout_seconds=asr_timeout_seconds,
            engine=asr_engine,
            model=asr_model,
        )
        _apply_transcription_result(record, result, "音频转写")
        if result.get("text"):
            return

    if _download_from_playurl(
        record,
        output_dir,
        asr_timeout_seconds=asr_timeout_seconds,
        asr_engine=asr_engine,
        asr_model=asr_model,
    ):
        return

    yt_dlp = find_binary("yt-dlp")
    if not yt_dlp:
        record["fetch_errors"].append("yt_dlp_unavailable")
        return

    asset_dir = output_dir / "assets" / record["id"]
    asset_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(asset_dir / "audio.%(ext)s")
    cmd = [
        yt_dlp,
        "-f",
        "bestaudio/best",
        "-o",
        output_template,
        record["url"],
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=900)
        audio_files = sorted(asset_dir.glob("audio.*"))
        if not audio_files:
            record["fetch_errors"].append("audio_download_missing_output")
            return
        audio_path = audio_files[0]
        record["assets"]["audio"].append(str(audio_path))
        result = transcribe_audio(
            audio_path,
            asset_dir,
            language="zh",
            timeout_seconds=asr_timeout_seconds,
            engine=asr_engine,
            model=asr_model,
        )
        _apply_transcription_result(record, result, "音频转写")
    except Exception as exc:
        record["fetch_errors"].append(f"audio_download_failed:{exc}")


def _download_from_playurl(
    record: dict,
    output_dir: Path,
    asr_timeout_seconds: int = 900,
    asr_engine: str = "auto",
    asr_model: str = "base",
) -> bool:
    bvid = record.get("platform_ids", {}).get("bvid") or extract_bvid(record["url"])
    cid = record.get("platform_ids", {}).get("cid")
    if not bvid or not cid:
        return False
    try:
        response = requests.get(
            "https://api.bilibili.com/x/player/playurl",
            params={"bvid": bvid, "cid": cid, "fnval": 16, "fourk": 1},
            headers=_headers(),
            timeout=25,
        )
        response.raise_for_status()
        payload = response.json()
        audios = payload.get("data", {}).get("dash", {}).get("audio", [])
        if not audios:
            record["fetch_errors"].append("playurl_audio_missing")
            return False
        audio_url = audios[0].get("baseUrl") or audios[0].get("base_url")
        if not audio_url:
            record["fetch_errors"].append("playurl_audio_url_missing")
            return False
        asset_dir = output_dir / "assets" / record["id"]
        asset_dir.mkdir(parents=True, exist_ok=True)
        audio_path = asset_dir / "audio.m4s"
        with requests.get(audio_url, headers=_headers(), stream=True, timeout=60) as audio_response:
            audio_response.raise_for_status()
            with audio_path.open("wb") as handle:
                for chunk in audio_response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)
        record["assets"]["audio"].append(str(audio_path))
        result = transcribe_audio(
            audio_path,
            asset_dir,
            language="zh",
            timeout_seconds=asr_timeout_seconds,
            engine=asr_engine,
            model=asr_model,
        )
        _apply_transcription_result(record, result, "音频转写")
        if result.get("text"):
            return True
    except Exception as exc:
        record["fetch_errors"].append(f"playurl_audio_download_failed:{exc}")
    return False


def collect_bilibili(
    record: dict,
    output_dir: Path,
    fetch_media: bool = True,
    asr_timeout_seconds: int = 900,
    asr_engine: str = "auto",
    asr_model: str = "base",
) -> dict:
    bvid = extract_bvid(record["url"])
    if not bvid:
        record["fetch_errors"].append("bvid_missing")
        return record

    record["resolved_url"] = f"https://www.bilibili.com/video/{bvid}/"
    record["content_type"] = "video"
    record["is_multi_speaker"] = True
    record["speaker_label_status"] = "unknown"

    try:
        response = requests.get(
            "https://api.bilibili.com/x/web-interface/view",
            params={"bvid": bvid},
            headers=_headers(),
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            record["fetch_errors"].append(f"metadata_api_error:{payload.get('message')}")
        data = payload.get("data", {})
        record["title"] = normalize_chinese_text(data.get("title", ""))
        record["author"] = normalize_chinese_text(data.get("owner", {}).get("name", ""))
        if data.get("pubdate"):
            record["published_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(data["pubdate"]))
        record["duration"] = data.get("duration")
        description, description_source, description_completeness = _metadata_description(data)
        record["platform_description"] = description
        record["description_source"] = description_source
        record["description_completeness"] = description_completeness
        if not description:
            record["notes"].append("description_missing")
        pages = data.get("pages") or []
        cid = pages[0].get("cid") if pages else data.get("cid")
        if cid:
            record["platform_ids"]["bvid"] = bvid
            record["platform_ids"]["cid"] = cid
            _load_subtitle(record, output_dir, int(cid))
            if not record.get("transcript_text"):
                _load_subtitle_with_bccdl(record, output_dir)
        else:
            record["fetch_errors"].append("cid_missing")
    except Exception as exc:
        record["fetch_errors"].append(f"metadata_fetch_failed:{exc}")

    if fetch_media and not record.get("transcript_text"):
        _download_and_transcribe(
            record,
            output_dir,
            asr_timeout_seconds=asr_timeout_seconds,
            asr_engine=asr_engine,
            asr_model=asr_model,
        )
    elif not fetch_media and not record.get("transcript_text"):
        record["notes"].append("media_fetch_disabled")

    record["text_completeness"] = evaluate_text_completeness(record)
    return normalize_record_text(record)


def looks_like_bilibili(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return "bilibili.com" in host or bool(extract_bvid(url))
