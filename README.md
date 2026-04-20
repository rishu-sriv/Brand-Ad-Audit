# Meta Ad Library Audit

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

## Configure

Set your SearchAPI key:
```bash
cp .env.example .env
# then edit .env
```

## Input

Edit `brands.csv` — one brand name per row:

```csv
brand_name
Mamaearth
boAt
Wakefit
```

## Run

```bash
python audit.py
```

## Output

| File                           | Contents                                              |
| ------------------------------ | ----------------------------------------------------- |
| `output/{brand}.json` | Raw SearchAPI response for each brand |
| `output/all_company_summaries.md` | Combined per-brand audit summaries |
| `output/company_ad_audits.csv` | `company_name,audit` summary export |
| `page_id_cache.csv` | Resolved brand → page_id mappings (reused on re-runs) |
| `failed.csv` | Brands that couldn't be resolved or fetched |

## Notes

- Browser opens in headed mode (visible Chrome window) — don't close it while running
- If FB blocks after many requests, add a longer delay or run in batches
- Brands already in `page_id_cache.csv` skip the Playwright step on re-runs
- If a brand resolves to the wrong FB page, manually add the correct `page_id` to `page_id_cache.csv`
