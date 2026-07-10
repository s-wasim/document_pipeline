from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import CompileError, StatementError

from app.db import Base, Document, Extraction, Invoice, InvoiceItem, Receipt


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    sess = TestSession()
    yield sess
    sess.close()


def test_document_creation(session):
    doc = Document(filename="test.pdf", path="/tmp/test.pdf", mime="application/pdf", status="processing")
    session.add(doc)
    session.commit()
    assert doc.id is not None
    assert doc.status == "processing"


def test_money_roundtrip_as_decimal(session):
    doc = Document(filename="inv.pdf", path="/tmp/inv.pdf", mime="application/pdf", status="processing")
    session.add(doc)
    session.flush()

    inv = Invoice(
        document_id=doc.id,
        vendor="Test Corp",
        invoice_no="INV-001",
        subtotal=Decimal("100.00"),
        tax=Decimal("10.00"),
        total=Decimal("110.00"),
    )
    session.add(inv)
    session.commit()

    fetched = session.query(Invoice).first()
    assert isinstance(fetched.subtotal, Decimal)
    assert fetched.subtotal == Decimal("100.00")


def test_document_invalid_status_rejected(session):
    doc = Document(filename="bad.pdf", path="/tmp/bad.pdf", mime="application/pdf", status="not_a_real_status")
    session.add(doc)
    with pytest.raises(StatementError, match="not among the defined enum values"):
        session.commit()


def test_document_invoice_relationship(session):
    doc = Document(filename="inv.pdf", path="/tmp/inv.pdf", mime="application/pdf", status="committed")
    session.add(doc)
    session.flush()

    inv = Invoice(
        document_id=doc.id,
        vendor="Vendor A",
        invoice_no="INV-001",
        subtotal=Decimal("200.00"),
        tax=Decimal("20.00"),
        total=Decimal("220.00"),
    )
    session.add(inv)
    session.flush()

    item = InvoiceItem(
        invoice_id=inv.id,
        description="Item 1",
        qty=Decimal("2"),
        unit_price=Decimal("100.00"),
        line_total=Decimal("200.00"),
    )
    session.add(item)
    session.commit()

    fetched_doc = session.query(Document).first()
    assert fetched_doc.invoice.vendor == "Vendor A"
    assert len(fetched_doc.invoice.items) == 1
