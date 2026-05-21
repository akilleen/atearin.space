#!/usr/bin/env python3
"""
adif_to_kml.py — Generate a KML file from an ADIF log.

Usage:
    python3 adif_to_kml.py input.adi [output.kml]
    python3 adif_to_kml.py input.adi output.kml --force   # overwrite if exists
    python3 adif_to_kml.py input.adi --no-lines           # omit lines to contacts

Location priority per QSO:
  - Contact: LAT/LON fields → GRIDSQUARE fallback
  - Activation site: MY_LAT/MY_LON fields → MY_GRIDSQUARE fallback

Run against the original (pre-strip) ADIF to get precise coordinates.
The output KML contains no names, email addresses, or other PII —
only call signs, operating data, and coordinates.
"""

import argparse
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from adif_strip_pii import parse_adif


# ── coordinate helpers ────────────────────────────────────────────────────────

def parse_adif_latlon(lat_str, lon_str):
    """
    Parse ADIF LAT/LON: 'N042 54.036' / 'W071 20.154'
    Returns (lat, lon) floats or None.
    """
    try:
        lat_h, lat_rest = lat_str[0].upper(), lat_str[1:]
        lon_h, lon_rest = lon_str[0].upper(), lon_str[1:]
        lat_d, lat_m = lat_rest.split()
        lon_d, lon_m = lon_rest.split()
        lat = float(lat_d) + float(lat_m) / 60.0
        lon = float(lon_d) + float(lon_m) / 60.0
        if lat_h == 'S':
            lat = -lat
        if lon_h == 'W':
            lon = -lon
        return lat, lon
    except (IndexError, ValueError):
        return None


def maidenhead_to_latlon(grid):
    """
    Convert a Maidenhead locator (2, 4, or 6 chars) to (lat, lon) center.
    """
    grid = grid.strip().upper()
    if len(grid) < 2:
        return None
    try:
        lon = (ord(grid[0]) - ord('A')) * 20.0 - 180
        lat = (ord(grid[1]) - ord('A')) * 10.0 - 90
        if len(grid) >= 4:
            lon += int(grid[2]) * 2.0
            lat += int(grid[3]) * 1.0
            if len(grid) >= 6:
                lon += (ord(grid[4]) - ord('A')) * (5.0 / 60)
                lat += (ord(grid[5]) - ord('A')) * (2.5 / 60)
                lon += 2.5 / 60   # centre of subsquare
                lat += 1.25 / 60
            else:
                lon += 1.0        # centre of square
                lat += 0.5
        else:
            lon += 10.0           # centre of field
            lat += 5.0
        return lat, lon
    except (IndexError, ValueError, TypeError):
        return None


def best_coords(fields, grid_key='GRIDSQUARE'):
    """
    Return (lat, lon) derived from the Maidenhead grid square only.
    Deliberately ignores precise LAT/LON fields so that published KML
    coordinates never exceed the ~5 km resolution of a 6-char grid square.
    """
    grid = fields.get(grid_key, '')
    if grid:
        return maidenhead_to_latlon(grid[:6])
    return None


# ── KML helpers ───────────────────────────────────────────────────────────────

def format_description(fields):
    """Build an HTML snippet for a KML placemark popup."""
    parts = []
    date = fields.get('QSO_DATE', '')
    time = fields.get('TIME_ON', '')
    if len(date) == 8:
        date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    if len(time) >= 4:
        time = f"{time[:2]}:{time[2:4]}Z"
    if date:
        parts.append(f"<b>Date:</b> {html.escape(date)}")
    if time:
        parts.append(f"<b>Time:</b> {html.escape(time)}")
    for label, key in [('Band', 'BAND'), ('Mode', 'MODE'),
                       ('RST Sent', 'RST_SENT'), ('RST Rcvd', 'RST_RCVD')]:
        if fields.get(key):
            parts.append(f"<b>{label}:</b> {html.escape(fields[key])}")
    for key in ('SIG_INFO', 'SIG'):
        if fields.get(key):
            parts.append(f"<b>POTA/SOTA:</b> {html.escape(fields[key])}")
            break
    return "<br/>".join(parts)


