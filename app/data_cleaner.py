"""Deterministic cleaning operations for imported tabular data."""

from __future__ import annotations

import pandas as pd


def clean_dataframe(
    frame: pd.DataFrame,
    *,
    trim_text: bool = False,
    drop_empty_rows: bool = False,
    drop_duplicates: bool = False,
    fill_missing_text: str | None = None,
) -> pd.DataFrame:
    """Return a cleaned copy without changing the source DataFrame in place."""
    cleaned = frame.copy()
    if trim_text:
        for column in cleaned.select_dtypes(include=["object", "string"]).columns:
            cleaned[column] = cleaned[column].map(
                lambda value: value.strip() if isinstance(value, str) else value
            )
    if drop_empty_rows:
        cleaned = cleaned.dropna(how="all")
    if drop_duplicates:
        cleaned = cleaned.drop_duplicates()
    if fill_missing_text is not None:
        for column in cleaned.select_dtypes(include=["object", "string"]).columns:
            cleaned[column] = cleaned[column].fillna(fill_missing_text)
    return cleaned.reset_index(drop=True)
