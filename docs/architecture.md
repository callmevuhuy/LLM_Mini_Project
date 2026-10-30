# System Architecture

Tài liệu kiến trúc triển khai hiện tại, ranh giới bảo mật, ingestion và giới hạn được duy trì tại [`given/RAG_Architecture.md`](../given/RAG_Architecture.md). Quy trình dự án và trạng thái từng giai đoạn tại [`given/RAG_Workflow.md`](../given/RAG_Workflow.md).

```text
React/Vite
  -> FastAPI: session + origin + demo role token checks
       -> router
            -> RAG: role-filtered local lexical retrieval + citations
            -> existing order flow: backend/SQLite validation
            -> safe handoff
```

Operational facts (SKU, price, inventory, orders) remain authoritative in SQLite. The RAG corpus is read-only for business actions. Current local index uses hashed n-gram term-frequency vectors, not a semantic embedding model.
