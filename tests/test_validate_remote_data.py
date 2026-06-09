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


def test_validate_data_accepts_traceable_indexes():
    validate_remote_data = load_module("validate_remote_data")
    cases = [
        {
            "case_id": "case_01",
            "source_links": ["https://podcasts.apple.com/example"],
            "source_ids": ["main:podcast_001"],
            "protagonists": [
                {
                    "protagonist_id": "case_01_p01",
                    "decision_nodes": [{"node_id": "case_01_p01_d01"}],
                }
            ],
        }
    ]
    search_index = [
        {
            "case_id": "case_01",
            "protagonist_id": "case_01_p01",
            "node_id": "case_01_p01_d01",
            "source_links": ["https://podcasts.apple.com/example"],
            "is_podcast_recommendable": True,
            "searchable_text": "大厂 裸辞 播客",
        }
    ]
    source_index = [
        {
            "source_id": "main:podcast_001",
            "case_id": "case_01",
            "url": "https://podcasts.apple.com/example",
            "is_podcast": True,
            "is_recommendable_for_skill": True,
        }
    ]
    manifest = {
        "files": {
            "odyssey_search_index": {"record_count": 1, "sha256": "skip"},
            "source_index": {"record_count": 1, "sha256": "skip"},
        }
    }

    errors = validate_remote_data.validate_data(
        manifest, search_index, source_index, cases, verify_sha=False
    )

    assert errors == []


def test_validate_data_rejects_untraceable_search_record():
    validate_remote_data = load_module("validate_remote_data")

    errors = validate_remote_data.validate_data(
        manifest={
            "files": {
                "odyssey_search_index": {"record_count": 1, "sha256": "skip"},
                "source_index": {"record_count": 0, "sha256": "skip"},
            }
        },
        search_index=[
            {
                "case_id": "missing",
                "protagonist_id": "missing_p",
                "node_id": "missing_n",
                "source_links": [],
                "is_podcast_recommendable": True,
                "searchable_text": "",
            }
        ],
        source_index=[],
        cases=[],
        verify_sha=False,
    )

    assert "search record missing_n does not trace back to source data" in errors
    assert "search record missing_n has empty searchable_text" in errors
    assert "podcast recommendable record missing_n has no source link" in errors
