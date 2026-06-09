#!/usr/bin/env python3
"""Fetch Odyssey cloud indexes from GitHub Raw with local cache fallback."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from typing import Callable


DEFAULT_REMOTE_BASE_URL = os.environ.get(
    "ODYSSEY_SKILL_REMOTE_BASE_URL",
    "https://raw.githubusercontent.com/yaosiyuuu6/odyssey-skill/main",
)
DEFAULT_CACHE_DIR = Path(os.environ.get("ODYSSEY_SKILL_CACHE_DIR", "~/.cache/odyssey-skill")).expanduser()
DEFAULT_TTL_SECONDS = int(os.environ.get("ODYSSEY_SKILL_CACHE_TTL_SECONDS", "86400"))
CACHE_WARNING = "远程数据库暂时不可用，当前使用本地缓存数据。"


def fetch_url_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=20) as response:
        return response.read().decode("utf-8")


def normalize_base_url(remote_base_url: str) -> str:
    return remote_base_url.rstrip("/")


def remote_url(remote_base_url: str, path: str) -> str:
    return f"{normalize_base_url(remote_base_url)}/{path.lstrip('/')}"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def touch_cache_files(cache_dir: Path, timestamp: float) -> None:
    for filename in ["manifest.json", "odyssey_search_index.json", "source_index.json"]:
        os.utime(cache_dir / filename, (timestamp, timestamp))


def cache_files_exist(cache_dir: Path) -> bool:
    return all(
        (cache_dir / filename).exists()
        for filename in ["manifest.json", "odyssey_search_index.json", "source_index.json"]
    )


def cache_is_fresh(cache_dir: Path, ttl_seconds: int, now: float) -> bool:
    if not cache_files_exist(cache_dir):
        return False
    newest_required = now - ttl_seconds
    mtimes = [
        (cache_dir / name).stat().st_mtime
        for name in ["manifest.json", "odyssey_search_index.json", "source_index.json"]
    ]
    if any(mtime > now for mtime in mtimes):
        return False
    return min(mtimes) >= newest_required


def sha256_json(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_manifest_hashes(manifest, search_index, source_index) -> None:
    expected_search = manifest["files"]["odyssey_search_index"]["sha256"]
    expected_source = manifest["files"]["source_index"]["sha256"]
    if expected_search != sha256_json(search_index):
        raise ValueError("odyssey_search_index sha256 mismatch")
    if expected_source != sha256_json(source_index):
        raise ValueError("source_index sha256 mismatch")


def read_cache(cache_dir: Path, cache_status: str, warning: str | None = None):
    return SimpleNamespace(
        manifest=load_json(cache_dir / "manifest.json"),
        search_index=load_json(cache_dir / "odyssey_search_index.json"),
        source_index=load_json(cache_dir / "source_index.json"),
        cache_status=cache_status,
        warning=warning,
    )


def get_indexes(
    remote_base_url: str = DEFAULT_REMOTE_BASE_URL,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    now: float | None = None,
    fetch_text: Callable[[str], str] = fetch_url_text,
    verify_sha: bool = True,
):
    cache_dir = Path(cache_dir).expanduser()
    now = time.time() if now is None else now
    if cache_is_fresh(cache_dir, ttl_seconds, now):
        return read_cache(cache_dir, "fresh-cache")

    try:
        manifest = json.loads(fetch_text(remote_url(remote_base_url, "data/manifest.json")))
        search_path = manifest["files"]["odyssey_search_index"]["path"]
        source_path = manifest["files"]["source_index"]["path"]
        search_index = json.loads(fetch_text(remote_url(remote_base_url, search_path)))
        source_index = json.loads(fetch_text(remote_url(remote_base_url, source_path)))
        if verify_sha:
            verify_manifest_hashes(manifest, search_index, source_index)
        cache_dir.mkdir(parents=True, exist_ok=True)
        write_json(cache_dir / "manifest.json", manifest)
        write_json(cache_dir / "odyssey_search_index.json", search_index)
        write_json(cache_dir / "source_index.json", source_index)
        touch_cache_files(cache_dir, now)
        return SimpleNamespace(
            manifest=manifest,
            search_index=search_index,
            source_index=source_index,
            cache_status="refreshed",
            warning=None,
        )
    except Exception:
        if cache_files_exist(cache_dir):
            return read_cache(cache_dir, "stale-cache", CACHE_WARNING)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Odyssey Skill indexes.")
    parser.add_argument("--remote-base-url", default=DEFAULT_REMOTE_BASE_URL)
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--ttl-seconds", type=int, default=DEFAULT_TTL_SECONDS)
    args = parser.parse_args()
    result = get_indexes(args.remote_base_url, args.cache_dir, args.ttl_seconds)
    if result.warning:
        print(result.warning)
    print(json.dumps({"cache_status": result.cache_status, "database_version": result.manifest.get("database_version")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
