# Meta Ad Audit Implementation Plan

This document explains how our Meta Ad Library audit workflow works and how to operate it.
It is written for both technical and non-technical team members.

## Plan 1: Execution Workflow (Operator Playbook)

### 1) Goal
Collect live Meta ad data for selected brands and save it in a structured format for analysis.

### 2) Inputs
- Brand list from `brands.csv` (column name must be `brand_name`)
- SearchAPI key in `.env`:
  - `SEARCHAPI_KEY=...`
- Country is currently set to India (`COUNTRY = "IN"` in script)

### 3) Outputs
- `output/{brand}.json`: Raw ad data response for each brand
- `page_id_cache.csv`: Saved brand-to-page mapping to speed up reruns
- `failed.csv`: Brands that failed and reason for failure

### 4) Runtime Workflow
1. Load all brands from input (or inline test brands when enabled).
2. For each brand:
   - Check if page id already exists in `page_id_cache.csv`.
   - If not found, open Meta Ad Library in browser (Playwright) and resolve page id.
   - Use resolved page id to call SearchAPI and fetch ad data.
   - Save response to `output/{brand}.json`.
   - Log failure to `failed.csv` if resolve/fetch fails.
3. Continue until all brands are processed.

### 5) Standard Run Steps
```bash
cd /Users/rishu/Downloads/meta-ad-audit
source .venv/bin/activate
set -a; source .env; set +a
python audit.py
```

### 6) Validation Checklist (Post Run)
- Confirm expected JSON files are created in `output/`
- Open 2-3 files and confirm ad records exist
- Check `failed.csv` for unresolved or blocked brands
- Confirm `page_id_cache.csv` is updated for new brands

### 7) Re-run and Recovery Rules
- Re-runs are faster because cached page ids skip browser lookup
- If a brand resolves to wrong page:
  - Manually fix `page_id_cache.csv` for that brand and rerun
- If a brand fails:
  - Update brand spelling (or exact page name), rerun only that brand in test mode

### 8) Known Risks and Mitigations
- Meta page structure changes -> fallback resolver logic handles alternate patterns
- Rate limiting/blocking -> run in batches, keep delays between requests
- Missing/invalid API key -> ensure `.env` has valid `SEARCHAPI_KEY`
- Wrong brand page match -> manually override cached page id

---

## Plan 2: High-Level Architecture (Non-Technical View)

### What this system does (in plain English)
This tool is an automated researcher.  
You give it brand names, and it finds each brand's Meta ad page, downloads active ad data, and stores files your team can review.

### Components (Simple)
- **Brand List** (`brands.csv`): The list of companies to audit
- **Resolver** (Playwright): Finds the brand's Meta page id
- **Data Fetcher** (SearchAPI): Pulls ad data using page id
- **Storage** (`output/*.json`): Saves one data file per brand
- **Memory Layer** (`page_id_cache.csv`): Remembers page ids for future speed
- **Issue Log** (`failed.csv`): Records what failed and why

### End-to-End Flow
1. Team provides brand names.
2. System identifies the correct Meta page for each brand.
3. System fetches ad data for that page.
4. System saves data files for analysis.
5. If something fails, it logs the issue and continues with next brand.

### Why this architecture is good for GTM
- **Scalable:** Can run for 1 brand or 500 brands
- **Resilient:** Continues processing even if some brands fail
- **Efficient:** Reuses cached page ids, reducing repeated effort
- **Auditable:** Every run leaves clear outputs and failure logs
- **Actionable:** Output files can feed competitor tracking, creative analysis, and market intelligence dashboards

### How GTM can use outputs
- Track competitor campaign frequency and themes
- Detect new ad launches from key brands
- Build weekly "who is advertising what" summaries
- Support positioning and messaging decisions with live ad evidence

### Recommended Team Process
- Weekly: run full brand list
- Daily: run top-priority competitor subset
- Monthly: clean and verify `page_id_cache.csv`
- Before stakeholder review: sample-check 5-10 brand outputs for quality
