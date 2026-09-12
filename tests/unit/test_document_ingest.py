from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / "services/dataplane/src"))
sys.path.insert(0, str(ROOT / "plugins/datamind-context/vendor/datamind-0.3.2-py3-none-any.whl"))

from datamind_dataplane.document_ingest import extract_document
from datamind_dataplane.experience import build_experience_tools


def test_csv_extraction_keeps_all_rows(tmp_path: Path) -> None:
    source = tmp_path / "records.csv"
    source.write_text("id,name\n1,A\n2,B\n3,C\n", encoding="utf-8")
    result = extract_document(source)
    assert result["method"] == "table"
    assert "3\tC" in result["text"]
    assert result["truncated"] is False


def test_docx_xml_extraction(tmp_path: Path) -> None:
    from zipfile import ZipFile, ZIP_DEFLATED

    source = tmp_path / "note.docx"
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p><w:r><w:t>企业入库说明</w:t></w:r></w:p></w:body></w:document>'
    )
    with ZipFile(source, "w", ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", xml)
    result = extract_document(source)
    assert result["method"] == "docx_xml"
    assert "企业入库说明" in result["text"]


def test_pdf_requires_text_or_explicit_ocr(tmp_path: Path) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"not a real pdf")
    with pytest.raises(Exception):
        extract_document(source, ocr=False)


@pytest.mark.asyncio
async def test_experience_tools_are_profile_scoped(tmp_path: Path) -> None:
    class Memory:
        async def save(self, content, **kwargs):
            assert kwargs["scope"] == "profile"
            return "memory-1"

    tools = {tool.name: tool for tool in build_experience_tools(profile_dir=tmp_path, memory=Memory())}
    result = await tools["wiki_upsert_source"].handler(title="入库说明", content="正文", source="a.pdf")
    assert Path(result["path"]).is_file()
    await tools["memory_record_interaction"].handler(session_id="s1", role="user", content="记住这个流程")
    feedback = await tools["memory_record_feedback"].handler(query="问题", feedback="答案不完整", score=-1)
    assert feedback["memory_id"] == "memory-1"
    status = await tools["wiki_status"].handler()
    assert status["markdown_pages"] == 1
    assert status["interaction_sessions"] == 1
    assert status["feedback_events"] == 1
