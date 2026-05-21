#!/usr/bin/env python3
"""
adif_strip_pii.py — Strip PII fields from an ADIF log file.

Usage:
    python3 adif_strip_pii.py input.adi [output.adi]
    python3 adif_strip_pii.py input.adi --dry-run
    python3 adif_strip_pii.py input.adi output.adi --force   # overwrite if exists

If no output path is given the cleaned file is written to <input>-clean.adi.
The output file will NOT be overwritten unless --force is passed.

Fields kept (non-PII):
    CALL, QSO_DATE, QSO_DATE_OFF, TIME_ON, TIME_OFF,
    BAND, FREQ, BAND_RX, FREQ_RX, MODE, SUBMODE,
    RST_SENT, RST_RCVD, STATION_CALLSIGN, MY_CALL,
    MY_SIG, MY_SIG_INFO, SIG, SIG_INFO,
    DXCC, COUNTRY, CONT, CQZ, ITUZ, STATE,
    ADIF_VER, PROGRAMID, PROGRAMVERSION (header only)

Everything else — including all free-form text between tags — is stripped.
The parser is length-driven: field values are consumed by their declared byte
count, so embedded <EOR>/<EOH> literals inside values cannot leak data.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

# Fields that are safe to publish. All others are stripped.
# Allowlist intentionally includes only well-defined, non-free-form fields.
# MY_SIG_INFO / SIG_INFO hold public POTA/SOTA references (e.g. "K-4564"), not PII.
# STATE is a two-letter abbreviation — coarse enough to retain.
SAFE_FIELDS = {
    "QSO_DATE",
    "QSO_DATE_OFF",
    "TIME_ON",
    "TIME_OFF",
    "BAND",
    "BAND_RX",
    "FREQ",
    "FREQ_RX",
    "MODE",
    "SUBMODE",
    "RST_SENT",
    "RST_RCVD",
    "MY_SIG",
    "MY_SIG_INFO",
    "SIG",
    "SIG_INFO",
    "GRIDSQUARE",
    "MY_GRIDSQUARE",
    "DXCC",
    "COUNTRY",
    "CONT",
    "CQZ",
    "ITUZ",
    "STATE",
    # ADIF header fields
    "ADIF_VER",
    "PROGRAMID",
    "PROGRAMVERSION",
}


def parse_adif(text):
    """
    Length-driven ADIF parser. Reads tags sequentially and consumes exactly
    the declared number of characters for each field value. All literal text
    between tags is discarded — it cannot carry leaked PII.

    Returns (header_fields, records) where each is a list of
    (field_name_upper, value) tuples.
    """
    pos = 0
    n = len(text)
    header_fields = []
    records = []
    current_record = []
    in_header = True

    while pos < n:
        tag_start = text.find("<", pos)
        if tag_start == -1:
            break

        tag_end = text.find(">", tag_start)
        if tag_end == -1:
            break

        tag_content = text[tag_start + 1 : tag_end]
        pos = tag_end + 1

        parts = tag_content.split(":", 2)
        name = parts[0].upper().strip()

        if name == "EOH":
            in_header = False
            continue

        if name == "EOR":
            if current_record:
                records.append(current_record)
            current_record = []
            continue

        # Regular field: must declare a length
        if len(parts) < 2:
            continue

        try:
            length = int(parts[1].strip())
        except ValueError:
            continue

        if length < 0:
            continue

        value = text[pos : pos + length]
        pos += length

        if in_header:
            header_fields.append((name, value))
        else:
            current_record.append((name, value))

    return header_fields, records


def rebuild_adif(header_fields, records):
    """
    Reconstruct clean ADIF from parsed fields, keeping only SAFE_FIELDS.
    Returns (cleaned_text, removed_counts).
    """
    removed = Counter()
    lines = []

    # Header
    header_parts = []
    for name, value in header_fields:
        if name in SAFE_FIELDS:
            header_parts.append(f"<{name}:{len(value)}>{value}")
        else:
            removed[name] += 1
    if header_parts:
        lines.append(" ".join(header_parts))
    lines.append("<EOH>")

    # Records
    for record in records:
        record_parts = []
        for name, value in record:
            if name in SAFE_FIELDS:
                record_parts.append(f"<{name}:{len(value)}>{value}")
            else:
                removed[name] += 1
        if record_parts:
            lines.append(" ".join(record_parts) + " <EOR>")

    return "\n".join(lines) + "\n", removed


def main():
    parser = argparse.ArgumentParser(
        description="Strip PII fields from an ADIF log file."
    )
    parser.add_argument("input", help="Path to input .adi file")
    parser.add_argument(
        "output",
        nargs="?",
        help="Path to output file (default: <input>-clean.adi)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be stripped without writing output",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output file if it already exists",
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.is_file():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        adif_text = input_path.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError:
        print(
            "Error: file is not valid UTF-8. Re-encode it first (e.g. iconv -f latin1 -t utf-8).",
            file=sys.stderr,
        )
        sys.exit(1)

    header_fields, records = parse_adif(adif_text)
    cleaned, removed = rebuild_adif(header_fields, records)

    if removed:
        print("Fields stripped:")
        for field, count in sorted(removed.items()):
            print(f"  {field}: {count} occurrence(s)")
    else:
        print("No PII fields found — file is already clean.")

    print(f"Records processed: {len(records)}")

    if args.dry_run:
        print("Dry run — no file written.")
        return

    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = input_path.with_stem(input_path.stem + "-clean")

    if output_path.exists() and not args.force:
        print(
            f"Error: output file already exists: {output_path}\n"
            "Use --force to overwrite.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        output_path.write_text(cleaned, encoding="utf-8")
    except OSError as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Cleaned file written to: {output_path}")


if __name__ == "__main__":
    main()
