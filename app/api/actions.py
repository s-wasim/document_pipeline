"""Write actions for the Review pane: approve/commit and reject.

Delegates to the unchanged app.commit functions. Commit validation is performed
server-side by commit_invoice/commit_receipt (the frontend also pre-validates
client-side); errors are returned for display.
"""

from fastapi import APIRouter

from app.commit import commit_invoice, commit_receipt, reject_document
from app.api.schemas import CommitRequest, RejectRequest

router = APIRouter()


@router.post("/api/documents/{document_id}/commit")
def commit_document(document_id: int, body: CommitRequest):
    if body.doc_type == "invoice":
        success, errors = commit_invoice(document_id, body.payload)
    elif body.doc_type == "receipt":
        success, errors = commit_receipt(document_id, body.payload)
    else:
        return {"success": False, "errors": [f"Unsupported doc_type: {body.doc_type}"]}
    return {"success": success, "errors": errors}


@router.post("/api/documents/{document_id}/reject")
def reject(document_id: int, body: RejectRequest):
    note = (body.note or "").strip() or "Rejected by user"
    ok = reject_document(document_id, note=note)
    return {"success": bool(ok)}
