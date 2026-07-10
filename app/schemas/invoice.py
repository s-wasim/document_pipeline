from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import parse_money, parse_date


class InvoiceItemPayload(BaseModel):
    description: str
    qty: Decimal
    unit_price: Decimal
    line_total: Decimal

    @field_validator("qty", "unit_price", "line_total", mode="before")
    @classmethod
    def _parse_money_fields(cls, v: Any) -> Decimal:
        return parse_money(v)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> InvoiceItemPayload:
        return cls(
            description=str(d.get("description", "")),
            qty=d.get("qty", 0),
            unit_price=d.get("unit_price", 0),
            line_total=d.get("line_total", 0),
        )


class InvoicePayload(BaseModel):
    vendor: str
    invoice_no: str
    invoice_date: date | None = None
    due_date: date | None = None
    currency: str = "USD"
    items: list[InvoiceItemPayload] = Field(default_factory=list)
    subtotal: Decimal = Decimal("0.00")
    tax: Decimal = Decimal("0.00")
    total: Decimal = Decimal("0.00")

    @field_validator("subtotal", "tax", "total", mode="before")
    @classmethod
    def _parse_money_fields(cls, v: Any) -> Decimal:
        return parse_money(v)

    @field_validator("invoice_date", "due_date", mode="before")
    @classmethod
    def _parse_date_fields(cls, v: Any) -> date | None:
        return parse_date(v)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> InvoicePayload:
        """Build from a raw extraction dict. Required fields (vendor, invoice_no)
        must be present — missing keys raise a pydantic ValidationError naming
        the field, per TASK-005 acceptance criteria."""
        raw_items = d.get("items", []) or []
        items = [InvoiceItemPayload.from_dict(it) for it in raw_items]
        payload_kwargs: dict[str, Any] = {
            "invoice_date": d.get("invoice_date"),
            "due_date": d.get("due_date"),
            "currency": d.get("currency") or "USD",
            "items": items,
            "subtotal": d.get("subtotal", 0),
            "tax": d.get("tax", 0),
            "total": d.get("total", 0),
        }
        # Omit required fields entirely when absent so pydantic raises its own
        # "Field required" ValidationError naming the field, rather than a
        # raw KeyError from this dict lookup.
        if "vendor" in d:
            payload_kwargs["vendor"] = d["vendor"]
        if "invoice_no" in d:
            payload_kwargs["invoice_no"] = d["invoice_no"]
        return cls(**payload_kwargs)

    def to_dict(self) -> dict:
        return {
            "vendor": self.vendor,
            "invoice_no": self.invoice_no,
            "invoice_date": self.invoice_date.isoformat() if self.invoice_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "currency": self.currency,
            "items": [
                {
                    "description": i.description,
                    "qty": str(i.qty),
                    "unit_price": str(i.unit_price),
                    "line_total": str(i.line_total),
                }
                for i in self.items
            ],
            "subtotal": str(self.subtotal),
            "tax": str(self.tax),
            "total": str(self.total),
        }
