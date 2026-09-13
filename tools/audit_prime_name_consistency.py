#!/usr/bin/env python3
"""Audit プライム (프라임) / プリム (프림) after guarded Event fixes.

The two names are distinct in the Japanese source but were historically
collapsed to 프림 in parts of the Korean translation.  This audit evaluates the
source-aligned units and simulates event_translation_review_fixes so it checks
what the build will actually emit rather than only the authority EBM payload.
"""
from __future__ import annotations

import re

from audit_glossary_substring_collisions import aligned_units
from event_translation_review_fixes import FIXES


FIX_BY_UID = {
    f"ebm:romfs/Event/event/{fix.path}:{fix.index}": fix
    for fix in FIXES
}
KATAKANA = r"ァ-ヶー"
PRIME_JP = re.compile(rf"プライム(?![{KATAKANA}])")
PRIM_JP = re.compile(rf"プリム(?![{KATAKANA}])")


def built_translation(uid: str, ko: str) -> str:
    fix = FIX_BY_UID.get(uid)
    if fix is None:
        return ko
    if ko == fix.old or ko == fix.new:
        return fix.new
    raise RuntimeError(f"review fix guard mismatch during audit: {uid}: {ko!r}")


def main() -> None:
    failures: list[tuple[str, str, str, str]] = []
    checked_prime = 0
    checked_prim = 0

    for uid, jp, ko in aligned_units():
        ko = built_translation(uid, ko)
        if PRIME_JP.search(jp):
            checked_prime += 1
            if "프라임" not in ko:
                failures.append((uid, "プライム→프라임", jp, ko))
        if PRIM_JP.search(jp):
            checked_prim += 1
            if "프림" not in ko:
                failures.append((uid, "プリム→프림", jp, ko))

    print(
        f"prime_units={checked_prime} prim_units={checked_prim} "
        f"failures={len(failures)}"
    )
    for uid, kind, jp, ko in failures:
        print(f"[{kind}] {uid}")
        print(f"  JP: {jp}")
        print(f"  KO: {ko}")

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
