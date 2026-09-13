#!/usr/bin/env python3
"""Refresh only glossary-title records inside an existing Switch IPS.

This is intentionally narrower than rebuilding ArNosurgeKoreanUI from scratch.
The existing IPS may contain inline-tail instruction patches that require the
original NSO to regenerate.  Glossary title slots are ordinary fixed-size
rodata records, so this tool rewrites exactly those 76 record payloads while
preserving every non-title byte in the IPS verbatim.
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
DEFAULT_IPS = (
    REPO / "atmosphere" / "exefs_patches" / "ArNosurgeKoreanUI" /
    f"{BUILD_ID}.ips"
)


def encode_runtime(text: str, mapping: dict[str, str]) -> bytes:
    missing = sorted({c for c in text if "가" <= c <= "힣" and c not in mapping})
    if missing:
        raise ValueError("font mapping missing Hangul: " + "".join(missing))
    return "".join(mapping.get(c, c) for c in text).encode("utf-8")


def title_rows(csv_path: Path):
    csv.field_size_limit(1 << 30)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    expected = set(glossary_terms())
    found = []
    for i, row in enumerate(rows[:-1]):
        pair = (row["original"], row["translation"])
        if pair in expected and rows[i + 1]["original"].startswith("<CLEG>【"):
            found.append(row)
    if len(found) != len(expected):
        raise ValueError(f"glossary title row count mismatch: {len(found)} != {len(expected)}")
    return found


def literal_record_payload_ranges(data: bytes) -> dict[int, tuple[int, int]]:
    """Return IPS record offset -> (payload_start, payload_size).

    Refuse overlapping/duplicate record starts and RLE records for title slots;
    the caller checks that every title uses a literal record.  Ordinary RLE
    records elsewhere are parsed and preserved byte-for-byte.
    """
    if not data.startswith(b"PATCH") or not data.endswith(b"EOF"):
        raise ValueError("not a standard IPS patch")
    pos = 5
    end = len(data) - 3
    literal: dict[int, tuple[int, int]] = {}
    seen: set[int] = set()
    while pos < end:
        if pos + 5 > end:
            raise ValueError("truncated IPS record header")
        offset = int.from_bytes(data[pos:pos + 3], "big")
        size = int.from_bytes(data[pos + 3:pos + 5], "big")
        if offset in seen:
            raise ValueError(f"duplicate IPS record start: 0x{offset:X}")
        seen.add(offset)
        pos += 5
        if size == 0:
            if pos + 3 > end:
                raise ValueError("truncated IPS RLE record")
            pos += 3
        else:
            if pos + size > end:
                raise ValueError("truncated IPS literal payload")
            literal[offset] = (pos, size)
            pos += size
    if pos != end:
        raise ValueError("IPS trailing bytes before EOF")
    return literal


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=DEFAULT_IPS)
    ap.add_argument("--output", type=Path, default=DEFAULT_IPS)
    ap.add_argument("--translations", type=Path,
                    default=REPO / "translations" / "exefs" / "main_1.0.1.csv")
    ap.add_argument("--mapping", type=Path,
                    default=REPO / "build" / "final_mod_report.json")
    args = ap.parse_args()

    original = args.input.read_bytes()
    ranges = literal_record_payload_ranges(original)
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))["hangul_to_standin"]
    rows = title_rows(args.translations)

    updated = bytearray(original)
    changed = []
    title_ranges: list[tuple[int, int]] = []
    for row in rows:
        index = int(row["index"])
        address = int(row["memory_address"], 16)
        capacity = int(row["capacity_bytes"])
        ips_offset = address + 0x100
        if ips_offset not in ranges:
            raise SystemExit(
                f"glossary slot is not a literal IPS record: index={index} offset=0x{ips_offset:X}"
            )
        payload_start, record_size = ranges[ips_offset]
        if record_size != capacity:
            raise SystemExit(
                f"glossary slot size mismatch: index={index} IPS={record_size} CSV={capacity}"
            )
        text = normalize_main_translation(index, row["translation"], row["original"])
        payload = encode_runtime(text, mapping)
        if len(payload) > capacity:
            raise SystemExit(
                f"glossary title overflow: index={index} {len(payload)} > {capacity}: {text!r}"
            )
        expected = payload.ljust(capacity, b"\0")
        before = original[payload_start:payload_start + record_size]
        title_ranges.append((payload_start, payload_start + record_size))
        if before != expected:
            changed.append((index, row["original"], text, before, expected))
            updated[payload_start:payload_start + record_size] = expected

    # Prove that not a single byte outside the 76 title payload ranges changed.
    mask = bytearray(len(original))
    for start, end in title_ranges:
        mask[start:end] = b"\x01" * (end - start)
    outside_changes = [
        i for i, (a, b) in enumerate(zip(original, updated))
        if a != b and not mask[i]
    ]
    if outside_changes:
        raise SystemExit(f"non-glossary IPS bytes changed: first={outside_changes[:10]}")
    if len(original) != len(updated):
        raise SystemExit("IPS size changed")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(updated)
    readback = args.output.read_bytes()
    if readback != bytes(updated):
        raise SystemExit("IPS readback mismatch")

    print(
        f"glossary title slots={len(rows)} changed={len(changed)} "
        f"non_title_byte_changes=0 size={len(original)}"
    )
    for index, jp, ko, _before, _after in changed:
        print(f"  index={index}: {jp} => {ko}")


if __name__ == "__main__":
    main()
