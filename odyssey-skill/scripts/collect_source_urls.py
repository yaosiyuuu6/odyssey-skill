from __future__ import annotations

import argparse
from datetime import date
import html
import json
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts.completeness import evaluate_text_completeness
from scripts.report import write_json, write_methods, write_report
from scripts.text_normalize import normalize_chinese_text, normalize_record_text


URL_RE = re.compile(
    r"(?:(?:https?://)?(?:www\.)?"
    r"(?:bilibili\.com|xhslink\.com|xiaohongshu\.com|podcasts\.apple\.com|xiaoyuzhoufm\.com|open\.firstory\.me|[\w.-]+\.fireside\.fm)"
    r"[^\s<>)]+)"
)


def normalize_url(raw_url: str) -> str:
    url = html.unescape(raw_url).replace("\\", "")
    url = url.rstrip(".,，。)")
    if url.startswith("bilibili.com") or url.startswith("www.bilibili.com"):
        url = "https://" + url
    if url.startswith("xhslink.com") or url.startswith("www.xhslink.com"):
        url = "http://" + url
    if url.startswith("xiaohongshu.com") or url.startswith("www.xiaohongshu.com"):
        url = "https://" + url
    if url.startswith("xiaoyuzhoufm.com") or url.startswith("www.xiaoyuzhoufm.com"):
        url = "https://" + url
    if url.startswith("open.firstory.me"):
        url = "https://" + url
    if re.match(r"^[\w.-]+\.fireside\.fm", url):
        url = "https://" + url
    return url


def platform_for_url(url: str) -> str:
    lowered = url.lower()
    if "bilibili.com" in lowered:
        return "bilibili"
    if "xhslink.com" in lowered or "xiaohongshu.com" in lowered:
        return "xiaohongshu"
    if any(host in lowered for host in ("podcasts.apple.com", "xiaoyuzhoufm.com", "open.firstory.me", "fireside.fm")):
        return "podcast"
    return "unknown"


def _sample_id(platform: str, index: int, case_id: str | None = None) -> str:
    if case_id:
        match = re.match(r"case_(\d+)", case_id)
        if match:
            return f"{platform}_{int(match.group(1)):03d}"
    return f"{platform}_{index:03d}"


def _sample_from_selected_case(record: dict, index: int) -> dict:
    url = normalize_url(str(record.get("url") or ""))
    platform = str(record.get("source_type") or "").strip() or platform_for_url(url)
    return {
        "id": _sample_id(platform, index, record.get("case_id")),
        "platform": platform,
        "url": url,
        "selected_case": record,
    }


def parse_selected_cases(json_path: Path) -> list[dict]:
    records = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("selected cases input must be a JSON list")
    return [_sample_from_selected_case(record, idx) for idx, record in enumerate(records, start=1)]


def parse_samples(markdown_path: Path) -> list[dict]:
    if markdown_path.suffix == ".json":
        return parse_selected_cases(markdown_path)
    text = html.unescape(markdown_path.read_text(encoding="utf-8").replace("\\", ""))
    matches = [normalize_url(match.group(0)) for match in URL_RE.finditer(text)]
    samples: list[dict] = []
    counters = {"bilibili": 0, "xiaohongshu": 0, "podcast": 0, "unknown": 0}
    for url in matches:
        platform = platform_for_url(url)
        counters[platform] += 1
        samples.append(
            {
                "id": f"{platform}_{counters[platform]:03d}",
                "platform": platform,
                "url": url,
            }
        )
    return samples


def default_source_record(sample: dict) -> dict:
    selected = sample.get("selected_case") or {}
    record = {
        "id": sample["id"],
        "platform": sample["platform"],
        "url": sample["url"],
        "resolved_url": sample.get("resolved_url", ""),
        "title": "",
        "author": "",
        "platform_description": "",
        "description_source": "",
        "description_completeness": "缺失",
        "published_at": "",
        "duration": None,
        "language": "zh",
        "content_type": "",
        "is_multi_speaker": False,
        "speaker_label_status": "unknown",
        "speaker_segments": [],
        "speaker_count": 0,
        "speaker_role_map": {},
        "correction_log": [],
        "text_source": "",
        "text_completeness": "缺失",
        "body_text": "",
        "ocr_text": "",
        "transcript_text": "",
        "merged_text": "",
        "platform_ids": {},
        "assets": {
            "audio": [],
            "remote_audio": [],
            "subtitles": [],
            "screenshots": [],
            "images": [],
            "remote_images": [],
            "transcripts": [],
        },
        "fetch_errors": [],
        "notes": [],
    }
    if selected:
        record.update(
            {
                "case_id": selected.get("case_id", ""),
                "case_number": selected.get("case_number"),
                "record_id": selected.get("record_id", ""),
                "source_id": selected.get("source_id", ""),
                "slug": selected.get("slug", ""),
                "seed_title": selected.get("title", ""),
                "seed_person_or_guest": selected.get("person_or_guest", ""),
                "seed_platform": selected.get("platform", ""),
                "topic_tags": selected.get("topic_tags", []),
                "possible_decision_scene": selected.get("possible_decision_scene", ""),
                "text_availability": selected.get("text_availability", ""),
                "priority": selected.get("priority", ""),
                "base_notes": selected.get("notes", ""),
            }
        )
        if selected.get("notes"):
            record["notes"].append(f"base_notes:{selected['notes']}")
    return record


