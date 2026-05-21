#!/usr/bin/env python3
"""
adif_strip_pii.py — Strip PII fields from an ADIF log file.

Usage:
    python3 adif_strip_pii.py input.adi [output.adi]
    python3 adif_strip_pii.py input.adi --dry-run

If no output path is given the cleaned file is written to <input>-clean.adi.
--dry-run reports what would be removed without writing anything.

Fields kept (non-PII):
    CALL, QSO_DATE, QSO_DATE_OFF, TIME_ON, TIME_OFF,
    BAND, FREQ, BAND_RX, FREQ_RX, MODE, SUBMODE,
    RST_SENT, RST_RCVD, STATION_CALLSIGN, MY_CALL,
    MY_SIG, MY_SIG_INFO, SIG, SIG_INFO,
    DXCC, COUNTRY, CONT, CQZ, ITUZ, STATE,
    ADIF_VER, PROGRAMID, PROGRAMVERSION (header only)

Everything else is stripped.
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

# Fields that are safe to publish. All others are stripped.
SAFE_FIELDS = {
    "CALL",
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
    "STATION_CALLSIGN",
    "MY_CALL",
    "MY_SIG",
    "MY_SIG_INFO",
    "SIG",
    "SIG_INFO",
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

# Regex to match a single ADIF field: <FIELD:LEN> or <FIELD:LEN:TYPE>
_FIELD_RE = re.compile(
    r"<([A-Za-z0-9_]+):(\d+)(?::[^>]+)?>(.*)",
    re.DOTALL,
)


def _parse_fields(text):
    """
    Yield (field_name_upper, raw_tag, value) tuples from an ADIF block.
    raw_tag includes the angle brackets and declared length; value is the
    declared-length slice of text immediately following the tag.
    Preserves all literal text between fields (whitespace, newlines).
    Returns a list of ('literal', text) | ('field', name, raw_tag, value) tuples.
    """
    tokens = []
    pos = 0
    for m in re.finditer(r"<([A-Za-z0-9_]+):(\d+)(?::[^>]+)?>", text):
        start, end = m.span()
        if pos < start:
            tokens.append(("literal", text[pos:start]))
        name = m.group(1).upper()
        length = int(m.group(2))
        value = text[end : end + length]
        tokens.append(("field", name, m.group(0), value))
        pos = end + length
    if pos < len(text):
        tokens.append(("literal", text[pos:]))
    return tokens


def strip_pii(adif_text):
    """
    Parse adif_text, remove any field not in SAFE_FIELDS, return
    (cleaned_text, removed_counts).
    """
    removed = Counter()

    # Split header from records at <EOH>
    eoh_match = re.search(r"<EOH>", adif_text, re.IGNORECASE)
    if eoh_match:
        header_raw = adif_text[: eoh_match.end()]
        records_raw = adif_text[eoh_match.end() :]
    else:
        # No header — treat everything as records
        header_raw = ""
        records_raw = adif_text

    def rebuild(tokens):
        out = []
        for token in tokens:
            if token[0] == "literal":
                out.append(token[1])
            else:
                _, name, raw_tag, value = token
                if name in SAFE_FIELDS:
                    out.append(raw_tag + value)
                else:
                    removed[name] += 1
        return "".join(out)

    cleaned_header = rebuild(_parse_fields(header_raw))

    # Split records on <EOR>, process each individually
    eor_re = re.compile(r"(<EOR>)", re.IGNORECASE)
    parts = eor_re.split(records_raw)
    # parts alternates: record_body, "<EOR>", record_body, "<EOR>", ... trailing
    cleaned_records = []
    i = 0
    while i < len(parts):
        body = parts[i]
        eor = parts[i + 1] if i + 1 < len(parts) else ""
        cleaned_body = rebuild(_parse_fields(body))
        # Only emit the record if it has at least one field left
        if re.search(r"<[A-Za-z0-9_]+:\d+", cleaned_body):
            cleaned_records.append(cleaned_body + eor)
        i += 2 if eor else 1

    cleaned = cleaned_header + "".join(cleaned_records)
    return cleaned, removed


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
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    adif_text = input_path.read_text(encoding="utf-8", errors="replace")
    cleaned, removed = strip_pii(adif_text)

    if removed:
        print("Fields stripped:")
        for field, count in sorted(removed.items()):
            print(f"  {field}: {count} occurrence(s)")
    else:
        print("No PII fields found — file is already clean.")

    if args.dry_run:
        print("Dry run — no file written.")
        return

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_stem(input_path.stem + "-clean")

    output_path.write_text(cleaned, encoding="utf-8")
    print(f"Cleaned file written to: {output_path}")


if __name__ == "__main__":
    main()
