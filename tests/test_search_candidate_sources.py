import importlib.util

from pathlib import Path


def load_script(name: str):
    root = Path(__file__).resolve().parents[1]
    path = root / "odyssey-skill" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_itunes_episode_payload_is_normalized_to_candidate():
    search_candidate_sources = load_script("search_candidate_sources")
    payload = {
        "wrapperType": "podcastEpisode",
        "trackName": "从大厂裸辞，到海外创业",
        "collectionName": "澳洲创业访谈录",
        "artistName": "Odyssey Guest",
        "trackViewUrl": "https://podcasts.apple.com/cn/podcast/example/id1?i=100",
        "releaseDate": "2026-01-01T00:00:00Z",
        "description": "这一期聊产品经理裸辞、海外生活、创业现金流。",
    }

    candidate = search_candidate_sources.normalize_itunes_episode(payload, "裸辞 创业")

    assert candidate["title"] == "从大厂裸辞，到海外创业"
    assert candidate["person"] == "Odyssey Guest"
    assert candidate["platform"] == "Apple Podcasts"
    assert candidate["url"] == "https://podcasts.apple.com/cn/podcast/example/id1?i=100"
    assert candidate["source_type"] == "podcast"
    assert candidate["topic_tags"] == ["裸辞", "创业", "海外生活", "大厂", "产品"]
    assert candidate["text_availability"] == "需音频 ASR"
    assert "播客访谈" in candidate["fit_reason"]


def test_candidates_are_deduped_by_url():
    search_candidate_sources = load_script("search_candidate_sources")
    candidates = [
        {"url": "https://example.com/a/", "title": "A"},
        {"url": "https://example.com/a", "title": "A duplicate"},
        {"url": "https://example.com/b", "title": "B"},
    ]

    deduped = search_candidate_sources.dedupe_candidates(candidates)

    assert [item["title"] for item in deduped] == ["A", "B"]


def test_bilibili_search_html_is_normalized_to_candidates():
    search_candidate_sources = load_script("search_candidate_sources")
    html = """
    <a href="//www.bilibili.com/video/BV1abc12345Z">从大厂裸辞到自由职业</a>
    <a href="//www.bilibili.com/video/BV1abc12345Z">duplicate</a>
    <a href="//www.bilibili.com/video/BV1xyz98765Q">转行海外工作一年复盘</a>
    """

    candidates = search_candidate_sources.parse_bilibili_html(html, "裸辞 转行")

    assert len(candidates) == 2
    assert candidates[0]["platform"] == "Bilibili"
    assert candidates[0]["source_type"] == "bilibili"
    assert candidates[0]["url"] == "https://www.bilibili.com/video/BV1abc12345Z"
    assert "裸辞" in candidates[0]["topic_tags"]


def test_bilibili_view_payload_repairs_title_and_person():
    search_candidate_sources = load_script("search_candidate_sources")
    candidate = {
        "title": "4393010:05",
        "person": "",
        "platform": "Bilibili",
        "url": "https://www.bilibili.com/video/BV1abc12345Z",
        "source_type": "bilibili",
        "topic_tags": [],
        "decision_scene": "人生或职业关键选择",
        "fit_reason": "",
        "text_availability": "可获取字幕或需音频 ASR",
        "notes": "query=裸辞; bvid=BV1abc12345Z",
    }
    payload = {
        "code": 0,
        "data": {
            "title": "31岁裸辞，零经验转行亚马逊运营助理",
            "owner": {"name": "欧尼哇小小me"},
            "desc": "裸辞 转行 复盘",
        },
    }

    repaired = search_candidate_sources.apply_bilibili_view_payload(candidate, payload)

    assert repaired["title"] == "31岁裸辞，零经验转行亚马逊运营助理"
    assert repaired["person"] == "欧尼哇小小me"
    assert repaired["topic_tags"] == ["裸辞", "转行"]


def test_xiaohongshu_search_task_candidate_is_explicitly_manual():
    search_candidate_sources = load_script("search_candidate_sources")

    candidate = search_candidate_sources.xiaohongshu_search_candidate("裸辞 转行")

    assert candidate["platform"] == "Xiaohongshu"
    assert candidate["source_type"] == "xiaohongshu"
    assert candidate["title"] == "小红书人工复核：裸辞 转行"
    assert "xiaohongshu.com/search_result" in candidate["url"]
    assert candidate["text_availability"] == "需人工打开确认 / 需 OCR"


