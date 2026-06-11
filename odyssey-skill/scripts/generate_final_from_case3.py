#!/usr/bin/env python3
"""Generate data/final files from data/case3.0 Markdown cases."""

from __future__ import annotations

import json
import re
import argparse
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CASE3_DIR = ROOT / "data" / "case3.0"
FINAL_DIR = ROOT / "data" / "final"
OLD_FINAL_JSON = FINAL_DIR / "decision_storylines_v2.json"
OUT_JSON = FINAL_DIR / "decision_storylines_v2.json"
OUT_MD = FINAL_DIR / "decision_storylines_v2.md"
OUT_INDEX = FINAL_DIR / "case_index.json"
TRANSCRIPT_DIR = ROOT / "data" / "text_clean"
UNKNOWN = "原文未提及"


def repo_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return ROOT / path


def configure_paths(case_dir: Path, out_dir: Path, metadata_path: Path | None = None, transcript_dir: Path | None = None) -> None:
    global CASE3_DIR, FINAL_DIR, OLD_FINAL_JSON, OUT_JSON, OUT_MD, OUT_INDEX, TRANSCRIPT_DIR

    CASE3_DIR = case_dir
    FINAL_DIR = out_dir
    OLD_FINAL_JSON = metadata_path or (FINAL_DIR / "decision_storylines_v2.json")
    OUT_JSON = FINAL_DIR / "decision_storylines_v2.json"
    OUT_MD = FINAL_DIR / "decision_storylines_v2.md"
    OUT_INDEX = FINAL_DIR / "case_index.json"
    TRANSCRIPT_DIR = transcript_dir or (ROOT / "data" / "text_clean")


def warn(warnings: list[str], case_id: str, message: str) -> None:
    warnings.append(f"{case_id}: {message}")


def clean_text(value: str | None) -> str:
    if value is None:
        return UNKNOWN
    text = value.strip()
    text = re.sub(r"\s+", " ", text)
    return text or UNKNOWN


