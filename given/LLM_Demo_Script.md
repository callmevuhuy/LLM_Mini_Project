# Group 7 — Inherited LLM demo script (6–7 minutes)

> This runbook covers the predecessor LLM application, not the required RAG demo.

Use synthetic customer details only. Ollama must be running and `qwen3.5:2b-q4_K_M` available. A FakeLLM run is a stable fallback if the local model is unavailable.

## Before the demo

PowerShell terminal 1:

```powershell
cd backend
$env:LLM_PROVIDER = "ollama"
$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
$env:OLLAMA_MODEL = "qwen3.5:2b-q4_K_M"
$env:LLM_TIMEOUT_SECONDS = "30"
..\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

PowerShell terminal 2:

```powershell
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173`. Keep the host as `127.0.0.1` so the demo session cookie matches the API origin.

## Run of show

| Time | Show | Narration / expected result |
| --- | --- | --- |
| 0:00–0:45 | Storefront | Introduce Group 7, mock catalog, search/product cards and that all catalog/cart data comes from FastAPI + SQLite. |
| 0:45–1:30 | Product and cart | Select a product variant and quantity, add it to cart. Point out that the server derives price and availability from catalog data. |
| 1:30–2:30 | Chat: price and stock | Ask “Giá Cà phê rang xay Đà Lạt loại 250g xay phin bao nhiêu?” and “Bình giữ nhiệt Everyday màu Kem 750ml còn hàng không?”. Responses use backend catalog facts. |
| 2:30–3:30 | Clear order | Ask “Chốt 2 Áo thun basic cotton màu Xanh size M, tên là Demo Buyer, số điện thoại 0901234567, địa chỉ giao hàng 123 Demo Street, Quận 7.” The assistant summarizes a draft as pending confirmation. Do not use real contact information. |
| 3:30–4:15 | Clarification and inventory | Ask “Mình muốn đặt Áo thun basic cotton màu Xanh size M.” The assistant asks for quantity and contact details. Then show a catalog variant that is unavailable or a quantity above stock; no invalid order should be created. |
| 4:15–5:00 | Injection and handoff | Send an instruction to reveal a key/delete orders alongside a valid product request. Show that the assistant does not disclose secrets or delete data. Ask to cancel an unspecified order; it should hand off rather than mutate an order. |
| 5:00–6:00 | API/security evidence | Show `/docs` and explain that cross-session order reads return 404 and spoofed checkout price/status fields return 422. Share `LLM_Evaluation_Results.md` and the two JSON reports. |
| 6:00–6:45 | Architecture and limitations | Explain LLM extraction vs server-side validation, why no fine-tuning is needed for this small MVP, and limits: mock inventory, anonymous demo session, one-item chat order, no payment or real staff messaging. |

## Suggested Q&A points

- LLM converts free text into structured intent/entity data; it does not determine price, stock, ownership or payment state.
- JSON syntax alone is not proof of a valid order: Pydantic, product/variant mapping, stock and session ownership checks remain server-side.
- Prompt delimiters and untrusted-input wording help, but authorization and action controls are enforced in code.
- Missing quantity is clarified rather than guessed. If Ollama asks for a quantity in the over-stock example, say that the backend fails closed; use the catalog UI/API to demonstrate the known inventory rule.
- The evaluation contains 14 cases per provider, with synthetic fixtures. It is useful evidence for this demo, not a guarantee for arbitrary chat messages.
