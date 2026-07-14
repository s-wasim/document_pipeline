# Document Pipeline — Frontend Linkage Design

**Date:** 2026-07-14
**Goal:** Replace the Streamlit UI entirely with the existing `frontend/` dc-runtime
app, served from a FastAPI monolith. Every UI control is wired to a real backend
function. **No backend business logic changes** — only the UI layer swaps and the
Streamlit UI files are removed.

---

## 1. Current state

### Backend business logic (MUST NOT CHANGE)
- `app/db.py` — SQLAlchemy models: `Document`, `Extraction`, `Invoice`,
  `InvoiceItem`, `Receipt`; `get_session`, `init_db`.
- `app/upload.py` — `validate_upload(filename, content) -> str|None`,
  `save_document(filename, content) -> int` (writes file, renders previews,
  inserts `Document` with status `processing`), `render_previews` (writes
  `data/previews/{doc_id}/page_N.png`).
- `app/graph/*` — LangGraph pipeline. Nodes: `load_doc → classify → extract →
  validate → {queue_for_review | repair_extract→validate | queue_failed}`, with
  `classify → mark_unsupported` for non invoice/receipt types. `classify` and
  `extract` make **real Anthropic LLM calls**.
- `app/graph/runner.py` — `stream_pipeline(document_id)` yields one
  `{"final": False, "event": {node_name: summary}}` per completed node, then a
  `{"final": True, "success", "final_status", "llm_calls", "validation_errors",
  "events"}` summary. It also persists the terminal `Document.status`/`llm_calls`.
- `app/commit.py` — `commit_invoice(doc_id, edited) -> (bool, errors)`,
  `commit_receipt(...)`, `reject_document(doc_id, note) -> bool`.
- `app/validation.py`, `app/schemas/*` — payload parsing + validation rules.

### Streamlit UI (TO BE REMOVED)
- `app/main.py`, `app/tabs/upload.py`, `app/tabs/review.py`, `app/tabs/database.py`.

### Frontend (`frontend/DocumentPipeline.html`)
A self-unpacking **dc-runtime bundle** (base64+gzip manifest, self-rewrites to
blob URLs at load). It contains:
- `support.js` (dc-runtime template engine).
- **`VeloAdapter`** — a purpose-built mock adapter (`API_BASE = null`) with every
  real endpoint documented in comments; explicitly designed for a live swap.
- An inline `<script type="text/x-dc" data-dc-script>` **Component** (`class
  Component extends DCLogic`) holding all UI state and an in-memory mock store.
- Vendored React/ReactDOM UMD + Inter/JetBrains Mono fonts.

The mock is fully client-side: canned pipeline animations (`SAMPLES[*].nodes`
with hardcoded delays), an in-memory `seedStore`, and HTML-synthesized document
previews. Node keys, branch topology, statuses, and field/validation shapes
already match the backend 1:1.

---

## 2. Target architecture

Monolithic FastAPI app on **port 8501** that (a) serves the unbundled dc-runtime
frontend as static files and (b) exposes `/api/*` endpoints which call the
existing backend functions unchanged.

```
browser ──HTTP/SSE──▶ FastAPI (app/server.py, :8501)
                         ├── GET /                → index.dc.html
                         ├── /support.js, /adapter.js, /vendor/*, /fonts/*  (static)
                         └── /api/*  (routers)    → app/upload, app/graph/runner,
                                                    app/commit, app/db  (UNCHANGED)
```

### 2.1 Unbundle the frontend (served layout)
Extract the bundle into a normal dc-runtime directory (rendered UI is
byte-identical — same template + support.js + Component):

```
frontend/
  index.dc.html      # template.html, with asset UUIDs rewritten to local paths;
                     #   loads support.js, adapter.js, then the inline Component
  support.js         # dc-runtime engine (asset 280cfee1)
  adapter.js         # VeloAdapter, rewired to LIVE mode (this is the only JS that
                     #   changes behaviour; see §3)
  vendor/
    react.production.min.js
    react-dom.production.min.js
  fonts/*.woff2      # the 13 Inter/JetBrains woff2 assets
```

