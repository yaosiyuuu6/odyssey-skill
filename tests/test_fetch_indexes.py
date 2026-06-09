import importlib.util
import json
from pathlib import Path


def load_module(name: str):
    root = Path(__file__).resolve().parents[1]
    path = root / "odyssey-skill" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_get_indexes_fetches_remote_then_reuses_fresh_cache(tmp_path):
    fetch_indexes = load_module("fetch_indexes")
    calls = []
    remote_files = {
        "https://example.test/data/manifest.json": json.dumps(
            {
                "database_version": "v1",
                "updated_at": "2026-06-09T00:00:00Z",
                "files": {
                    "odyssey_search_index": {
                        "path": "data/odyssey_search_index.json",
                        "sha256": "skip",
                        "record_count": 1,
                    },
                    "source_index": {
                        "path": "data/source_index.json",
                        "sha256": "skip",
                        "record_count": 1,
                    },
                },
            }
        ),
        "https://example.test/data/odyssey_search_index.json": json.dumps(
            [{"node_id": "n1", "searchable_text": "裸辞"}]
        ),
        "https://example.test/data/source_index.json": json.dumps(
            [{"source_id": "s1", "url": "https://podcasts.apple.com/example"}]
        ),
    }

    def fetch_text(url):
        calls.append(url)
        return remote_files[url]

    first = fetch_indexes.get_indexes(
        remote_base_url="https://example.test",
        cache_dir=tmp_path,
        ttl_seconds=86400,
        now=1_000_000,
        fetch_text=fetch_text,
        verify_sha=False,
    )
    second = fetch_indexes.get_indexes(
        remote_base_url="https://example.test",
        cache_dir=tmp_path,
        ttl_seconds=86400,
        now=1_000_100,
        fetch_text=fetch_text,
        verify_sha=False,
    )

    assert first.cache_status == "refreshed"
    assert second.cache_status == "fresh-cache"
    assert first.search_index[0]["node_id"] == "n1"
    assert second.source_index[0]["source_id"] == "s1"
    assert calls == [
        "https://example.test/data/manifest.json",
        "https://example.test/data/odyssey_search_index.json",
        "https://example.test/data/source_index.json",
    ]


def test_get_indexes_falls_back_to_stale_cache_when_remote_fails(tmp_path):
    fetch_indexes = load_module("fetch_indexes")
    (tmp_path / "manifest.json").write_text(
        json.dumps({"database_version": "cached"}), encoding="utf-8"
    )
    (tmp_path / "odyssey_search_index.json").write_text(
        json.dumps([{"node_id": "cached-node"}]), encoding="utf-8"
    )
    (tmp_path / "source_index.json").write_text(
        json.dumps([{"source_id": "cached-source"}]), encoding="utf-8"
    )

    def fetch_text(url):
        raise OSError("network down")

    result = fetch_indexes.get_indexes(
        remote_base_url="https://example.test",
        cache_dir=tmp_path,
        ttl_seconds=1,
        now=2_000_000,
        fetch_text=fetch_text,
        verify_sha=False,
    )

    assert result.cache_status == "stale-cache"
    assert result.warning == "远程数据库暂时不可用，当前使用本地缓存数据。"
    assert result.search_index[0]["node_id"] == "cached-node"
