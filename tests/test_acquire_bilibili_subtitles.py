import importlib.util
from pathlib import Path


def load_module(name: str):
    root = Path(__file__).resolve().parents[1]
    path = root / "odyssey-skill" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_bvid_from_bilibili_url():
    acquire = load_module("acquire_bilibili_subtitles")

    assert acquire.extract_bvid("https://www.bilibili.com/video/BV1inE46EExQ?p=1") == "BV1inE46EExQ"


def test_subtitle_json_to_text_joins_non_empty_content():
    acquire = load_module("acquire_bilibili_subtitles")
    subtitle_json = {
        "body": [
            {"from": 0, "to": 1, "content": "第一句"},
            {"from": 1, "to": 2, "content": ""},
            {"from": 2, "to": 3, "content": "第二句"},
        ]
    }

    assert acquire.subtitle_json_to_text(subtitle_json) == "第一句\n第二句\n"


def test_pick_subtitle_prefers_lan_doc_zh_then_first():
    acquire = load_module("acquire_bilibili_subtitles")
    subtitles = [
        {"lan": "ai-en", "subtitle_url": "//example.com/en.json"},
        {"lan": "zh-CN", "subtitle_url": "//example.com/zh.json"},
    ]

    assert acquire.pick_subtitle(subtitles)["subtitle_url"] == "//example.com/zh.json"
    assert acquire.pick_subtitle([subtitles[0]])["subtitle_url"] == "//example.com/en.json"
    assert acquire.pick_subtitle([]) is None
