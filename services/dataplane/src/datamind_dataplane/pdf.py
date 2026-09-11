"""Internal PDF extraction capability for StoreAgent."""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from datamind.core.tools import ToolSpec

_MAX_CHARS = 2_000_000


def _extract_text_layer(path: Path, max_chars: int) -> tuple[int, str] | None:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages: list[str] = []
    chars = 0
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        chars += len(text)
        if chars > max_chars:
            raise ValueError(f"PDF 文本超过上限 {max_chars} 字符")
        pages.append(f"## 第 {page_number} 页\n\n{text}")
    text = "\n\n".join(pages).strip()
    return (len(reader.pages), text) if text else None


def _extract_ocr(path: Path, max_chars: int, language: str) -> tuple[int, str]:
    if not shutil.which("pdftoppm") or not shutil.which("tesseract"):
        raise RuntimeError("OCR 不可用：需要安装 pdftoppm、tesseract 和中文语言包 chi_sim")
    with tempfile.TemporaryDirectory(prefix="datamind-pdf-ocr-") as directory:
        prefix = str(Path(directory) / "page")
        subprocess.run(["pdftoppm", "-png", "-r", "200", str(path), prefix], check=True, capture_output=True, text=True, timeout=300)
        images = sorted(Path(directory).glob("page-*.png"), key=lambda item: int(item.stem.rsplit("-", 1)[1]))
        if not images:
            raise RuntimeError("OCR 未生成 PDF 页面图像")
        pages: list[str] = []
        chars = 0
        for index, image in enumerate(images, start=1):
            result = subprocess.run(["tesseract", str(image), "stdout", "-l", language, "--psm", "3"], check=True, capture_output=True, text=True, timeout=300)
            text = result.stdout.strip()
            if not text:
                continue
            chars += len(text)
            if chars > max_chars:
                raise ValueError(f"PDF OCR 文本超过上限 {max_chars} 字符")
            pages.append(f"## 第 {index} 页\n\n{text}")
        text = "\n\n".join(pages).strip()
        if not text:
            raise RuntimeError("OCR 未识别到文本，可能是空白页或图像质量不足")
        return len(images), text


def extract_pdf(path: str, *, max_chars: int = _MAX_CHARS, ocr_fallback: bool = True) -> dict[str, Any]:
    if max_chars <= 0 or max_chars > _MAX_CHARS:
        raise ValueError(f"max_chars 必须在 1 到 {_MAX_CHARS} 之间")
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"PDF 文件不存在：{source}")
    if source.suffix.lower() != ".pdf":
        raise ValueError("pdf_extract_text 只接受 .pdf 文件")
    text_error = ""
    try:
        result = _extract_text_layer(source, max_chars)
        if result:
            pages, text = result
            return {"source": str(source), "pages": pages, "chars": len(text), "mode": "text", "text": text}
        text_error = "PDF 没有可提取的文字层"
    except Exception as exc:
        text_error = str(exc)
    if not ocr_fallback:
        raise RuntimeError(text_error)
    try:
        pages, text = _extract_ocr(source, max_chars, "chi_sim+eng")
        return {"source": str(source), "pages": pages, "chars": len(text), "mode": "ocr", "text": text}
    except Exception as exc:
        raise RuntimeError(f"PDF 抽取失败；文本方式：{text_error}；OCR 方式：{exc}") from exc


def build_pdf_tools() -> list[ToolSpec]:
    async def _pdf_extract_text(path: str, max_chars: int = _MAX_CHARS, ocr_fallback: bool = True) -> dict[str, Any]:
        return await asyncio.to_thread(extract_pdf, path, max_chars=max_chars, ocr_fallback=ocr_fallback)

    return [ToolSpec(
        name="pdf_extract_text",
        description=("抽取 PDF 文字供 StoreAgent 入库：先使用文字层，失败后使用中文+英文 OCR；"
                     "返回内容只能交给 kb_add_text，不能写入 Memory 或 Skills。"),
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "活动租户 profile 数据根目录内的 PDF 路径。"},
                "max_chars": {"type": "integer", "minimum": 1, "maximum": _MAX_CHARS, "default": _MAX_CHARS},
                "ocr_fallback": {"type": "boolean", "default": True},
            },
            "required": ["path"],
        },
        handler=_pdf_extract_text,
        metadata={"group": "ingest", "surface": "kb", "access": "write"},
    )]


__all__ = ["build_pdf_tools", "extract_pdf"]
