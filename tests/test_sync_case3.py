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


def test_sync_case3_copies_final_json_and_reports_counts(tmp_path):
    sync_case3 = load_script("sync_case3_from_odysseymap")
    odyssey_map = tmp_path / "OdysseyMap"
    final_dir = odyssey_map / "data" / "final"
    final_dir.mkdir(parents=True)
    source = [
        {
            "case_id": "case_21",
            "case_title": "测试案例",
            "source_links": ["https://example.com/new"],
            "source_ids": ["case3:podcast_001"],
            "story_id": "case3:story_001",
            "source_text_paths": ["data/text_clean/case_21.txt"],
            "text_completeness": "完整",
            "merge_basis": "case3.0",
            "protagonists": [
                {
                    "protagonist_id": "case_21_p01",
                    "name": "测试主人公",
                    "identity": "测试身份",
                    "profile": {},
                    "decision_nodes": [
                        {
                            "node_id": "case_21_p01_d01",
                            "timeline_order": 1,
                            "decision_scene": "是否转行",
                        }
                    ],
                }
            ],
        }
    ]
    (final_dir / "decision_storylines_v2.json").write_text(json.dumps(source), encoding="utf-8")
    skill_data = tmp_path / "skill" / "data"

    report = sync_case3.sync_final_json(odyssey_map, skill_data)

    copied = json.loads((skill_data / "decision_storylines_v2.json").read_text(encoding="utf-8"))
    assert copied == source
    assert report == {
        "source": str(final_dir / "decision_storylines_v2.json"),
        "target": str(skill_data / "decision_storylines_v2.json"),
        "cases": 1,
        "protagonists": 1,
        "decision_nodes": 1,
    }
