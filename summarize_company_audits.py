import argparse
import json
import csv
from collections import Counter
from datetime import datetime
from pathlib import Path


OUTPUT_DIR = Path("output")
BRANDS_CSV = Path("brands.csv")


def json_stem(brand_name: str) -> str:
    """Must match `save_json` in audit.py (filename stem)."""
    return brand_name.replace("/", "_").replace(" ", "_")


def company_name_for_json_path(path: Path, ordered_brands: list[str]) -> str:
    stem = path.stem
    for b in ordered_brands:
        if json_stem(b) == stem:
            return b
    return stem.replace("_", " ")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def flight_window(ads: list[dict]) -> tuple[str, str]:
    starts = [parse_iso(ad.get("start_date")) for ad in ads]
    ends = [parse_iso(ad.get("end_date")) for ad in ads]
    starts = [dt for dt in starts if dt]
    ends = [dt for dt in ends if dt]
    if not starts or not ends:
        return ("N/A", "N/A")
    return (min(starts).strftime("%b %d"), max(ends).strftime("%b %d"))


def summarize_formats(ads: list[dict]) -> str:
    if not ads:
        return "No creatives"
    format_counter = Counter()
    total_videos = 0
    for ad in ads:
        snapshot = ad.get("snapshot", {})
        display_format = snapshot.get("display_format", "UNKNOWN")
        format_counter[display_format] += 1
        total_videos += len(snapshot.get("videos", []) or [])

    top = [name for name, _ in format_counter.most_common(3)]
    has_video = "near-zero video" if total_videos == 0 else f"{total_videos} video assets"
    return f"Heavy {'/'.join(top)} + {has_video}"


def summarize_platforms(ads: list[dict]) -> str:
    platforms = set()
    for ad in ads:
        for platform in ad.get("publisher_platform", []) or []:
            platforms.add(platform)
    if not platforms:
        return "Unknown"
    order = ["FACEBOOK", "INSTAGRAM", "MESSENGER", "THREADS", "AUDIENCE_NETWORK"]
    sorted_platforms = [p for p in order if p in platforms] + sorted(platforms - set(order))
    mapping = {
        "FACEBOOK": "FB",
        "INSTAGRAM": "IG",
        "MESSENGER": "Messenger",
        "THREADS": "Threads",
        "AUDIENCE_NETWORK": "Audience Network",
    }
    return ", ".join(mapping.get(p, p.title()) for p in sorted_platforms)


def build_summary(company: str, payload: dict) -> str:
    ads = payload.get("ads", []) if isinstance(payload.get("ads", []), list) else []
    total_results = payload.get("search_information", {}).get("total_results", len(ads))
    start, end = flight_window(ads)
    platforms = summarize_platforms(ads)
    formats = summarize_formats(ads)

    return f"""## {company}

🧾 Snapshot
Active creatives: ~{total_results} ads
Flight window: {start} -> {end} (continuous refresh)
Platforms: {platforms}
Formats: {formats}

🧠 What {company} is missing
1. ❌ No memory -> stateless ads
DPA / DCO + catalog scaling
Every ad = first-time experience
No awareness of what user already saw
No sequencing or cross-session learning

👉 Result: repetition, not compounding

2. ❌ No journey orchestration
Flow = click -> PDP -> hope
No "what next if no conversion"
No funnel progression (style -> offer -> proof -> urgency)

👉 Result: flat funnel, no narrative

3. ❌ Over-reliance on offers
B1G1, discounts, price-led hooks
Missing identity + lifestyle positioning
No contextual messaging by persona/use-case

👉 Result: margin pressure + commoditization

4. ❌ No creative learning loop
Creatives scale, but learnings don't
No hook-level intelligence
No cross-campaign memory

👉 Result: re-learning the same lessons

5. ❌ Weak differentiation
Product-led, clean, offer-heavy ads
Missing UGC, story, emotion, problem hooks

👉 Result: blends with every D2C brand

Pitch Angle
One-liner

"You've optimized delivery - but not memory. So your ads scale impressions, not learning."
"""


def load_brands_in_order(path: Path) -> list[str]:
    if not path.exists():
        return []
    brands: list[str] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            brand = (row.get("brand_name") or "").strip()
            if brand:
                brands.append(brand)
    return brands


def compile_ordered_sections(ordered_brands: list[str]) -> tuple[list[str], int]:
    compiled: list[str] = []
    missing_count = 0
    for brand in ordered_brands:
        path = OUTPUT_DIR / f"{json_stem(brand)}.json"
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            compiled.append(build_summary(brand, payload).strip())
        else:
            missing_count += 1
            compiled.append(
                f"""## {brand}

⚠️ No audit data available yet for this brand in `output/`.
"""
            )
    return compiled, missing_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Build per-brand summaries from Meta audit JSON.")
    parser.add_argument(
        "--append-to-combined",
        action="store_true",
        help="Append brands.csv-ordered summaries to output/all_company_summaries.md (does not replace file).",
    )
    args = parser.parse_args()

    json_files = sorted(OUTPUT_DIR.glob("*.json"))
    ordered_brands = load_brands_in_order(BRANDS_CSV)

    if json_files:
        for path in json_files:
            with path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            company = company_name_for_json_path(path, ordered_brands)
            summary = build_summary(company, payload)
            out_path = OUTPUT_DIR / f"{path.stem}_summary.md"
            out_path.write_text(summary, encoding="utf-8")
            print(f"Saved {out_path}")
    elif not args.append_to_combined:
        print("No JSON files found in output/.")
        return

    if not ordered_brands and json_files:
        ordered_brands = sorted(p.stem.replace("_", " ") for p in json_files)

    compiled, missing_count = compile_ordered_sections(ordered_brands)
    combined_path = OUTPUT_DIR / "all_company_summaries.md"
    body = "\n\n---\n\n".join(compiled) + "\n"

    if args.append_to_combined:
        if combined_path.exists():
            prev = combined_path.read_text(encoding="utf-8").rstrip()
            combined_path.write_text(prev + "\n\n---\n\n" + body, encoding="utf-8")
            print(f"Appended to {combined_path}")
        else:
            combined_path.write_text(body, encoding="utf-8")
            print(f"Created {combined_path}")
    else:
        combined_path.write_text(body, encoding="utf-8")
        print(f"Saved {combined_path}")

    print(f"Brands listed: {len(ordered_brands)} | Missing summaries: {missing_count}")


if __name__ == "__main__":
    main()
