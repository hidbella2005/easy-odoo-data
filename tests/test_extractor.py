from pathlib import Path

import pandas as pd
import numpy as np
from PIL import Image

from app.extractor import ExtractionError, extract_file
from app.data_cleaner import clean_dataframe
from app.source_connectors import fetch_tool_json


class FakeReader:
    def __init__(self):
        self.inputs = []

    def readtext(self, image, detail=0, paragraph=False):
        self.inputs.append(image)
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

    reader = FakeReader()
    result = extract_file(source, ocr_reader=reader)

    assert isinstance(result, pd.DataFrame)
    assert isinstance(reader.inputs[0], np.ndarray)
    assert reader.inputs[0].shape == (10, 10, 3)
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


def test_fetch_tool_json_normalizes_data_envelope(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self):
            return b'{"data": [{"name": "Ada", "score": 10}]}'

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: FakeResponse())

    result = fetch_tool_json("https://tool.example/data")

    assert list(result.columns) == ["name", "score"]
    assert result.iloc[0].to_dict() == {"name": "Ada", "score": 10}


def test_clean_dataframe_trims_deduplicates_and_fills_text():
    source = pd.DataFrame({"name": [" Ada ", " Ada ", None], "score": [1, 1, None]})

    result = clean_dataframe(
        source,
        trim_text=True,
        drop_duplicates=True,
        fill_missing_text="Unknown",
    )

    assert result.loc[0, "name"] == "Ada"
    assert result.loc[0, "score"] == 1
    assert result.loc[1, "name"] == "Unknown"
    assert pd.isna(result.loc[1, "score"])
    assert source.iloc[0]["name"] == " Ada "

