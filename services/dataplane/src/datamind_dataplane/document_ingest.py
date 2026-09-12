"""Document extraction helpers for the DataPlane ingestion surface.

Extraction happens inside DataPlane so Codex and the Gateway never need to
parse or persist office/PDF files themselves.  OCR is deliberately optional:
text extraction remains deterministic, while deployments can install
``pytesseract`` plus a Tesseract binary when scanned PDFs must be indexed.
"""
from __future__ import annotations

import asyncio
import csv
import io
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

SUPPORTED_DOCUMENT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".csv", ".tsv", ".docx", ".xlsx", ".xls", ".pdf",
}


def _clip(text: str, max_chars: int) -> str:
    text = text.replace("\x00", "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[文档内容已达到抽取上限，后续内容未进入索引]"


def _extract_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    lines: list[str] = []
    for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
        parts = [node.text or "" for node in paragraph.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")]
        line = "".join(parts).strip()
        if line:
            lines.append(line)
    return "\n\n".join(lines)


def _extract_spreadsheet(path: Path) -> str:
    if path.suffix.lower() == ".xls":
        try:
            import xlrd
        except ImportError as exc:
            raise RuntimeError("XLS 抽取需要 xlrd") from exc
        book = xlrd.open_workbook(str(path), on_demand=True)
        sections: list[str] = []
        for sheet in book.sheets():
            rows = ["\t".join(str(value) for value in sheet.row_values(i))
                    for i in range(sheet.nrows)]
            rows = [row for row in rows if row.strip()]
            if rows:
                sections.append(f"## 工作表: {sheet.name}\n\n" + "\n".join(rows))
        return "\n\n".join(sections)
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError("XLSX 抽取需要 openpyxl") from exc
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sections: list[str] = []
    try:
        for sheet in book.worksheets:
            rows = []
            for row in sheet.iter_rows(values_only=True):
                values = ["" if value is None else str(value) for value in row]
                if any(value.strip() for value in values):
                    rows.append("\t".join(values))
            if rows:
                sections.append(f"## 工作表: {sheet.title}\n\n" + "\n".join(rows))
    finally:
        book.close()
    return "\n\n".join(sections)


def _extract_delimited(path: Path) -> str:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    rows = csv.reader(io.StringIO(raw), delimiter=delimiter)
    return "\n".join("\t".join(cell.strip() for cell in row) for row in rows)


def _extract_pdf(path: Path, *, ocr: bool) -> tuple[str, bool]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF 文本抽取需要 pypdf") from exc
    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    text = "\n\n".join(f"## 第 {i} 页\n\n{value}" for i, value in enumerate(pages, 1) if value)
    if text or not ocr:
        return text, False

    # OCR is opt-in and only attempted when normal PDF text extraction is empty.
    try:
        import fitz
        from PIL import Image
        import pytesseract
    except ImportError as exc:
        raise RuntimeError("扫描版 PDF 需要安装 pymupdf、Pillow、pytesseract 和 Tesseract OCR") from exc
    document = fitz.open(str(path))
    try:
        ocr_pages = []
        for i, page in enumerate(document, 1):
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            text_page = pytesseract.image_to_string(image, lang="chi_sim+eng").strip()
            if text_page:
                ocr_pages.append(f"## 第 {i} 页（OCR）\n\n{text_page}")
    finally:
        document.close()
    return "\n\n".join(ocr_pages), True


def extract_document(path: Path, *, max_chars: int = 2_000_000, ocr: bool = False) -> dict[str, Any]:
    """Extract one supported document and return text plus provenance."""
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise ValueError(f"不支持的文档类型: {suffix or '<无扩展名>'}")
    used_ocr = False
    if suffix in {".txt", ".md", ".markdown"}:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        method = "text"
    elif suffix in {".csv", ".tsv"}:
        text = _extract_delimited(path)
        method = "table"
    elif suffix == ".docx":
        text = _extract_docx(path)
        method = "docx_xml"
    elif suffix in {".xlsx", ".xls"}:
        text = _extract_spreadsheet(path)
        method = "spreadsheet"
    else:
        text, used_ocr = _extract_pdf(path, ocr=ocr)
        method = "pdf_ocr" if used_ocr else "pdf_text"
    return {
        "text": _clip(text, max_chars),
        "source": path.name,
        "extension": suffix,
        "method": method,
        "ocr_used": used_ocr,
        "characters": len(text),
        "truncated": len(text) > max_chars,
    }


def build_document_ingest_tools(svc: Any) -> list[Any]:
    """Build DataPlane tools backed by the existing KB IngestService."""
    from datamind.core.tools import ToolSpec

    async def _document(path: str, max_chars: int = 2_000_000, ocr: bool = False) -> dict[str, Any]:
        resolved = svc._locate_file(path)
        if not resolved.is_file():
            raise ValueError(f"不是文件: {resolved}")
        extracted = await asyncio.to_thread(extract_document, resolved, max_chars=max_chars, ocr=ocr)
        if not extracted["text"].strip():
            raise ValueError("文档未抽取到可索引文本；扫描版 PDF 请设置 ocr=true")
        result = await svc.kb_add_text(text=extracted["text"], source=resolved.name, persist=True)
        return {**result, "extraction": {k: v for k, v in extracted.items() if k != "text"}}

    async def _path(path: str, recursive: bool = True, max_files: int = 500,
                    max_chars: int = 2_000_000, ocr: bool = False) -> dict[str, Any]:
        resolved = svc._locate_file(path)
        if resolved.is_file():
            return {"files_processed": 1, "files": [await _document(str(resolved), max_chars=max_chars, ocr=ocr)]}
        if not resolved.is_dir():
            raise ValueError(f"路径不存在: {resolved}")
        iterator = resolved.rglob("*") if recursive else resolved.glob("*")
        files = [p for p in sorted(iterator) if p.is_file() and p.suffix.lower() in SUPPORTED_DOCUMENT_EXTENSIONS]
        if len(files) > max_files:
            raise ValueError(f"目录包含 {len(files)} 个文档，超过 max_files={max_files}")
        results, errors = [], []
        for item in files:
            try:
                results.append(await _document(str(item), max_chars=max_chars, ocr=ocr))
            except Exception as exc:  # keep per-file progress visible
                errors.append({"file": str(item), "error": str(exc)})
        return {"files_processed": len(results), "files": results, "errors": errors,
                "failed": len(errors), "supported_extensions": sorted(SUPPORTED_DOCUMENT_EXTENSIONS)}

    return [
        ToolSpec(
            name="kb_ingest_document",
            description="在 DataPlane 内抽取并入库单个 TXT、Markdown、CSV、TSV、DOCX、XLSX 或 PDF。PDF 默认提取文本；扫描版 PDF 可显式启用 OCR。",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_chars": {"type": "integer", "minimum": 1000, "maximum": 10000000, "default": 2000000},
                    "ocr": {"type": "boolean", "default": False},
                },
                "required": ["path"],
            },
            handler=_document,
            metadata={"group": "ingest", "surface": "kb", "access": "write"},
        ),
        ToolSpec(
            name="kb_ingest_path",
            description="在 DataPlane 内递归抽取并入库目录中的文档，逐文件返回抽取方式、字符数和错误。",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "recursive": {"type": "boolean", "default": True},
                    "max_files": {"type": "integer", "minimum": 1, "maximum": 5000, "default": 500},
                    "max_chars": {"type": "integer", "minimum": 1000, "maximum": 10000000, "default": 2000000},
                    "ocr": {"type": "boolean", "default": False},
                },
                "required": ["path"],
            },
            handler=_path,
            metadata={"group": "ingest", "surface": "kb", "access": "write"},
        ),
    ]
