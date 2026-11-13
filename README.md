# Easy Odoo Data

Open-source ETL foundation for importing Excel, CSV, and OCR-extracted documents into Odoo.

## Phase 1

- `app/odoo_client.py`: authenticated XML-RPC client, model metadata, many2one lookup, and batch create/write.
- `app/extractor.py`: CSV/XLS/XLSX and image/PDF extraction into pandas DataFrames.
- `main.py`: minimal Streamlit entry point for the upcoming mapping wizard.

## Local setup

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
streamlit run main.py
```

OCR dependencies are loaded only when an image or PDF is extracted. Keep Odoo credentials in `.env`, never in source control.

