# Demo Script — Document Pipeline

**Goal:** Complete the TRD §3 7-step flow in <7 minutes.

---

## Step 1 — Upload Clean Invoice

1. Open http://localhost:8501
2. Go to **Upload** tab
3. Click **Invoice (Clean)** sample button
4. Observe the pipeline trace: load_doc → classify → extract → validate → queue_for_review
5. Confirm status shows **needs_review**

## Step 2 — Review Clean Invoice

1. Switch to **Review Queue** tab
2. Click **Review** on the clean invoice
3. Left pane: rendered PDF preview (2 pages)
4. Right pane: vendor, invoice no, dates, line items
5. Confirm all badges are **green**
6. Line items show 4 rows with correct math

## Step 3 — Edit & Approve

1. Change a line-item quantity (e.g., 40 → 41)
2. Observe the line_total badge update live
3. Click **Approve & Commit**
4. Confirm success message

## Step 4 — Database Tab

1. Switch to **Database** tab
2. Click **Invoices** sub-tab
3. Confirm the committed invoice appears with correct totals
4. Expand line items to see all 4 items
5. Click **View Document** to see the preview

## Step 5 — Receipt Image

1. Go to **Upload** tab
2. Click **Receipt** sample button
3. Observe pipeline trace (runs through image content block path)
4. Switch to **Review Queue**, approve the receipt
5. Switch to **Database → Receipts** to see the committed row

## Step 6 — Broken Invoice (Guard Rail)

1. Go to **Upload** tab
2. Click **Invoice (Broken Totals)** sample button
3. Observe trace: extract → validate fails → repair_extract → validate fails again → queue_failed
4. Switch to **Review Queue** — status shows **failed_validation** with **red badges**
5. Fix the subtotal field to match the line items
6. Click **Approve & Commit** — should succeed

## Step 7 — Unsupported Document (Guard Rail)

1. Go to **Upload** tab
2. Click **Purchase Order** sample button
3. Observe trace: classify → mark_unsupported → END
4. Note the status shows **unsupported** with a message
5. Document does not appear in Review Queue default filter

---

## Talking Points

- **No OCR:** Claude reads the PDF/image natively via the Anthropic Messages API
- **Validation is free:** math checks run in pure Python, no LLM calls
- **One repair only:** the graph enforces exactly one re-extraction attempt
- **No auto-commit:** everything stops in Review Queue — the human decides
- **Swap schemas:** changing the extraction schema is a pydantic model swap
- **Call count:** each document shows its LLM call count (≤3)
