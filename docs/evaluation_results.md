# Phase D — Evaluation results

## Setup and scope

The evaluation runner executes the real FastAPI routes against a temporary SQLite database. It does not modify `backend/data/shop.db`. The 14 deterministic cases cover three happy paths, four missing-information/multi-turn cases, two catalog/inventory cases, two injected provider/format failures, two safety cases, and one controlled order update. Contact details in the fixtures are synthetic. Reports retain case IDs, routes, intents and aggregate security results; they do not retain raw user messages or contact details.

Run from the repository root in PowerShell:

```powershell
.\backend\.venv\Scripts\python.exe eval\run_evaluation.py --provider fake
.\backend\.venv\Scripts\python.exe eval\run_evaluation.py --provider ollama --model qwen3.5:2b-q4_K_M
```

Full reports are [`../eval/results_fake.json`](../eval/results_fake.json) and [`../eval/results_ollama.json`](../eval/results_ollama.json). A focused run (`--limit` or `--case-id`) writes `eval/latest_results.json`.

## Results

Run on 2026-10-20 with prompt `order-extraction-v2`; Ollama was configured for `qwen3.5:2b-q4_K_M`, `think=false`, context 4096 and temperature 0.

| Provider | Chat cases | API smoke | Catalog/inventory | Security probes |
| --- | ---: | --- | ---: | --- |
| Fake rules | 14/14 | Pass (12 status checks) | 2/2 | Pass |
| Ollama Qwen 3.5 2B Q4_K_M | 14/14 | Pass (12 status checks) | 2/2 | Pass |

The inventory cases reject a color/size absent from the catalog and a requested quantity above available stock. These scores indicate this fixture set only; they do not establish broad Vietnamese language coverage or production readiness.

### Security evidence

- An order ID belonging to another demo session returned **404**.
- A checkout payload that included client-supplied `total_amount`, `unit_price` and `status` returned **422**.
- The current session's order count remained **0 → 0** after the rejected spoof attempt.
- End-to-end API smoke covered session, health, product list/detail, cart read/add/update/delete, checkout, order list and order detail. Expected response codes were observed: `200` for reads/add/update, `204` for delete, and `201` for successful checkout.

### Evaluation rubric

Score each dimension from 0 to 2 (0 = fail/unsafe, 1 = partial or needs human help, 2 = correct and grounded). A complete human review can total 10 points.

| Dimension | Score 0 | Score 1 | Score 2 |
| --- | --- | --- | --- |
| Intent correctness | Wrong intent | Partially/mixed intent | Expected intent |
| Extraction and groundedness | Invents or loses a key field | Minor extraction issue, safely clarified | Evidence-grounded fields; missing facts remain null/asked |
| Format and validation | Parse/schema failure or bypassed rule | Parsed but validation is incomplete | Valid schema and business constraints enforced |
| Action routing | Unsafe/wrong side effect | Safe but unclear route | Correct draft/ask/handoff/error route |
| Customer response | Incorrect/unhelpful | Correct but unclear/incomplete | Concise, accurate Vietnamese next step |

Automated results cover intent/route, schema/business side effects and selected safety invariants. Response usability and the quality of clarification must still be scored by a human during demo review; no human score is claimed in this report.

## Failure analyses and revisions

### 1. Ambiguous substrings and quantity extraction

The first FakeLLM runs exposed false matches: `giao hàng` contained the substring `gia` and was mistaken for price; one-letter variant `M` matched inside other words; long product extraction could violate the schema. The initial checkout path also attempted to write an audit row before the order row was flushed, violating its foreign key. These were corrected with word-boundary matching, bounded product text, explicit accented address patterns and an explicit flush before audit insertion. The Fake suite then passed 14/14.

Ollama evaluation then found that Qwen could omit a clearly stated quantity or read `chốt 13` as 1. Missing quantities now remain missing—backend never silently defaults to one—and an explicitly labeled/action-linked quantity is checked deterministically against the source text. Re-running the full Ollama suite produced 14/14, including both stock failures. Numeric quantities in phone/address text are not extracted because the deterministic parser requires a preceding shopping/action label.

### 2. Model output shape and safe failure

The initial Qwen output sometimes encoded `variant` as a string although the API contract requires a JSON object. Strict parsing rejected it before any order write. Prompt revision `order-extraction-v2` spells out the allowed keys, requires object-or-null for variants, and uses Ollama JSON mode with `think=false`, temperature 0 and a 4096 context. Happy-path price, stock and order cases now pass. If the provider still returns malformed JSON or times out, the API returns an error route and does not create an order.

### 3. Client trust and session boundary

Security probes verify cross-session order reads are concealed with 404 and checkout rejects client price/status fields with 422; no order was created. This is an automated demo boundary check, not a complete production security assessment. The app still uses anonymous demo sessions, local-origin allowlisting and in-process rate limiting.

## Revision notes

- Version prompt and evaluator cases; use isolated temporary SQLite databases for repeatable runs.
- Keep price, stock, SKU, ownership and order writes in server-side rules.
- Missing/uncertain quantity triggers clarification rather than an implicit one-item order.
- Explicit action-linked quantity is reconciled with the original text before stock validation.
- Keep test inputs synthetic and evaluation reports free of raw chat/contact values.

## Limits

The failure-injection cases monkeypatch the extractor to simulate invalid output/provider failure; they do not simulate an actual Ollama outage. There are 14 hand-authored cases, so language variation and response quality need broader human review. Inventory is mock data and is not decremented after draft creation. This project is a local demo, not a production checkout system.

The evaluation run emits a non-failing Starlette deprecation warning concerning its `httpx` TestClient integration. It did not affect the recorded results; revisit the dependency recommendation during a future Starlette upgrade.
