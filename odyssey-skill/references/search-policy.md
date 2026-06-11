# Search Policy

The search is evidence-bounded. It ranks real decision nodes from the Odyssey cloud index; it does not search the open web.

## Retrieval And Reranking

The script does broad retrieval and deterministic pre-ranking. It returns a diversified JSON candidate pool, usually up to 30 nodes, with `ranking_evidence`, `matched_terms`, and `matched_dimensions`.

The Agent does the final rerank from that evidence. Do not automatically use the first three script results as the answer. Prefer three different cases by default; only show multiple nodes from the same case when the user wants to go deeper into that story or when there are not enough relevant cases.

## Agent Reranking Priorities

1. Decision scene match.
2. Constraint and resource match.
3. Cost/risk match.
4. Action path match.
5. Result similarity.
6. Source quality and traceability.
7. Diversity across cases.

Results are useful as references, not as recommended choices.

## If Context Is Missing

Ask one concise follow-up question before searching when the user gives a very broad intention such as “我想裸辞” and there is no clear search angle. Also wait if the user is clearly still expressing their situation; do not interrupt with results just because there is already enough searchable context. Do not ask all missing details at once.

Minimum useful context:

- why they want the change
- current role/industry/stage
- savings runway
- hard constraints
- what kind of reference they want

If the user does not answer, gives a short answer, or asks to see cases, proceed with a reasonable default based on what they already said and label the match as broad.

## If No Good Match Exists

Say the database does not currently contain a highly similar case. Offer lower-confidence references only if they are clearly labeled.

Never invent a podcast, person, result, income, education, city, or source.