- A `window.__resources = { "<react CDN url>": "./vendor/react.production.min.js",
  ... }` map is injected before `support.js` so `loadReactUmd()` resolves React
  from the local vendor copies (offline, same pattern as inbound_lead_responder).
- Font `@font-face src` URLs in the template’s `<helmet>` are rewritten from
  UUIDs to `./fonts/*.woff2`.
- The original `frontend/DocumentPipeline.html` bundle is removed (replaced by the
  served layout). No behavioural change to the rendered app.

### 2.2 FastAPI server — `app/server.py`
- On startup: `os.makedirs("data/...")`, `init_db()`. **No seed** (see §4).
- Mount API routers under `/api`, then serve the frontend: `GET /` →
  `index.dc.html`; `StaticFiles` for the rest. Routers registered before the
  catch-all static mount.
- CMD: `uvicorn app.server:app --host 0.0.0.0 --port 8501`.

### 2.3 API endpoints (`app/api/`)

| Method & path | Backend call | Returns |
|---|---|---|
| `GET /api/health` | `SELECT 1` on a session | `{db_ok, db_error}` |
| `POST /api/documents` (multipart `file`) | `validate_upload` → `save_document` | `{document_id, filename, pages, mime}` or 400 `{error}` |
| `POST /api/documents/sample/{sample_id}` | read `samples/<file>` → `validate_upload` → `save_document` | same as above |
| `POST /api/documents/{id}/process` (**SSE**) | iterate `stream_pipeline(id)` | `event: node`/`event: final`/`event: error` frames |
| `GET /api/documents?status=` | query `Document` | `Doc[]` (id, filename, doc_type, pages, llm_calls, status, note, created_at) |
| `GET /api/documents/{id}/extraction` | latest `Extraction` for doc | `{payload, validation_errors, repair_attempted, doc_type}` or 404 |
| `GET /api/documents/{id}/preview` | list `data/previews/{id}/*.png` | `{pageCount, pages:[{num, src}]}` |
| `GET /api/documents/{id}/preview/{n}` | `FileResponse` of `page_{n}.png` | PNG (path-safe) |
| `GET /api/invoices` | `Invoice` join `Document` | `Invoice[]` (+ items, source_filename) |
| `GET /api/receipts` | `Receipt` join `Document` | `Receipt[]` (+ source_filename) |
| `POST /api/documents/{id}/commit` (json payload) | `commit_invoice`/`commit_receipt` by doc_type | `{success, errors}` |
| `POST /api/documents/{id}/reject` (json `{note}`) | `reject_document` | `{success}` |

**Serialization** (`app/api/serializers.py`) matches the mock field names/shapes
exactly (`document_id`, `source_filename`, money as strings, dates as
`YYYY-MM-DD`) so the Component’s `renderVals()` and template need no shape
changes.

**SSE processing:** the `/process` endpoint runs `stream_pipeline(id)` on a worker
thread and relays each yielded event as an SSE frame. `event: node` carries
`{node, summary}` (the per-node `{doc_type, llm_calls, validation_errors,
repair_attempted}`); `event: final` carries `{final_status, llm_calls,
validation_errors}`. Terminal per-node `confidence` is not surfaced by
`stream_pipeline` and is omitted from the terminal card (cosmetic only) — the
backend is not modified to expose it.

---

## 3. Frontend (`adapter.js` + Component) wiring

### 3.1 `adapter.js` — LIVE mode
`API_BASE = window.location.origin`. Pure helpers (`toCents`, `fmtMoney`,
`validateFile`, **`revalidate`** — kept client-side by design) are unchanged.
Data functions become real:
- `getHealth()` → `GET /api/health` (fallback `{db_ok:false,...}` on network error).
- `getDocuments(status?)`, `getInvoices()`, `getReceipts()`, `getExtraction(id)`,
  `getPreview(id)` → the GET endpoints above.
- `uploadFile(file)` → `POST /api/documents` (multipart).
- `uploadSample(sampleId)` → `POST /api/documents/sample/{id}`.
- `processDocument(id, handlers)` → SSE reader dispatching `onNode`/`onFinal`/
  `onError`; returns a cancel fn.
