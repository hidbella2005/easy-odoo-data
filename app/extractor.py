"""Extract Excel, CSV, and image/PDF sources into a normalized DataFrame."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

LOGGER = logging.getLogger(__name__)
TABULAR_SUFFIXES = {".csv", ".xlsx", ".xls"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".pdf"}


class ExtractionError(RuntimeError):
    """Raised when a source cannot be extracted."""


class OCRReader(Protocol):
    """Minimal protocol implemented by EasyOCR and test doubles."""

    def readtext(self, image: Any, detail: int = 0, paragraph: bool = False) -> list[Any]:
        ...


def extract_file(
    path: str | Path,
    *,
    ocr_reader: OCRReader | None = None,
    sheet_name: str | int = 0,
) -> pd.DataFrame:
    """Extract one supported file into a stable, tabular shape.

    Tabular files preserve their source columns and add ``source_file``.
    OCR files become key/value rows with ``raw_text`` retained for review.
    """
    source = Path(path)
    if not source.is_file():
        raise ExtractionError(f"Source file does not exist: {source}")
    suffix = source.suffix.lower()
    try:
        if suffix == ".csv":
            frame = pd.read_csv(source)
            return _with_source(frame, source)
        if suffix in TABULAR_SUFFIXES - {".csv"}:
            frame = pd.read_excel(source, sheet_name=sheet_name)
            return _with_source(frame, source)
        if suffix in IMAGE_SUFFIXES:
            return _extract_ocr(source, ocr_reader)
    except (OSError, ValueError, ImportError, pd.errors.ParserError) as exc:
        raise ExtractionError(f"Could not extract {source.name}: {exc}") from exc
    raise ExtractionError(
        f"Unsupported file type {suffix!r}; expected CSV, XLS/XLSX, JPG, PNG, or PDF"
    )


def _with_source(frame: pd.DataFrame, source: Path) -> pd.DataFrame:
    result = frame.copy()
    result.columns = [str(column).strip() for column in result.columns]
    result["source_file"] = source.name
    return result


def _extract_ocr(source: Path, ocr_reader: OCRReader | None) -> pd.DataFrame:
    reader = ocr_reader or _create_ocr_reader()
    pages = _load_pages(source)
    rows: list[dict[str, str | int]] = []
    for page_number, image in enumerate(pages, start=1):
        try:
            import numpy as np

            ocr_input = np.asarray(image.convert("RGB"))
            detected = reader.readtext(ocr_input, detail=0, paragraph=False)
        except ImportError as exc:
            raise ExtractionError(
                "OCR extraction requires NumPy. Install requirements.txt first."
            ) from exc
        except Exception as exc:
            LOGGER.exception("OCR failed for %s page %s", source, page_number)
            raise ExtractionError(f"OCR failed for {source.name} page {page_number}: {exc}") from exc
        for line_number, item in enumerate(detected, start=1):
            text = str(item).strip()
            if not text:
                continue
            key, separator, value = text.partition(":")
            rows.append(
                {
                    "key": key.strip() if separator else "",
                    "value": value.strip() if separator else text,
                    "raw_text": text,
                    "source_file": source.name,
                    "page": page_number,
                    "line": line_number,
                }
            )
    return pd.DataFrame(
        rows,
        columns=["key", "value", "raw_text", "source_file", "page", "line"],
    )


@lru_cache(maxsize=1)
def _create_ocr_reader() -> OCRReader:
    """Create the OCR model once per process; model startup is expensive."""
    try:
        import easyocr
    except ImportError as exc:
        raise ExtractionError(
            "OCR extraction requires EasyOCR. Install requirements.txt or pass an OCR reader."
        ) from exc
    try:
        return easyocr.Reader(["en"], gpu=False)
    except Exception as exc:
        raise ExtractionError(f"Could not initialize EasyOCR: {exc}") from exc


def _load_pages(source: Path) -> list[Any]:
    if source.suffix.lower() != ".pdf":
        try:
            from PIL import Image

            with Image.open(source) as image:
                return [image.copy()]
        except (OSError, ImportError) as exc:
            raise ExtractionError(f"Could not open image {source.name}: {exc}") from exc
    try:
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(str(source))
        pages = []
        for page_index in range(len(document)):
            page = document[page_index]
            bitmap = page.render(scale=2)
            pages.append(bitmap.to_pil())
            page.close()
        document.close()
        return pages
    except (OSError, ImportError, ValueError) as exc:
        raise ExtractionError(f"Could not render PDF {source.name}: {exc}") from exc

