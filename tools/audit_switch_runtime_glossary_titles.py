#!/usr/bin/env python3
"""Verify current normalized glossary-title slots in the installed Switch IPS.

The Switch main-text patch writes CSV memory-address slots to IPS offsets
(address + 0x100).  This tool reconstructs the 76 glossary-title records,
normalizes/encodes them exactly like build_main_text_patch.py, parses the
installed ArNosurgeKoreanUI IPS, and requires every title slot payload to match.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_glossary_substring_collisions import glossary_terms
from rename_term import normalize_main_translation

REPO = Path(__file__).resolve().parents[1]
BUILD_ID = "28F3C3965CEB60AC18A23E2B2C0C4BEEE3C81D8B"


def parse_ips(data: bytes) -> dict[int, bytes]:
    if not data.startswith(b"PATCH") or not data.endswith(b"EOF"):
        raise ValueError("not a standard IPS patch")
    pos = 5
    out: dict[int, bytes] = {}
    end = len(data) - 3
    while pos < end:
        if pos + 5 > end:
            raise ValueError("truncated IPS record header")
        offset = int.from_bytes(data[pos:pos + 3], "big")
        size = int.from_bytes(data[pos + 3:pos + 5], "big")
        pos += 5
        if size == 0:
            if pos + 3 > end:
                raise ValueError("truncated IPS RLE record")
            run = int.from_bytes(data[pos:pos + 2], "big")
            value = data[pos + 2:pos + 3]
            pos += 3
            out[offset] = value * run
        else:
            if pos + size > end:
                raise ValueError("truncated IPS payload")
            out[offset] = data[pos:pos + size]
            pos += size
    if pos != end:
        raise ValueError("IPS trailing bytes before EOF")
    return out


def decode_runtime(payload: bytes, inverse: dict[str, str]) -> str:
    text = payload.rstrip(b"\0").decode("utf-8", errors="replace")
    return "".join(inverse.get(ch, ch) for ch in text)


def encode_runtime(text: str, mapping: dict[str, str]) -> bytes:
    missing = sorted({c for c in text if "가" <= c <= "힣" and c not in mapping})
    if missing:
        raise ValueError("font mapping missing Hangul: " + "".join(missing))
    return "".join(mapping.get(c, c) for c in text).encode("utf-8")


def title_rows(csv_path: Path):
    csv.field_size_limit(1 << 30)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    expected_pairs = set(glossary_terms())
    found = []
    for i, row in enumerate(rows[:-1]):
        pair = (row["original"], row["translation"])
        if pair in expected_pairs and rows[i + 1]["original"].startswith("<CLEG>【"):
            found.append(row)
    return found


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ips", type=Path,
                    default=REPO / "atmosphere" / "exefs_patches" /
                            "ArNosurgeKoreanUI" / f"{BUILD_ID}.ips")
    ap.add_argument("--translations", type=Path,
                    default=REPO / "translations" / "exefs" / "main_1.0.1.csv")
    ap.add_argument("--mapping", type=Path,
                    default=REPO / "build" / "final_mod_report.json")
    args = ap.parse_args()

    patch = parse_ips(args.ips.read_bytes())
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))["hangul_to_standin"]
    inverse = {standin: hangul for hangul, standin in mapping.items()}
    rows = title_rows(args.translations)
    bad = []
    for row in rows:
        index = int(row["index"])
        address = int(row["memory_address"], 16)
        capacity = int(row["capacity_bytes"])
        translated = normalize_main_translation(index, row["translation"], row["original"])
        payload = encode_runtime(translated, mapping).ljust(capacity, b"\0")
        ips_offset = address + 0x100
        actual = patch.get(ips_offset)
        if actual != payload:
            bad.append((index, row["original"], translated, ips_offset,
                        None if actual is None else actual.hex(),
                        None if actual is None else decode_runtime(actual, inverse),
                        payload.hex()))

    print(f"ips: {args.ips}")
    print(f"glossary title slots: {len(rows)} / exact: {len(rows) - len(bad)} / mismatch: {len(bad)}")
    for index, jp, ko, offset, actual, actual_text, expected in bad:
        print(f"MISMATCH index={index} ips=0x{offset:X} {jp} => {ko}")
        print(f"  actual text: {actual_text!r}")
        print(f"  actual:      {actual}")
        print(f"  expected:    {expected}")
    if len(rows) != 76 or bad:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
