#!/usr/bin/env python3
"""Rank translation files by likely mistranslation density.

This is a triage tool, not an automatic fixer.  It compares aligned Japanese
and Korean runtime strings from main, Event EBM, Saves XML and balloonsel, and
assigns conservative suspicion flags for patterns that often correlate with
real translation mistakes:

* Japanese kana left in Korean output
* control-token count/order mismatch
* ASCII number / identifier loss
* likely Japanese/Korean negation polarity mismatch
* very large meaning-bearing source compressed into a tiny translation
* identical Japanese source translated inconsistently inside the same file

The output ranks files by weighted suspicious units and prints representative
contexts so a human reviewer can inspect the highest-risk files first.
"""
from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict

from audit_glossary_substring_collisions import aligned_units

CONTROL = re.compile(r"<[^>]+>")
KANA = re.compile(r"[\u3040-\u30ff]")
ASCII_TOKEN = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z][A-Za-z0-9_+-]{1,}|\d+(?:[.:/-]\d+)*")
JP_NEG = re.compile(r"ない|なかった|なく|ません|ませんでした|ず(?:に|、|。|$)|ぬ(?:\W|$)|じゃない|ではない|できない|出来ない|無理|不可|禁止")
KO_NEG = re.compile(r"않|못\s*|아니|없|무리|불가|금지|말(?:아|라|고)|실패|불가능")
JP_POS_EXCEPTION = re.compile(r"しかない|ほかない|他ない|違いない")
KO_POS_EXCEPTION = re.compile(r"수밖에\s*없|틀림없")
SPACE_PUNCT = re.compile(r"[\s、。！？!?：:；;,.…―—「」『』【】（）()［］\[\]・~～ー]+")

WEIGHT = {
    "kana_left": 8,
    "control_mismatch": 10,
    "ascii_loss": 5,
    "negation_missing": 7,
    "negation_added": 5,
    "severe_omission": 6,
    "inconsistent_same_source": 3,
    "elongation_after_punct": 8,
    "ascii_hyphen_elongation": 6,
}


def visible(text: str) -> str:
    return SPACE_PUNCT.sub("", CONTROL.sub("", text))


def controls(text: str) -> list[str]:
    # <CR> is layout, not semantic control. Event/main builders intentionally
    # reflow line breaks, so comparing CR count/order creates large false-positive
    # clusters. Keep only non-layout control tokens here.
    return [token for token in CONTROL.findall(text) if token != "<CR>"]


def file_key(uid: str) -> str:
    if uid.startswith("main:"):
        return "main_1.0.1.csv"
    if uid.startswith("ebm:"):
        # ebm:romfs/Event/event/C11_1/FILE.ebm:12
        body = uid[4:]
        return body.rsplit(":", 1)[0]
    if uid.startswith("xml:"):
        body = uid[4:]
        return body.rsplit(":", 1)[0]
    if uid.startswith("balloonsel:"):
        return "romfs/Event/balloonsel/balloonseldata.json"
    return uid.split(":", 1)[0]


