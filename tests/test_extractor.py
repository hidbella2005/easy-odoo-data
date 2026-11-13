from pathlib import Path

import pandas as pd
from PIL import Image

from app.extractor import ExtractionError, extract_file


class FakeReader:
    def readtext(self, image, detail=0, paragraph=False):
        return ["Name: Ada Lovelace", "Country: United Kingdom", "unstructured line"]


def test_extract_csv_adds_source_file(tmp_path: Path):
    source = tmp_path / "contacts.csv"
    source.write_text("name,email\nAda,ada@example.com\n", encoding="utf-8")

    result = extract_file(source)

    assert list(result.columns) == ["name", "email", "source_file"]
    assert result.iloc[0]["source_file"] == "contacts.csv"


def test_extract_ocr_normalizes_key_value_rows(tmp_path: Path):
    source = tmp_path / "scan.png"
    Image.new("RGB", (10, 10), "white").save(source)

    result = extract_file(source, ocr_reader=FakeReader())

    assert isinstance(result, pd.DataFrame)
    assert result.loc[0, "key"] == "Name"
    assert result.loc[0, "value"] == "Ada Lovelace"
    assert result.loc[2, "key"] == ""


def test_extract_rejects_unknown_suffix(tmp_path: Path):
    source = tmp_path / "data.json"
    source.write_text("{}", encoding="utf-8")

    try:
        extract_file(source)
    except ExtractionError as exc:
        assert "Unsupported file type" in str(exc)
    else:
        raise AssertionError("Expected unsupported file type error")

