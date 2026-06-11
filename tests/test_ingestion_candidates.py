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


def test_candidate_rows_are_deduped_and_mark_existing_sources():
    ingestion_candidates = load_script("ingestion_candidates")
    existing_sources = [{"url": "https://example.com/existing"}]
    candidates = [
        {
            "title": "大厂产品经理裸辞后创业",
            "person": "Zoe",
            "platform": "Apple Podcasts",
            "url": "https://example.com/existing",
            "source_type": "podcast",
            "topic_tags": ["裸辞", "创业"],
            "decision_scene": "从大厂离职后是否创业",
            "fit_reason": "包含明确的离职、现金流和创业路径。",
            "text_availability": "需 ASR",
        },
        {
            "title": "大厂产品经理裸辞后创业 duplicate",
            "person": "Zoe",
            "platform": "Apple Podcasts",
            "url": "https://example.com/existing",
            "source_type": "podcast",
        },
        {
            "title": "从国企到海外读书",
            "person": "王红颜",
            "platform": "Bilibili",
            "url": "https://example.com/new",
            "source_type": "bilibili",
            "topic_tags": "留学, 海外工作",
        },
    ]

    rows = ingestion_candidates.build_review_rows(candidates, existing_sources)

    assert len(rows) == 2
    assert rows[0]["标题"] == "大厂产品经理裸辞后创业"
    assert rows[0]["主题标签"] == ["裸辞", "创业"]
    assert rows[0]["去重状态"] == "已在 Odyssey"
    assert rows[0]["审阅状态"] == "待审阅"
    assert rows[0]["优先级"] == "P2"
    assert rows[1]["主题标签"] == ["留学", "海外工作"]
    assert rows[1]["去重状态"] == "新候选"


def test_candidate_rows_mark_existing_by_bvid_and_title_alias():
    ingestion_candidates = load_script("ingestion_candidates")
    existing_sources = [
        {
            "title": "大厂裸辞来澳洲",
            "url": "https://podcasts.apple.com/au/podcast/澳洲创业访谈录/id1879743524?i=1000768250686",
        },
        {
            "title": "本科同学深漂八年",
            "url": "https://www.bilibili.com/video/BV1fFkTB9EYu?vd_source=abc",
        },
    ]
    candidates = [
        {
            "title": "从大厂裸辞来澳洲，我们后悔了吗？| 番外篇1",
            "person": "澳洲创业访谈录",
            "platform": "Podcast RSS",
            "url": "https://www.xiaoyuzhoufm.com/episode/6a09b28ae1eb34a939908852",
            "source_type": "podcast",
        },
        {
            "title": "本科同学深漂八年后：“没什么逃避的，也没什么面对的”",
            "person": "就叫老张好了",
            "platform": "Bilibili",
            "url": "https://www.bilibili.com/video/BV1fFkTB9EYu",
            "source_type": "bilibili",
        },
    ]

    rows = ingestion_candidates.build_review_rows(candidates, existing_sources)

    assert rows[0]["去重状态"] == "已在 Odyssey"
    assert "existing_title=大厂裸辞来澳洲" in rows[0]["备注"]
    assert rows[1]["去重状态"] == "已在 Odyssey"
    assert "existing_bvid=BV1fFkTB9EYu" in rows[1]["备注"]


def test_candidate_rows_mark_existing_by_title_token_overlap():
    ingestion_candidates = load_script("ingestion_candidates")
    existing_sources = [
        {"title": "微软阿里创业", "url": "https://podcasts.apple.com/example"},
        {"title": "Olga工作", "url": "https://podcasts.apple.com/olga"},
    ]
    candidates = [
        {
            "title": "微软、阿里光环褪去，在澳洲做AI创业，如何逆风翻盘？| 对话Vincent",
            "platform": "Podcast RSS",
            "url": "https://www.xiaoyuzhoufm.com/episode/a",
            "source_type": "podcast",
        },
        {
            "title": "E79｜对话Olga姐姐：为了让自己更“值钱”，我无所不用其极",
            "platform": "Podcast RSS",
            "url": "https://www.xiaoyuzhoufm.com/episode/b",
            "source_type": "podcast",
        },
    ]

    rows = ingestion_candidates.build_review_rows(candidates, existing_sources)

    assert rows[0]["去重状态"] == "已在 Odyssey"
    assert "existing_title_tokens=微软阿里创业" in rows[0]["备注"]
    assert rows[1]["去重状态"] == "已在 Odyssey"
    assert "existing_title_token=Olga工作" in rows[1]["备注"]


def test_candidate_rows_mark_existing_by_short_distinctive_chinese_title():
    ingestion_candidates = load_script("ingestion_candidates")
    existing_sources = [
        {"title": "葱花", "url": "https://podcasts.apple.com/example"},
    ]
    candidates = [
        {
            "title": "E228 对话葱花：别让命运替你写下答案｜小酒馆故事会",
            "platform": "Podcast RSS",
            "url": "https://www.xiaoyuzhoufm.com/episode/c",
            "source_type": "podcast",
        },
    ]

    rows = ingestion_candidates.build_review_rows(candidates, existing_sources)

    assert rows[0]["去重状态"] == "已在 Odyssey"
    assert "existing_title=葱花" in rows[0]["备注"]


def test_lark_records_jsonl_uses_review_field_names(tmp_path):
    ingestion_candidates = load_script("ingestion_candidates")
    candidates_path = tmp_path / "candidates.json"
    sources_path = tmp_path / "source_index.json"
    output_path = tmp_path / "records.jsonl"
    candidates_path.write_text(
        json.dumps(
            [
                {
                    "title": "从咨询转到 AI 产品",
                    "person": "Alex",
                    "platform": "Apple Podcasts",
                    "url": "https://example.com/ai-pm",
                    "source_type": "podcast",
                    "topic_tags": ["转行", "AI"],
                    "decision_scene": "是否离开咨询进入 AI 产品",
                    "fit_reason": "有清晰职业路径选择。",
                    "text_availability": "可获取音频",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    sources_path.write_text("[]", encoding="utf-8")

    count = ingestion_candidates.write_lark_records_jsonl(candidates_path, sources_path, output_path)

    assert count == 1
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert rows == [
        {
            "标题": "从咨询转到 AI 产品",
            "人物/嘉宾": "Alex",
            "平台": "Apple Podcasts",
            "URL": "https://example.com/ai-pm",
            "来源类型": "podcast",
            "主题标签": ["转行", "AI"],
            "可能决策场景": "是否离开咨询进入 AI 产品",
            "适合原因": "有清晰职业路径选择。",
            "原文可得性": "可获取音频",
            "去重状态": "新候选",
            "审阅状态": "待审阅",
            "优先级": "P2",
            "备注": "",
        }
    ]
