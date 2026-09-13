#!/usr/bin/env python3
"""Refresh selected main CSV records inside an existing Switch IPS.

The installed ArNosurgeKoreanUI IPS can contain inline-tail and raw code patches
that cannot be regenerated safely without the original NSO.  This tool rewrites
only explicitly requested fixed-size rodata records and proves that no byte
outside those payloads changed.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from refresh_switch_glossary_titles import DEFAULT_IPS, encode_runtime, literal_record_payload_ranges
from rename_term import normalize_main_translation

REPO = Path(__file__).resolve().parents[1]


def load_rows(path: Path) -> dict[int, dict[str, str]]:
    csv.field_size_limit(1 << 30)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return {int(row["index"]): row for row in csv.DictReader(f)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=DEFAULT_IPS)
    ap.add_argument("--output", type=Path, default=DEFAULT_IPS)
    ap.add_argument("--translations", type=Path,
                    default=REPO / "translations" / "exefs" / "main_1.0.1.csv")
    ap.add_argument("--mapping", type=Path,
                    default=REPO / "build" / "final_mod_report.json")
    ap.add_argument("--index", type=int, action="append", required=True,
                    help="main CSV index to refresh; may be repeated")
    args = ap.parse_args()

    wanted = list(dict.fromkeys(args.index))
    rows = load_rows(args.translations)
    missing_rows = [index for index in wanted if index not in rows]
    if missing_rows:
        raise SystemExit(f"main CSV index not found: {missing_rows}")

    original = args.input.read_bytes()
    ranges = literal_record_payload_ranges(original)
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))["hangul_to_standin"]
    updated = bytearray(original)
    allowed_ranges: list[tuple[int, int]] = []
    changed = []

    for index in wanted:
        row = rows[index]
        address = int(row["memory_address"], 16)
        capacity = int(row["capacity_bytes"])
        ips_offset = address + 0x100
        if ips_offset not in ranges:
            raise SystemExit(
                f"selected slot is not a literal IPS record: index={index} offset=0x{ips_offset:X}"
            )
        payload_start, record_size = ranges[ips_offset]
        if record_size != capacity:
            raise SystemExit(
                f"slot size mismatch: index={index} IPS={record_size} CSV={capacity}"
            )
        text = normalize_main_translation(index, row["translation"], row["original"])
        payload = encode_runtime(text, mapping)
        if len(payload) > capacity:
            raise SystemExit(
                f"slot overflow: index={index} {len(payload)} > {capacity}: {text!r}"
            )
        expected = payload.ljust(capacity, b"\0")
        before = original[payload_start:payload_start + record_size]
        allowed_ranges.append((payload_start, payload_start + record_size))
        if before != expected:
            updated[payload_start:payload_start + record_size] = expected
            changed.append((index, row["original"], text))

    mask = bytearray(len(original))
    for start, end in allowed_ranges:
        mask[start:end] = b"\x01" * (end - start)
    outside_changes = [
        i for i, (a, b) in enumerate(zip(original, updated))
        if a != b and not mask[i]
    ]
    if outside_changes:
        raise SystemExit(f"bytes outside selected records changed: {outside_changes[:10]}")
    if len(original) != len(updated):
        raise SystemExit("IPS size changed")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(updated)
    if args.output.read_bytes() != bytes(updated):
        raise SystemExit("IPS readback mismatch")

    print(
        f"selected={len(wanted)} changed={len(changed)} "
        f"outside_byte_changes=0 size={len(original)}"
    )
    for index, jp, ko in changed:
        print(f"  index={index}: {jp[:80]} => {ko[:120]}")


if __name__ == "__main__":
    main()
