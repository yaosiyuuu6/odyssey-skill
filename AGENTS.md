# Odyssey Skill Agent 维护说明

本文件面向维护仓库的 Agent，不面向普通用户。`README.md` 是用户展示页，必须保持用户友好，不放内部采集、整理、发布、测试等维护细节。

## 维护规则

- 修改目录结构、脚本入口、数据路径、内部 skill 流程、测试命令或发布流程时，必须同步更新本文件。
- 新增文件时，要在“仓库结构”或对应模块说明中补上用途；删除或废弃文件时，也要同步标记。
- 所有新采集数据、转写、storylines、final 产物都必须落在 `/Users/chenkai/Desktop/CodeX/odyssey-skill/data` 下。
- `OdysseyMap` 和 `Lifestory` 只作为历史参考来源，不再作为运行时数据目录。不要向它们写入新的采集输出、转写、case Markdown、storylines 或 final 文件。
- 保留 `decision_storylines_v2.json` 文件名，除非用户明确要求做 schema/文件名迁移。

## 仓库结构

```text
odyssey-skill/
├── AGENTS.md
├── README.md
├── .gitignore
├── assets/
│   └── cover-odyssey.png
├── config/
│   ├── corrections_zh.json
│   └── hotwords_zh.txt
├── data/
│   ├── decision_storylines_v2.json
│   ├── manifest.json
│   ├── odyssey_search_index.json
│   ├── source_index.json
│   └── intake/
├── internal-skills/
│   └── odyssey-case-ingestion/
│       ├── SKILL.md
│       ├── agents/
│       └── references/
├── odyssey-skill/
│   ├── SKILL.md
│   ├── agents/
│   │   └── openai.yaml
│   ├── references/
│   │   ├── data-contract.md
│   │   ├── response-style.md
│   │   └── search-policy.md
│   └── scripts/
├── scripts/
└── tests/
```

说明：

- `AGENTS.md`：本文件，维护 Agent 的项目地图和操作规则。结构变化时实时更新。
- `README.md`：用户侧说明和安装介绍。不要写内部维护细节。
- `assets/`：用户侧展示素材，目前包含封面图。
- `config/`：采集/转写辅助配置，包含中文热词和确定性错词修正。
- `data/`：唯一的数据归档和发布目录。
- `internal-skills/`：仅供维护者/Agent 使用的内部技能。
- `odyssey-skill/`：可安装的用户侧 skill 包。
- `scripts/`：仓库级辅助脚本，当前主要是历史/运维辅助，不是用户侧 skill 脚本入口。
- `tests/`：脚本、索引和数据契约测试。

## 数据目录

所有新数据都放在 `data/`：

- `data/intake/YYYY-MM-DD/`：入选 URL、Lark 导出、blocked 列表、采集报告；候选源归档到其下的 `candidates/`。
- `data/assets/YYYY-MM-DD/`：下载的字幕、音频、图片、OCR、ASR 转写和采集元数据。
- `data/working/YYYY-MM-DD/`：URL 采集后的 `sources.json`、`stories.json`、`report.md`、`methods.md`；重试采集产物归档到其下的 `retry/`。
- `data/case3.0/`：人工 deep-read 后写出的 case Markdown，一案一文件。
- `data/final/`：由 case3 Markdown 生成的 final JSON、Markdown 和 case index。
- `data/decision_storylines_v2.json`：发布给搜索脚本使用的主数据库。
- `data/odyssey_search_index.json`：搜索索引。
- `data/source_index.json`：来源索引。
- `data/manifest.json`：远端数据 manifest。

当前仓库里已有 `data/intake/2026-06-10/` 下的候选和入选记录；后续新批次按日期子目录继续归档。

原始音视频文件可保留在本机 `data/assets/` 下用于复跑转写，但默认不进入 Git；提交时保留转写文本、字幕、OCR、采集元数据和 final/index 产物。

## 用户侧 Skill

用户侧 skill 位于 `odyssey-skill/`：

- `odyssey-skill/SKILL.md`：面向用户的人生决策案例搜索和回答流程。保持轻量，不加入内部采集流程。
- `odyssey-skill/agents/openai.yaml`：Codex/OpenAI agent UI 元数据。
- `odyssey-skill/references/data-contract.md`：搜索数据字段契约。
- `odyssey-skill/references/response-style.md`：用户回答风格。
- `odyssey-skill/references/search-policy.md`：搜索、排序和边界策略。

用户侧搜索脚本：

- `fetch_indexes.py`：拉取远端索引并写入本地缓存。
- `search_odyssey.py`：根据用户处境搜索真实案例。
- `validate_remote_data.py`：验证发布数据契约。
- `build_indexes.py`：由 `decision_storylines_v2.json` 生成 manifest、搜索索引和来源索引。

## 内部采集与生成脚本

内部维护脚本位于 `odyssey-skill/scripts/`：

