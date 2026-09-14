#!/usr/bin/env python3
"""Read-only audit of Japanese proper-name honorifics missing in Korean.

This is intentionally a candidate generator, not an auto-fixer.  It ignores
おネイ wordplay and ordinary ネイ forms handled by source_honorifics.py, then
groups katakana-name + さん/ちゃん/君/くん/様/さま occurrences whose Korean
record does not contain the corresponding suffix at all.
"""
from __future__ import annotations

import argparse
import re
from collections import Counter

from audit_glossary_substring_collisions import aligned_units
from rename_term import rename
from source_honorifics import (
    NAMED_HONORIFIC_BASES,
    normalize_nei_honorifics,
    normalize_source_terms,
)

HONORIFIC = {
    "さん": "씨",
    "ちゃん": "쨩",
    "君": "군",
    "くん": "군",
    "様": "님",
    "さま": "님",
}
PATTERN = re.compile(r"([ァ-ヺー]{2,})(ちゃん|さん|君|くん|様|さま)")
NON_KATAKANA_NAMED_BASES = tuple(
    name for name in NAMED_HONORIFIC_BASES
    if not re.fullmatch(r"[ァ-ヺー]+", name)
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--simulate", action="store_true",
                    help="audit after source-driven build normalization")
    ap.add_argument("--token", help="show only one exact Japanese name+honorific token")
    args = ap.parse_args()

    totals: Counter[str] = Counter()
    missing: Counter[str] = Counter()
    examples: dict[str, tuple[str, str, str]] = {}
    all_examples: dict[str, list[tuple[str, str, str]]] = {}

    planned_event_fixes: dict[str, str] = {}
    if args.simulate:
        from event_translation_review_fixes import FIXES as EVENT_REVIEW_FIXES
        planned_event_fixes = {
            f"ebm:romfs/Event/event/{fix.path}:{fix.index}": fix.new
            for fix in EVENT_REVIEW_FIXES
        }

    for uid, japanese, korean in aligned_units():
        if args.simulate:
            korean = planned_event_fixes.get(uid, korean)
            korean = normalize_nei_honorifics(japanese, korean)
            korean = rename(korean)
            korean = normalize_source_terms(japanese, korean)
        # おネイ is ネイ + お姉 wordplay and is deliberately contextual.
        stripped = japanese.replace("おネイちゃん", "").replace("おネイさん", "")
        found = PATTERN.findall(stripped)
        for name in NON_KATAKANA_NAMED_BASES:
            for suffix in HONORIFIC:
                found.extend([(name, suffix)] * stripped.count(name + suffix))
        for name, suffix in found:
            if name == "ネイ":
                continue
            token = name + suffix
            if args.token and token != args.token:
                continue
            totals[token] += 1
            if args.token:
                all_examples.setdefault(token, []).append((uid, japanese, korean))
            expected_suffix = HONORIFIC[suffix]
            expected = NAMED_HONORIFIC_BASES.get(name, "") + expected_suffix
            if (expected not in korean) if name in NAMED_HONORIFIC_BASES else (expected_suffix not in korean):
                missing[token] += 1
                examples.setdefault(token, (uid, japanese, korean))

    print(
        f"forms={len(totals)} missing_forms={len(missing)} "
        f"missing_occurrences={sum(missing.values())}"
    )
    if args.token:
        for uid, japanese, korean in all_examples.get(args.token, []):
            print(f"  {uid}")
            print(f"  JP: {japanese[:220]}")
            print(f"  KO: {korean[:220]}")
        return
    for token, count in missing.most_common():
        uid, japanese, korean = examples[token]
        print(f"{count:4d}/{totals[token]:4d} {token}")
        print(f"  {uid}")
        print(f"  JP: {japanese[:220]}")
        print(f"  KO: {korean[:220]}")


if __name__ == "__main__":
    main()
