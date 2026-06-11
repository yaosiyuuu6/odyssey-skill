# Case3 Authoring

Write authored cases under `data/case3.0/` as `case_XX_标题.md`.

## Required Shape

- `# 案例 XX：姓名或标题｜身份标签`
- `## 一、人物背景`
- `## 二、核心决策场景拆解`
- Decision scene headings use `### 场景 N：场景标题`.
- Each scene should include:
  - `一句话决策`
  - `核心变量`
  - `主要代价`
  - `#### 1. 当时约束`
  - `#### 2. 备选项`
  - `#### 3. 最终选择`
  - `#### 4. 行动路径`
  - `#### 5. 结果`
  - `#### 6. 代价`
  - `#### 7. 关键变量`
  - `#### 8. 可参考人群`

## Rules

- Use only facts supported by the source transcript/body/OCR.
- Use `原文未提及` for missing facts.
- Prefix inferred facts with `推断：`.
- Preserve source metadata through generated final files; do not remove existing links or source IDs when regenerating.
