import logging

from langchain_core.messages import HumanMessage

from app.graph.state import DocState
from app.llm import get_llm, content_block_for_file
from app.schemas.invoice import InvoicePayload
from app.schemas.receipt import ReceiptPayload

logger = logging.getLogger(__name__)

INVOICE_EXTRACT_PROMPT = """You are a data extraction specialist. Extract invoice data from this document
matching the required schema exactly.

IMPORTANT:
- Return money values as strings (e.g., "150.00"), NOT numbers with commas
- Do NOT include currency symbols in money values
- Extract ALL line items visible in the document
- This is a DEMO — extract the best available data

Example item: {"description": "Consulting Services", "qty": "40", "unit_price": "150.00", "line_total": "6000.00"}"""

RECEIPT_EXTRACT_PROMPT = """You are a data extraction specialist. Extract receipt data from this image
matching the required schema exactly.

IMPORTANT:
- Return money values as strings (e.g., "46.38"), NOT numbers with commas
- Do NOT include currency symbols"""


def extract_node(state: DocState) -> DocState:
    logger.info("Extracting data from document %s", state["document_id"])

    doc_type = state["doc_type"]
    if doc_type == "invoice":
        schema, prompt = InvoicePayload, INVOICE_EXTRACT_PROMPT
    else:
        schema, prompt = ReceiptPayload, RECEIPT_EXTRACT_PROMPT

    llm = get_llm().with_structured_output(schema)
    doc_block = content_block_for_file(state["file_path"], state["mime"])

    msg = HumanMessage(
        content=[{"type": "text", "text": prompt}, doc_block]
    )

    try:
        payload = llm.invoke([msg])
        state["payload"] = payload.to_dict()
        state["llm_calls"] += 1
        logger.info("Extraction successful")
    except Exception as e:
        logger.warning("Extraction failed: %s", e)
        state["payload"] = None
        state["validation_errors"] = [f"Extraction error: {str(e)}"]
        state["llm_calls"] += 1

    return state