def strip_markdown(value: str) -> str:
    text = value.strip()
    text = re.sub(r"^\s*>\s?", "", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    return clean_text(text)


def load_old_metadata() -> dict[str, dict]:
    if not OLD_FINAL_JSON.exists():
        return {}
    data = json.loads(OLD_FINAL_JSON.read_text(encoding="utf-8"))
    metadata = {}
    for item in data:
        case_id = item.get("case_id")
        if not case_id:
            continue
        metadata[case_id] = {
            "source_links": item.get("source_links", []),
            "source_ids": item.get("source_ids", []),
            "story_id": item.get("story_id", f"case2:{case_id}"),
            "source_text_paths": item.get("source_text_paths", []),
            "text_completeness": item.get("text_completeness", UNKNOWN),
            "merge_basis": item.get("merge_basis", UNKNOWN),
        }
    return metadata


def load_old_cases() -> dict[str, dict]:
    if not OLD_FINAL_JSON.exists():
        return {}
    data = json.loads(OLD_FINAL_JSON.read_text(encoding="utf-8"))
    return {item["case_id"]: item for item in data if item.get("case_id") and item.get("protagonists") is not None}


def parse_table(lines: list[str], start: int) -> tuple[list[dict[str, str]], int]:
    table_lines = []
    i = start
    while i < len(lines) and lines[i].lstrip().startswith("|"):
        table_lines.append(lines[i].strip())
        i += 1
    if len(table_lines) < 2:
        return [], i

    rows = []
    headers = [cell.strip() for cell in table_lines[0].strip("|").split("|")]
    for raw in table_lines[2:]:
        cells = [cell.strip() for cell in raw.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows, i


def first_table_after_heading(text: str, heading: str) -> list[dict[str, str]]:
    pattern = re.compile(rf"^#+\s+{re.escape(heading)}\s*$", re.M)
    match = pattern.search(text)
    if not match:
        return []
    lines = text[match.end() :].splitlines()
    for idx, line in enumerate(lines):
        if line.lstrip().startswith("|"):
            rows, _ = parse_table(lines, idx)
            return rows
        if line.startswith("## ") or line.startswith("### "):
            break
    return []


def parse_profile_from_rows(rows: list[dict[str, str]]) -> dict[str, str]:
    profile = {}
    for row in rows:
        key = row.get("维度") or row.get("收入阶段") or row.get("字段") or row.get("项目")
        value = row.get("具体信息") or row.get("内容") or row.get("信息")
        if key:
            profile[clean_text(key)] = clean_text(value)
    return profile


def parse_income_table(text: str, start_pos: int = 0) -> dict[str, str]:
    income_text = text[start_pos:]
    rows = first_table_after_heading(income_text, "收入阶段")
    if not rows:
        return {}
    parts = []
    for row in rows:
        stage = clean_text(row.get("收入阶段"))
        info = clean_text(row.get("具体信息"))
        if stage != UNKNOWN or info != UNKNOWN:
            parts.append(f"{stage}：{info}")
    return {"收入阶段": "；".join(parts) if parts else UNKNOWN}


def parse_case_header(path: Path, text: str) -> tuple[str, str, str, str]:
    case_match = re.match(r"case_(\d+)_", path.name)
    if not case_match:
        raise ValueError(f"Cannot parse case id from {path.name}")
    case_id = f"case_{case_match.group(1)}"
    file_title = path.stem.split("_", 2)[2].replace("_", " ")

    first_heading = next((line for line in text.splitlines() if line.startswith("# ")), "")
    heading = first_heading.removeprefix("# ").strip()
    name = file_title
    identity = UNKNOWN
    title_match = re.match(r"案例\s*\d+：(.+?)(?:｜(.+))?$", heading)
    if title_match:
        left = clean_text(title_match.group(1))
        identity = clean_text(title_match.group(2))
        name = left
        if "｜" in left:
            name, left_identity = left.split("｜", 1)
            identity = clean_text(left_identity)
    return case_id, file_title, clean_text(name), identity


def find_heading_blocks(text: str, pattern: str) -> list[tuple[re.Match, str]]:
    matches = list(re.finditer(pattern, text, re.M))
    blocks = []
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        blocks.append((match, text[match.end() : end]))
    return blocks


def parse_people(text: str, default_name: str, default_identity: str, case_id: str, warnings: list[str]) -> list[dict]:
    body_start = text.find("## 二、核心决策场景拆解")
    profile_text = text if body_start == -1 else text[:body_start]
    person_blocks = find_heading_blocks(profile_text, r"^### 人物\s*(\d+)：(.+)$")
    if not person_blocks:
        rows = first_table_after_heading(profile_text, "一、人物背景")
        profile = parse_profile_from_rows(rows)
        profile.update(parse_income_table(profile_text))
        return [
            {
                "label": default_name,
                "name": profile.get("名称") or profile.get("姓名") or default_name,
                "identity": profile.get("身份标签") or default_identity,
                "profile": profile,
                "scene_start": 0,
                "scene_end": len(text),
            }
        ]

    people = []
    for idx, (match, block) in enumerate(person_blocks):
        next_start = person_blocks[idx + 1][0].start() if idx + 1 < len(person_blocks) else len(profile_text)
        if next_start == -1:
            next_start = len(profile_text)
        profile_region = profile_text[match.end() : next_start]
        rows = []
        lines = profile_region.splitlines()
        for line_idx, line in enumerate(lines):
            if line.lstrip().startswith("|"):
                rows, _ = parse_table(lines, line_idx)
                break
        profile = parse_profile_from_rows(rows)
        profile.update(parse_income_table(profile_region))
        raw_label = clean_text(match.group(2))
        name = profile.get("姓名") or profile.get("名称") or raw_label
        identity = profile.get("身份标签") or default_identity
        people.append(
            {
                "label": raw_label,
                "name": name,
                "identity": identity,
                "profile": profile,
                "scene_start": 0,
                "scene_end": len(text),
            }
        )

    if not people:
        warn(warnings, case_id, "no protagonists parsed; using case heading as protagonist")
    return people


def parse_summary_line(block: str, label: str) -> str:
    match = re.search(rf"^\s*>\s*\*\*{re.escape(label)}：\*\*\s*(.+)$", block, re.M)
    return strip_markdown(match.group(1)) if match else UNKNOWN


def split_sections(block: str) -> dict[str, str]:
    matches = list(re.finditer(r"^####\s+\d+\.\s+(.+)$", block, re.M))
    sections = {}
    for idx, match in enumerate(matches):
        title = clean_text(match.group(1))
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(block)
        sections[title] = block[match.end() : end].strip()
    return sections


def parse_list(section: str) -> list[str]:
    items = []
    for line in section.splitlines():
        match = re.match(r"^\s*(?:[-*]|\d+\.)\s+(.+)$", line)
        if match:
            items.append(strip_markdown(match.group(1)))
    if items:
        return items
    text = paragraph_text(section)
    return [text] if text != UNKNOWN else [UNKNOWN]


def paragraph_text(section: str) -> str:
    lines = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("|") or re.match(r"^\|?\s*-+\s*\|", stripped):
            continue
        lines.append(strip_markdown(stripped))
    return clean_text(" ".join(line for line in lines if line != UNKNOWN))


def parse_options(section: str) -> dict[str, str]:
    lines = section.splitlines()
    for idx, line in enumerate(lines):
        if line.lstrip().startswith("|"):
            rows, _ = parse_table(lines, idx)
            options = {}
            for row in rows:
                key = row.get("选项") or row.get("key") or row.get("Key")
                value = row.get("内容") or row.get("具体信息") or row.get("text")
                if key:
                    options[clean_text(key)] = clean_text(value)
            if options:
                return options
    return {}


def parse_result(section: str) -> dict[str, str]:
    lines = section.splitlines()
    for idx, line in enumerate(lines):
        if line.lstrip().startswith("|"):
            rows, _ = parse_table(lines, idx)
            result = {}
            for row in rows:
                key = row.get("阶段") or row.get("结果阶段") or row.get("key")
                value = row.get("结果") or row.get("具体信息") or row.get("内容")
                if key:
                    result[clean_text(key)] = clean_text(value)
            if result:
                return result
    text = paragraph_text(section)
    return {"结果": text} if text != UNKNOWN else {}


def infer_age(profile: dict[str, str]) -> str | None:
    value = profile.get("年龄")
    if not value or value == UNKNOWN:
        return None
    return value


def infer_location(profile: dict[str, str]) -> str:
    return (
        profile.get("城市")
        or profile.get("常住 / 过往城市")
        or profile.get("常住/过往城市")
        or UNKNOWN
    )


def belongs_to_person(scene_title: str, block: str, person: dict, people: list[dict], joint_mode: bool) -> bool:
    if len(people) == 1:
        return True
    if joint_mode:
        return True
    label = person["label"]
    name = person["name"]
    haystack = f"{scene_title}\n{block}"
    if label and label in haystack:
        return True
    if name and name in haystack:
        return True
    return False


def owner_index_from_heading(heading: str) -> int | None:
    match = re.match(r"人物\s+(\d+)：", heading)
    if not match:
        return None
    return int(match.group(1)) - 1


def make_node(case_id: str, protagonist_idx: int, node_order: int, scene_order: int, scene_title: str, block: str, profile: dict[str, str]) -> dict:
    sections = split_sections(block)
    one_line = parse_summary_line(block, "一句话决策")
    variables_summary = parse_summary_line(block, "核心变量")
    cost_summary = parse_summary_line(block, "主要代价")

    constraints = parse_list(sections.get("当时约束", ""))
    options = parse_options(sections.get("备选项", ""))
    final_choice = paragraph_text(sections.get("最终选择", "")) or one_line
    actions = parse_list(sections.get("行动路径", ""))
    result = parse_result(sections.get("结果", ""))
    cost = paragraph_text(sections.get("代价", "")) or cost_summary
    variables = parse_list(sections.get("关键变量", ""))
    if variables == [UNKNOWN] and variables_summary != UNKNOWN:
        variables = [clean_text(item) for item in re.split(r"[、,，]", variables_summary) if clean_text(item) != UNKNOWN]
    audience = paragraph_text(sections.get("可参考人群", ""))

    return {
        "node_id": f"{case_id}_p{protagonist_idx:02d}_d{node_order:02d}",
        "timeline_order": node_order,
        "decision_scene": scene_title,
        "time_label": UNKNOWN,
        "stage_at_decision": scene_title,
        "age_at_decision": infer_age(profile),
        "location_at_decision": infer_location(profile),
        "人物背景": profile.get("身份标签") or profile.get("从业行业") or profile.get("行业") or UNKNOWN,
        "当时约束": constraints,
        "备选项": options,
        "最终选择": final_choice if final_choice != UNKNOWN else one_line,
        "行动路径": actions,
        "结果": result,
        "代价": cost if cost != UNKNOWN else cost_summary,
        "关键变量": variables,
        "可参考人群": audience,
        "evidence_quotes": [],
        "confidence": "medium",
    }


def parse_case(path: Path, metadata: dict[str, dict], warnings: list[str]) -> dict:
    text = path.read_text(encoding="utf-8")
    case_id, case_title, default_name, default_identity = parse_case_header(path, text)
    inherited = metadata.get(case_id, {})
    people = parse_people(text, default_name, default_identity, case_id, warnings)

    scene_blocks = find_heading_blocks(text, r"^### 场景\s+(\d+)：(.+)$")
    scene_titles = [clean_text(match.group(2)) for match, _ in scene_blocks]
    for title, count in Counter(scene_titles).items():
        if count > 1:
            warn(warnings, case_id, f"duplicate scene title kept {count} times: {title}")
    if not scene_blocks:
        warn(warnings, case_id, "no scenes parsed")

    protagonist_nodes: list[list[tuple[int, str, str]]] = [[] for _ in people]
    joint_mode = False
    current_owner_hint = ""
    for match, block in scene_blocks:
        scene_order = int(match.group(1))
        scene_title = clean_text(match.group(2))
        prefix = text[: match.start()]
        recent_headings = re.findall(r"^### (人物\s+\d+：.+|共同决策)\s*$", prefix, re.M)
        if recent_headings:
            current_owner_hint = recent_headings[-1]
        joint_mode = current_owner_hint == "共同决策"

        assigned = False
        owner_idx = owner_index_from_heading(current_owner_hint)
        if owner_idx is not None and not joint_mode and 0 <= owner_idx < len(people):
            protagonist_nodes[owner_idx].append((scene_order, scene_title, block))
            assigned = True
        else:
            for idx, person in enumerate(people):
                if belongs_to_person(scene_title, block, person, people, joint_mode):
                    protagonist_nodes[idx].append((scene_order, scene_title, block))
                    assigned = True
        if not assigned and people:
            warn(warnings, case_id, f"scene assigned to first protagonist by fallback: {scene_title}")
            protagonist_nodes[0].append((scene_order, scene_title, block))

    protagonists = []
    for idx, person in enumerate(people, start=1):
        nodes = []
        for node_order, (_scene_order, scene_title, block) in enumerate(protagonist_nodes[idx - 1], start=1):
            nodes.append(make_node(case_id, idx, node_order, _scene_order, scene_title, block, person["profile"]))
        if not nodes:
            warn(warnings, case_id, f"protagonist has no nodes: {person['name']}")
        protagonists.append(
            {
                "protagonist_id": f"{case_id}_p{idx:02d}",
                "name": clean_text(person["name"]),
                "identity": clean_text(person["identity"]),
                "profile": person["profile"],
                "decision_nodes": nodes,
            }
        )

    return {
        "case_id": case_id,
        "case_title": case_title,
        "source_links": inherited.get("source_links", []),
        "source_ids": inherited.get("source_ids", []),
        "story_id": inherited.get("story_id", f"case2:{case_id}"),
        "source_text_paths": inherited.get("source_text_paths", []),
        "text_completeness": inherited.get("text_completeness", UNKNOWN),
        "merge_basis": inherited.get("merge_basis", UNKNOWN),
        "protagonists": protagonists,
    }


def render_markdown(cases: list[dict]) -> str:
    lines = ["# 关键决策故事线 v2", "", f"- 案例数：{len(cases)}", ""]
    for case in cases:
        lines.extend(
            [
                f"## {case['case_id']} {case['case_title']}",
                "",
                f"- 原始链接数：{len(case.get('source_links', []))}",
                f"- 正文完整度：{case.get('text_completeness', UNKNOWN)}",
                f"- source：{'、'.join(case.get('source_ids', [])) or UNKNOWN}",
                "",
            ]
        )
        for link in case.get("source_links", []):
            lines.append(f"- 链接：{link}")
        if case.get("source_links"):
            lines.append("")

        for protagonist in case["protagonists"]:
            lines.extend([f"### 主人公：{protagonist['name']}", "", "**人物画像**", ""])
            for key, value in protagonist.get("profile", {}).items():
                lines.append(f"- {key}：{value}")
            lines.append("")
            for node in protagonist.get("decision_nodes", []):
                lines.extend(
                    [
                        f"#### {node['timeline_order']}. {node['decision_scene']}",
                        "",
                        f"- 主人公当时的场景和基本信息：{node['stage_at_decision']}",
                        f"- 当时约束：{'、'.join(node.get('当时约束', [])) or UNKNOWN}",
                        "",
                        "**备选项**",
                        "",
                    ]
                )
                for key, value in node.get("备选项", {}).items():
                    lines.append(f"- {key}：{value}")
                lines.extend(
                    [
                        f"- 最终选择：{node.get('最终选择', UNKNOWN)}",
                        f"- 行动路径：{'、'.join(node.get('行动路径', [])) or UNKNOWN}",
                        "",
                        "**结果**",
                        "",
                    ]
                )
                for key, value in node.get("结果", {}).items():
                    lines.append(f"- {key}：{value}")
                lines.extend(
                    [
                        f"- 代价：{node.get('代价', UNKNOWN)}",
                        f"- 关键变量：{'、'.join(node.get('关键变量', [])) or UNKNOWN}",
                        f"- 可参考人群：{node.get('可参考人群', UNKNOWN)}",
                        f"- 置信度：{node.get('confidence', UNKNOWN)}",
                        "",
                    ]
                )
    return "\n".join(lines).rstrip() + "\n"


def make_index(cases: list[dict]) -> list[dict]:
    index = []
    for case in cases:
        node_count = sum(len(person.get("decision_nodes", [])) for person in case.get("protagonists", []))
        case_file = next(CASE3_DIR.glob(f"{case['case_id']}_*.md"), None)
        transcript_file = next(TRANSCRIPT_DIR.glob(f"{case['case_id']}_*.txt"), None)
        index.append(
            {
                "case_id": case["case_id"],
                "case_title": case["case_title"],
                "case_file": str(case_file.relative_to(ROOT / "data")) if case_file and case_file.is_relative_to(ROOT / "data") else (str(case_file) if case_file else ""),
                "transcript_file": str(transcript_file.relative_to(ROOT / "data")) if transcript_file and transcript_file.is_relative_to(ROOT / "data") else (str(transcript_file) if transcript_file else ""),
                "decision_node_count": node_count,
                "protagonist_count": len(case.get("protagonists", [])),
            }
        )
    return index


def generate(case_dir: Path = CASE3_DIR, out_dir: Path = FINAL_DIR, metadata_path: Path | None = None, transcript_dir: Path | None = None) -> dict:
    configure_paths(case_dir, out_dir, metadata_path=metadata_path, transcript_dir=transcript_dir)
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    metadata = load_old_metadata()
    old_cases = load_old_cases()
    cases = []
    parsed_case_ids = set()
    for path in sorted(CASE3_DIR.glob("case_*.md")):
        case = parse_case(path, metadata, warnings)
        cases.append(case)
        parsed_case_ids.add(case["case_id"])
    for case_id, case in old_cases.items():
        if case_id not in parsed_case_ids:
            cases.append(case)
    cases.sort(key=lambda item: item["case_id"])

    OUT_JSON.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(cases), encoding="utf-8")
    OUT_INDEX.write_text(json.dumps(make_index(cases), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "cases": len(cases),
        "protagonists": sum(len(c.get("protagonists", [])) for c in cases),
        "decision_nodes": sum(len(p.get("decision_nodes", [])) for c in cases for p in c.get("protagonists", [])),
        "warnings": warnings,
        "out_json": str(OUT_JSON),
        "out_markdown": str(OUT_MD),
        "out_index": str(OUT_INDEX),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Odyssey final files from data/case3.0 Markdown cases.")
    parser.add_argument("--case-dir", default="data/case3.0")
    parser.add_argument("--out-dir", default="data/final")
    parser.add_argument("--metadata", default=None, help="Existing final JSON to inherit source metadata from.")
    parser.add_argument("--transcript-dir", default="data/text_clean")
    args = parser.parse_args()

    report = generate(
        repo_path(args.case_dir),
        repo_path(args.out_dir),
        metadata_path=repo_path(args.metadata) if args.metadata else None,
        transcript_dir=repo_path(args.transcript_dir),
    )

    print(f"Generated {report['cases']} cases")
    print(f"Generated {report['decision_nodes']} protagonist decision nodes")
    warnings = report["warnings"]
    if warnings:
        print("Warnings:")
        for item in warnings:
            print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
