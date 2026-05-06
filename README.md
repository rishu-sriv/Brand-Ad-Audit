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

## Similarweb Lead Workflow

Collect Similarweb channel + traffic source data for a specific company/domain:

```bash
python similarweb_audit.py --company gonoise.com --manual-login
```

Output:
- `output/{company}_similarweb.json`

Tips:
- First run with `--manual-login`, sign in, then press Enter in terminal to scrape.
- By default it uses your macOS Chrome user data directory (`~/Library/Application Support/Google/Chrome`) and profile `Default`.
- You can target another Chrome profile via `--profile-name "Profile 1"`.
- Keep the page filters as needed (date range, geo, traffic type) before extraction.
- If your main Chrome is already open and profile lock happens, attach to existing Chrome:
  1) `open -na "Google Chrome" --args --remote-debugging-port=9222`
  2) `python similarweb_audit.py --company gonoise.com --connect-cdp-url http://127.0.0.1:9222`

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
