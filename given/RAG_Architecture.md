# RAG Extension Architecture

**Status:** proposed design; the copied application does not implement these RAG components yet. This document describes the target extension, not the current running system. The inherited LLM implementation is documented separately in [`LLM_Architecture.md`](LLM_Architecture.md).

## Goals and boundaries

- Reuse the existing React/Vite storefront, FastAPI API, SQLite operational database, catalog, inventory, session, cart/order flows, and order assistant.
- Add document ingestion, chunking, embeddings, permission-aware retrieval, grounded answer generation, citations, and index lifecycle management.
- Keep operational facts in the operational database. Embeddings search document knowledge; they do not decide live price, inventory, SKU validity, ownership, or order state.
- Keep RAG read-only. Order writes remain on the existing API/business-rule path and require its current validation and authorization.

## Target request flow

```text
Browser chat
  -> FastAPI: validate request + resolve server-side identity/role
  -> Router
       -> order/price/stock/update: inherited LLM extraction + business/API validation
       -> knowledge: authorize -> filter allowed docs -> retrieve -> assemble evidence
                       -> grounded answer + resolvable citations
       -> mixed: knowledge answer with citations + separately validated order action
       -> ambiguous/risky: clarification or handoff
  -> Browser: route status, answer, and citations
```

The router must never treat model output as authorization or as permission to perform a write. The knowledge route has no write-capable tools. For a mixed message, the order portion is independently validated; an unsupported knowledge answer does not authorize the action and a valid action does not justify unsupported claims.

## Ingestion and index

```text
Manifest + approved mock source documents
  -> validate IDs, files, encoding, metadata and provenance
  -> deterministic chunking with stable source/chunk identifiers
  -> document embeddings
  -> versioned local index bundle: vectors + chunk map + manifest
```

Each chunk carries document ID, chunk ID, source/title, document version, access level, and section/offset metadata where available. The manifest records corpus/index version, embedding model and revision, query/document encoding, normalization, distance metric, chunking settings, and bundle integrity information.

For the small course/demo corpus, start with a local reproducible index bundle rather than a separately hosted vector database. Choose the embedding model through development-set retrieval evaluation, document its exact revision and query/document encoding, and keep it fixed for a test run. Do not describe vector scores as factual confidence.

The loader checks that vector rows, chunk mappings, and manifest entries agree before serving queries. If integrity checks fail, retrieval must fail closed or return a visible degraded/error status; it must not cite an uncertain source mapping.

## Access control and trust boundaries

1. FastAPI resolves the caller's identity and allowed role on the server. A browser-supplied role is never authorization.
2. The current inherited cookie identifies an anonymous customer demo session only. It does not establish staff or admin identity.
3. Public customer content can use the public route. Do not ingest or serve restricted staff/admin documents until backend authentication and authorization exist.
4. Apply allowed-document filters before candidate retrieval/ranking and before cache lookup, prompt context, generation, and citations. Separate caches by access scope or avoid caching.
5. Treat the user query, retrieved document content, and model response as untrusted. Prompt instructions delimit evidence as data; server-side validation controls the response contract and route.
6. Keep logs to safe operational metadata. Do not store secrets, unnecessary raw prompts, PII, or internal retrieved text.

## Grounded answer contract

The knowledge route returns one explicit status: `answered`, `insufficient_evidence`, `access_denied`, `handoff`, or `error`. An answer includes concise Vietnamese text, citations with chunk/document/source/version identifiers, and a missing-information explanation when relevant.

Every material policy/product claim must be supported by evidence in the assembled context. Citations must resolve to the exact indexed source version and chunk. Missing, conflicting, or inaccessible evidence must produce a safe limitation or handoff rather than a guessed answer. Current price and stock questions continue to use the operational database, even if documents contain snapshots.

## Index lifecycle

Build a candidate bundle from a versioned corpus, validate its manifest and source mappings, then activate it as one atomic version. Keep the prior active bundle available for rollback. Invalidate caches on activation and record index version plus safe request/audit metadata. Never mix superseded and current policy versions in one active retrieval set unless the manifest defines an explicit, reviewed effective-date rule.

The required demo update is corpus/index version 1.0 to 1.1. Verification must prove the new policy is retrieved, the old text is no longer active, rollback restores the previous behavior, and restricted chunks never appear in customer candidates, context, cache, or citations.

## Evaluation boundary

Evaluate retrieval, evidence coverage, answer claims, citation resolution/support, abstention, access denial, route selection, and mixed-action validation separately. The inherited 14-case LLM order evaluation is not evidence of RAG quality. Keep development and test cases separate before tuning; report test results only after the chosen configuration is frozen.

## Related documents

- [`RAG_Workflow.md`](RAG_Workflow.md) — implementation phases and acceptance gates.
- [`Project_RAG_Requirements.pdf`](Project_RAG_Requirements.pdf) — authoritative assignment requirements.
- [`LLM_Architecture.md`](LLM_Architecture.md) — inherited implementation, not RAG architecture.
- [Root README](../README.md) — setup for the inherited baseline and current status.
