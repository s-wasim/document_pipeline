import json
import logging

from langchain_core.messages import HumanMessage

from app.graph.state import DocState
from app.llm import get_llm, make_page_preview_block

logger = logging.getLogger(__name__)

CLASSIFY_PROMPT = """You are a document classifier. Look at this document page and determine its type.

Respond with a JSON object:
{
  "doc_type": "invoice" | "receipt" | "purchase_order" | "other",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<brief explanation>"
}

Rules:
- invoice: contains line items with quantities, unit prices, subtotal, tax, total. Usually has "INVOICE" header, invoice number, vendor info.
- receipt: from a retailer showing items purchased, total paid, payment method. Usually smaller total amounts.
- purchase_order: a request to purchase goods. Usually has "PURCHASE ORDER" header, PO number, ship-to address.
- other: anything that doesn't fit the above categories.

Return ONLY valid JSON, no other text."""


def classify_node(state: DocState) -> DocState:
    logger.info("Classifying document %s", state["document_id"])
    llm = get_llm()

    preview_block = make_page_preview_block(state["file_path"], state["mime"], page=0)

    msg = HumanMessage(
        content=[{"type": "text", "text": CLASSIFY_PROMPT}, preview_block]
    )

    try:
        response = llm.invoke([msg])
        raw = response.content.strip()

        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        result = json.loads(raw)
        doc_type = result.get("doc_type", "other")
        confidence = result.get("confidence", 0.0)

        if doc_type not in ("invoice", "receipt", "purchase_order", "other"):
            doc_type = "other"

        state["doc_type"] = doc_type
        state["confidence"] = confidence
        state["llm_calls"] += 1
        logger.info("Classified as %s (confidence: %.2f)", doc_type, confidence)
    except Exception as e:
        logger.warning("Classification failed: %s", e)
        state["doc_type"] = "other"
        state["confidence"] = 0.0
        state["llm_calls"] += 1

    return state
