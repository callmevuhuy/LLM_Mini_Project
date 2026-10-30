# RAG project workflow

## Goal

Extend the inherited Live Commerce Order Assistant with reproducible document ingestion, embeddings, permission-aware retrieval, grounded Vietnamese answers with citations, and evaluation. Keep the existing storefront, API, catalog/inventory, session-scoped cart/orders, and validated order assistant working.

The RAG route answers from documents. It does not create or change orders and is not the source of truth for live price, stock, SKU validity, or order state.

**Current status:** planning only. The copied baseline does not yet implement RAG ingestion, embeddings, retrieval, role-based document access, citations, or RAG evaluation. Mark a phase complete only after its gate is verified.

## Inherited project status

The LLM project has been copied into this repository root. Its backend, frontend, seed catalog, mock database schema code, order/chat flows, evaluation runner/cases, reports, and setup documentation are present. Generated dependencies, `.git`, local SQLite database files, and caches were intentionally excluded; recreate them from the checked-in setup and seed instructions when needed.

The source LLM working tree had local modifications and untracked handoff/presentation files at copy time. The copied version contains those current files, but this RAG folder is not initialized as a Git repository. Confirm repository ownership/remotes before initializing or publishing it.

## Working rules

1. Read this workflow, [`RAG_Architecture.md`](RAG_Architecture.md), root `AGENTS.md`, `Project_RAG_Requirements.pdf`, root `README.md`, and the relevant inherited LLM architecture/requirements before implementation.
2. Preserve existing order and security behavior. Route requests explicitly to order/business logic, knowledge retrieval, mixed handling, or clarification/handoff.
3. Keep one authoritative catalog/database for operational facts. Document corpus references must use the same product/SKU identifiers.
4. Build with mock/anonymized data. Never use real customer data, secrets, or unauthorized internal documents.
5. Change one layer at a time and record decisions, evidence, limitations, and actual verification results in the relevant docs.

## Delivery phases and gates

### Phase 0 — Baseline and boundaries

- Confirm the inherited app structure, startup instructions, database/seed behavior, current API contracts, and known limits.
- Document customer/staff/admin access and how backend identity determines roles. A UI selector or request field is not authentication.
- Draw the router boundary: order actions stay on the existing validated API path; knowledge reads go through permission-filtered retrieval; mixed inputs separate answerable knowledge from any separately validated action.

**Gate:** baseline is runnable from documented setup; each route's permissions and side effects are explicit. Do not add internal-document access until backend role checks exist.

### Phase 1 — Corpus and provenance

- Create a manifest-driven mock corpus with at least 12 documents or 30 meaningful sections/chunks.
- Cover catalog/product facts, FAQ, delivery/return/warranty policies, no-evidence questions, and restricted staff material.
- Record stable document ID, source, creator, version, access level, and relevant section metadata. Use only content the team may use.
- Keep product and SKU references consistent with the operational database. Do not place evaluation ground-truth answers in runtime prompts.

**Gate:** ingestion rejects missing/empty files, duplicate IDs, invalid encoding, and missing required metadata; corpus has public and restricted examples and contains no real PII or secrets.

### Phase 2 — Ingestion, embeddings, and index bundle

- Read the manifest and chunk documents deterministically. Store stable `doc_id`/`chunk_id`, source, version, access level, and section/offset metadata with each chunk.
- Embed documents and queries using a documented, compatible model/revision and encoding configuration. Keep the first implementation local and simple for the expected demo corpus; do not add a vector service for scale that is not required.
- Save an index bundle with vectors, chunk mapping, and manifest. Record corpus/index version, embedding model/revision, query/document encoding, normalization, distance metric, and chunking settings.
- Validate bundle integrity before serving. A mismatch must stop retrieval or expose an explicit degraded/error state; never cite through an untrusted mapping.

**Gate:** the same corpus/config can rebuild the index reproducibly, and every indexed vector resolves to the correct source chunk and metadata.

