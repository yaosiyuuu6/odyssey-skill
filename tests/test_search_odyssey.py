import importlib.util
from pathlib import Path


def load_module(name: str):
    root = Path(__file__).resolve().parents[1]
    path = root / "odyssey-skill" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_search_prioritizes_podcast_and_decision_context():
    search_odyssey = load_module("search_odyssey")
    index = [
        {
            "case_id": "case_a",
            "case_title": "普通转岗",
            "protagonist_id": "p_a",
            "protagonist_name": "A",
            "node_id": "n_a",
            "decision_scene": "内部转岗",
            "cost": "压力下降",
            "result": {"短期": "稳定"},
            "source_links": ["https://example.com/article"],
            "is_podcast_recommendable": False,
            "searchable_text": "大厂 产品 转岗 稳定",
            "search_tags": ["大厂"],
            "match_dimensions": ["职业阶段相似"],
        },
        {
            "case_id": "case_b",
            "case_title": "大厂裸辞来澳洲",
            "protagonist_id": "p_b",
            "protagonist_name": "B",
            "node_id": "n_b",
            "decision_scene": "大厂裸辞",
            "cost": "放弃稳定收入",
            "result": {"短期": "收入不稳定"},
            "source_links": ["https://podcasts.apple.com/example"],
            "is_podcast_recommendable": True,
            "searchable_text": "大厂 产品经理 工作四年 裸辞 创业 播客",
            "search_tags": ["大厂", "裸辞", "创业"],
            "match_dimensions": ["决策场景相似", "风险代价相似"],
        },
    ]

    results = search_odyssey.search_index("大厂产品经理 工作四年 想裸辞 推荐播客", index, limit=2)

    assert [item["node_id"] for item in results] == ["n_b", "n_a"]
    assert results[0]["match_score"] > results[1]["match_score"]
    assert "决策场景相似" in results[0]["matched_dimensions"]


def test_render_recommendations_uses_story_style_without_trace_ids():
    search_odyssey = load_module("search_odyssey")
    results = [
        {
            "case_title": "大厂裸辞来澳洲",
            "protagonist_name": "Zoe",
            "decision_scene": "大厂裸辞",
            "final_choice": "离开大厂去澳洲探索",
            "cost": "放弃稳定收入",
            "result": {"短期": "收入不稳定"},
            "source_links": ["https://podcasts.apple.com/example"],
            "matched_terms": ["大厂", "裸辞"],
            "matched_dimensions": ["决策场景相似"],
            "case_id": "case_01",
            "protagonist_id": "case_01_p01",
            "node_id": "case_01_p01_d01",
        }
    ]

    rendered = search_odyssey.render_recommendations(
        "大厂产品经理想裸辞，有什么播客吗？", results
    )

    assert "无法真正感同身受" in rendered
    assert "相似的人生片段" in rendered
    assert "Zoe" in rendered
    assert "对方当时面对的是大厂裸辞" in rendered
    assert "后来对方选择了离开大厂去澳洲探索" in rendered
    assert "这个选择的代价是放弃稳定收入" in rendered
    assert "https://podcasts.apple.com/example" in rendered
    assert "。，" not in rendered
    assert "。。" not in rendered
    assert "case_01" not in rendered
    assert "case_01_p01" not in rendered
    assert "case_01_p01_d01" not in rendered


def test_render_database_unavailable_does_not_invent_results():
    search_odyssey = load_module("search_odyssey")

    rendered = search_odyssey.render_database_unavailable()

    assert "我这里暂时连不上奥德赛案例库" in rendered
    assert "不会临时编造案例" in rendered
    assert "ODYSSEY_SKILL_REMOTE_BASE_URL" not in rendered
