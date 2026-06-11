import importlib.util
import json
import subprocess
import sys
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


def test_select_candidate_results_fetches_thirty_and_recommends_three_by_default():
    search_odyssey = load_module("search_odyssey")
    index = []
    for idx in range(35):
        index.append(
            {
                "case_id": f"case_{idx}",
                "case_title": f"案例 {idx}",
                "protagonist_id": f"p_{idx}",
                "protagonist_name": f"主人公 {idx}",
                "node_id": f"n_{idx}",
                "decision_scene": "大厂裸辞",
                "cost": "放弃稳定收入",
                "result": {"短期": "继续探索"},
                "source_links": ["https://podcasts.apple.com/example"],
                "is_podcast_recommendable": True,
                "searchable_text": "大厂 产品经理 裸辞 播客 " + ("创业 " * idx),
                "search_tags": ["大厂", "裸辞"],
                "match_dimensions": ["决策场景相似", "风险代价相似"],
            }
        )

    selection = search_odyssey.select_candidate_results(
        "大厂产品经理想裸辞，有什么播客吗？",
        index,
    )

    assert len(selection["candidates"]) == 30
    assert len(selection["recommended_results"]) == 3
    assert selection["candidate_limit"] == 30
    assert selection["default_display_limit"] == 3
    assert selection["recommended_results"] == selection["candidates"][:3]


def test_search_diversifies_cases_before_returning_second_node_from_same_case():
    search_odyssey = load_module("search_odyssey")
    index = []
    for idx in range(4):
        index.append(
            {
                "case_id": "case_long",
                "case_title": "长案例",
                "protagonist_id": "p_long",
                "protagonist_name": "长案例主人公",
                "node_id": f"long_{idx}",
                "decision_scene": "大厂裸辞",
                "cost": "放弃稳定收入",
                "result": {"短期": "继续探索"},
                "source_links": ["https://podcasts.apple.com/example"],
                "is_podcast_recommendable": True,
                "searchable_text": "大厂 裸辞",
                "search_tags": ["大厂", "裸辞"],
                "match_dimensions": ["决策场景相似"],
            }
        )
    for case_id in ["case_b", "case_c"]:
        index.append(
            {
                "case_id": case_id,
                "case_title": "短案例",
                "protagonist_id": f"p_{case_id}",
                "protagonist_name": "短案例主人公",
                "node_id": f"{case_id}_node",
                "decision_scene": "大厂裸辞",
                "cost": "放弃稳定收入",
                "result": {"短期": "继续探索"},
                "source_links": ["https://podcasts.apple.com/example"],
                "is_podcast_recommendable": True,
                "searchable_text": "大厂 裸辞",
                "search_tags": ["大厂", "裸辞"],
                "match_dimensions": ["决策场景相似"],
            }
        )

    results = search_odyssey.search_index("大厂裸辞", index, limit=5)

    assert len({item["case_id"] for item in results[:3]}) == 3
    assert [item["case_id"] for item in results].count("case_long") == 3


def test_stable_tie_breaker_does_not_keep_input_order_for_equal_scores():
    search_odyssey = load_module("search_odyssey")
    index = [
        {
            "case_id": f"case_{idx}",
            "case_title": f"案例 {idx}",
            "protagonist_id": f"p_{idx}",
            "protagonist_name": f"主人公 {idx}",
            "node_id": f"n_{idx}",
            "decision_scene": "大厂裸辞",
            "cost": "放弃稳定收入",
            "result": {"短期": "继续探索"},
            "source_links": ["https://podcasts.apple.com/example"],
            "is_podcast_recommendable": True,
            "searchable_text": "大厂 裸辞",
            "search_tags": ["大厂", "裸辞"],
            "match_dimensions": ["决策场景相似"],
        }
        for idx in range(10)
    ]

    results = search_odyssey.search_index("大厂裸辞", index, limit=10)

    assert [item["node_id"] for item in results] != [item["node_id"] for item in index]


def test_json_results_include_ranking_evidence_and_hints():
    search_odyssey = load_module("search_odyssey")
    index = [
        {
            "case_id": "case_a",
            "case_title": "大厂裸辞来澳洲",
            "protagonist_id": "p_a",
            "protagonist_name": "A",
            "node_id": "n_a",
            "decision_scene": "大厂裸辞",
            "cost": "放弃稳定收入",
            "result": {"短期": "收入不稳定"},
            "source_links": ["https://podcasts.apple.com/example"],
            "is_podcast_recommendable": True,
            "searchable_text": "大厂 产品经理 裸辞",
            "search_tags": ["大厂", "裸辞"],
            "match_dimensions": ["决策场景相似", "风险代价相似"],
            "ranking_evidence": {"decision_scene": "大厂裸辞", "cost": "放弃稳定收入"},
        }
    ]

    results = search_odyssey.search_index("大厂裸辞", index, limit=1)

    assert results[0]["ranking_evidence"]["decision_scene"] == "大厂裸辞"
    assert results[0]["rank_hints"]["case_diversity"] == "first_node_for_case"


def test_cli_json_returns_thirty_candidates_from_cache(tmp_path):
    root = Path(__file__).resolve().parents[1]
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    search_index = []
    for idx in range(35):
        search_index.append(
            {
                "case_id": f"case_{idx}",
                "case_title": f"案例 {idx}",
                "protagonist_id": f"p_{idx}",
                "protagonist_name": f"主人公 {idx}",
                "node_id": f"n_{idx}",
                "decision_scene": "大厂裸辞",
                "cost": "放弃稳定收入",
                "result": {"短期": "继续探索"},
                "source_links": ["https://podcasts.apple.com/example"],
                "is_podcast_recommendable": True,
                "searchable_text": "大厂 产品经理 裸辞 播客",
                "search_tags": ["大厂", "裸辞"],
                "match_dimensions": ["决策场景相似", "风险代价相似"],
            }
        )
    manifest = {
        "files": {
            "odyssey_search_index": {"sha256": "unused"},
            "source_index": {"sha256": "unused"},
        }
    }
    (cache_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (cache_dir / "odyssey_search_index.json").write_text(json.dumps(search_index), encoding="utf-8")
    (cache_dir / "source_index.json").write_text("[]", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(root / "odyssey-skill" / "scripts" / "search_odyssey.py"),
            "大厂产品经理想裸辞",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
        env={"ODYSSEY_SKILL_CACHE_DIR": str(cache_dir)},
    )

    results = json.loads(completed.stdout)
    assert len(results) == 30