- `commit(id, payload)` → `POST /api/documents/{id}/commit`.
- `reject(id, note)` → `POST /api/documents/{id}/reject`.
- `SAMPLES` keeps only display metadata (label, id) used by the chip row; the
  canned `nodes`/`payload`/`preview` data is dropped (server now drives runs).

### 3.2 Component — data source swap (UI layer only)
The **store shape stays identical** (`{documents, invoices, receipts, extractions,
previews}`), so `renderVals()` is essentially unchanged. Only the methods that
produced mock data are rewired:
- `componentDidMount` → load store via `getDocuments()/getInvoices()/getReceipts()`;
  start a `getHealth()` poll (updates the health pill — real, no simulate toggle).
- Upload paths (`acceptFile`+`startRunClick`, `handleSampleClick`, drop) →
  `uploadFile`/`uploadSample` then open an SSE run.
- `startRun`/`_stepRun`/`_finishRun` → replaced by SSE-driven progression:
  each `onNode` appends to `run.nodes` and advances `stepIndex` (feeding the
  existing active/lit/dimmed/failed derivation in `renderVals`); `onFinal` sets
  the terminal marker from `final_status` and reloads the store so the doc appears
  in Review/Database.
- `_ensureEditPayload(docId)` → `getExtraction(id)` into `store.extractions[id]`,
  then client-side `revalidate`.
- Preview: `getPreview(id)` into `store.previews[id]`; `_renderPreviewPages`
  returns `{num, src}` image descriptors.
- `approveCommit` → client `revalidate` gate (unchanged) then `commit(...)`, on
  success reload store. `rejectDoc` → `reject(...)` then reload store.

### 3.3 Template — one edit
The three preview blocks currently use
`sc-camel-dangerously-set-inner-h-t-m-l="{{ pg.html }}"`. These change to an
`<img src="{{ pg.src }}">` so the Review and Database previews show the **real
rendered PNG pages** (`render_previews` output). No other template changes.

---

## 4. Decisions (confirmed with user)
1. **Preview source:** real PNG page images from `render_previews`, served via
   `/api/documents/{id}/preview[/n]`.
2. **First-load data:** start empty. No seed module (avoids new backend code);
   the demo is driven by upload → process → commit.
3. **Processing model:** SSE live streaming of real node-completion events.
4. **Verification:** full live Docker E2E (postgres + uvicorn + real LLM calls).

## 5. Deployment / tooling changes
- `requirements.txt`: drop `streamlit`; add `fastapi`, `uvicorn[standard]`,
  `python-multipart` (multipart upload). Keep everything else.
- `Dockerfile`: CMD → uvicorn on 8501. (`docker-compose.yml` unchanged: still
  maps 8501, postgres, `ANTHROPIC_API_KEY`, mounts `./data` + `./samples`.)
- Delete `app/main.py`, `app/tabs/`.
- `tests/test_api.py`: TestClient over the routers on in-memory SQLite
  (`StaticPool`, shared connection for the worker thread), covering health,
  upload validation, document/invoice/receipt lists, extraction, commit/reject,
  preview path-safety, and the SSE frame sequence (with `stream_pipeline` mocked).

## 6. Explicit non-goals
- No change to any file under `app/graph/`, `app/schemas/`, and no change to
  `app/db.py`, `app/upload.py`, `app/commit.py`, `app/validation.py`, `app/llm.py`.
- No new seed/business logic.
- No visual redesign — the rendered UI matches the current bundle.

## 7. Risks
- **LLM latency/variance:** real `classify`/`extract` calls make live runs slower
  and non-deterministic vs. the canned mock. Acceptable — it is the real pipeline.
- **Extraction payload date formats:** `Extraction.payload` stores raw model
  output; the editor expects `YYYY-MM-DD` strings. Serializer passes payload
  through as-is (same as Streamlit review tab did). No transformation added.
- **Preview absence:** if `render_previews` produced no page for a doc, the
  preview endpoint returns an empty `pages` list; the UI shows its existing empty
  state.
