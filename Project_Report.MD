# Project Report — Group 7 AI Live Commerce Order Assistant

**Date:** 2026-10-20
**Scope:** full local evaluation against `given/Project_Requirements.md` and `given/workflow.md`
**Stack:** React + Vite, FastAPI, SQLAlchemy, SQLite, FakeLLM and optional Ollama
**Ollama model used:** `qwen3.5:2b-q4_K_M`

**Verification runtime:** Python 3.14.7, Node.js 24.21.0, npm 11.19.0, Vite 8.3.4 on Windows.

## 1. Executive summary

Group 7 delivers a local marketplace demo with catalog browsing, session-scoped cart and draft checkout, plus a Vietnamese chat assistant. Backend rules remain authoritative for catalog mapping, price, stock, session ownership and order changes; the LLM is used to extract intent and fields. Missing/uncertain quantity does not silently become one, and explicit quantity is reconciled with the original message before stock validation.

The full automated evaluation run passed: **14/14 chat cases with FakeLLM and 14/14 with Ollama**. The API smoke flow passed 12 endpoint checks. Cross-session order access returned 404; a checkout request with spoofed price, stock and state fields returned 422 and did not create an order. The Vite production build passed. A browser smoke confirmed storefront catalog rendering, chat panel open and an API-grounded price response.

**Overall assessment:** the project meets the core local MVP and evaluation requirements. Production deployment, live human-support handoff, real payments, multi-item chat order entry, and human-scored response quality remain out of scope or unverified.

## 2. Product scope and architecture

The application supports three mock product categories and 12 SKU variants. The storefront uses a marketplace-inspired layout and a bottom-right interactive shopping assistant. The reference image is treated as visual guidance only; Group 7 uses its own name, product data and imagery.

```text
React/Vite browser
  -> FastAPI REST API + demo session cookie
     -> LLM extraction (FakeLLM or Ollama)
     -> Pydantic/schema + catalog/inventory/order rules
     -> SQLAlchemy -> SQLite
```

SQLite is the source of operational catalog, inventory, cart and order data. The frontend communicates through API routes and does not read the SQLite file or seed JSON directly. The checkout total and order item price snapshots are calculated by the backend.

## 3. Requirements coverage

| Guiding-doc requirement                                                                  | Evidence / result                                                                                                           | Status                                          |
| ---------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| Website shows products, price and availability from backend; customer can shop           | React storefront renders API catalog; API smoke covers session, products, details, cart, checkout and order reads           | Met for local MVP                               |
| Relational database stores products/SKU, inventory, cart/order, item snapshots and audit | SQLAlchemy schema + SQLite; seed contains 3 products and 12 SKUs; order snapshots and audit events implemented              | Met                                             |
| Browser does not access DB and server validates writes                                   | API-only frontend; schemas forbid extra checkout values; server calculates totals and rechecks stock                        | Met                                             |
| Ownership check blocks cross-session order access                                        | Automated probe: foreign order returned 404                                                                                 | Met                                             |
| Required intents and safe fallback                                                       | Price, stock, create, update and handoff cases in 14-case set                                                               | Met on defined cases                            |
| Prompt has scope, untrusted-input rule, JSON contract and version                        | Prompt `order-extraction-v2`; strict Pydantic extraction; model output cannot execute actions                             | Met                                             |
| Timeout, bounded retry, error route and idempotency                                      | Ollama timeout, up to two retries for selected transient failures; chat idempotency by session/message ID                   | Met for implementation; live outage not induced |
| Privacy and audit                                                                        | Synthetic fixtures; no raw user message retained in report/chat logs; contact fields are not duplicated into audit metadata | Met for demo design                             |
| Minimum evaluation set, rubric and failure analyses                                      | 14 fixtures per provider, rubric with five 0–2 dimensions, three failure analyses/revisions                                | Met; human rubric scoring pending               |
| 5–8 minute demo material                                                                | `docs/demo_script.md` gives a 6–7 minute flow                                                                            | Met                                             |

## 4. Verification performed

All evaluations used a temporary SQLite database, leaving `backend/data/shop.db` untouched. The test fixtures use synthetic demo contact details.

### 4.1. Chat evaluation

| Case group                        |        Count |         FakeLLM |          Ollama |
| --------------------------------- | -----------: | --------------: | --------------: |
| Happy path                        |            3 |             3/3 |             3/3 |
| Missing / ambiguous / multi-turn  |            4 |             4/4 |             4/4 |
| Catalog / inventory failure       |            2 |             2/2 |             2/2 |
| Provider / format fault injection |            2 |             2/2 |             2/2 |
| Safety / adversarial              |            2 |             2/2 |             2/2 |
| Controlled update                 |            1 |             1/1 |             1/1 |
| **Total**                   | **14** | **14/14** | **14/14** |

Ollama settings: prompt `order-extraction-v2`, JSON response mode, `think=false`, context 4096 and temperature 0. Failure cases FA-01/FA-02 inject provider/format faults at the extractor boundary; they are not proof of behavior during a real Ollama outage.