def test_apple_collection_ids_are_extracted_from_existing_sources():
    search_candidate_sources = load_script("search_candidate_sources")
    sources = [
        {"source_type": "podcast", "url": "https://podcasts.apple.com/au/podcast/foo/id1494812579?i=100"},
        {"source_type": "podcast", "url": "https://podcasts.apple.com/au/podcast/bar/id1494812579?i=101"},
        {"source_type": "bilibili", "url": "https://www.bilibili.com/video/BV1abc12345Z"},
    ]

    assert search_candidate_sources.apple_collection_ids_from_sources(sources) == ["1494812579"]


def test_rss_items_are_normalized_to_podcast_candidates():
    search_candidate_sources = load_script("search_candidate_sources")
    rss = """<?xml version="1.0"?>
    <rss><channel><title>知行小酒馆</title>
      <item>
        <title>从第一份工作到长期主义</title>
        <link>https://example.com/episode</link>
        <description>这一期聊毕业、工作、城市选择。</description>
      </item>
    </channel></rss>
    """

    candidates = search_candidate_sources.parse_podcast_rss(rss, "知行小酒馆")

    assert candidates[0]["title"] == "从第一份工作到长期主义"
    assert candidates[0]["platform"] == "Podcast RSS"
    assert candidates[0]["url"] == "https://example.com/episode"
    assert "第一份工作" in candidates[0]["topic_tags"]
    assert "城市选择" in candidates[0]["topic_tags"]


def test_balanced_select_round_robins_source_groups():
    search_candidate_sources = load_script("search_candidate_sources")
    candidates = [
        {"title": "A1", "source_show": "A", "url": "https://example.com/a1"},
        {"title": "A2", "source_show": "A", "url": "https://example.com/a2"},
        {"title": "B1", "source_show": "B", "url": "https://example.com/b1"},
        {"title": "B2", "source_show": "B", "url": "https://example.com/b2"},
    ]

    selected = search_candidate_sources.balanced_select(candidates, "source_show", 3)

    assert [item["title"] for item in selected] == ["A1", "B1", "A2"]


def test_podcast_candidates_from_existing_sources_cover_later_shows(monkeypatch, tmp_path):
    search_candidate_sources = load_script("search_candidate_sources")
    source_index = tmp_path / "source_index.json"
    source_index.write_text(
        """
        [
          {"source_type": "podcast", "url": "https://podcasts.apple.com/au/podcast/a/id111?i=1"},
          {"source_type": "podcast", "url": "https://podcasts.apple.com/au/podcast/b/id222?i=2"},
          {"source_type": "podcast", "url": "https://podcasts.apple.com/au/podcast/c/id333?i=3"}
        ]
        """,
        encoding="utf-8",
    )
    feeds = {
        "111": {"collectionName": "Show A", "feedUrl": "https://rss.example/a"},
        "222": {"collectionName": "Show B", "feedUrl": "https://rss.example/b"},
        "333": {"collectionName": "Show C", "feedUrl": "https://rss.example/c"},
    }

    monkeypatch.setattr(
        search_candidate_sources,
        "lookup_podcast_collection",
        lambda collection_id, country="AU": feeds[collection_id],
    )
    monkeypatch.setattr(search_candidate_sources, "fetch_text", lambda url: url)
    monkeypatch.setattr(
        search_candidate_sources,
        "parse_podcast_rss",
        lambda rss_text, show_name, limit=12: [
            {
                "title": f"{show_name} episode {index}",
                "person": show_name,
                "platform": "Podcast RSS",
                "source_show": show_name,
                "url": f"https://episode.example/{show_name}/{index}",
                "source_type": "podcast",
                "topic_tags": ["创业"],
                "decision_scene": "离开稳定工作后是否创业",
                "fit_reason": "",
                "text_availability": "需音频 ASR",
                "notes": f"source_show={show_name}",
            }
            for index in range(limit)
        ],
    )

    candidates = search_candidate_sources.search_podcast_candidates_from_existing_sources(
        source_index,
        target_count=5,
        per_show_limit=1,
    )

    assert {item["source_show"] for item in candidates} == {"Show A", "Show B", "Show C"}
