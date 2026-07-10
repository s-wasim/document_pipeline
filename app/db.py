import os
import time
from decimal import Decimal

from sqlalchemy import create_engine, Column, Integer, String, Numeric, Boolean, Text, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import func

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://docpipe:docpipe@localhost:5432/docpipe")

engine = None
SessionLocal = None
Base = declarative_base()

DOCUMENT_STATUS = Enum(
    "processing", "needs_review", "failed_validation",
    "unsupported", "committed", "rejected",
    name="document_status",
    create_constraint=True,
    validate_strings=True,
)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    path = Column(String(512), nullable=False)
    mime = Column(String(50), nullable=False)
    pages = Column(Integer, default=0)
    doc_type = Column(String(50), nullable=True)
    status = Column(DOCUMENT_STATUS, nullable=False, default="processing")
    llm_calls = Column(Integer, default=0)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    extractions = relationship("Extraction", back_populates="document", cascade="all, delete-orphan")
    invoice = relationship("Invoice", back_populates="document", uselist=False, cascade="all, delete-orphan")
    receipt = relationship("Receipt", back_populates="document", uselist=False, cascade="all, delete-orphan")


class Extraction(Base):
    __tablename__ = "extractions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    payload = Column(JSON, nullable=True)
    validation_errors = Column(JSON, nullable=True)
    repair_attempted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="extractions")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, unique=True)
    vendor = Column(String(255), nullable=False)
    invoice_no = Column(String(100), nullable=False)
    invoice_date = Column(DateTime(timezone=True), nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    currency = Column(String(10), default="USD")
    subtotal = Column(Numeric(12, 2), nullable=False)
    tax = Column(Numeric(12, 2), nullable=False)
    total = Column(Numeric(12, 2), nullable=False)

    document = relationship("Document", back_populates="invoice")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    description = Column(String(500), nullable=False)
    qty = Column(Numeric(12, 2), nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    line_total = Column(Numeric(12, 2), nullable=False)

    invoice = relationship("Invoice", back_populates="items")


class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, unique=True)
    merchant = Column(String(255), nullable=False)
    purchase_date = Column(DateTime(timezone=True), nullable=True)
    currency = Column(String(10), default="USD")
    total = Column(Numeric(12, 2), nullable=False)
    payment_method = Column(String(100), nullable=True)

    document = relationship("Document", back_populates="receipt")


def get_engine():
    global engine
    if engine is None:
        engine = create_engine(DATABASE_URL)
    return engine


def get_session():
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = sessionmaker(bind=get_engine())
    return SessionLocal()


def init_db(max_retries=10, delay=2):
    for attempt in range(max_retries):
        try:
            eng = get_engine()
            Base.metadata.create_all(eng)
            return
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise e