def build_kml(activation_coords, activation_label, contacts, include_lines=True):
    lat0, lon0 = activation_coords

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '<Document>',
        f'  <name>{html.escape(activation_label)}</name>',
        '',
        '  <Style id="activation-site">',
        '    <IconStyle><color>ff00cc00</color><scale>1.4</scale></IconStyle>',
        '  </Style>',
        '  <Style id="contact">',
        '    <IconStyle><color>ffff7800</color><scale>0.9</scale></IconStyle>',
        '  </Style>',
        '  <Style id="line">',
        '    <LineStyle><color>997800ff</color><width>1.5</width></LineStyle>',
        '  </Style>',
        '',
        '  <Folder><name>Activation Site</name>',
        '  <Placemark>',
        f'    <name>{html.escape(activation_label)}</name>',
        '    <styleUrl>#activation-site</styleUrl>',
        '    <Point>',
        f'      <coordinates>{lon0},{lat0},0</coordinates>',
        '    </Point>',
        '  </Placemark>',
        '  </Folder>',
        '',
        '  <Folder><name>Contacts</name>',
    ]

    for c in contacts:
        lines += [
            '  <Placemark>',
            f'    <name>{html.escape(c["call"])}</name>',
            f'    <description><![CDATA[{c["description"]}]]></description>',
            '    <styleUrl>#contact</styleUrl>',
            '    <Point>',
            f'      <coordinates>{c["lon"]},{c["lat"]},0</coordinates>',
            '    </Point>',
            '  </Placemark>',
        ]

    lines += ['  </Folder>']

    if include_lines:
        lines += ['', '  <Folder><name>Lines</name>']
        for c in contacts:
            lines += [
                '  <Placemark>',
                f'    <name>Line to {html.escape(c["call"])}</name>',
                '    <styleUrl>#line</styleUrl>',
                '    <LineString>',
                '      <tessellate>1</tessellate>',
                f'      <coordinates>{lon0},{lat0},0 {c["lon"]},{c["lat"]},0</coordinates>',
                '    </LineString>',
                '  </Placemark>',
            ]
        lines += ['  </Folder>']

    lines += ['</Document>', '</kml>']
    return '\n'.join(lines) + '\n'


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Generate a KML file from an ADIF log.'
    )
    parser.add_argument('input', help='Path to input .adi file')
    parser.add_argument(
        'output', nargs='?',
        help='Path to output .kml file (default: <input>.kml)',
    )
    parser.add_argument('--force', action='store_true',
                        help='Overwrite output file if it already exists')
    parser.add_argument('--no-lines', action='store_true',
                        help='Omit lines from activation site to contacts')
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.is_file():
        print(f'Error: file not found: {input_path}', file=sys.stderr)
        sys.exit(1)

    try:
        adif_text = input_path.read_text(encoding='utf-8', errors='strict')
    except UnicodeDecodeError:
        print('Error: file is not valid UTF-8.', file=sys.stderr)
        sys.exit(1)

    _, records = parse_adif(adif_text)
    if not records:
        print('No QSO records found.', file=sys.stderr)
        sys.exit(1)

    first = {k: v for k, v in records[0]}

    activation_coords = best_coords(first, grid_key='MY_GRIDSQUARE')
    if not activation_coords:
        print('Error: no MY_GRIDSQUARE in first record.', file=sys.stderr)
        sys.exit(1)

    activation_label = first.get('MY_SIG_INFO') or 'Activation Site'

    contacts = []
    skipped = 0
    for i, record in enumerate(records, start=1):
        fields = {k: v for k, v in record}
        label = fields.get('GRIDSQUARE', '')[:6] or f'Contact {i}'
        coords = best_coords(fields)
        if not coords:
            skipped += 1
            print(f'Warning: no location for contact {i} — skipping', file=sys.stderr)
            continue
        contacts.append({
            'call': label,
            'lat': round(coords[0], 6),
            'lon': round(coords[1], 6),
            'description': format_description(fields),
        })

    print(f'Activation site : {activation_label} ({activation_coords[0]:.4f}, {activation_coords[1]:.4f})')
    print(f'Contacts placed : {len(contacts)}')
    if skipped:
        print(f'Contacts skipped: {skipped} (no location data)')

    kml = build_kml(activation_coords, activation_label, contacts,
                    include_lines=not args.no_lines)

    output_path = (Path(args.output).resolve() if args.output
                   else input_path.with_suffix('.kml'))

    if output_path.exists() and not args.force:
        print(f'Error: output already exists: {output_path}\nUse --force to overwrite.',
              file=sys.stderr)
        sys.exit(1)

    try:
        output_path.write_text(kml, encoding='utf-8')
    except OSError as e:
        print(f'Error writing output: {e}', file=sys.stderr)
        sys.exit(1)

    print(f'KML written to  : {output_path}')


if __name__ == '__main__':
    main()