### 4.2. API smoke and security probes

| Operation                                   |              Expected |              Observed |
| ------------------------------------------- | --------------------: | --------------------: |
| Create demo session                         |                   200 |                   200 |
| Health                                      |                   200 |                   200 |
| Product list / product detail               |             200 / 200 |             200 / 200 |
| Cart read / add / update / delete           | 200 / 200 / 200 / 204 | 200 / 200 / 200 / 204 |
| Cart re-add / checkout                      |             200 / 201 |             200 / 201 |
| Order list / own order detail               |             200 / 200 |             200 / 200 |
| Other session requests order                |                   404 |                   404 |
| Spoof price + stock + state checkout fields |  422; no order change |     422; count 0 → 0 |

The browser smoke opened the local Group 7 page and confirmed three product cards, assistant open/close controls and chat interaction. Asking for the coffee 250g price returned **149,000₫** from the selected catalog variant. `npm run build` completed successfully (Vite 8.3.4).

### 4.3. Commands used

Run from repository root in PowerShell:

```powershell
.\backend\.venv\Scripts\python.exe eval\run_evaluation.py --provider fake
.\backend\.venv\Scripts\python.exe eval\run_evaluation.py --provider ollama --model qwen3.5:2b-q4_K_M
cd frontend
npm run build
```

The evaluation runner emitted a non-failing Starlette deprecation warning about its current `httpx` TestClient integration. It did not change the API/evaluation results; the dependency integration should be revisited when upgrading Starlette.

The runner writes complete provider reports to [`eval/results_fake.json`](eval/results_fake.json) and [`eval/results_ollama.json`](eval/results_ollama.json). Focused runs using `--limit` or `--case-id` write `eval/latest_results.json`.

## 5. Evaluation rubric

Each output can be scored from 0 to 2 in five dimensions (maximum 10), following the guiding brief:

| Dimension                 | 0                         | 1                             | 2                                     |
| ------------------------- | ------------------------- | ----------------------------- | ------------------------------------- |
| Intent correctness        | Wrong                     | Partly/mixed                  | Correct expected intent               |
| Extraction / groundedness | Invents or loses key data | Minor issue                   | Supported by message/catalog evidence |
| Format / validation       | Invalid or bypasses rule  | Partly validated              | Schema and business rules enforced    |
| Action routing            | Unsafe/wrong side effect  | Safe but unclear              | Correct draft/ask/handoff/error route |
| Customer response         | Wrong/unhelpful           | Understandable but incomplete | Clear, accurate and actionable        |

Automated checks measure routes/intents and selected data/safety invariants. We did not assign human response-quality scores; those should be completed during the live demo review.

## 6. Failure analyses and changes

1. **Heuristic substring/variant false positives and checkout FK ordering.** The first FakeLLM runs matched `gia` inside `giao hàng`, matched one-character `M` within unrelated words, and exposed audit insertion before its order FK row was flushed. Word boundaries, narrower patterns, bounded extraction and an explicit DB flush corrected the issues.
2. **Qwen quantity omission/undercount.** Qwen could omit quantity or interpret `chốt 13` as 1. Backend behavior was changed to fail closed when quantity is absent and reconcile explicitly action-labeled quantities against the source message. Both over-stock and unavailable-variant cases now route to `out_of_stock` without creating an order.
3. **Variant output shape mismatch.** Qwen initially returned a string for `variant` where the schema requires a JSON object. Prompt v2 now explicitly demands object-or-null; JSON mode and deterministic settings improved stable parsing. Malformed output continues to error safely without an order write.

## 7. Known limitations and remaining review

- Demo session is anonymous, local-only; it is not a production login or identity system. `Secure` cookie is configured for HTTPS, and production needs a stronger CSRF/auth strategy.
- Rate limiting is in-process, so it is not shared across multiple workers.
- SQLAlchemy `create_all` is used; no schema migration framework is included.
- Chat order creation supports one product line at a time. Drafts are pending confirmation only; no real payment, reservation or stock decrement occurs.
- “Handoff” communicates that staff help is needed; it does not send a real staff message.
- Human scoring of response clarity and manual browser completion of cart/checkout were not performed in this verification round. API checkout path was tested end to end.
- Failure injection checks provider error handling but does not shut down Ollama or induce a real timeout.
- The case set contains only 14 hand-authored inputs. Passing scores do not imply broad language generalization or production readiness.
- Product photos depend on external Unsplash URLs; the storefront may show missing images without internet access.

## 8. Artifacts

- [`README.md`](README.md) — separate FakeLLM and Ollama launch instructions.
- [`given/workflow.md`](given/workflow.md) — agent/developer workflow and phase status.
- [`docs/architecture.md`](docs/architecture.md) — architecture, data and API behavior.
- [`docs/evaluation_results.md`](docs/evaluation_results.md) — rubric, detailed results, revisions and evaluation limits.
- [`docs/demo_script.md`](docs/demo_script.md) — timed presentation runbook.
- [`eval/test_cases.json`](eval/test_cases.json) — anonymized evaluation cases.
