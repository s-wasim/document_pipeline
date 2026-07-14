(function(){
"use strict";
// ============================================================================
// VeloRelAI "Document Pipeline" — LIVE API ADAPTER
// ----------------------------------------------------------------------------
// Single source of truth for all data access. Talks to the FastAPI backend
// served from the same origin as this page. Pure helpers (money math,
// validateFile, revalidate) are kept client-side by design and are unchanged
// from the original mock; only the data-fetching functions are now live.
// ============================================================================

const API_BASE = window.location.origin;

async function getJson(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Money helpers — integer-cents arithmetic. NEVER use raw float +/- on money.
// ---------------------------------------------------------------------------
function toCents(n) { return Math.round((Number(n) || 0) * 100); }
function fromCents(c) { return c / 100; }
function fmtMoney(amount, currency) {
  const n = Number(amount);
  if (!isFinite(n)) return (currency || '') + ' —';
  return (currency ? currency + ' ' : '') + n.toFixed(2);
}
function fmtDate(d) { return d || '—'; }

// ---------------------------------------------------------------------------
// GET /api/health -> { db_ok, db_error }
// ---------------------------------------------------------------------------
async function getHealth() {
  try {
    return await getJson('/api/health');
  } catch (e) {
    return { db_ok: false, db_error: (e && e.message) || String(e) };
  }
}

// ---------------------------------------------------------------------------
// Client-side pre-validation copy (mirrors backend upload endpoint exactly).
// ---------------------------------------------------------------------------
const MAX_MB = 15;
const MAX_PAGES = 20;
const ACCEPTED_TYPES = ['application/pdf', 'image/png', 'image/jpeg'];

function validateFile(file, assumedPages) {
  const sizeMb = file.size / (1024 * 1024);
  if (sizeMb > MAX_MB) {
    return `File exceeds 15 MB limit (${sizeMb.toFixed(1)} MB)`;
  }
  if (!ACCEPTED_TYPES.includes(file.type)) {
    return 'Unsupported file type. Accepted: PDF, PNG, JPG';
  }
  if (assumedPages && assumedPages > MAX_PAGES) {
    return `Document exceeds 20-page limit (${assumedPages} pages)`;
  }
  return null;
}

// ---------------------------------------------------------------------------
// VALIDATION RULES — pure client-side, mirrors backend Python exactly.
// ---------------------------------------------------------------------------
function revalidate(docType, payload) {
  const fieldErrors = {};
  const itemErrors = [];
  const allErrors = [];

  function addField(name, msg) {
    if (!fieldErrors[name]) fieldErrors[name] = [];
    fieldErrors[name].push(msg);
    allErrors.push(msg);
  }

  if (docType === 'invoice') {
    if (!payload.vendor || !String(payload.vendor).trim()) addField('vendor', 'Vendor is required');
    if (!payload.invoice_no || !String(payload.invoice_no).trim()) addField('invoice_no', 'Invoice number is required');

    const items = payload.items || [];
    let sumCents = 0;
    items.forEach((it, idx) => {
      const i = idx + 1;
      const errs = [];
      if (!it.description || !String(it.description).trim()) {
        errs.push(`Item ${i}: description is required`);
      }
      const qty = Number(it.qty) || 0;
      const unit = Number(it.unit_price) || 0;
      const lineTotal = Number(it.line_total) || 0;
      const expectedCents = Math.round(qty * unit * 100);
      const lineCents = toCents(lineTotal);
      if (Math.abs(expectedCents - lineCents) > 2) {
        const expected = fromCents(expectedCents).toFixed(2);
        const diff = fromCents(Math.abs(expectedCents - lineCents)).toFixed(2);
        errs.push(`Item ${i} ('${it.description || ''}'): qty ${qty} × unit_price ${unit.toFixed(2)} = ${expected}, but line_total is ${lineTotal.toFixed(2)} (diff ${diff})`);
      }
      sumCents += lineCents;
      itemErrors[idx] = errs;
      errs.forEach(e => allErrors.push(e));
    });

    const subtotal = Number(payload.subtotal) || 0;
    const tax = Number(payload.tax) || 0;
    const total = Number(payload.total) || 0;
    const subtotalCents = toCents(subtotal);
    const taxCents = toCents(tax);
    const totalCents = toCents(total);

    if (subtotalCents < 0) addField('subtotal', `Subtotal cannot be negative: ${subtotal.toFixed(2)}`);
    if (taxCents < 0) addField('tax', `Tax cannot be negative: ${tax.toFixed(2)}`);
    if (totalCents < 0) addField('total', `Total cannot be negative: ${total.toFixed(2)}`);

    if (Math.abs(sumCents - subtotalCents) > 2) {
      const sum = fromCents(sumCents).toFixed(2);
      const diff = fromCents(Math.abs(sumCents - subtotalCents)).toFixed(2);
      addField('subtotal', `Subtotal mismatch: sum of line items = ${sum}, declared subtotal = ${subtotal.toFixed(2)} (diff ${diff})`);
    }
    const calcTotalCents = subtotalCents + taxCents;
    if (Math.abs(calcTotalCents - totalCents) > 2) {
      const calc = fromCents(calcTotalCents).toFixed(2);
      const diff = fromCents(Math.abs(calcTotalCents - totalCents)).toFixed(2);
      addField('total', `Total mismatch: subtotal ${subtotal.toFixed(2)} + tax ${tax.toFixed(2)} = ${calc}, but declared total is ${total.toFixed(2)} (diff ${diff})`);
    }
  } else if (docType === 'receipt') {
    if (!payload.merchant || !String(payload.merchant).trim()) addField('merchant', 'Merchant is required');
    const total = Number(payload.total) || 0;
    if (toCents(total) < 0) addField('total', `Total cannot be negative: ${total.toFixed(2)}`);
  }

  return { field_errors: fieldErrors, item_errors: itemErrors, all_errors: allErrors };
}

// ---------------------------------------------------------------------------
// Collection reads.
// ---------------------------------------------------------------------------
function getDocuments(status) {
  return getJson('/api/documents' + (status ? `?status=${encodeURIComponent(status)}` : ''));
}
function getInvoices() { return getJson('/api/invoices'); }
function getReceipts() { return getJson('/api/receipts'); }
function getExtraction(docId) { return getJson(`/api/documents/${docId}/extraction`); }
function getPreview(docId) { return getJson(`/api/documents/${docId}/preview`); }

// ---------------------------------------------------------------------------
// Uploads -> POST /api/documents (multipart) / sample loader.
// Both resolve to { document_id, filename, pages, mime } or { error }.
// ---------------------------------------------------------------------------
async function uploadFile(file) {
  const fd = new FormData();
  fd.append('file', file, file.name);
  const res = await fetch(`${API_BASE}/api/documents`, { method: 'POST', body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) return { error: data.error || data.detail || `HTTP ${res.status}` };
  return data;
}

async function uploadSample(sampleId) {
  const res = await fetch(`${API_BASE}/api/documents/sample/${encodeURIComponent(sampleId)}`, { method: 'POST' });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) return { error: data.error || data.detail || `HTTP ${res.status}` };
  return data;
}

// ---------------------------------------------------------------------------
// POST /api/documents/{id}/process — Server-Sent Events live node trace.
// Dispatches frames to onNode({node,summary}), onFinal({final_status,llm_calls,
// validation_errors}), onError({message}). Returns a cancel function.
// ---------------------------------------------------------------------------
function processDocument(docId, handlers) {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${API_BASE}/api/documents/${docId}/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        const text = await res.text().catch(() => '');
        handlers.onError && handlers.onError({ message: text || `HTTP ${res.status}` });
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });

        let idx;
        while ((idx = buf.indexOf('\n\n')) !== -1) {
          const frame = buf.slice(0, idx);
          buf = buf.slice(idx + 2);

          const eventMatch = /^event:\s*(.+)$/m.exec(frame);
          const dataMatch = /^data:\s*(.+)$/m.exec(frame);
          if (!eventMatch || !dataMatch) continue;

          const eventName = eventMatch[1].trim();
          let data;
          try { data = JSON.parse(dataMatch[1]); } catch { continue; }

          const handlerName = 'on' + eventName[0].toUpperCase() + eventName.slice(1);
          const handler = handlers[handlerName];
          if (handler) handler(data);
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        handlers.onError && handlers.onError({ message: (e && e.message) || String(e) });
      }
    }
  })();

  return () => controller.abort();
}

// ---------------------------------------------------------------------------
// Write actions.
// ---------------------------------------------------------------------------
async function commit(docId, docType, payload) {
  try {
    const res = await fetch(`${API_BASE}/api/documents/${docId}/commit`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doc_type: docType, payload }),
    });
    if (!res.ok) return { success: false, errors: [`HTTP ${res.status}`] };
    return res.json();
  } catch (e) {
    return { success: false, errors: [(e && e.message) || String(e)] };
  }
}

async function reject(docId, note) {
  try {
    const res = await fetch(`${API_BASE}/api/documents/${docId}/reject`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note }),
    });
    if (!res.ok) return { success: false };
    return res.json();
  } catch (e) {
    return { success: false };
  }
}

window.VeloAdapter = {
  API_BASE, toCents, fromCents, fmtMoney, fmtDate,
  MAX_MB, MAX_PAGES, ACCEPTED_TYPES, validateFile, revalidate,
  getHealth, getDocuments, getInvoices, getReceipts, getExtraction, getPreview,
  uploadFile, uploadSample, processDocument, commit, reject,
};
})();