def unit_flags(jp: str, ko: str) -> list[str]:
    flags: list[str] = []
    vjp, vko = visible(jp), visible(ko)
    if not vjp or not vko:
        return flags

    # Kana in target is almost always an untranslated remnant.  Ignore the
    # katakana middle-dot range only via explicit punctuation removal above.
    if KANA.search(vko):
        flags.append("kana_left")

    if controls(jp) != controls(ko):
        flags.append("control_mismatch")

    src_ascii = Counter(t.casefold() for t in ASCII_TOKEN.findall(CONTROL.sub("", jp)))
    dst_ascii = Counter(t.casefold() for t in ASCII_TOKEN.findall(CONTROL.sub("", ko)))
    # Only flag tokens that look semantically meaningful; isolated Japanese-era
    # punctuation and one-letter particles are filtered by the regex.
    if any(dst_ascii[t] < n for t, n in src_ascii.items()):
        flags.append("ascii_loss")

    jp_neg = bool(JP_NEG.search(jp)) and not bool(JP_POS_EXCEPTION.search(jp))
    ko_neg = bool(KO_NEG.search(ko)) and not bool(KO_POS_EXCEPTION.search(ko))
    if jp_neg and not ko_neg:
        flags.append("negation_missing")
    elif ko_neg and not jp_neg:
        # Added negation is noisier, so only flag reasonably substantial units.
        if len(vjp) >= 8:
            flags.append("negation_added")

    # Korean is normally not dramatically shorter than Japanese in character
    # count.  Require a long source and a very low ratio to avoid flagging UI
    # labels and normal condensation.
    if len(vjp) >= 22 and len(vko) <= 10 and len(vko) / len(vjp) < 0.38:
        flags.append("severe_omission")

    # Source elongation mark should not migrate behind terminal punctuation.
    # This pattern is a reliable symptom of an old mechanical replacement.
    if re.search(r"[.!?。！？]ー", ko):
        flags.append("elongation_after_punct")

    # A bare ASCII hyphen is not the source Japanese elongation mark.  Restrict
    # this to records where the Japanese actually contains ー so normal hyphens
    # in identifiers are not reported.
    if "ー" in jp and re.search(r"[가-힣]-", ko):
        flags.append("ascii_hyphen_elongation")

    return flags


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--contexts", type=int, default=10)
    ap.add_argument("--min-score", type=int, default=1)
    ap.add_argument("--only-flag", choices=tuple(WEIGHT),
                    help="only rank/print units carrying this suspicion flag")
    ap.add_argument("--path", help="only audit units whose id contains this substring")
    ap.add_argument("--start-rank", type=int, default=1,
                    help="1-based ranked-file offset for chunked manual review")
    ap.add_argument("--simulate-review-fixes", action="store_true",
                    help="audit Event EBM text after confirmed record-guarded review fixes")
    ap.add_argument("--simulate-build", action="store_true",
                    help="also simulate glossary fixes, source honorifics, and build-time term normalization")
    ap.add_argument("--dump-aligned", action="store_true",
                    help="print every aligned JP/KO unit selected by --path, then exit")
    args = ap.parse_args()

    units = list(aligned_units())
    if args.simulate_review_fixes or args.simulate_build:
        from event_translation_review_fixes import FIXES

        fixes = {
            f"ebm:romfs/Event/event/{fix.path}:{fix.index}": fix
            for fix in FIXES
        }
        glossary_fixes = {}
        if args.simulate_build:
            from fix_glossary_false_links import FIXES as GLOSSARY_FIXES

            glossary_fixes = {
                f"ebm:romfs/Event/event/{fix.path}:{fix.index}": fix
                for fix in GLOSSARY_FIXES
            }
        simulated = []
        for uid, jp, ko in units:
            for fix_map, label in ((glossary_fixes, "glossary"), (fixes, "review")):
                fix = fix_map.get(uid)
                if fix is not None:
                    if ko == fix.old or ko == fix.new:
                        ko = fix.new
                    else:
                        raise RuntimeError(
                            f"{label} fix guard mismatch during quality audit: {uid}: {ko!r}"
                        )
            if args.simulate_build:
                from rename_term import normalize_main_translation, rename
                from source_honorifics import normalize_nei_honorifics, normalize_source_terms

                if uid.startswith("ebm:"):
                    ko = normalize_nei_honorifics(jp, ko)
                    ko = rename(ko)
                    ko = normalize_source_terms(jp, ko)
                elif uid.startswith("main:"):
                    ko = normalize_main_translation(uid.split(":", 1)[1], ko, jp)
                else:
                    ko = rename(ko)
            simulated.append((uid, jp, ko))
        units = simulated

    if args.dump_aligned:
        selected = [unit for unit in units if not args.path or args.path in unit[0]]
        print(f"aligned_units={len(units)} selected={len(selected)}")
        for uid, jp, ko in selected:
            print(f"[{uid}]")
            print(f"  JP: {jp}")
            print(f"  KO: {ko}")
        return

    by_file: dict[str, list[tuple[str, str, str, list[str]]]] = defaultdict(list)
    all_by_file: Counter[str] = Counter()
    same_source: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)

    for uid, jp, ko in units:
        if args.path and args.path not in uid:
            continue
        fk = file_key(uid)
        all_by_file[fk] += 1
        same_source[(fk, jp)][ko] += 1
        flags = unit_flags(jp, ko)
        if flags and (not args.only_flag or args.only_flag in flags):
            by_file[fk].append((uid, jp, ko, flags))

    # Identical JP source with multiple KO renderings in one file is worth a
    # manual look.  Add the flag only to minority renderings so repeated normal
    # canonical translations don't dominate the score.
    inconsistent_ids: set[tuple[str, str, str]] = set()
    for (fk, jp), counts in same_source.items():
        if len(counts) < 2 or sum(counts.values()) < 2:
            continue
        canonical, _ = counts.most_common(1)[0]
        for ko in counts:
            if ko != canonical:
                inconsistent_ids.add((fk, jp, ko))

    # Re-walk only to attach inconsistency records not already suspicious.
    seen = {(uid, jp, ko) for rows in by_file.values() for uid, jp, ko, _ in rows}
    for uid, jp, ko in units:
        if args.path and args.path not in uid:
            continue
        fk = file_key(uid)
        if (fk, jp, ko) not in inconsistent_ids:
            continue
        if args.only_flag and args.only_flag != "inconsistent_same_source":
            continue
        key = (uid, jp, ko)
        if key in seen:
            for row in by_file[fk]:
                if row[0] == uid and row[1] == jp and row[2] == ko:
                    row[3].append("inconsistent_same_source")
                    break
        else:
            by_file[fk].append((uid, jp, ko, ["inconsistent_same_source"]))

    ranked = []
    for fk, rows in by_file.items():
        score = sum(sum(WEIGHT[f] for f in flags) for *_x, flags in rows)
        if score < args.min_score:
            continue
        counts = Counter(f for *_x, flags in rows for f in flags)
        density = len(rows) / max(1, all_by_file[fk])
        ranked.append((score, density, len(rows), all_by_file[fk], fk, counts, rows))
    ranked.sort(key=lambda x: (-x[0], -x[1], -x[2], x[4]))

    print(f"aligned_units={len(units)} files={len(all_by_file)} suspicious_files={len(ranked)}")
    start = max(0, args.start_rank - 1)
    selected = ranked[start:start + args.top]
    for rank, (score, density, suspicious, total, fk, counts, rows) in enumerate(selected, start + 1):
        ctext = ", ".join(f"{k}={v}" for k, v in counts.most_common())
        print(f"\n#{rank:02d} score={score} suspicious={suspicious}/{total} density={density:.1%} {fk}")
        print(f"  {ctext}")
        rows = sorted(rows, key=lambda r: -sum(WEIGHT[f] for f in r[3]))
        for uid, jp, ko, flags in rows[:args.contexts]:
            print(f"  [{','.join(flags)}] {uid}")
            print(f"    JP: {jp[:220]}")
            print(f"    KO: {ko[:220]}")


if __name__ == "__main__":
    main()
