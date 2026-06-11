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


def test_normalize_selected_records_extracts_urls_and_assigns_case_ids():
    exporter = load_module("export_selected_lark_cases")
    raw = {
        "ok": True,
        "data": {
            "fields": ["标题", "人物/嘉宾", "平台", "URL", "来源类型", "主题标签", "可能决策场景", "原文可得性", "优先级", "备注"],
            "record_id_list": ["rec_a", "rec_b"],
            "has_more": False,
            "data": [
                [
                    "Episode A",
                    "Show A",
                    "Podcast RSS",
                    "[https://example.com/a?utm_source=rss](https://example.com/a?utm_source=rss)",
                    ["podcast"],
                    ["创业", "产品"],
                    "是否创业",
                    ["需音频 ASR"],
                    ["P2"],
                    "keep",
                ],
                [
                    "Video B",
                    "UP B",
                    "Bilibili",
                    "https://www.bilibili.com/video/BV123",
                    ["bilibili"],
                    ["转行"],
                    "是否转行",
                    ["可获取字幕或需音频 ASR"],
                    ["P1"],
                    "",
                ],
            ],
        },
    }

    records = exporter.normalize_selected_records(raw, start_case_number=21)

    assert records == [
        {
            "case_id": "case_21",
            "case_number": 21,
            "record_id": "rec_a",
            "title": "Episode A",
            "person_or_guest": "Show A",
            "platform": "Podcast RSS",
            "url": "https://example.com/a?utm_source=rss",
            "source_type": "podcast",
            "topic_tags": ["创业", "产品"],
            "possible_decision_scene": "是否创业",
            "text_availability": "需音频 ASR",
            "priority": "P2",
            "notes": "keep",
            "source_id": "case3:podcast_21",
            "slug": "Episode_A",
        },
        {
            "case_id": "case_22",
            "case_number": 22,
            "record_id": "rec_b",
            "title": "Video B",
            "person_or_guest": "UP B",
            "platform": "Bilibili",
            "url": "https://www.bilibili.com/video/BV123",
            "source_type": "bilibili",
            "topic_tags": ["转行"],
            "possible_decision_scene": "是否转行",
            "text_availability": "可获取字幕或需音频 ASR",
            "priority": "P1",
            "notes": "",
            "source_id": "case3:bilibili_22",
            "slug": "Video_B",
        },
    ]


def test_normalize_selected_records_rejects_missing_required_values():
    exporter = load_module("export_selected_lark_cases")
    raw = {
        "ok": True,
        "data": {
            "fields": ["标题", "人物/嘉宾", "平台", "URL", "来源类型", "主题标签", "可能决策场景", "原文可得性", "优先级", "备注"],
            "record_id_list": ["rec_a"],
            "has_more": False,
            "data": [["Episode A", "Show A", "Podcast RSS", "", ["podcast"], [], "", [], [], ""]],
        },
    }

    try:
        exporter.normalize_selected_records(raw, start_case_number=21)
    except ValueError as exc:
        assert "rec_a missing URL" in str(exc)
    else:
        raise AssertionError("expected missing URL to fail")


def test_write_outputs_preserves_raw_and_normalized_json(tmp_path):
    exporter = load_module("export_selected_lark_cases")
    raw = {
        "ok": True,
        "data": {
            "fields": ["标题", "人物/嘉宾", "平台", "URL", "来源类型", "主题标签", "可能决策场景", "原文可得性", "优先级", "备注"],
            "record_id_list": ["rec_a"],
            "has_more": False,
            "data": [["Episode A", "Show A", "Podcast RSS", "https://example.com/a", ["podcast"], [], "", [], [], ""]],
        },
    }

    report = exporter.write_outputs(raw, tmp_path / "selected.raw.json", tmp_path / "selected.json", start_case_number=21)

    assert report == {"record_count": 1, "unique_url_count": 1, "has_more": False}
    assert json.loads((tmp_path / "selected.raw.json").read_text(encoding="utf-8")) == raw
    normalized = json.loads((tmp_path / "selected.json").read_text(encoding="utf-8"))
    assert normalized[0]["case_id"] == "case_21"
