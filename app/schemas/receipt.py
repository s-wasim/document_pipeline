from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, field_validator

from app.schemas.common import parse_money, parse_date


class ReceiptPayload(BaseModel):
    merchant: str
    purchase_date: date | None = None
    currency: str = "USD"
    total: Decimal = Decimal("0.00")
    payment_method: str | None = None

    @field_validator("total", mode="before")
    @classmethod
    def _parse_money_field(cls, v: Any) -> Decimal:
        return parse_money(v)

    @field_validator("purchase_date", mode="before")
    @classmethod
    def _parse_date_field(cls, v: Any) -> date | None:
        return parse_date(v)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReceiptPayload:
        """Build from a raw extraction dict. `merchant` is required — a missing
        key raises a pydantic ValidationError naming the field."""
        kwargs: dict[str, Any] = {
            "purchase_date": d.get("purchase_date"),
            "currency": d.get("currency") or "USD",
            "total": d.get("total", 0),
            "payment_method": d.get("payment_method"),
        }
        if "merchant" in d:
            kwargs["merchant"] = d["merchant"]
        return cls(**kwargs)

    def to_dict(self) -> dict:
        return {
            "merchant": self.merchant,
            "purchase_date": self.purchase_date.isoformat() if self.purchase_date else None,
            "currency": self.currency,
            "total": str(self.total),
            "payment_method": self.payment_method,
        }
