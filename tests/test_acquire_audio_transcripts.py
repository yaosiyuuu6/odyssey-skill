import importlib.util
from pathlib import Path


def load_module(name: str):
    root = Path(__file__).resolve().parents[1]
    path = root / "odyssey-skill" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_media_and_text_paths_use_case_id_and_slug(tmp_path):
    acquire = load_module("acquire_audio_transcripts")
    record = {"case_id": "case_21", "slug": "Some_Title"}

    paths = acquire.paths_for_record(record, tmp_path)

    assert paths["media"] == tmp_path / "media" / "case_21_Some_Title.m4a"
    assert paths["raw_text"] == tmp_path / "text" / "case_21_Some_Title.txt"
    assert paths["clean_text"] == tmp_path / "text_clean" / "case_21_Some_Title.txt"
    assert paths["metadata"] == tmp_path / "acquisition" / "case_21_Some_Title.audio.json"


def test_format_segments_preserves_timestamps_and_text():
    acquire = load_module("acquire_audio_transcripts")
    segments = [
        {"start": 0.0, "end": 1.25, "text": " 第一段 "},
        {"start": 1.25, "end": 3.0, "text": ""},
        {"start": 3.0, "end": 4.0, "text": "第二段"},
    ]

    assert acquire.format_segments(segments) == "[00:00:00.000 --> 00:00:01.250] 第一段\n[00:00:03.000 --> 00:00:04.000] 第二段\n"


def test_should_process_filters_source_types_and_existing_outputs(tmp_path):
    acquire = load_module("acquire_audio_transcripts")
    podcast = {"source_type": "podcast", "case_id": "case_21", "slug": "A"}
    article = {"source_type": "article", "case_id": "case_22", "slug": "B"}

    assert acquire.should_process(podcast, {"podcast"}, tmp_path, reuse_existing=True) is True
    assert acquire.should_process(article, {"podcast"}, tmp_path, reuse_existing=True) is False

    paths = acquire.paths_for_record(podcast, tmp_path)
    paths["clean_text"].parent.mkdir(parents=True)
    paths["clean_text"].write_text("done", encoding="utf-8")

    assert acquire.should_process(podcast, {"podcast"}, tmp_path, reuse_existing=True) is False
    assert acquire.should_process(podcast, {"podcast"}, tmp_path, reuse_existing=False) is True
