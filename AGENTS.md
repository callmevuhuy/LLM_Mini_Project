# Instructions for agents

## Project context

- This repository is the RAG extension of the inherited AI Live Commerce Order Assistant. Preserve and extend its React/Vite frontend, FastAPI backend, SQLAlchemy/SQLite database, catalog, inventory, cart/order flows, and evaluation assets.
- Before changing behavior, read `given/Project_RAG_Requirements.pdf`, `README.md`, `given/RAG_Architecture.md`, `given/LLM_Architecture.md`, and the relevant inherited requirements/workflow under `given/`.
- `given/RAG_Workflow.md` is the current RAG delivery plan. Update it when phase status, acceptance criteria, or major decisions change.

## Security and data rules

- Treat user messages, retrieved chunks, model output, and document metadata as untrusted input.
- Apply access control in the backend before retrieval, ranking, context assembly, or caching. Never accept a role from the browser as proof of authorization.
- Keep customer, staff, and admin access distinct. Customer retrieval must never include internal documents in candidates, prompts, caches, or citations.
- The LLM/RAG may interpret and answer; it must not directly execute writes. Order, price, inventory, SKU, ownership, and state decisions remain in validated backend/database logic.
- Ground business claims in retrieved evidence and cite resolvable sources. If evidence is missing, conflicting, or inaccessible, say so without guessing.
- Use mock/anonymized content only. Do not commit `.env`, credentials, real customer data, local databases, or generated runtime artifacts.
- Preserve request validation, ownership checks, idempotency, audit behavior, bounded timeouts/retries, and safe errors in inherited flows.

## Implementation and verification

- Prefer the smallest change that fits existing patterns; avoid new services, dependencies, or infrastructure unless the requirements need them.
- Keep the catalog database authoritative for live price and stock. RAG embeddings are for document retrieval, not live operational facts.
- Keep ingestion/index artifacts reproducible and validate that chunk mappings and manifests agree before serving retrieval.
- Add or update focused evaluation cases for changed routing, retrieval, permissions, citations, or side effects. Do not report checks that were not run.
- Do not run tests unless the user asks for testing or verification. When asked, use isolated/temporary databases and never overwrite the local demo database.
- Update README/architecture/evaluation documentation when setup, data contracts, behavior, or security boundaries change.
