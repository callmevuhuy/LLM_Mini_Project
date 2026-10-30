# RAG Evaluation Report — run 30/10/2026

## Test set

20 authored cases split equally between dev/test: exact/code (4), paraphrase (4), multi-condition (3), no-evidence (2), access-denied (2), mixed (3), safety/adversarial (2). Recall/MRR are computed only for cases with expected chunks. The set is small and hand-authored; do not interpret it as production quality evidence.

## Results

| Metric | All 20 | Dev 10 | Test 10 |
|---|---:|---:|---:|
| Hit@3 | 100.00% | 100.00% | 100.00% |
| Recall@5 | 93.89% | 86.90% | 100.00% |
| MRR | 0.9000 | 0.7857 | 1.0000 |
| Citation metadata resolution and role eligibility | 100.00% | — | — |
| Expected claim string inclusion proxy | 70.00% | 70.00% | 70.00% |
| Safe abstention | 100.00% | 100.00% | 100.00% |
| Access-denied | 100.00% | 100.00% | 100.00% |
| Expected route / status | 100.00% / 100.00% | 100.00% / 100.00% | 100.00% / 100.00% |
| Mixed category route + citation presence | 100.00% | 100.00% | 100.00% |

The claim metric checks whether expected strings appear in the answer; it does not establish entailment. Mixed accuracy here verifies router classification and citation presence, not successful execution of each order action. The inherited evaluation separately exercises API order flows.

## Fixes made during takeover

- Added integrity and structure checks to index loading, and required access metadata at ingestion; missing access levels no longer default to public.
- Restricted Staff/Admin demo roles to server-configured tokens; re-index requires a valid session, allowed origin and admin role token. Unauthenticated role spoofing was reproduced before the fix and returned 403 after it.
- Added an atomically replaced active-bundle pointer and per-request process refresh for same-host workers.
- Prioritized topic-matched evidence and narrowed citations; a return-period query previously selected shipping evidence and now returns the return policy source.
- Completed exact/code, short-phrase and adversarial route patterns. Evaluator now reports route/status matches and validates citation metadata/role eligibility.

## Limits

The embedder is a deterministic hashed lexical vectorizer, not semantic embeddings. The citation evaluator checks identity/metadata, and claim support remains a string proxy. The report does not include human judgment, large-scale load, multi-host coordination, signed artifacts, or an external identity provider. Run the scripts above to reproduce metrics.
