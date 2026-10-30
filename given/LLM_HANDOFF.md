# HANDOFF — Group 7 AI Live Commerce Order Assistant

> Archived handoff for the predecessor LLM project. Its publication instructions and status are historical and do not describe the current RAG implementation.

**Last updated:** 2026-10-20  
**Repository:** `D:\VSCode\Project\LLM`  
**Current Git branch:** `main`

## 1. Project goal

Build a local, Vietnamese-language marketplace demo with a Shopee-inspired layout and a fixed interactive shopping assistant in the bottom-right corner. Customers can browse a mock catalog, manage a session-scoped cart, create a draft order, and ask the assistant about product price, stock, order creation, or draft updates.

The chosen stack is **React + Vite**, **FastAPI**, **SQLAlchemy + SQLite**, with **FakeLLM** as the offline default and optional **Ollama** (`qwen3.5:2b-q4_K_M`). The LLM extracts intent and fields only. Backend code remains authoritative for SKU mapping, price, stock, session ownership, order state, validation, and database writes. The interface uses Group 7 branding and mock assets; the Shopee screenshot is visual guidance, not an asset to copy.

## 2. What is done

- **Phase A — marketplace foundation:** FastAPI/SQLite setup, repeatable seed catalog (3 products / 12 variants), health/catalog API, and React marketplace storefront.
- **Phase B — cart and draft checkout:** opaque HttpOnly demo session cookie, SQLite cart, variant/quantity handling, checkout to `pending_confirmation`, order listing/detail scoped to session, price snapshots, and audit log.
- **Phase C — assistant:** chat widget and session-aware API, FakeLLM and optional Ollama providers, intent/extraction validation, grounded price/stock responses, controlled draft creation/update, clarification state, idempotency, and metadata-only chat logging.
- **Phase D — evaluation and demo:** 14 chat cases for each provider, rubric and failure analyses, isolated-SQLite API/security probes, and a 6–7 minute demo script.
- **Docs and packaging:** the predecessor README separated FakeLLM/Ollama setup; its source requirements/workflow/reference material and reports are archived under `given/`.
- **Recorded verification (2026-10-20):** FakeLLM 14/14, Ollama 14/14, API workflow/security probes passed, frontend production build passed, and a browser smoke confirmed storefront/chat interaction. See [`LLM_Project_Report.md`](LLM_Project_Report.md) and [`LLM_Evaluation_Results.md`](LLM_Evaluation_Results.md) for scope and limitations.

## 3. Current project map

- `../README.md` — current RAG project entry point; predecessor run instructions are archived there and in this folder.
- `LLM_Project_Requirements.md` — original predecessor requirements.
- `LLM_Workflow.md` — predecessor workflow, architecture principles, phase checklist/log.
- `LLM_Architecture.md` — inherited components, data model, session and business rules.
- `LLM_Evaluation_Results.md` — predecessor evaluation rubric, results and failure analysis.
- `LLM_Demo_Script.md` — predecessor timed demo plan.
- `LLM_Project_Report.md` — predecessor verification report.
- `backend/` — FastAPI application and SQLite integration.
- `frontend/` — React/Vite storefront and chat widget.
- `eval/` — fixtures, runner, and provider result reports.
- `data/` — catalog seed source.

## 4. What to do next

The MVP phases are complete. Continue in this order, depending on the intended handoff:

1. **Finish GitHub publication:** confirm the `origin` URL and authenticate in terminal with a GitHub account that has write permission to the repository, then push `main`. The earlier push attempt was rejected because GitHub authenticated the request as `Vux147`, which lacked write permission to `callmevuhuy/LLM_Mini_Project`. Changing `git config user.name` does not change GitHub authentication. Never put a token in source files or commit it.
2. **Run the demo from a clean setup:** follow README from virtual-environment creation through backend/frontend startup. Use FakeLLM for a no-model demo; use Ollama only after confirming the service and model are available.
3. **Do a human acceptance pass:** manually complete browse → select variant → cart → checkout and chat flows at desktop and narrow/mobile widths. Record clarity/accessibility issues and manually score response quality using the evaluation rubric; automated fixture scores are not human quality scores.
4. **Choose post-MVP scope before implementation:** likely follow-ups are migrations, production authentication/CSRF, shared rate limiting for multiple workers, multi-item chat order entry, and real staff handoff. These are explicitly not required for the local demo; do not add real payment or customer data without a separate requirement.

## 5. Known limitations and safety boundaries

- Demo sessions are anonymous and intended for local use, not production identity/authentication.
- No migration framework; schema startup uses SQLAlchemy `create_all`.
- Chat order creation handles one item at a time. Draft orders do not take payment, reserve stock, or decrement inventory.
- Handoff tells the customer that staff help is needed; it does not contact a real staff member.
- Rate limiting is per process. Evaluation covers 14 authored cases per provider and does not establish general language quality.
- Provider failure cases are injected at the extractor boundary; a real Ollama outage/timeout was not induced in the reported run.
- Use synthetic names, phone numbers, and addresses in demos. Keep `.env`, databases, virtual environments, caches, and build output out of Git as configured by `.gitignore`.

## 6. Quick start reference

From the repository root in PowerShell, create and install the backend environment:

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

Start the backend in FakeLLM mode in one terminal:

```powershell
$env:LLM_PROVIDER = "fake"
cd backend
..\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Start the frontend in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. For Ollama configuration and evaluation commands, use README as the source of truth.

## 7. Handoff rule

Before changing predecessor behavior, read `LLM_Project_Requirements.md`, `LLM_Workflow.md`, the root README, and `LLM_Architecture.md`. Update docs when API contracts, behavior, setup, phase status, or verification results change. Report only checks that were actually run, and preserve the backend trust boundary described above.
