import os
import base64
from pathlib import Path

from langchain_anthropic import ChatAnthropic

MODEL = "claude-sonnet-5"


def get_llm(temperature: float = 0) -> ChatAnthropic:
    return ChatAnthropic(
        model=MODEL,
        max_tokens=4096,
        api_key=os.environ["ANTHROPIC_API_KEY"],
    )


def make_pdf_content_block(file_path: str) -> dict:
    path = Path(file_path)
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": data,
        },
    }


def make_image_content_block(file_path: str) -> dict:
    path = Path(file_path)
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    ext = path.suffix.lower()
    media_type = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": data,
        },
    }


def make_page_preview_block(file_path: str, mime: str, page: int = 0) -> dict:
    """Create an image content block for the given page of the source document.

    PDFs are rasterised to PNG on the fly (page ``page``); images are sent as-is.
    Renders directly from the source file so it does not depend on the doc_id
    keyed preview cache (files on disk are named by uuid, not doc_id).
    """
    if mime == "application/pdf":
        import io

        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(Path(file_path).read_bytes())
        idx = page if 0 <= page < len(pdf) else 0
        pil_image = pdf[idx].render(scale=2).to_pil()
        buf = io.BytesIO()
        pil_image.save(buf, "PNG")
        data = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": data,
            },
        }

    return make_image_content_block(file_path)


def content_block_for_file(file_path: str, mime: str) -> dict:
    if mime == "application/pdf":
        return make_pdf_content_block(file_path)
    else:
        return make_image_content_block(file_path)
