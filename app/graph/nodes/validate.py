import logging

from app.graph.state import DocState
from app.schemas.invoice import InvoicePayload
from app.schemas.receipt import ReceiptPayload
from app.validation import validate_payload

logger = logging.getLogger(__name__)


def validate_node(state: DocState) -> DocState:
    logger.info("Validating document %s", state["document_id"])

    if not state["payload"]:
        state["validation_errors"] = ["No extraction payload to validate"]
        logger.warning("No payload to validate")
        return state

    try:
        doc_type = state["doc_type"]
        if doc_type == "invoice":
            payload = InvoicePayload.from_dict(state["payload"])
        elif doc_type == "receipt":
            payload = ReceiptPayload.from_dict(state["payload"])
        else:
            state["validation_errors"] = [f"Unknown doc type: {doc_type}"]
            return state

        errors = validate_payload(doc_type, payload)
        state["validation_errors"] = errors

        if errors:
            logger.info("Validation found %d error(s)", len(errors))
        else:
            logger.info("Validation passed")
    except Exception as e:
        logger.warning("Validation error: %s", e)
        state["validation_errors"] = [f"Validation error: {str(e)}"]

    return state
