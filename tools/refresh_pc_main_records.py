#!/usr/bin/env python3
"""Refresh selected translated main-string slots in an already patched PC EXE.

File offsets are rediscovered from a preserved pristine EXE using the Japanese
source strings from main_1.0.1.csv.  The same offsets are then updated in the
current installed EXE, preserving every unrelated string/code patch.  This is
intentionally narrower than rebuilding the whole EXE.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_pc_main_text_patch import (
    PACKED_STRING_OFFSETS,
    SAFE_PADDING_INDICES,
    encode,
    find_slots,
    sections,
    slot_capacity,
)
from rename_term import normalize_main_translation

REPO = Path(__file__).resolve().parents[1]


def load_rows(path: Path) -> dict[int, dict[str, str]]:
    csv.field_size_limit(1 << 30)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return {int(row["index"]): row for row in csv.DictReader(f)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exe", type=Path, default=REPO / "Ar.Nosurge.DX_PC" / "ArnosurgeDX.exe")
    ap.add_argument("--original-exe", type=Path,
                    default=REPO / "build" / "pc" / "ArnosurgeDX.ORIGINAL.exe")
    ap.add_argument("--output", type=Path,
                    default=REPO / "Ar.Nosurge.DX_PC" / "ArnosurgeDX.exe")
    ap.add_argument("--translations", type=Path,
                    default=REPO / "translations" / "exefs" / "main_1.0.1.csv")
    ap.add_argument("--mapping", type=Path,
                    default=REPO / "build" / "final_mod_report.json")
    ap.add_argument("--index", type=int, action="append", required=True,
                    help="main CSV index to refresh; may be repeated")
    args = ap.parse_args()

    current = args.exe.read_bytes()
    pristine = args.original_exe.read_bytes()
    if len(current) != len(pristine):
        raise SystemExit(f"EXE size mismatch: current={len(current)} pristine={len(pristine)}")

    current_base, current_secs = sections(current)
    pristine_base, pristine_secs = sections(pristine)
    current_rdata = next((s for s in current_secs if s["name"] == ".rdata"), None)
    pristine_rdata = next((s for s in pristine_secs if s["name"] == ".rdata"), None)
    if current_base != pristine_base or current_rdata != pristine_rdata or current_rdata is None:
        raise SystemExit("current/pristine PE layout differs; refusing offset-based refresh")
    lo = pristine_rdata["roff"]
    hi = lo + pristine_rdata["rsize"]

    rows = load_rows(args.translations)
    wanted = list(dict.fromkeys(args.index))
    missing_rows = [index for index in wanted if index not in rows]
    if missing_rows:
        raise SystemExit(f"main CSV index not found: {missing_rows}")
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))["hangul_to_standin"]

    updated = bytearray(current)
    allowed_ranges: list[tuple[int, int]] = []
    changed = []

    for index in wanted:
        row = rows[index]
        original_text = row["original"]
        # PC판은 정식 이름/용어를 고정 슬롯용 축약으로 되돌리면 안 된다.
        # 긴 표기는 전체 PC 빌드의 relocation 경로가 담당하며, 이 좁은 refresh
        # 도구에서는 슬롯에 안 들어가면 실패시켜 전체 빌드를 요구한다.
        translation = normalize_main_translation(
            index, row["translation"], original_text, compact=False
        )

        candidates = [(original_text, translation)]
        if "\r\n" in original_text:
            candidates.append((original_text.replace("\r\n", "\n"),
                               translation.replace("\r\n", "\n")))

        hits: list[int] = []
        needle = b""
        chosen = translation
        for candidate_original, candidate_translation in candidates:
            probe = candidate_original.encode("utf-8")
            found = [h for h in find_slots(pristine, probe, hi) if lo <= h < hi]
            if found:
                hits, needle, chosen = found, probe, candidate_translation
                break

        if not hits and index in PACKED_STRING_OFFSETS:
            manual = PACKED_STRING_OFFSETS[index]
            probe = original_text.encode("utf-8")
            end = manual + len(probe)
            if lo <= manual < hi and end < hi and pristine[manual:end] == probe and pristine[end] == 0:
                hits, needle, chosen = [manual], probe, translation

        if not hits:
            raise SystemExit(f"pristine source slot not found: index={index} original={original_text!r}")

        payload = encode(chosen, mapping)
        row_changes = 0
        for offset in hits:
            capacity = (slot_capacity(pristine, offset, len(needle))
                        if index in SAFE_PADDING_INDICES else len(needle) + 1)
            if len(payload) + 1 > capacity:
                raise SystemExit(
                    f"selected PC slot overflow: index={index} {len(payload)+1} > {capacity}; "
                    "정식 표기를 유지하려면 build_pc_main_text_patch.py 전체 빌드의 "
                    "relocation 경로를 사용하세요"
                )
            expected = payload.ljust(capacity, b"\0")
            before = current[offset:offset + capacity]
            allowed_ranges.append((offset, offset + capacity))
            if before != expected:
                updated[offset:offset + capacity] = expected
                row_changes += 1
        if row_changes:
            changed.append((index, len(hits), original_text, chosen))

    mask = bytearray(len(current))
    for start, end in allowed_ranges:
        mask[start:end] = b"\x01" * (end - start)
    outside_changes = [
        i for i, (a, b) in enumerate(zip(current, updated))
        if a != b and not mask[i]
    ]
    if outside_changes:
        raise SystemExit(f"bytes outside selected PC slots changed: {outside_changes[:10]}")
    if len(current) != len(updated):
        raise SystemExit("EXE size changed")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(updated)
    if args.output.read_bytes() != bytes(updated):
        raise SystemExit("PC EXE readback mismatch")

    print(
        f"selected={len(wanted)} changed_rows={len(changed)} "
        f"outside_byte_changes=0 size={len(current)}"
    )
    for index, hits, jp, ko in changed:
        print(f"  index={index} slots={hits}: {jp[:80]} => {ko[:120]}")


if __name__ == "__main__":
    main()
