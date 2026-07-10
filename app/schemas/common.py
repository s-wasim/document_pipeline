from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


def parse_money(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace("$", "").replace("USD", "").strip()
        if not cleaned:
            raise ValueError(f"Cannot parse money from empty string")
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            raise ValueError(f"Cannot parse money: '{value}'")
    raise ValueError(f"Unexpected money type: {type(value)}")


DATE_FORMATS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%Y/%m/%d",
]


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Cannot parse date: '{value}'")
    raise ValueError(f"Unexpected date type: {type(value)}")
