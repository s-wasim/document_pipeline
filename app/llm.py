import os
import base64
from pathlib import Path

from langchain_anthropic import ChatAnthropic

MODEL = "claude-sonnet-4-6"


def get_llm(temperature: float = 0) -> ChatAnthropic:
    return ChatAnthropic(
        model=MODEL,
        temperature=temperature,
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
    """Create a content block from a cached page preview PNG."""
    preview_dir = Path(file_path).parent.parent / "data" / "previews"
    preview_path = preview_dir / str(Path(file_path).stem) / f"page_{page}.png"

    if preview_path.exists():
        return make_image_content_block(str(preview_path))

    from app.upload import render_previews
    content = Path(file_path).read_bytes()
    previews = render_previews(content, mime, int(Path(file_path).stem))

    if previews:
        path = Path(previews[0])
        data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": data,
            },
        }

    return make_image_content_block(str(preview_path))


def content_block_for_file(file_path: str, mime: str) -> dict:
    if mime == "application/pdf":
        return make_pdf_content_block(file_path)
    else:
        return make_image_content_block(file_path)
