"""Request bodies for the write endpoints (commit / reject)."""

from typing import Any

from pydantic import BaseModel, Field


class CommitRequest(BaseModel):
    doc_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class RejectRequest(BaseModel):
    note: str | None = None
