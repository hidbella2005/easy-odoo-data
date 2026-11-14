"""Streamlit wizard for exploring and preparing data for Odoo imports."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from app.extractor import ExtractionError, extract_file
from app.odoo_client import OdooClient, OdooConfig, OdooError
from app.source_connectors import SourceConnectionError, fetch_tool_json, query_postgres


st.set_page_config(page_title="Easy Odoo Data", page_icon="↔", layout="wide")


def _init_state() -> None:
    defaults = {
        "connected": False,
        "odoo_client": None,
        "odoo_fields": {},
        "data": None,
        "source_name": None,
        "upload_key": None,
        "temp_path": None,
        "source_kind": "File upload",
        "source_status": {"File upload": False, "PostgreSQL warehouse": False, "Tool connection": False},
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _save_upload(uploaded_file) -> Path:
    """Persist an upload long enough for the shared extractor to process it."""
    digest = hashlib.sha256(uploaded_file.getvalue()).hexdigest()
    if st.session_state.upload_key != digest:
        if st.session_state.temp_path:
            Path(st.session_state.temp_path).unlink(missing_ok=True)
        suffix = Path(uploaded_file.name).suffix.lower()
        temporary = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temporary.write(uploaded_file.getvalue())
        temporary.close()
        st.session_state.temp_path = temporary.name
        st.session_state.upload_key = digest
    return Path(st.session_state.temp_path)


def _connection_panel() -> None:
    with st.sidebar:
        st.header("1. Connect to Odoo")
        url = st.text_input("Odoo URL", placeholder="https://odoo.example.com")
        database = st.text_input("Database")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Connect", type="primary", width="stretch"):
            if not all(value.strip() for value in (url, database, username, password)):
                st.error("Fill in all Odoo connection fields.")
            else:
                try:
                    client = OdooClient(OdooConfig(url, database, username, password))
                    uid = client.authenticate()
                    st.session_state.odoo_client = client
                    st.session_state.connected = True
                    st.success(f"Connected as user #{uid}.")
                except (OdooError, ValueError) as exc:
                    st.session_state.connected = False
                    st.error(str(exc))
        if st.session_state.connected:
            st.success("Odoo connection active")


def _connection_overview() -> None:
    st.subheader("Connection overview")
    statuses = st.session_state.source_status
    cards = st.columns(3)
    connections = (
        ("Odoo", st.session_state.connected, "XML-RPC target"),
        ("PostgreSQL warehouse", statuses["PostgreSQL warehouse"], "SQL source"),
        ("Tool connection", statuses["Tool connection"], "JSON source"),
    )
    for card, (name, active, detail) in zip(cards, connections):
        with card:
            with st.container(border=True):
                st.metric(name, "Connected" if active else "Not connected")
                st.caption(detail)


def _postgres_panel() -> None:
    st.subheader("PostgreSQL warehouse")
    with st.form("postgres_source"):
        host = st.text_input("Host", placeholder="warehouse.example.com")
        port = st.number_input("Port", min_value=1, max_value=65535, value=5432)
        database = st.text_input("Database")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        query = st.text_area("Read-only SQL query", value="SELECT * FROM public.my_table")
        submitted = st.form_submit_button("Query warehouse", type="primary")
    if submitted:
        if not all(value.strip() for value in (host, database, username, password, query)):
            st.error("Fill in all PostgreSQL connection fields.")
            return
        try:
            frame = query_postgres(host, int(port), database, username, password, query)
            st.session_state.data = frame
            st.session_state.source_name = f"PostgreSQL: {database}"
            st.session_state.source_status["PostgreSQL warehouse"] = True
            st.success(f"Loaded {len(frame):,} rows from PostgreSQL.")
        except (SourceConnectionError, ValueError) as exc:
            st.session_state.source_status["PostgreSQL warehouse"] = False
            st.error(str(exc))


def _tool_panel() -> None:
    st.subheader("Tool connection")
    st.caption("Connect to a tool that returns JSON records, such as an internal API or automation step.")
    with st.form("tool_source"):
        url = st.text_input("Tool URL", placeholder="https://tool.example.com/data")
        api_key = st.text_input("Bearer token (optional)", type="password")
        submitted = st.form_submit_button("Connect tool", type="primary")
    if submitted:
        try:
            frame = fetch_tool_json(url, api_key)
            st.session_state.data = frame
            st.session_state.source_name = f"Tool: {url}"
            st.session_state.source_status["Tool connection"] = True
            st.success(f"Loaded {len(frame):,} rows from tool response.")
        except (SourceConnectionError, ValueError) as exc:
            st.session_state.source_status["Tool connection"] = False
            st.error(str(exc))


def _upload_panel() -> None:
    st.header("2. Choose a source")
    source_kind = st.segmented_control(
        "Source type",
        ["File upload", "PostgreSQL warehouse", "Tool connection"],
        default=st.session_state.source_kind,
        key="source_kind_selector",
    )
    if source_kind is None:
        source_kind = "File upload"
    st.session_state.source_kind = source_kind
    if source_kind == "PostgreSQL warehouse":
        _postgres_panel()
        _connection_overview()
        return
    if source_kind == "Tool connection":
        _tool_panel()
        _connection_overview()
        return

    st.subheader("File upload")
    uploaded_file = st.file_uploader(
        "Choose a CSV, Excel file, image, or PDF",
        type=["csv", "xlsx", "xls", "jpg", "jpeg", "png", "bmp", "tif", "tiff", "pdf"],
    )
    if uploaded_file is None:
        st.info("Upload a source file to start the import wizard.")
        return

    st.session_state.source_name = uploaded_file.name
    st.session_state.source_status["File upload"] = True
    if st.button("Extract data", type="primary", width="content"):
        try:
            frame = extract_file(_save_upload(uploaded_file))
            st.session_state.data = frame
            st.success(f"Extracted {len(frame):,} rows and {len(frame.columns):,} columns.")
        except ExtractionError as exc:
            st.error(str(exc))

    frame = st.session_state.data
    if isinstance(frame, pd.DataFrame) and st.session_state.source_name == uploaded_file.name:
        st.subheader(f"Preview: {uploaded_file.name}")
        edited = st.data_editor(
            frame.head(100),
            width="stretch",
            hide_index=True,
            key="source_preview",
        )
        if not edited.equals(frame.head(100)):
            updated = frame.copy()
            updated.loc[edited.index, edited.columns] = edited
            st.session_state.data = updated
        st.download_button(
            "Download preview as CSV",
            data=frame.to_csv(index=False).encode("utf-8"),
            file_name=f"{Path(uploaded_file.name).stem}-preview.csv",
            mime="text/csv",
        )
    _connection_overview()


def _visualization_panel(frame: pd.DataFrame) -> None:
    st.header("3. Data quality and visualisation")
    st.caption(f"Source: {st.session_state.source_name or 'current source'}")
    row_count, column_count = frame.shape
    missing_count = int(frame.isna().sum().sum())
    metric_columns = st.columns(3)
    metric_columns[0].metric("Rows", f"{row_count:,}")
    metric_columns[1].metric("Columns", f"{column_count:,}")
    metric_columns[2].metric("Missing values", f"{missing_count:,}")

    left, right = st.columns(2)
    with left:
        st.subheader("Missing values by column")
        missing = frame.isna().sum().sort_values(ascending=False)
        st.bar_chart(missing[missing > 0], height=260, alt="Missing values by source column")
        if missing.sum() == 0:
            st.success("No missing values detected.")
    with right:
        st.subheader("Numeric distribution")
        numeric = frame.select_dtypes(include="number")
        if numeric.empty:
            st.info("No numeric columns available for a chart.")
        else:
            selected = st.selectbox("Numeric column", list(numeric.columns))
            st.line_chart(
                numeric[selected].reset_index(drop=True),
                height=260,
                alt=f"Distribution of {selected}",
            )

    st.subheader("Column profile")
    profile = pd.DataFrame(
        {
            "Column": frame.columns,
            "Type": [str(frame[column].dtype) for column in frame.columns],
            "Non-empty": [int(frame[column].notna().sum()) for column in frame.columns],
            "Unique": [int(frame[column].nunique(dropna=True)) for column in frame.columns],
        }
    )
    st.dataframe(profile, width="stretch", hide_index=True, alt="Source column profile")


def _mapping_panel(frame: pd.DataFrame) -> None:
    st.header("4. Visual field mapping")
    model = st.text_input("Target Odoo model", value="res.partner", key="target_model")
    if st.button("Load Odoo fields", disabled=not st.session_state.connected):
        try:
            client: OdooClient = st.session_state.odoo_client
            st.session_state.odoo_fields = client.fields_get(model)
            st.success(f"Loaded {len(st.session_state.odoo_fields)} fields from {model}.")
        except (OdooError, ValueError) as exc:
            st.error(str(exc))
    if not st.session_state.connected:
        st.caption("Connect to Odoo to load live target fields. You can still review source data.")
        return
    fields = st.session_state.odoo_fields
    if not fields:
        st.info("Load the target model fields to create mappings.")
        return
    source_columns = ["(skip)"] + list(frame.columns)
    mapping_rows = []
    for field_name, metadata in fields.items():
        selected = st.selectbox(
            f"{metadata.get('string', field_name)} ({metadata.get('type', 'unknown')})",
            source_columns,
            key=f"mapping_{field_name}",
        )
        if selected != "(skip)":
            mapping_rows.append({"Odoo field": field_name, "Source column": selected})
    if mapping_rows:
        st.dataframe(pd.DataFrame(mapping_rows), width="stretch", hide_index=True, alt="Odoo field mappings")


def main() -> None:
    _init_state()
    _connection_panel()
    st.title("Easy Odoo Data")
    st.caption("Connect → upload → inspect → map. A clear path from raw files to Odoo.")
    _upload_panel()
    if isinstance(st.session_state.data, pd.DataFrame):
        frame = st.session_state.data
        _visualization_panel(frame)
        _mapping_panel(frame)
    if st.button("Reset current import"):
        st.session_state.data = None
        st.session_state.source_name = None
        st.session_state.odoo_fields = {}
        st.session_state.source_status = {
            "File upload": False,
            "PostgreSQL warehouse": False,
            "Tool connection": False,
        }
        st.rerun()


if __name__ == "__main__":
    main()