### Phase 3 — Permission-aware retrieval and grounded answers

- Resolve role on the backend. Filter allowed documents before candidate generation/ranking and before prompt/context assembly; keep customer and restricted content separated in any cache.
- Implement bounded top-k retrieval with rank/score metadata for debugging. Treat scores as ranking signals, not confidence or proof.
- Handle empty queries, unavailable/corrupt indexes, no candidates, insufficient evidence, conflicting sources, and access denied explicitly.
- Generate concise Vietnamese answers from supplied evidence only. Require citations that resolve to the actual source/version/chunk and support material claims. Preserve important exceptions and conditions.
- Treat the question and retrieved documents as untrusted data. Ignore embedded instructions, requests for secrets, and requests to bypass policy.

**Gate:** customer requests cannot retrieve restricted content; unsupported answers abstain; citations resolve and support claims; no RAG output can trigger database writes.

### Phase 4 — Chat/API/UI integration

- Add a `knowledge_query` route to the existing chat experience without breaking order intent handling.
- For mixed requests, answer the knowledge part with citations and send any requested order action through the existing SKU/ownership/inventory/state validation path. Ask for clarification or hand off when the target or authority is ambiguous.
- Show source/title/document ID/version and clear status for answered, insufficient evidence, access denied, handoff, and technical error.
- Provide only the small staff/admin demo surface needed to inspect source/index status or request a controlled re-index. Enforce its permissions in the backend.

**Gate:** inherited catalog, cart, checkout, price/stock checks, order ownership, and order audit behavior remain intact; UI does not decide role or operational facts.

### Phase 5 — Evaluation and controlled improvement

- Create at least 20 cases and freeze a test split before tuning. Each case records query, role/route, answerability, relevant evidence or expected action behavior, and review outcome.
- Meet the required category counts: exact/code 4; paraphrase 4; multi-condition/multi-source 3; no-evidence 2; access-denied 2; mixed order+knowledge 3; safety/adversarial 2.
- Measure Hit@3, Recall@5, and MRR for cases with relevant evidence; evidence coverage for multi-condition cases; claim support status; citation resolve/support rate; safe abstention and false refusal; access-denied correctness; and mixed route/action correctness. Do not calculate recall where the relevant set is empty.
- Analyze at least five errors or near-misses by pipeline layer. Try one controlled change on development cases before evaluating on the frozen test set.

**Gate:** report the case set, metrics, failure analysis, change tried, and limitations. Do not claim general quality from a small authored set.

### Phase 6 — Re-index, rollback, and demo handoff

- Simulate a meaningful corpus update from version 1.0 to 1.1. Record the policy/source/chunks changed and the old/new index snapshots or reproducible bundle identifiers.
- Rebuild and validate a candidate index, activate it only after checks pass, invalidate affected caches, and retain a documented rollback path.
- Run verification queries proving changed content is served from the active version and obsolete content is not used. Verify internal material remains absent from customer candidates/context/cache/citations.
- Record safe operational metadata only; avoid secrets, unnecessary raw prompts, PII, and internal context in logs/audit.
- Prepare a 10–12 minute demo: cited product/policy answer; multi-condition answer; existing order/inventory flow; mixed query; no-evidence and access-denied; evaluation evidence; and re-index behavior.

**Gate:** active index/version is inspectable and reversible; demo behavior matches evaluated behavior; README and architecture explain inheritance, setup, corpus provenance, access model, limitations, and evaluation commands.

## Definition of done

- The inherited LLM flows remain available and server-authoritative.
- Corpus ingestion and index generation are reproducible and integrity-checked.
- Retrieval applies access policy before ranking and context creation.
- Knowledge answers are evidence-grounded with resolvable citations or a safe non-answer.
- No-evidence, access-denied, mixed, and adversarial cases route safely.
- At least 20 evaluation cases, required metrics, five error analyses, and one controlled re-index scenario are documented.
- Setup, architecture, permissions, known limits, and actually run checks are documented; no secrets or real customer data are committed.
