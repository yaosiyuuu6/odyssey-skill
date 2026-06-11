import importlib.util
import sys
from pathlib import Path


def load_platform(name: str):
    root = Path(__file__).resolve().parents[1]
    skill_root = root / "odyssey-skill"
    if str(skill_root) not in sys.path:
        sys.path.insert(0, str(skill_root))
    path = root / "odyssey-skill" / "scripts" / "platforms" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, text="", json_data=None, content=None):
        self.text = text
        self._json_data = json_data
        self.content = content if content is not None else text.encode("utf-8")

    def raise_for_status(self):
        return None

    def json(self):
        return self._json_data


def test_discover_generic_episode_from_page_rss_and_item_enclosure(monkeypatch):
    podcast = load_platform("podcast")
    page_url = "https://guiguzaozhidao.fireside.fm/20240424"
    rss_url = "https://guiguzaozhidao.fireside.fm/rss"
    calls = []

    def fake_get(url, **_kwargs):
        calls.append(url)
        if url == page_url:
            return FakeResponse(
                """
                <html><head>
                <link rel="alternate" type="application/rss+xml" href="https://guiguzaozhidao.fireside.fm/rss">
                <meta property="og:title" content="页面标题">
                <meta property="og:description" content="页面简介">
                </head></html>
                """
            )
        if url == rss_url:
            return FakeResponse(
                """
                <rss><channel><item>
                <title>RSS 标题</title>
                <link>https://guiguzaozhidao.fireside.fm/20240424</link>
                <description><![CDATA[RSS 简介]]></description>
                <pubDate>Wed, 24 Apr 2026 00:00:00 GMT</pubDate>
                <itunes:duration xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">01:02:03</itunes:duration>
                <enclosure url="https://cdn.example.com/audio.mp3" type="audio/mpeg" />
                </item></channel></rss>
                """
            )
        raise AssertionError(url)

    monkeypatch.setattr(podcast.requests, "get", fake_get)

    metadata = podcast.discover_generic_episode(page_url)

    assert calls == [page_url, rss_url]
    assert metadata["title"] == "RSS 标题"
    assert metadata["description"] == "RSS 简介"
    assert metadata["description_source"] == "rss_description"
    assert metadata["audio_url"] == "https://cdn.example.com/audio.mp3"
    assert metadata["published_at"] == "Wed, 24 Apr 2026 00:00:00 GMT"
    assert metadata["duration"] == "01:02:03"


def test_collect_podcast_preserves_seed_metadata_when_fetch_fails(monkeypatch, tmp_path):
    podcast = load_platform("podcast")
    record = {
        "id": "podcast_021",
        "url": "https://www.xiaoyuzhoufm.com/episode/missing",
        "seed_title": "Seed Title",
        "seed_person_or_guest": "Seed Show",
        "platform_ids": {},
        "assets": {"audio": [], "remote_audio": [], "subtitles": [], "screenshots": [], "images": [], "remote_images": [], "transcripts": []},
        "fetch_errors": [],
        "notes": [],
        "correction_log": [],
    }

    monkeypatch.setattr(podcast, "discover_generic_episode", lambda _url: {})

    result = podcast.collect_podcast(record, tmp_path, fetch_media=False)

    assert result["title"] == "Seed Title"
    assert result["author"] == "Seed Show"
    assert result["description_completeness"] == "缺失"
    assert "audio_url_missing" in result["fetch_errors"]


def test_discover_generic_episode_extracts_inline_audio_url(monkeypatch):
    podcast = load_platform("podcast")

    def fake_get(url, **_kwargs):
        assert url == "https://open.firstory.me/story/abc"
        return FakeResponse(
            '<meta property="og:title" content="Title">'
            '<meta property="og:description" content="Description">'
            '"https://d3mww1g1pfq2pt.cloudfront.net/Record/user/audio.mp3?v=123\\u0026x=1"'
        )

    monkeypatch.setattr(podcast.requests, "get", fake_get)

    metadata = podcast.discover_generic_episode("https://open.firstory.me/story/abc")

    assert metadata["audio_url"] == "https://d3mww1g1pfq2pt.cloudfront.net/Record/user/audio.mp3?v=123&x=1"


def test_collect_podcast_skips_asr_when_transcript_already_exists(monkeypatch, tmp_path):
    podcast = load_platform("podcast")
    record = {
        "id": "podcast_021",
        "url": "https://open.firstory.me/story/abc",
        "title": "Seed Title",
        "author": "Seed Show",
        "transcript_text": "已有转写",
        "merged_text": "已有转写",
        "platform_ids": {},
        "assets": {"audio": [], "remote_audio": [], "subtitles": [], "screenshots": [], "images": [], "remote_images": [], "transcripts": []},
        "fetch_errors": [],
        "notes": [],
        "correction_log": [],
    }

    monkeypatch.setattr(
        podcast,
        "discover_generic_episode",
        lambda _url: {
            "description": "简介",
            "description_source": "page_meta",
            "description_completeness": "部分",
            "audio_url": "https://example.com/audio.mp3",
        },
    )
    monkeypatch.setattr(
        podcast,
        "_download_audio",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("download should be skipped")),
    )
    monkeypatch.setattr(
        podcast,
        "transcribe_audio",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("asr should be skipped")),
    )

    result = podcast.collect_podcast(record, tmp_path, fetch_media=True)

    assert result["merged_text"] == "已有转写"
    assert result["platform_description"] == "简介"
    assert result["assets"]["remote_audio"] == ["https://example.com/audio.mp3"]
    assert result["assets"]["audio"] == []
    assert result["fetch_errors"] == []
