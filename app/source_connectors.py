"""Connectors for warehouse and tool-backed tabular sources."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

import pandas as pd


class SourceConnectionError(RuntimeError):
    """Raised when an external source cannot be reached or parsed."""


def query_postgres(
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    query: str,
    *,
    limit: int = 5000,
) -> pd.DataFrame:
    """Run one read-only PostgreSQL query and return its rows as a DataFrame."""
    if not query.strip():
        raise ValueError("SQL query must not be empty")
    if limit < 1:
        raise ValueError("limit must be positive")
    try:
        import psycopg
    except ImportError as exc:
        raise SourceConnectionError(
            "PostgreSQL support requires psycopg. Install requirements.txt first."
        ) from exc

    connection = None
    try:
        connection = psycopg.connect(
            host=host.strip(),
            port=port,
            dbname=database.strip(),
            user=username.strip(),
            password=password,
            connect_timeout=10,
        )
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(f"SELECT * FROM ({query.rstrip(';')}) AS source_query LIMIT %s", (limit,))
            rows = cursor.fetchall()
            columns = [column.name for column in cursor.description]
        return pd.DataFrame(rows, columns=columns)
    except (psycopg.Error, OSError, ValueError) as exc:
        raise SourceConnectionError(f"PostgreSQL query failed: {exc}") from exc
    finally:
        if connection is not None:
            connection.close()


def fetch_tool_json(url: str, api_key: str = "") -> pd.DataFrame:
    """Fetch a JSON tool response and normalize common list/object payloads."""
    if not url.strip():
        raise ValueError("Tool URL must not be empty")
    request = urllib.request.Request(url.strip(), headers={"Accept": "application/json"})
    if api_key.strip():
        request.add_header("Authorization", f"Bearer {api_key.strip()}")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload: Any = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise SourceConnectionError(f"Tool connection failed: {exc}") from exc

    if isinstance(payload, dict):
        for key in ("data", "results", "items"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = [payload]
    else:
        raise SourceConnectionError("Tool response must be a JSON object or array")
    if not all(isinstance(row, dict) for row in rows):
        raise SourceConnectionError("Tool response rows must be JSON objects")
    return pd.json_normalize(rows)
