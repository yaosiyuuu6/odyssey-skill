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


CASE_MD = """# 案例 21：测试主人公｜测试身份

## 一、人物背景

| 维度 | 具体信息 |
| --- | --- |
| 姓名 | 测试主人公 |
| 身份标签 | 测试身份 |
| 城市 | 上海 |

## 二、核心决策场景拆解

### 场景 1：是否转行

> **一句话决策：** 从原行业转到新行业。
> **核心变量：** 收入、成长
> **主要代价：** 短期收入下降。

#### 1. 当时约束

- 存款有限
- 行业变化

#### 2. 备选项

| 选项 | 内容 |
| --- | --- |
| A | 留在原行业 |
| B | 转到新行业 |

#### 3. 最终选择

选择转到新行业。

#### 4. 行动路径

- 学习新技能
- 找到新岗位

#### 5. 结果

| 阶段 | 结果 |
| --- | --- |
| 短期 | 收入下降 |
| 长期 | 找到新方向 |

#### 6. 代价

短期收入下降。

#### 7. 关键变量

- 收入
- 成长

#### 8. 可参考人群

适合考虑转行的人。
"""


def test_generate_final_writes_to_requested_data_final(tmp_path):
    generator = load_script("generate_final_from_case3")
    case_dir = tmp_path / "data" / "case3.0"
    final_dir = tmp_path / "data" / "final"
    transcript_dir = tmp_path / "data" / "text_clean"
    case_dir.mkdir(parents=True)
    transcript_dir.mkdir(parents=True)
    (case_dir / "case_21_测试.md").write_text(CASE_MD, encoding="utf-8")
    (transcript_dir / "case_21_测试.txt").write_text("source text", encoding="utf-8")
    metadata = tmp_path / "existing_final.json"
    metadata.write_text(
        json.dumps(
            [
                {
                    "case_id": "case_21",
                    "source_links": ["https://example.com/source"],
                    "source_ids": ["case3:podcast_001"],
                    "story_id": "case3:story_001",
                    "source_text_paths": ["data/text_clean/case_21_测试.txt"],
                    "text_completeness": "完整",
                    "merge_basis": "单集",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = generator.generate(case_dir, final_dir, metadata_path=metadata, transcript_dir=transcript_dir)

    assert report["cases"] == 1
    assert (final_dir / "decision_storylines_v2.json").exists()
    assert (final_dir / "decision_storylines_v2.md").exists()
    assert (final_dir / "case_index.json").exists()
    data = json.loads((final_dir / "decision_storylines_v2.json").read_text(encoding="utf-8"))
    assert data[0]["source_links"] == ["https://example.com/source"]
    index = json.loads((final_dir / "case_index.json").read_text(encoding="utf-8"))
    assert index[0]["case_file"].endswith("case3.0/case_21_测试.md")
    assert index[0]["transcript_file"].endswith("text_clean/case_21_测试.txt")


def test_generate_final_preserves_metadata_cases_without_case_markdown(tmp_path):
    generator = load_script("generate_final_from_case3")
    case_dir = tmp_path / "data" / "case3.0"
    final_dir = tmp_path / "data" / "final"
    case_dir.mkdir(parents=True)
    (case_dir / "case_21_测试.md").write_text(CASE_MD, encoding="utf-8")
    metadata = tmp_path / "existing_final.json"
    old_case = {
        "case_id": "case_01",
        "case_title": "旧案例",
        "source_links": ["https://example.com/old"],
        "source_ids": ["main:old"],
        "story_id": "main:story_old",
        "source_text_paths": [],
        "text_completeness": "完整",
        "merge_basis": "旧数据",
        "protagonists": [],
    }
    metadata.write_text(
        json.dumps(
            [
                old_case,
                {
                    "case_id": "case_21",
                    "source_links": ["https://example.com/source"],
                    "source_ids": ["case3:podcast_021"],
                    "story_id": "story_podcast_021",
                    "source_text_paths": [],
                    "text_completeness": "完整",
                    "merge_basis": "单集",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = generator.generate(case_dir, final_dir, metadata_path=metadata)

    data = json.loads((final_dir / "decision_storylines_v2.json").read_text(encoding="utf-8"))
    assert report["cases"] == 2
    assert [case["case_id"] for case in data] == ["case_01", "case_21"]
    assert data[0] == old_case
    assert data[1]["source_links"] == ["https://example.com/source"]
