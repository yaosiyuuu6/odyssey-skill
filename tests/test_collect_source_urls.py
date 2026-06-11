import importlib.util
import json
from pathlib import Path


def load_script(name: str):
    root = Path(__file__).resolve().parents[1]
    path = root / "odyssey-skill" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_writes_working_outputs_and_uses_separate_asset_root(tmp_path, monkeypatch):
    collect = load_script("collect_source_urls")
    input_path = tmp_path / "selected_urls.md"
    input_path.write_text("https://www.bilibili.com/video/BV1abc123456/", encoding="utf-8")
    working_dir = tmp_path / "data" / "working" / "2026-06-10"
    asset_root = tmp_path / "data" / "assets" / "2026-06-10"
    seen = {}

    def fake_collect_source(record, output_dir, **_kwargs):
        seen["output_dir"] = output_dir
        record["title"] = "测试标题"
        record["text_completeness"] = "完整"
        record["transcript_text"] = "完整转写"
        record["merged_text"] = "完整转写"
        record["assets"]["transcripts"].append(str(output_dir / "assets" / record["id"] / "transcript.txt"))
        return record

    monkeypatch.setattr(collect, "collect_source", fake_collect_source)

    sources, stories = collect.run(input_path, working_dir, asset_dir=asset_root, fetch_media=False)

    assert seen["output_dir"] == asset_root
    assert (working_dir / "sources.json").exists()
    assert (working_dir / "stories.json").exists()
    assert (working_dir / "report.md").exists()
    assert (working_dir / "methods.md").exists()
    assert not (working_dir / "assets").exists()
    assert sources[0]["assets"]["transcripts"][0].startswith(str(asset_root))
    assert stories[0]["source_ids"] == ["bilibili_001"]


def test_parse_samples_recognizes_current_podcast_hosts(tmp_path):
    collect = load_script("collect_source_urls")
    input_path = tmp_path / "selected_urls.md"
    input_path.write_text(
        "\n".join(
            [
                "https://www.xiaoyuzhoufm.com/episode/67ed0567f9578163d6929b77?utm_source=rss",
                "https://open.firstory.me/story/cmpm9l6a5010x01p528xs67ck",
                "https://guiguzaozhidao.fireside.fm/20240424",
                "https://www.bilibili.com/video/BV1abc123456/",
            ]
        ),
        encoding="utf-8",
    )

    samples = collect.parse_samples(input_path)

    assert [sample["platform"] for sample in samples] == ["podcast", "podcast", "podcast", "bilibili"]
    assert [sample["id"] for sample in samples] == ["podcast_001", "podcast_002", "podcast_003", "bilibili_001"]


def test_run_seeds_records_from_selected_cases_json(tmp_path, monkeypatch):
    collect = load_script("collect_source_urls")
    selected_path = tmp_path / "selected_cases.json"
    selected_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "case_21",
                    "record_id": "rec_a",
                    "title": "Episode A",
                    "person_or_guest": "Show A",
                    "platform": "Podcast RSS",
                    "url": "https://www.xiaoyuzhoufm.com/episode/67ed0567f9578163d6929b77?utm_source=rss",
                    "source_type": "podcast",
                    "topic_tags": ["创业"],
                    "possible_decision_scene": "是否创业",
                    "text_availability": "需音频 ASR",
                    "priority": "P2",
                    "notes": "source_show=Show A",
                    "source_id": "case3:podcast_21",
                    "slug": "Episode_A",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    working_dir = tmp_path / "working"
    asset_root = tmp_path / "assets"
    seen = {}

    def fake_collect_source(record, output_dir, **_kwargs):
        seen["record"] = record.copy()
        record["platform_description"] = "简介"
        record["description_source"] = "test"
        record["description_completeness"] = "完整"
        record["text_completeness"] = "完整"
        record["transcript_text"] = "完整转写"
        record["merged_text"] = "完整转写"
        return record

    monkeypatch.setattr(collect, "collect_source", fake_collect_source)

    sources, stories = collect.run(selected_path, working_dir, asset_dir=asset_root, fetch_media=False)

    assert seen["record"]["id"] == "podcast_021"
    assert seen["record"]["case_id"] == "case_21"
    assert seen["record"]["record_id"] == "rec_a"
    assert seen["record"]["seed_title"] == "Episode A"
    assert seen["record"]["seed_person_or_guest"] == "Show A"
    assert seen["record"]["topic_tags"] == ["创业"]
    assert sources[0]["platform_description"] == "简介"
    assert stories[0]["case_id"] == "case_21"
    assert stories[0]["source_ids"] == ["podcast_021"]


def test_run_checkpoints_each_completed_source(tmp_path, monkeypatch):
    collect = load_script("collect_source_urls")
    input_path = tmp_path / "selected_urls.md"
    input_path.write_text(
        "\n".join(
            [
                "https://www.bilibili.com/video/BV1abc123456/",
                "https://www.bilibili.com/video/BV2abc123456/",
            ]
        ),
        encoding="utf-8",
    )
    working_dir = tmp_path / "working"
    calls = []

    def fake_collect_source(record, output_dir, **_kwargs):
        calls.append(record["id"])
        if record["id"] == "bilibili_002":
            raise RuntimeError("boom")
        record["title"] = "第一条"
        record["text_completeness"] = "完整"
        record["transcript_text"] = "第一条转写"
        record["merged_text"] = "第一条转写"
        return record

    monkeypatch.setattr(collect, "collect_source", fake_collect_source)

    try:
        collect.run(input_path, working_dir, fetch_media=False)
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("expected second source to fail")

    saved_sources = json.loads((working_dir / "sources.json").read_text(encoding="utf-8"))
    saved_stories = json.loads((working_dir / "stories.json").read_text(encoding="utf-8"))
    assert calls == ["bilibili_001", "bilibili_002"]
    assert [source["id"] for source in saved_sources] == ["bilibili_001"]
    assert saved_stories[0]["merged_text"] == "第一条转写"
    assert (working_dir / "report.md").exists()


def test_run_reuses_transcript_file_from_asset_root(tmp_path, monkeypatch):
    collect = load_script("collect_source_urls")
    input_path = tmp_path / "selected_urls.md"
    input_path.write_text("https://www.bilibili.com/video/BV1abc123456/", encoding="utf-8")
    working_dir = tmp_path / "working"
    asset_root = tmp_path / "assets"
    transcript_dir = asset_root / "assets" / "bilibili_001"
    transcript_dir.mkdir(parents=True)
    transcript_path = transcript_dir / "audio.faster_whisper.transcript.txt"
    transcript_path.write_text("已有转写", encoding="utf-8")
    seen = {}

    def fake_collect_source(record, output_dir, **_kwargs):
        seen["record"] = record.copy()
        record["title"] = "测试标题"
        record["text_completeness"] = "完整"
        return record

    monkeypatch.setattr(collect, "collect_source", fake_collect_source)

    sources, stories = collect.run(input_path, working_dir, asset_dir=asset_root, fetch_media=True)

    assert seen["record"]["transcript_text"] == "已有转写"
    assert seen["record"]["merged_text"] == "已有转写"
    assert str(transcript_path) in seen["record"]["assets"]["transcripts"]
    assert sources[0]["merged_text"] == "已有转写"
    assert stories[0]["merged_text"] == "已有转写"
