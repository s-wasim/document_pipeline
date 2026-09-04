# Document Pipeline

A demontration of a structured extraction pipeline: upload PDFs/images → classify → extract → validate → review → commit to PostgreSQL. Uses Claude's native PDF and vision input (no OCR service).

## Quickstart

```bash
cp .env.example .env
# Edit .env — set your ANTHROPIC_API_KEY

docker compose up --build
```

Open http://localhost:8501.

### Reset

```bash
docker compose down -v
```

## What it does

1. **Upload** a PDF or image → the pipeline runs with a live node trace
2. Document lands in **Review Queue** with side-by-side preview vs. extracted fields
3. Edit any field, then **Approve & Commit** → rows written to the database
4. **Database** tab shows committed documents

### Sample documents

| File | Type | Expected result |
|------|------|-----------------|
| `invoice_clean.pdf` | Invoice, 2 pages, 4 line items | Clean extraction, all-green badges |
| `receipt.jpg` | Grocery receipt image | Receipt committed |
| `invoice_broken_totals.pdf` | Invoice where line totals don't sum | Validation fails, repair runs, `failed_validation` |
| `purchase_order.pdf` | Purchase order | Classified unsupported, parked |

## Architecture

- **Monolith** — Streamlit app calls LangGraph in-process; no queue/worker
- **Pipeline** (LangGraph): `load_doc → classify → extract → validate → (repair loop once) → review queue`
- **Human-in-the-loop** outside the graph: Approve/Reject are app actions
- **LLM budget** ≤3 calls per document (classify + extract + optional repair)

## Structure

```
document_pipeline/
├── app/
│   ├── main.py              # Streamlit entry point
│   ├── db.py                # SQLAlchemy models (5 tables)
│   ├── llm.py               # ChatAnthropic factory + content block helpers
│   ├── upload.py            # File validation, storage, preview rendering
│   ├── validation.py        # Cross-field math checks (no LLM)
│   ├── commit.py            # Transactional approve & commit
│   ├── schemas/             # Pydantic extraction schemas
│   ├── graph/               # LangGraph state, builder, nodes
│   └── tabs/                # Streamlit tab pages
├── samples/                 # Generated sample documents
├── scripts/                 # Sample generator
├── tests/                   # pytest suite (69 tests)
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```
