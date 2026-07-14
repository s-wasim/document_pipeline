# Document Pipeline Frontend Linkage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Streamlit UI with the existing dc-runtime `frontend/`, served from a FastAPI monolith on port 8501, wiring every UI control to the existing (unchanged) backend functions.

**Architecture:** FastAPI serves the unbundled dc-runtime frontend as static files and exposes `/api/*` routers that call `app/upload.py`, `app/graph/runner.py`, `app/commit.py`, `app/db.py` unchanged. The frontend's `VeloAdapter` flips from mock to live (fetch + SSE); the Component's store shape is preserved so `renderVals()` is essentially unchanged.

**Tech Stack:** FastAPI, uvicorn, python-multipart, SQLAlchemy (existing), LangGraph (existing), dc-runtime (existing), React 18 UMD (vendored).

## Global Constraints
- **No backend business-logic changes.** Do not modify `app/db.py`, `app/upload.py`, `app/commit.py`, `app/validation.py`, `app/llm.py`, `app/graph/**`, `app/schemas/**`.
- Serve on **port 8501** (unchanged from Streamlit / docker-compose).
- Serializer field names/shapes must match the mock exactly: `document_id`, `source_filename`, money as strings, dates `YYYY-MM-DD`.
- Keep client-side `revalidate` in the adapter (mirror of backend rules) — do not add a `/validate` endpoint.
- No seed data. Live app starts empty.
- Frontend rendered output stays byte-identical except the single preview `<img>` edit.

---

### Task 1: API package — serializers + health
**Files:** Create `app/api/__init__.py`, `app/api/serializers.py`, `app/api/health.py`.
- `serializers.py`: `document_to_dict`, `invoice_to_dict` (+items+source_filename), `receipt_to_dict` (+source_filename), `extraction_to_dict`. Money → `str`, dates → `YYYY-MM-DD`, `created_at` → ISO.
- `health.py`: `GET /api/health` → `{db_ok, db_error}` via `SELECT 1`.
- [ ] Implement, then covered by tests in Task 8.

### Task 2: Documents router
**Files:** Create `app/api/documents.py`.
- `POST /api/documents` (multipart `file`) → `validate_upload` then `save_document` → `{document_id, filename, pages, mime}`; 400 `{error}` on validation failure.
- `POST /api/documents/sample/{sample_id}` → map id→`samples/<file>`, read bytes, same flow.
- `GET /api/documents?status=` → `document_to_dict[]` (all statuses if omitted), newest first.
- `GET /api/documents/{id}/extraction` → latest Extraction `{payload, validation_errors, repair_attempted, doc_type}`; 404 if none.
- `GET /api/documents/{id}/preview` → `{pageCount, pages:[{num, src}]}` from `data/previews/{id}/page_*.png`.
- `GET /api/documents/{id}/preview/{n}` → `FileResponse` PNG, basename-guarded.
- `POST /api/documents/{id}/process` (SSE) → run `stream_pipeline(id)` on a worker thread + `queue.Queue`; relay `event: node` `{node, summary}`, then `event: final` `{final_status, llm_calls, validation_errors}` (or `event: error`).

### Task 3: Records router
**Files:** Create `app/api/records.py`.
- `GET /api/invoices` → `invoice_to_dict[]` (Invoice join Document, newest first).
- `GET /api/receipts` → `receipt_to_dict[]`.

### Task 4: Commit / reject router
**Files:** Create `app/api/actions.py`, `app/api/schemas.py` (pydantic request bodies).
- `POST /api/documents/{id}/commit` (json = edited payload + doc_type) → `commit_invoice`/`commit_receipt` → `{success, errors}`.
- `POST /api/documents/{id}/reject` (json `{note}`) → `reject_document` → `{success}`.

### Task 5: Server + deployment swap
**Files:** Create `app/server.py`; modify `requirements.txt`, `Dockerfile`; delete `app/main.py`, `app/tabs/`.
- `server.py`: startup `init_db()` + `makedirs`; include routers; `GET /` → `frontend/index.dc.html`; mount `StaticFiles(frontend)` last.
- `requirements.txt`: drop streamlit; add `fastapi`, `uvicorn[standard]`, `python-multipart`.
- `Dockerfile`: CMD → `uvicorn app.server:app --host 0.0.0.0 --port 8501`.

### Task 6: Unbundle frontend to served layout
**Files:** Create `frontend/index.dc.html`, `frontend/support.js`, `frontend/adapter.js`, `frontend/vendor/react*.js`, `frontend/fonts/*.woff2`; delete `frontend/DocumentPipeline.html`.
- Extract template.html → `index.dc.html`; rewrite font UUID `src` → `./fonts/<uuid>.woff2`; script srcs → `./support.js`, `./adapter.js`.
- Inject `window.__resources` map (React CDN → `./vendor/*`) before support.js.
- Edit the 3 preview blocks: `sc-camel-dangerously-set-inner-h-t-m-l="{{ pg.html }}"` → `<img ... src="{{ pg.src }}">`.

### Task 7: adapter.js — LIVE mode
**Files:** `frontend/adapter.js` (the extracted VeloAdapter, edited).
- `API_BASE = window.location.origin`. Keep helpers + `validateFile` + `revalidate`.
- Add `getDocuments/getInvoices/getReceipts/getExtraction/getPreview/getHealth`, `uploadFile/uploadSample`, `processDocument(id, handlers)` (SSE reader → cancel fn), `commit/reject`. Trim `SAMPLES` to display metadata.

### Task 8: Component rewiring (inline in index.dc.html)
- `componentDidMount`: async load store (documents/invoices/receipts) + `getHealth()` poll (health pill).
- Upload paths → `uploadFile`/`uploadSample` then SSE run.
- Replace `_stepRun`/`_finishRun` with SSE progression (`onNode` appends node + advances stepIndex; `onFinal` sets terminal + reloads store).
- `_ensureEditPayload` → `getExtraction`; preview lazy-load via `getPreview`; `_renderPreviewPages` → `{num, src}`.
- `approveCommit`/`rejectDoc` → real POST + reload store.

### Task 9: API tests
**Files:** Create `tests/test_api.py`.
- In-memory SQLite (`StaticPool`, `check_same_thread:False`), seed a Document/Invoice/Receipt/Extraction, TestClient over the 4 routers. Cover health, upload validation (reject bad type/size), lists, extraction+404, commit/reject, preview traversal guard/404, SSE frame sequence (`stream_pipeline` mocked).

### Task 10: Full live Docker E2E verification
- `docker compose up -d --build`; wait healthy; browser-drive: sample process (live SSE + real LLM) → review/commit → Database → reject → PO/unsupported → broken-totals repair → health pill. Confirm `pytest` green in-container or venv.

## Self-Review
- Spec §2.3 endpoints → Tasks 1–4. Frontend unbundle §2.1 → Task 6. Adapter §3.1 → Task 7. Component §3.2 → Task 8. Template edit §3.3 → Task 6. Deployment §5 → Task 5. Tests → Task 9. Verification §4.4 → Task 10. No gaps.
- No placeholders; contracts named consistently (`document_to_dict`, `processDocument`, `getPreview`).