- `collect_source_urls.py`：从 Markdown URL 列表采集 Bilibili、Podcast、小红书原文，输出 working 和 assets。
- `acquire_bilibili_subtitles.py`：针对入选 Bilibili 记录抓官方字幕。
- `acquire_audio_transcripts.py`：对已下载音频做 ASR 转写。
- `generate_final_from_case3.py`：从 `data/case3.0/` 生成 `data/final/`。
- `search_candidate_sources.py`：搜索候选案例源。
- `ingestion_candidates.py`：把候选源转成 Lark Base 可导入/更新的记录。
- `export_selected_lark_cases.py`：规范化 Lark 入选记录。
- `sync_case3_from_odysseymap.py`：历史迁移工具，仅用于从旧 OdysseyMap 迁移，不是新流程入口。
- `asr.py`、`asr_quality.py`、`ocr.py`、`completeness.py`、`report.py`、`text_normalize.py`：采集、转写、OCR、完整度、报告和文本规范化支撑模块。
- `platforms/`：平台采集实现，包含 `bilibili.py`、`podcast.py`、`xiaohongshu.py`。

补充：

- `collect_source_urls.py` 支持直接读取规范化后的 selected cases JSON，并将 `case_id`、`record_id`、`source_id`、Base 备注、主题标签等 seed 到 source 记录。
- `collect_source_urls.py` 支持小宇宙、Firstory、Fireside Podcast 链接；每完成一条 source 会立即 checkpoint 写出 `sources.json`、`stories.json`、`report.md`、`methods.md`，避免长 ASR 中断导致已完成结果丢失。
- `asr.py` 中 `--asr-timeout-seconds 0` 表示不设置单条 ASR 超时。

内部采集脚本可以依赖 `requests`、`beautifulsoup4`、`yt-dlp`、`faster-whisper`、`mlx-whisper`、`whisperx`、`pytesseract` 等可选依赖；用户侧搜索 runtime 仍保持轻量。

## 内部 Skill

内部 skill 位于 `internal-skills/odyssey-case-ingestion/`：

- `SKILL.md`：维护流程总入口，覆盖候选搜索、URL 采集、case3 编写、final 生成、索引重建和验证。
- `references/acquisition-methods.md`：Bilibili、Podcast、小红书采集方法。
- `references/case3-authoring.md`：case3 Markdown 编写结构和事实边界。
- `agents/`：内部 skill UI 元数据目录；如新增/修改内部 skill 展示信息，需要同步更新。

## 标准流程

从 URL 到发布索引的标准流程：

1. 入选 URL 或 Lark 导出放入 `data/intake/YYYY-MM-DD/`。
2. 采集源内容：

```bash
python3 odyssey-skill/scripts/collect_source_urls.py \
  --input data/intake/YYYY-MM-DD/selected_urls.md \
  --output data/working/YYYY-MM-DD \
  --asset-root data/assets/YYYY-MM-DD
```

3. 人工 deep-read，把 case Markdown 写入 `data/case3.0/`。
4. 生成 final：

```bash
python3 odyssey-skill/scripts/generate_final_from_case3.py \
  --case-dir data/case3.0 \
  --out-dir data/final
```

5. 发布主数据库并重建索引：

```bash
cp data/final/decision_storylines_v2.json data/decision_storylines_v2.json
python3 odyssey-skill/scripts/build_indexes.py \
  --source data/decision_storylines_v2.json \
  --out-dir data
```

6. 验证：

```bash
pytest tests -q
python3 odyssey-skill/scripts/validate_remote_data.py --data-dir data
/opt/anaconda3/bin/python /Users/chenkai/.codex/skills/.system/skill-creator/scripts/quick_validate.py odyssey-skill
```

本机系统 `python3` 缺少 `PyYAML`，运行 `quick_validate.py` 时使用 `/opt/anaconda3/bin/python`。

## 采集与事实规则

- 不得只根据平台简介、标题、评论或元数据结构化案例。
- 缺失事实写 `原文未提及`。
- 推断事实必须以 `推断：` 开头。
- 保留可追踪字段：`source_links`、`source_ids`、`source_text_paths`、`case_id`、`protagonist_id`、`node_id`。
- Bilibili：官方字幕优先，其次 `bccdl`，最后音频 ASR。
- Podcast：从 Apple `i=` episode id、iTunes lookup/RSS 获取音频，再 ASR。
- 小红书：公开正文加可见图片 OCR；不得点赞、评论、关注、私信或修改任何内容。

## 测试结构

`tests/` 覆盖以下内容：

- 数据索引与远端数据验证：`test_build_indexes.py`、`test_fetch_indexes.py`、`test_validate_remote_data.py`、`test_search_odyssey.py`。
- 候选和 Lark 相关脚本：`test_search_candidate_sources.py`、`test_ingestion_candidates.py`、`test_export_selected_lark_cases.py`、`test_upload_lark_jsonl.py`。
- 采集与转写脚本：`test_collect_source_urls.py`、`test_acquire_bilibili_subtitles.py`、`test_acquire_audio_transcripts.py`。
- ASR 和平台采集细节：`test_asr.py`、`test_podcast_platform.py`。
- final 生成和历史同步：`test_generate_final_from_case3.py`、`test_sync_case3.py`。

新增脚本时优先补最小单元测试；改变路径默认值时必须补路径断言测试，确保输出仍在 `odyssey-skill/data` 内。
