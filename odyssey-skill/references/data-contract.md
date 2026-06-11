# Data Contract

The skill reads cloud data from a GitHub Raw base URL. The installable skill folder does not carry the full database.

## Files

- `data/manifest.json`: database version, updated time, checksums, record counts.
- `data/odyssey_search_index.json`: one record per decision node, optimized for search.
- `data/source_index.json`: one record per source link.
- `data/decision_storylines_v2.json`: full structured case database, used for generation and validation.

## Search Record

Required fields:

- `case_id`
- `case_title`
- `protagonist_id`
- `protagonist_name`
- `node_id`
- `decision_scene`
- `constraints`
- `options`
- `final_choice`
- `action_path`
- `cost`
- `result`
- `reference_group`
- `source_links`
- `is_podcast_recommendable`
- `searchable_text`
- `search_tags`
- `match_dimensions`
- `ranking_evidence`

Optional runtime fields added by the search script:

- `match_score`
- `matched_terms`
- `matched_dimensions`
- `rank_hints`

## Source Record

Required fields:

- `source_id`
- `case_id`
- `source_type`
- `platform`
- `title`
- `url`
- `is_podcast`
- `is_recommendable_for_skill`

## Data Integrity

- Missing facts remain `原文未提及`.
- Inferred facts begin with `推断：`.
- Recommendations must be traceable to `case_id`, `protagonist_id`, `node_id`, and source link.
