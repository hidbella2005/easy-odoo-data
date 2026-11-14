"""Prepare tabular rows for Odoo batch creation."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd


def prepare_import_values(
    frame: pd.DataFrame, mapping: dict[str, str]
) -> list[dict[str, Any]]:
    """Convert mapped DataFrame columns into XML-RPC-safe Odoo values."""
    if not mapping:
        raise ValueError("Map at least one source column to an Odoo field")
    missing_columns = sorted(set(mapping.values()) - set(frame.columns))
    if missing_columns:
        raise ValueError(f"Mapped source columns do not exist: {', '.join(missing_columns)}")

    values: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        values.append(
            {
                field_name: _to_odoo_value(row[source_column])
                for field_name, source_column in mapping.items()
            }
        )
    return values


def _to_odoo_value(value: Any) -> Any:
    if pd.isna(value):
        return False
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value
