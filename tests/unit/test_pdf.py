from pathlib import Path

import pytest

from datamind_dataplane.pdf import extract_pdf


def test_pdf_rejects_non_pdf_path(tmp_path: Path):
    source = tmp_path / "input.txt"
    source.write_text("not a pdf", encoding="utf-8")
    with pytest.raises(ValueError, match="只接受 .pdf"):
        extract_pdf(str(source))


def test_pdf_reports_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        extract_pdf(str(tmp_path / "missing.pdf"))