def collect_source(
    record: dict,
    output_dir: Path,
    fetch_media: bool = True,
    asr_timeout_seconds: int = 900,
    asr_engine: str = "auto",
    asr_model: str = "base",
) -> dict:
    if record["platform"] == "bilibili":
        from scripts.platforms.bilibili import collect_bilibili

        return collect_bilibili(
            record,
            output_dir,
            fetch_media=fetch_media,
            asr_timeout_seconds=asr_timeout_seconds,
            asr_engine=asr_engine,
            asr_model=asr_model,
        )
    if record["platform"] == "xiaohongshu":
        from scripts.platforms.xiaohongshu import collect_xiaohongshu

        return collect_xiaohongshu(record, output_dir, fetch_media=fetch_media)
    if record["platform"] == "podcast":
        from scripts.platforms.podcast import collect_podcast

        return collect_podcast(
            record,
            output_dir,
            fetch_media=fetch_media,
            asr_timeout_seconds=asr_timeout_seconds,
            asr_engine=asr_engine,
            asr_model=asr_model,
        )
    record["fetch_errors"].append("unsupported_platform")
    record["text_completeness"] = evaluate_text_completeness(record)
    return normalize_record_text(record)


def hydrate_existing_assets(record: dict, collection_dir: Path) -> None:
    asset_dir = collection_dir / "assets" / record["id"]
    if not asset_dir.exists():
        return
    transcript_files = sorted(asset_dir.glob("*.transcript.txt"))
    if transcript_files and not record.get("transcript_text"):
        transcript = normalize_chinese_text(transcript_files[-1].read_text(encoding="utf-8"))
        if transcript:
            record["transcript_text"] = transcript
            record["merged_text"] = transcript
            record["text_source"] = "已有音频转写"
            for path in transcript_files:
                value = str(path)
                if value not in record["assets"]["transcripts"]:
                    record["assets"]["transcripts"].append(value)
    audio_files = sorted(
        path
        for path in asset_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".mp3", ".m4a", ".m4s", ".wav", ".aac", ".ogg", ".opus"}
    )
    for path in audio_files:
        value = str(path)
        if value not in record["assets"]["audio"]:
            record["assets"]["audio"].append(value)
    if record.get("merged_text"):
        record["text_completeness"] = evaluate_text_completeness(record)


def build_stories(sources: list[dict]) -> list[dict]:
    stories: list[dict] = []
    consumed: set[str] = set()
    source_by_id = {source["id"]: source for source in sources}
    combined_ids = ["bilibili_002", "bilibili_003"]
    combined_bvids = {
        source.get("platform_ids", {}).get("bvid") or re.search(r"(BV[0-9A-Za-z]+)", source.get("url", "") or "").group(1)
        if re.search(r"(BV[0-9A-Za-z]+)", source.get("url", "") or "")
        else ""
        for source in (source_by_id.get(source_id, {}) for source_id in combined_ids)
    }
    should_combine = combined_bvids == {"BV1ygXLBjEpy", "BV1NQXSBjEse"}
    if all(source_id in source_by_id for source_id in combined_ids) and should_combine:
        parts = [source_by_id[source_id] for source_id in combined_ids]
        stories.append(
            {
                "story_id": "story_bilibili_002_003",
                "source_ids": combined_ids,
                "is_combined_episode": True,
                "combined_title": "B站上下集",
                "merged_text": "\n\n".join(
                    part.get("merged_text") or part.get("transcript_text") or ""
                    for part in parts
                    if part.get("merged_text") or part.get("transcript_text")
                ),
                "text_completeness": "完整"
                if all(part.get("text_completeness") == "完整" for part in parts)
                else "部分",
            }
        )
        consumed.update(combined_ids)

    for source in sources:
        if source["id"] in consumed:
            continue
        stories.append(
            {
                "story_id": f"story_{source['id']}",
                "source_ids": [source["id"]],
                "case_id": source.get("case_id", ""),
                "record_id": source.get("record_id", ""),
                "is_combined_episode": False,
                "combined_title": source.get("title") or source["url"],
                "merged_text": source.get("merged_text") or source.get("transcript_text") or source.get("body_text") or "",
                "text_completeness": source.get("text_completeness") or "缺失",
            }
        )
    return stories


def write_checkpoint(output_dir: Path, sources: list[dict]) -> list[dict]:
    stories = build_stories(sources)
    write_json(output_dir / "sources.json", sources)
    write_json(output_dir / "stories.json", stories)
    write_report(output_dir / "report.md", sources, stories)
    write_methods(output_dir / "methods.md")
    return stories


