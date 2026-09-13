#!/usr/bin/env python3
"""Check that the installed PC executable contains current normalized glossary titles.

The executable stores Hangul through the project's Japanese stand-in mapping.
This tool encodes the 76 current glossary title translations exactly as the PC
main-text builder does, then searches the installed executable for those byte
strings.  It is a presence/readback guard; substring-link correctness of the
rest of runtime text is handled by audit_glossary_runtime_readback.py.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_glossary_substring_collisions import glossary_terms
from rename_term import rename

REPO = Path(__file__).resolve().parents[1]


def encode_runtime(text: str, mapping: dict[str, str]) -> bytes:
    missing = sorted({c for c in text if "가" <= c <= "힣" and c not in mapping})
    if missing:
        raise ValueError("font mapping missing Hangul: " + "".join(missing))
    return "".join(mapping.get(c, c) for c in text).encode("utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exe", type=Path,
                    default=REPO / "Ar.Nosurge.DX_PC" / "ArnosurgeDX.exe")
    ap.add_argument("--mapping", type=Path,
                    default=REPO / "build" / "final_mod_report.json")
    args = ap.parse_args()

    data = args.exe.read_bytes()
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))["hangul_to_standin"]
    terms = [(jp, rename(ko)) for jp, ko in glossary_terms()]

    missing = []
    counts = []
    for jp, ko in terms:
        payload = encode_runtime(ko, mapping)
        count = data.count(payload)
        counts.append((count, jp, ko))
        if count == 0:
            missing.append((jp, ko))

    print(f"exe: {args.exe}")
    print(f"glossary titles: {len(terms)} / present: {len(terms) - len(missing)} / missing: {len(missing)}")
    for jp, ko in missing:
        print(f"MISSING {jp} => {ko}")
    print("\nleast frequent present titles:")
    for count, jp, ko in sorted((x for x in counts if x[0]), key=lambda x: x[0])[:30]:
        print(f"  {count:4d}  {jp} => {ko}")
    if missing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
