# Examples

This folder contains safe, minimal examples so users can understand the workflow without accessing private data.

## Included

- `brands.sample.csv`: a tiny sample brand list format.

## Typical flow

1. Copy `.env.example` to `.env` and set `SEARCHAPI_KEY`.
2. Prepare your own `brands.csv` (not committed).
3. Run `python audit.py` to fetch ad library JSON.
4. Run `python summarize_company_audits.py` for markdown summaries.
5. Run `python export_brand_audits_csv.py` for a `company_name,audit` CSV export.
