from io import BytesIO

import pytest
from reportlab.pdfgen import canvas

from app.upload import validate_upload, guess_mime


def _make_pdf(num_pages: int) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf)
    for _ in range(num_pages):
        c.drawString(100, 700, "page")
        c.showPage()
    c.save()
    return buf.getvalue()


def test_guess_mime_pdf():
    assert guess_mime("invoice.pdf") == "application/pdf"


def test_guess_mime_jpg():
    assert guess_mime("receipt.jpg") == "image/jpeg"
    assert guess_mime("receipt.jpeg") == "image/jpeg"


def test_guess_mime_png():
    assert guess_mime("image.png") == "image/png"


def test_validate_oversize():
    content = b"x" * (16 * 1024 * 1024)
    err = validate_upload("test.pdf", content)
    assert err is not None
    assert "15 MB" in err


def test_validate_unsupported_type():
    err = validate_upload("test.txt", b"hello")
    assert err is not None
    assert "Unsupported" in err


def test_validate_valid_pdf():
    err = validate_upload("test.pdf", b"small content")
    assert err is None


def test_validate_valid_image():
    err = validate_upload("photo.jpg", b"small content")
    assert err is None


def test_validate_rejects_21_page_pdf():
    content = _make_pdf(21)
    err = validate_upload("big.pdf", content)
    assert err is not None
    assert "20" in err


def test_validate_accepts_20_page_pdf():
    content = _make_pdf(20)
    err = validate_upload("ok.pdf", content)
    assert err is None
