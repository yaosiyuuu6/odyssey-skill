import importlib.util
from pathlib import Path


def load_module(name: str):
    root = Path(__file__).resolve().parents[1]
    path = root / "odyssey-skill" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_cases():
    return [
        {
            "case_id": "case_01",
            "case_title": "大厂裸辞来澳洲",
            "source_links": ["https://podcasts.apple.com/example"],
            "source_ids": ["main:podcast_001"],
            "story_id": "main:story_001",
            "source_text_paths": [],
            "text_completeness": "完整",
            "merge_basis": "单集播客",
            "protagonists": [
                {
                    "protagonist_id": "case_01_p01",
                    "name": "Zoe",
                    "identity": "大厂产品经理，后来在澳洲创业",
                    "profile": {"行业": "互联网产品", "城市": "北京、悉尼"},
                    "decision_nodes": [
                        {
                            "node_id": "case_01_p01_d01",
                            "timeline_order": 1,
                            "decision_scene": "从大厂裸辞，准备海外生活和创业",
                            "stage_at_decision": "工作多年后职业倦怠",
                            "age_at_decision": "原文未提及",
                            "location_at_decision": "北京、澳洲",
                            "当时约束": ["收入下降风险", "海外生活不确定性"],
                            "备选项": {"A": "继续留在大厂", "B": "裸辞去澳洲"},
                            "最终选择": "选择 B，离开大厂去澳洲探索。",
                            "行动路径": ["辞职", "迁移到澳洲", "尝试创业"],
                            "结果": {"短期": "收入不稳定", "长期": "开始新业务"},
                            "代价": "放弃稳定收入和平台资源。",
                            "关键变量": ["储蓄", "海外适应", "产品能力迁移"],
                            "可参考人群": "考虑裸辞、海外生活或转型创业的大厂从业者。",
                            "evidence_quotes": [],
                            "confidence": "medium",
                        }
                    ],
                }
            ],
        }
    ]


def test_build_indexes_creates_node_and_source_indexes():
    build_indexes = load_module("build_indexes")

    result = build_indexes.build_indexes(
        sample_cases(),
        database_version="2026-06-09.1",
        updated_at="2026-06-09T00:00:00Z",
    )

    search_index = result["odyssey_search_index"]
    source_index = result["source_index"]
    manifest = result["manifest"]

    assert len(search_index) == 1
    record = search_index[0]
    assert record["case_id"] == "case_01"
    assert record["protagonist_id"] == "case_01_p01"
    assert record["node_id"] == "case_01_p01_d01"
    assert record["is_podcast_recommendable"] is True
    assert "裸辞" in record["search_tags"]
    assert "大厂" in record["search_tags"]
    assert "决策场景相似" in record["match_dimensions"]
    assert "大厂产品经理" in record["searchable_text"]

    assert len(source_index) == 1
    assert source_index[0]["source_id"] == "main:podcast_001"
    assert source_index[0]["is_podcast"] is True
    assert source_index[0]["is_recommendable_for_skill"] is True

    assert manifest["database_version"] == "2026-06-09.1"
    assert manifest["files"]["odyssey_search_index"]["record_count"] == 1
    assert manifest["files"]["source_index"]["record_count"] == 1


def test_tag_inference_ignores_field_names_and_unknown_values():
    build_indexes = load_module("build_indexes")
    cases = [
        {
            "case_id": "case_01",
            "case_title": "缺少个人背景信息的选择",
            "source_links": ["https://example.com/article"],
            "source_ids": ["main:article_001"],
            "protagonists": [
                {
                    "protagonist_id": "case_01_p01",
                    "name": "A",
                    "identity": "内容创作者",
                    "profile": {
                        "城市": "原文未提及",
                        "家庭资源": "原文未提及",
                        "行业": "内容创作",
                    },
                    "decision_nodes": [
                        {
                            "node_id": "case_01_p01_d01",
                            "decision_scene": "要不要继续做内容项目",
                            "当时约束": ["原文未提及"],
                            "备选项": {"A": "继续", "B": "暂停"},
                            "最终选择": "继续尝试。",
                            "行动路径": ["复盘选题"],
                            "结果": {"短期": "原文未提及"},
                            "代价": "原文未提及",
                            "关键变量": [],
                            "可参考人群": "内容创作者。",
                        }
                    ],
                }
            ],
        }
    ]

    result = build_indexes.build_indexes(cases)

    record = result["odyssey_search_index"][0]
    assert "城市选择" not in record["search_tags"]
    assert "家庭约束" not in record["search_tags"]
    assert "原文未提及" not in record["searchable_text"]


def test_tag_inference_keeps_explicit_rich_tags_from_values():
    build_indexes = load_module("build_indexes")
    result = build_indexes.build_indexes(sample_cases())

    tags = result["odyssey_search_index"][0]["search_tags"]

    assert "裸辞" in tags
    assert "大厂" in tags
    assert "海外生活" in tags
    assert "城市选择" in tags
