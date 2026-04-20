"""
Meta Ad Library Audit Script
Input:  brands.csv (column: brand_name)
Output: output/{brand_name}.json, page_id_cache.csv, failed.csv
"""

import asyncio
import csv
import json
import os
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import re

import requests
from playwright.async_api import async_playwright

# ── Config ────────────────────────────────────────────────────────────────────
SEARCHAPI_KEY = os.getenv("SEARCHAPI_KEY")
COUNTRY = "IN"
INPUT_CSV = "brands.csv"
OUTPUT_DIR = Path("output")
CACHE_FILE = Path("page_id_cache.csv")
FAILED_FILE = Path("failed.csv")

PLAYWRIGHT_DELAY_MIN = 3  # seconds between browser requests
PLAYWRIGHT_DELAY_MAX = 6
SEARCHAPI_DELAY = 3.5
LOOKBACK_DAYS = 14

# Quick validation mode: set to True to bypass brands.csv and test one/few brands inline.
USE_INLINE_TEST_BRANDS = False
INLINE_TEST_BRANDS = ["Lenskart"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_brands(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_cache() -> dict:
    cache = {}
    if CACHE_FILE.exists():
        with open(CACHE_FILE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                cache[row["brand_name"]] = row["page_id"]
    return cache


def append_cache(brand_name: str, page_id: str):
    write_header = not CACHE_FILE.exists()
    with open(CACHE_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["brand_name", "page_id", "resolved_at"])
        if write_header:
            w.writeheader()
        w.writerow({"brand_name": brand_name, "page_id": page_id, "resolved_at": datetime.utcnow().isoformat()})


def append_failed(brand_name: str, reason: str):
    write_header = not FAILED_FILE.exists()
    with open(FAILED_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["brand_name", "reason", "failed_at"])
        if write_header:
            w.writeheader()
        w.writerow({"brand_name": brand_name, "reason": reason, "failed_at": datetime.utcnow().isoformat()})


def save_json(brand_name: str, data: dict):
    OUTPUT_DIR.mkdir(exist_ok=True)
    safe_name = brand_name.replace("/", "_").replace(" ", "_")
    path = OUTPUT_DIR / f"{safe_name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  ✓ Saved → {path}")


def _parse_iso8601(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def filter_ads_last_n_days(data: dict, days: int) -> dict:
    """
    Keep ads that started or ended within the lookback window.
    This protects against upstream API params changing or being unavailable.
    """
    ads = data.get("ads", [])
    if not isinstance(ads, list) or days <= 0:
        return data

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    filtered_ads = []

    for ad in ads:
        start_dt = _parse_iso8601(ad.get("start_date"))
        end_dt = _parse_iso8601(ad.get("end_date"))

        # Keep ads if either boundary falls inside the lookback window.
        if (start_dt and start_dt >= cutoff) or (end_dt and end_dt >= cutoff):
            filtered_ads.append(ad)

    output = dict(data)
    output["ads"] = filtered_ads

    # Reflect filtered count so downstream consumers see accurate totals.
    search_info = dict(output.get("search_information", {}))
    search_info["total_results"] = len(filtered_ads)
    output["search_information"] = search_info
    output["filters_applied"] = {"lookback_days": days}

    return output


# ── Playwright: resolve page_id ───────────────────────────────────────────────

async def resolve_page_id(page, brand_name: str) -> str | None:
    url = (
        f"https://www.facebook.com/ads/library/"
        f"?search_type=page&q={requests.utils.quote(brand_name)}&country={COUNTRY}"
        f"&active_status=active&ad_type=all&media_type=all"
    )
    print(f"  → Playwright: opening FB Ad Library for '{brand_name}'")

    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)  # let React render

        # Primary selector: classic Meta Ad Library result links
        links = await page.query_selector_all("a[href*='view_all_page_id']")

        # Fallback selector: any anchor with page_id style params
        if not links:
            links = await page.query_selector_all("a[href*='page_id='], a[href*='view_all_page_id=']")

        for link in links:
            href = await link.get_attribute("href")
            if not href:
                continue
            parsed = urlparse(href)
            params = parse_qs(parsed.query)
            page_id = (
                params.get("view_all_page_id", [None])[0]
                or params.get("page_id", [None])[0]
                or params.get("id", [None])[0]
            )
            if page_id and page_id.isdigit():
                print(f"  ✓ Resolved page_id: {page_id}")
                return page_id

        # Final fallback: regex scan full HTML for likely numeric page IDs.
        html = await page.content()
        patterns = [
            r"view_all_page_id=(\d{6,})",
            r"[?&]page_id=(\d{6,})",
            r'"pageID":"(\d{6,})"',
            r'"page_id":"(\d{6,})"',
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                page_id = match.group(1)
                print(f"  ✓ Resolved page_id (fallback): {page_id}")
                return page_id

        print(f"  ✗ No page results found for '{brand_name}'")
        return None

    except Exception as e:
        print(f"  ✗ Playwright error for '{brand_name}': {e}")
        return None


# ── SearchAPI: fetch ads ──────────────────────────────────────────────────────

def fetch_ads(page_id: str) -> dict | None:
    params = {
        "engine": "meta_ad_library",
        "page_id": page_id,
        "country": COUNTRY,
        "active_status": "active",
        "ad_type": "all",
        "api_key": SEARCHAPI_KEY,
    }
    backoff = 5.0
    for attempt in range(1, 6):
        try:
            resp = requests.get("https://www.searchapi.io/api/v1/search", params=params, timeout=30)
            if resp.status_code == 429:
                print(f"  ⚠ SearchAPI 429 (attempt {attempt}/5), sleeping {backoff:.0f}s…")
                time.sleep(backoff + random.uniform(0, 2))
                backoff = min(backoff * 1.8, 120.0)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as e:
            print(f"  ✗ SearchAPI HTTP error for page_id {page_id}: {e}")
            return None
        except Exception as e:
            print(f"  ✗ SearchAPI error for page_id {page_id}: {e}")
            return None
    print(f"  ✗ SearchAPI: gave up after 429s for page_id {page_id}")
    return None


# ── Main ──────────────────────────────────────────────────────────────────────

async def run():
    if not SEARCHAPI_KEY:
        raise ValueError("SEARCHAPI_KEY is missing. Set it in your environment or .env before running.")

    if USE_INLINE_TEST_BRANDS:
        brands = [{"brand_name": brand.strip()} for brand in INLINE_TEST_BRANDS if brand.strip()]
    else:
        brands = load_brands(INPUT_CSV)
    cache = load_cache()
    print(f"Loaded {len(brands)} brands. Cache has {len(cache)} resolved IDs.\n")

    async with async_playwright() as p:
        # Headless mode is more stable for unattended batch runs.
        browser = await p.chromium.launch(headless=True, channel="chrome")
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        for i, row in enumerate(brands, 1):
            brand_name = row["brand_name"].strip()
            print(f"\n[{i}/{len(brands)}] {brand_name}")

            # 1. Resolve page_id
            if brand_name in cache:
                page_id = cache[brand_name]
                print(f"  → page_id from cache: {page_id}")
            else:
                page_id = await resolve_page_id(page, brand_name)
                if not page_id:
                    append_failed(brand_name, "page_id not resolved")
                    continue
                cache[brand_name] = page_id
                append_cache(brand_name, page_id)
                await asyncio.sleep(random.uniform(PLAYWRIGHT_DELAY_MIN, PLAYWRIGHT_DELAY_MAX))

            # 2. Fetch ads from SearchAPI
            print(f"  → SearchAPI: fetching ads for page_id {page_id}")
            data = fetch_ads(page_id)
            if not data:
                append_failed(brand_name, "SearchAPI returned no data")
                continue

            data = filter_ads_last_n_days(data, LOOKBACK_DAYS)

            # 3. Save JSON
            save_json(brand_name, data)
            time.sleep(SEARCHAPI_DELAY)

        await browser.close()

    print(f"\nDone. Check output/ for results, failed.csv for errors.")


if __name__ == "__main__":
    asyncio.run(run())
