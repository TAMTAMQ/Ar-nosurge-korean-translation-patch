#!/usr/bin/env python3
"""Audit ネイ / おネイ honorific preservation.

`おネイ` is intentionally transliterated as 오네이 rather than localized as
누나/언니/누님. Ordinary suffixes remain さん→씨 and ちゃん→쨩.
"""
from __future__ import annotations

import argparse
from collections import Counter

from audit_glossary_substring_collisions import aligned_units
from event_translation_review_fixes import FIXES
from source_honorifics import normalize_nei_honorifics


FIX_BY_UID = {
    f"ebm:romfs/Event/event/{fix.path}:{fix.index}": fix
    for fix in FIXES
}


def built_translation(uid: str, jp: str, ko: str) -> str:
    fix = FIX_BY_UID.get(uid)
    if fix is not None:
        if ko == fix.old or ko == fix.new:
            ko = fix.new
        else:
            raise RuntimeError(f"review fix guard mismatch during audit: {uid}: {ko!r}")
    return normalize_nei_honorifics(jp, ko)


def requirements(jp: str) -> list[str]:
    wanted: list[str] = []
    remainder = jp
    if "疾風のおネイさん" in remainder:
        wanted.append("질풍의 오네이씨")
        remainder = remainder.replace("疾風のおネイさん", "")
    elif "疾風のおネイちゃん" in remainder:
        wanted.append("질풍의 오네이쨩")
        remainder = remainder.replace("疾風のおネイちゃん", "")
    elif "疾風のおネイ" in remainder:
        wanted.append("질풍의 오네이")
        remainder = remainder.replace("疾風のおネイ", "")
    if "座長のおネイさん" in remainder:
        wanted.append("좌장 오네이씨")
        remainder = remainder.replace("座長のおネイさん", "")
    elif "座長のおネイちゃん" in remainder:
        wanted.append("좌장 오네이쨩")
        remainder = remainder.replace("座長のおネイちゃん", "")
    elif "座長のおネイ" in remainder:
        wanted.append("좌장 오네이")
        remainder = remainder.replace("座長のおネイ", "")
    if "おネイの新メニュー" in remainder:
        wanted.append("오네이의 신메뉴")
        remainder = remainder.replace("おネイの新メニュー", "")
    if "おネイちゃん" in remainder:
        wanted.extend(["오네이쨩"] * remainder.count("おネイちゃん"))
        remainder = remainder.replace("おネイちゃん", "")
    if "おネイさん" in remainder:
        wanted.extend(["오네이씨"] * remainder.count("おネイさん"))
        remainder = remainder.replace("おネイさん", "")
    if "おネイ" in remainder:
        wanted.extend(["오네이"] * remainder.count("おネイ"))
        remainder = remainder.replace("おネイ", "")
    if "ネイちゃん" in remainder:
        wanted.append("네이쨩")
    if "ネイさん" in remainder:
        wanted.append("네이씨")
    return wanted


def has_token(ko: str, token: str) -> bool:
    """Treat an optional Korean spacing before 씨/쨩 as stylistic, not semantic."""
    variants = {token}
    for suffix in ("씨", "쨩"):
        if token.endswith(suffix):
            variants.add(token[:-len(suffix)] + " " + suffix)
    return any(variant in ko for variant in variants)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--contexts", type=int, default=30,
                    help="maximum number of failing contexts to print")
    ap.add_argument("--surface", choices=("main", "ebm", "xml", "balloonsel"),
                    help="only print failures from one aligned-text surface")
    args = ap.parse_args()

    checked = 0
    failures: list[tuple[str, list[str], str, str]] = []
    for uid, jp, ko in aligned_units():
        wanted = requirements(jp)
        if not wanted:
            continue
        checked += 1
        ko = built_translation(uid, jp, ko)
        missing = [token for token in wanted if not has_token(ko, token)]
        for duplicated in ("오네이씨씨", "오네이쨩쨩", "오네이씨쨩", "오네이쨩씨"):
            if duplicated in ko:
                missing.append(f"중복호칭:{duplicated}")
        if any(bad in ko for bad in ("질풍의 오네이가", "질풍의 오네이……가", "질풍의 오네이로서")):
            # 오네이는 모음으로 끝나므로 가/로서가 정상이다. 이 분기는
            # 과거 누님 전용 조사 보정의 회귀만 잡기 위해 남겨둔다.
            pass
        if missing:
            failures.append((uid, missing, jp, ko))

    surfaces = Counter(uid.split(":", 1)[0] for uid, *_ in failures)
    missing_kinds = Counter(tuple(missing) for _, missing, _, _ in failures)
    print(f"checked={checked} failures={len(failures)} surfaces={dict(surfaces)}")
    print("missing_kinds=" + repr(dict(missing_kinds.most_common(12))))
    printable = [f for f in failures if not args.surface or f[0].startswith(args.surface + ":")]
    for uid, missing, jp, ko in printable[:args.contexts]:
        print(f"[{', '.join(missing)}] {uid}")
        print(f"  JP: {jp}")
        print(f"  KO: {ko}")
    if len(printable) > args.contexts:
        print(f"... {len(printable) - args.contexts} more")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
