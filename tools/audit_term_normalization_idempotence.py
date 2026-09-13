#!/usr/bin/env python3
"""Verify that build-time Korean term normalization is idempotent.

The final build applies ``rename_term.rename`` to translated runtime text.  A
substring rule whose source is also a prefix of its destination can corrupt an
already-correct term on a second pass (for example ``팬데믹스`` ->
``팬데믹스스``).  This audit checks every aligned authority translation after
record-guarded Event review fixes and fails if one normalization pass differs
from two passes.
"""
from __future__ import annotations

from audit_glossary_substring_collisions import aligned_units
from event_translation_review_fixes import FIXES
from rename_term import rename


def main() -> None:
    review_fixes = {
        f"ebm:romfs/Event/event/{fix.path}:{fix.index}": fix.new
        for fix in FIXES
    }

    checked = 0
    failures: list[tuple[str, str, str, str]] = []
    for uid, _jp, ko in aligned_units():
        checked += 1
        text = review_fixes.get(uid, ko)
        once = rename(text)
        twice = rename(once)
        if once != twice:
            failures.append((uid, text, once, twice))

    print(f"checked={checked} failures={len(failures)}")
    for uid, original, once, twice in failures[:50]:
        print(f"[{uid}]")
        print(f"  original: {original}")
        print(f"  once:     {once}")
        print(f"  twice:    {twice}")

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
