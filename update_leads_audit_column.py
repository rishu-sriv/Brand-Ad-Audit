"""
Fill or refresh an "Audit Summary" (or custom) column from output/{{company}}.json,
using the same narrative as export_brand_audits_csv.build_audit_summary.

Prerequisite: run audit.py (with enough JSON files in output/) for each company row.

Usage:
  python update_leads_audit_column.py -i path/to/leads.csv \\
    --company-column company_name --audit-column "Audit Summary" -o leads_with_audits.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from export_brand_audits_csv import build_audit_summary
from summarize_company_audits import json_stem

OUTPUT_DIR = Path("output")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update audit summary column from Meta audit JSON files in output/."
    )
    parser.add_argument("-i", "--input", type=Path, required=True, help="Input leads CSV path")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output CSV (default: <input_stem>_with_audits.csv next to input)",
    )
    parser.add_argument(
        "--company-column",
        default="company_name",
        help="Column containing brand / company name (must match audit JSON naming). Default: company_name",
    )
    parser.add_argument(
        "--audit-column",
        default="Audit Summary",
        help='Column to write summaries into (created if missing). Default: "Audit Summary"',
    )
    args = parser.parse_args()

    input_path = args.input.expanduser().resolve()
    if not input_path.is_file():
        raise SystemExit(f"Input not found: {input_path}")

    out_path = args.output
    if out_path is None:
        out_path = input_path.with_name(f"{input_path.stem}_with_audits{input_path.suffix}")
    else:
        out_path = out_path.expanduser().resolve()

    with input_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise SystemExit("CSV has no header row.")
        fieldnames = list(reader.fieldnames)
        company_col = args.company_column
        audit_col = args.audit_column
        if company_col not in fieldnames:
            raise SystemExit(
                f"Column {company_col!r} not found. Available: {', '.join(fieldnames)}"
            )
        if audit_col not in fieldnames:
            fieldnames.append(audit_col)
        rows = list(reader)

    filled = 0
    missing_json = 0
    for row in rows:
        company = (row.get(company_col) or "").strip()
        if not company:
            row[audit_col] = ""
            continue
        json_path = OUTPUT_DIR / f"{json_stem(company)}.json"
        if not json_path.exists():
            missing_json += 1
            row[audit_col] = (
                "No audit summary: no matching JSON in output/ for this row "
                f"(expected file: {json_stem(company)}.json)."
            )
            continue
        with json_path.open("r", encoding="utf-8") as jf:
            payload = json.load(jf)
        row[audit_col] = build_audit_summary(company, payload)
        filled += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as wf:
        w = csv.DictWriter(wf, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})

    print(
        f"Wrote {len(rows)} rows -> {out_path}\n"
        f"  Summaries from JSON: {filled}\n"
        f"  Missing JSON (placeholder text): {missing_json}"
    )


if __name__ == "__main__":
    main()
