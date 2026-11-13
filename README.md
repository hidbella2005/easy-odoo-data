# Easy Odoo Data

Open-source ETL foundation for importing Excel, CSV, and OCR-extracted documents into Odoo.

## Phase 1

- `app/odoo_client.py`: authenticated XML-RPC client, model metadata, many2one lookup, and batch create/write.
- `app/extractor.py`: CSV/XLS/XLSX and image/PDF extraction into pandas DataFrames.
- `main.py`: Streamlit wizard with Odoo connection, file upload, editable preview,
  data-quality metrics, charts, column profiling, and live field mapping.

## Local setup

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
streamlit run main.py
```

OCR dependencies are loaded only when an image or PDF is extracted. Keep Odoo credentials in `.env`, never in source control.

The UI guides users through four visible steps:

1. Connect to Odoo.
2. Upload and extract a CSV, Excel file, image, or PDF.
3. Review row counts, missing values, numeric distributions, and column profiles.
4. Load a target Odoo model and map source columns to its fields.

