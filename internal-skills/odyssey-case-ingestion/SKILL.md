---
name: odyssey-case-ingestion
description: "Use for internal Odyssey case-library maintenance: search candidate life-decision stories, ingest selected URLs, author case3 Markdown, generate final storylines, rebuild indexes, and validate the searchable skill database."
---

# Odyssey Case Ingestion

Use this internal skill for Odyssey data maintenance. It is not the user-facing recommendation skill.

## Data Home

All active ingestion data lives in `/Users/chenkai/Desktop/CodeX/odyssey-skill/data`.

- Raw intake and review exports: `data/intake/YYYY-MM-DD/`
- Candidate search exports: `data/intake/YYYY-MM-DD/candidates/`
- Downloaded subtitles/audio/images/transcripts: `data/assets/YYYY-MM-DD/`
- Collection working files: `data/working/YYYY-MM-DD/`; retry outputs go under `data/working/YYYY-MM-DD/retry/`
- Authored case Markdown: `data/case3.0/`
- Generated final files: `data/final/`
- Published search data: `data/decision_storylines_v2.json`, `data/odyssey_search_index.json`, `data/source_index.json`, `data/manifest.json`

`OdysseyMap` and `Lifestory` are historical references only. Do not write new collection outputs, final files, transcripts, or case3 Markdown there.

Keep `decision_storylines_v2.json` as the downstream filename until a schema migration is explicitly approved.

## Workflow

1. Search candidates from the odyssey-skill repo.

```bash
python3 odyssey-skill/scripts/search_candidate_sources.py \
  --from-existing-sources \
  --source-index data/source_index.json \
  --podcast-count 70 \
  --bilibili-count 25 \
  --xiaohongshu-count 5 \
  --out data/intake/YYYY-MM-DD/candidates/candidate_cases.json
```

2. Prepare Lark review records when review is needed.

```bash
python3 odyssey-skill/scripts/ingestion_candidates.py \
  --candidates data/intake/YYYY-MM-DD/candidates/candidate_cases.json \
  --source-index data/source_index.json \
  --out data/intake/YYYY-MM-DD/candidates/candidate_cases.lark.jsonl
```

3. Export selected records or write selected URLs.
   - Put selected exports under `data/intake/YYYY-MM-DD/`.
   - If using URL Markdown, save it as `data/intake/YYYY-MM-DD/selected_urls.md`.
   - Confirm URL uniqueness before assigning case IDs.

4. Collect source content into odyssey-skill.

```bash
python3 odyssey-skill/scripts/collect_source_urls.py \
  --input data/intake/YYYY-MM-DD/selected_urls.md \
  --output data/working/YYYY-MM-DD \
  --asset-root data/assets/YYYY-MM-DD
```

   - Bilibili: official subtitles first, then `bccdl`, then audio ASR.
   - Podcast: Apple `i=` episode id, iTunes lookup/RSS, then audio ASR.
   - Xiaohongshu: public body and image OCR; do not like, comment, follow, send, or modify anything.
   - Do not structure a case from metadata/description alone. Missing complete source text goes into a blocked list under `data/intake/YYYY-MM-DD/`.

5. Author case3 Markdown in `data/case3.0/`.
   - One file per case: `case_XX_标题.md`.
   - Use the format in `references/case3-authoring.md`.
   - Preserve source URLs, source IDs, text completeness, and merge basis.

6. Generate final files in odyssey-skill.

```bash
python3 odyssey-skill/scripts/generate_final_from_case3.py \
  --case-dir data/case3.0 \
  --out-dir data/final
```

7. Publish search data and rebuild indexes.

```bash
cp data/final/decision_storylines_v2.json data/decision_storylines_v2.json
python3 odyssey-skill/scripts/build_indexes.py \
  --source data/decision_storylines_v2.json \
  --out-dir data
```

8. Validate before reporting success.

```bash
python3 -m pytest tests -q
python3 odyssey-skill/scripts/validate_remote_data.py --data-dir data
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py odyssey-skill
```

## Data Rules

- Do not invent facts about protagonists, timeline, result, education, income, family background, or location.
- Missing facts must be `原文未提及`.
- Inferred facts must start with `推断：`.
- Preserve source URL traceability through `source_links`, `source_ids`, `source_text_paths`, `case_id`, `protagonist_id`, and `node_id`.
- Recommendations remain evidence-bounded references, not life advice.

For platform acquisition details, read `references/acquisition-methods.md`.
For case3 Markdown structure, read `references/case3-authoring.md`.
