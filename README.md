# Easy Odoo Data

Open-source ETL foundation for importing Excel, CSV, and OCR-extracted documents into Odoo.

## Phase 1

- `app/odoo_client.py`: authenticated XML-RPC client, model metadata, many2one lookup, and batch create/write.
- `app/extractor.py`: CSV/XLS/XLSX and image/PDF extraction into pandas DataFrames.
- `main.py`: Streamlit wizard with Odoo connection, file upload, PostgreSQL warehouse
  queries, JSON tool connections, editable preview, data preparation and cleaning,
  data-quality metrics, charts, connection status cards, column profiling, and live
  field mapping.

## Local setup

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
streamlit run main.py
```

OCR dependencies are loaded only when an image or PDF is extracted. Keep Odoo credentials in `.env`, never in source control.

To prefill the Odoo connection form locally, copy the example and edit it:

```powershell
Copy-Item .env.example .env
```

Docker loads the same `.env` file through `docker-compose.yml`.

The UI guides users through four visible steps:

1. Connect to Odoo.
2. Upload and extract a CSV, Excel file, image, or PDF.
3. Prepare data by trimming text, removing empty or duplicate rows, and filling missing text values.
4. Review connection status, row counts, missing values, numeric distributions, and column profiles.
5. Load a target Odoo model and map source columns to its fields.
6. Choose an Odoo destination (Contacts, CRM leads, Products, Users, or a custom model).
7. Import the prepared mapped rows to Odoo in one batch.

PostgreSQL queries are wrapped in a row limit for safe previews. Tool connections
accept JSON arrays or objects (including `data`, `results`, or `items` envelopes).
The direct Odoo import maps writable scalar fields; relational fields such as
many2one and one2many are hidden until dedicated lookup support is available.