def run(
    input_path: Path,
    output_dir: Path,
    asset_dir: Path | None = None,
    fetch_media: bool = True,
    asr_timeout_seconds: int = 900,
    asr_engine: str = "auto",
    asr_model: str = "base",
    reuse_existing_text: bool = False,
    reuse_existing_media: bool = False,
) -> tuple[list[dict], list[dict]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    collection_dir = asset_dir or output_dir
    collection_dir.mkdir(parents=True, exist_ok=True)
    existing_sources = {}
    existing_path = output_dir / "sources.json"
    if (reuse_existing_text or reuse_existing_media) and existing_path.exists():
        import json

        existing_sources = {
            source["id"]: source
            for source in json.loads(existing_path.read_text(encoding="utf-8"))
        }
    samples = parse_samples(input_path)
    sources = []
    for sample in samples:
        print(f"collecting {sample['id']} {sample['platform']} {sample['url']}", flush=True)
        record = default_source_record(sample)
        hydrate_existing_assets(record, collection_dir)
        old = existing_sources.get(record["id"], {})
        if reuse_existing_media and old.get("assets"):
            for key in ("audio", "remote_audio", "subtitles", "screenshots", "images", "remote_images", "transcripts"):
                old_values = (old.get("assets") or {}).get(key) or []
                if old_values:
                    record["assets"][key] = old_values
        source = collect_source(
            record,
            collection_dir,
            fetch_media=fetch_media,
            asr_timeout_seconds=asr_timeout_seconds,
            asr_engine=asr_engine,
            asr_model=asr_model,
        )
        old = existing_sources.get(source["id"], {})
        if old:
            for key in (
                "body_text",
                "ocr_text",
                "transcript_text",
                "merged_text",
                "text_source",
                "speaker_segments",
                "speaker_count",
                "speaker_role_map",
                "speaker_label_status",
                "correction_log",
            ):
                if old.get(key):
                    source[key] = old[key]
            for key in ("audio", "remote_audio", "subtitles", "screenshots", "images", "remote_images", "transcripts"):
                old_values = (old.get("assets") or {}).get(key) or []
                if old_values:
                    source["assets"][key] = old_values
            source["notes"] = [
                note
                for note in source.get("notes", [])
                if note != "media_fetch_disabled"
            ]
            source["text_completeness"] = evaluate_text_completeness(source)
        print(
            f"finished {source['id']} completeness={source.get('text_completeness')} errors={len(source.get('fetch_errors', []))}",
            flush=True,
        )
        sources.append(source)
        write_checkpoint(output_dir, sources)
    stories = write_checkpoint(output_dir, sources)
    return sources, stories


def repo_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def main() -> int:
    today = date.today().isoformat()
    parser = argparse.ArgumentParser(description="Collect Odyssey source content from URL Markdown.")
    parser.add_argument(
        "--input",
        default=f"data/intake/{today}/selected_urls.md",
        help="Input Markdown file. Relative paths resolve from the odyssey-skill repo root.",
    )
    parser.add_argument(
        "--output",
        default=f"data/working/{today}",
        help="Directory for sources.json, stories.json, report.md, and methods.md.",
    )
    parser.add_argument(
        "--asset-root",
        default=f"data/assets/{today}",
        help="Directory for downloaded subtitles/audio/images/transcripts.",
    )
    parser.add_argument(
        "--no-fetch-media",
        action="store_true",
        help="Skip audio/video downloads and ASR. Metadata/subtitle/public page fetch still runs.",
    )
    parser.add_argument(
        "--asr-timeout-seconds",
        type=int,
        default=900,
        help="Maximum seconds to spend transcribing one audio file.",
    )
    parser.add_argument(
        "--asr-engine",
        choices=["auto", "mlx", "faster-whisper", "whisperx"],
        default="auto",
        help="ASR engine. auto tries MLX first, then faster-whisper.",
    )
    parser.add_argument(
        "--asr-model",
        default="base",
        help="Whisper model for faster-whisper fallback. Use small/medium for higher quality.",
    )
    parser.add_argument(
        "--reuse-existing-text",
        action="store_true",
        help="Reuse existing text/transcript/OCR fields from output sources.json while refreshing metadata.",
    )
    parser.add_argument(
        "--reuse-existing-media",
        action="store_true",
        help="Reuse existing downloaded audio when available before attempting media downloads.",
    )
    args = parser.parse_args()
    sources, stories = run(
        repo_path(args.input),
        repo_path(args.output),
        asset_dir=repo_path(args.asset_root),
        fetch_media=not args.no_fetch_media,
        asr_timeout_seconds=args.asr_timeout_seconds,
        asr_engine=args.asr_engine,
        asr_model=args.asr_model,
        reuse_existing_text=args.reuse_existing_text,
        reuse_existing_media=args.reuse_existing_media,
    )
    complete = sum(1 for source in sources if source.get("text_completeness") == "完整")
    print(f"wrote {len(sources)} sources, {len(stories)} stories, {complete} complete sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
