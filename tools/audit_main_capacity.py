#!/usr/bin/env python3
"""Read-only validation of main_1.0.1.csv fixed-slot constraints."""
from __future__ import annotations

import csv
from pathlib import Path

from rename_term import normalize_main_translation
from translate_main_japanese import protected_tokens


ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "translations" / "exefs" / "main_1.0.1.csv"


def main() -> None:
    csv.field_size_limit(1 << 30)
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    structure_errors = []
    overflows = []
    token_mismatches = []
    for line_no, row in enumerate(rows, start=2):
        # csv.DictReader stores surplus unquoted comma-separated fields under
        # the None key.  That can silently truncate `translation` while the
        # rest of the row still looks superficially valid, so fail loudly.
        if None in row:
            structure_errors.append((line_no, row.get("index", "?"), row[None]))
            continue
        missing = [name for name in ("index", "capacity_bytes", "original", "translation") if row.get(name) is None]
        if missing:
            structure_errors.append((line_no, row.get("index", "?"), missing))
            continue
        raw_text = row["translation"]
        if not raw_text:
            continue
        index = int(row["index"])
        text = normalize_main_translation(index, raw_text, row["original"])
        used = len(text.encode("utf-8"))
        capacity = int(row["capacity_bytes"])
        if used > capacity:
            overflows.append((row["index"], used, capacity, text))
        original_tokens = [t for t in protected_tokens(row["original"]) if t != "<CR>"]
        translated_tokens = [t for t in protected_tokens(text) if t != "<CR>"]
        if translated_tokens != original_tokens:
            token_mismatches.append((row["index"], row["original"], text))

    print(
        f"rows={len(rows)} structure_errors={len(structure_errors)} "
        f"overflows={len(overflows)} "
        f"protected_token_mismatches={len(token_mismatches)}"
    )
    for line_no, index, detail in structure_errors[:20]:
        print(f"[structure] line={line_no} index={index}: {detail!r}")
    for index, used, capacity, text in overflows[:20]:
        print(f"[overflow] {index}: {used}>{capacity}: {text}")
    for index, original, text in token_mismatches[:20]:
        print(f"[token] {index}\n  JP: {original}\n  KO: {text}")
    if structure_errors or overflows or token_mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
