from typing import TypedDict, Any


class DocState(TypedDict):
    document_id: int
    file_path: str
    mime: str
    doc_type: str | None
    confidence: float | None
    payload: dict | None
    validation_errors: list[str]
    repair_attempted: bool
    final_status: str | None
    llm_calls: int
