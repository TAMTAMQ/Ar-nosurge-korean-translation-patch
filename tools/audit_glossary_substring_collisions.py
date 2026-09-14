#!/usr/bin/env python3
"""Audit Korean glossary terms that can trigger false substring links.

The game highlights registered glossary terms by substring.  A Korean term may
therefore become a false link when it appears in a translation even though the
corresponding Japanese glossary spelling is absent from the source text.

This tool extracts the registered glossary titles from main_1.0.1.csv (a short
title slot followed by one or more <CLEG> description pages), then compares
aligned Japanese/Korean runtime text across main, Event EBM, Saves XML, and
balloonsel choices.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RECORD_HEADER = 32
ATTR = re.compile(r'''(?P<head>\s(?P<name>[\w:.-]+)\s*=\s*)(?P<q>["'])(?P<value>.*?)(?P=q)''', re.DOTALL)
TAG = re.compile(r"<(?P<tag>[A-Za-z_][\w:.-]*)(?P<body>(?:[^\"'>]|\"[^\"]*\"|'[^']*')*)/?>", re.DOTALL)
CONTROL = re.compile(r"<[^>]+>")
ASCII_IDENTIFIER = re.compile(r"^[A-Z0-9_]+$")
HANGUL = re.compile(r"[가-힣]")


def normalize_japanese(text: str) -> str:
    """Normalize harmless spelling differences for glossary-term comparison.

    The runtime source often writes the same term in hiragana, inserts a middle
    dot, or splits it with <CR>.  Those are not Korean-only false links, so the
    audit treats them as the same Japanese term.
    """
    text = CONTROL.sub("", text).replace("・", "")
    out = []
    for ch in text:
        code = ord(ch)
        if 0x3041 <= code <= 0x3096:
            ch = chr(code + 0x60)
        out.append(ch)
    return "".join(out)


def japanese_term_count(text: str, term: str) -> int:
    return normalize_japanese(text).count(normalize_japanese(term))


def intentional_alias_count(text: str, jp_term: str, ko_term: str) -> int:
    """Count source occurrences that intentionally share a Korean glossary word.

    `禊` has to use the short UI translation `정화` in several fixed-width
    surfaces.  The script also sees phonetic katakana spellings of registered
    glossary terms; those are genuine source-side occurrences, not Korean-only
    substring collisions.
    """
    normalized = normalize_japanese(text)
    aliases = {
        ("浄化", "정화"): ("禊", "ジョウカ"),
        ("救済", "구제"): ("キュウサイ",),
        ("審判", "심판"): ("シンパン",),
    }
    return sum(normalized.count(normalize_japanese(alias)) for alias in aliases.get((jp_term, ko_term), ()))


def parse_ebm(data: bytes) -> list[str]:
    count = int.from_bytes(data[:4], "little")
    pos = 4
    out: list[str] = []
    for _ in range(count):
        length = int.from_bytes(data[pos + RECORD_HEADER:pos + RECORD_HEADER + 4], "little")
        start = pos + RECORD_HEADER + 4
        end = start + length
        if end > len(data) or length < 1 or data[end - 1] != 0:
            raise ValueError(f"invalid EBM record framing at offset {pos}")
        out.append(data[start:end - 1].decode("utf-8"))
        pos = end
    if pos != len(data):
        raise ValueError(f"EBM trailing/parse mismatch: parsed={pos} file={len(data)}")
    return out


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp932")


def xml_tag_attrs(path: Path) -> list[tuple[str, dict[str, str]]]:
    """Parse the game's XML-like files without requiring strict XML validity."""
    out: list[tuple[str, dict[str, str]]] = []
    for tag_match in TAG.finditer(read_text(path)):
        attrs = {
            m.group("name"): html.unescape(m.group("value"))
            for m in ATTR.finditer(tag_match.group("body"))
        }
        out.append((tag_match.group("tag"), attrs))
    return out


def aligned_xml_attrs(src: Path, tr: Path) -> list[tuple[str, str]]:
    """Align values by tag sequence and attribute name, not attribute position.

    Korean UI files intentionally add layout-only attributes such as
    limit_width, and some source files use XML-like syntax that Python's strict
    XML parser rejects.  Tag order remains stable, so matching the same tag
    occurrence and attribute name preserves source/translation alignment while
    safely ignoring Korean-only layout attributes.
    """
    jp_tags = xml_tag_attrs(src)
    ko_tags = xml_tag_attrs(tr)
    if len(jp_tags) != len(ko_tags):
        raise ValueError(f"XML tag-count mismatch: {src}: jp={len(jp_tags)} ko={len(ko_tags)}")
    pairs: list[tuple[str, str]] = []
    for i, ((jp_tag, jp_attrs), (ko_tag, ko_attrs)) in enumerate(zip(jp_tags, ko_tags)):
        if jp_tag != ko_tag:
            raise ValueError(f"XML tag mismatch at #{i}: jp={jp_tag} ko={ko_tag}: {src}")
        for name, ko_value in ko_attrs.items():
            if name in jp_attrs:
                pairs.append((jp_attrs[name], ko_value))
    return pairs


def glossary_terms() -> list[tuple[str, str]]:
    csv.field_size_limit(1 << 30)
    path = REPO / "translations" / "exefs" / "main_1.0.1.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    terms: list[tuple[str, str]] = []
    for i in range(len(rows) - 1):
        original = rows[i]["original"]
        translated = rows[i]["translation"]
        next_original = rows[i + 1]["original"]
        if not translated or not next_original.startswith("<CLEG>【"):
            continue
        # Glossary title slots are short standalone strings.  Description-page
        # continuations can also precede a new <CLEG> page, so reject those.
        if len(original) > 30 or "<" in original or "。" in original or "<CR>" in original:
            continue
        terms.append((original, translated))
    return terms


def aligned_units():
    csv.field_size_limit(1 << 30)
    main = REPO / "translations" / "exefs" / "main_1.0.1.csv"
    with main.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row["translation"]:
                yield f"main:{row['index']}", row["original"], row["translation"]

    tr_root = REPO / "translations" / "romfs" / "Event" / "event"
    for tr in sorted(tr_root.rglob("*.ebm")):
        rel = tr.relative_to(REPO / "translations").as_posix()
        src = REPO / "originalText" / rel.replace("romfs/Event", "romfs/EVENT")
        if not src.is_file():
            continue
        jp = parse_ebm(src.read_bytes())
        ko = parse_ebm(tr.read_bytes())
        if len(jp) != len(ko):
            raise ValueError(f"EBM record-count mismatch: {rel}: jp={len(jp)} ko={len(ko)}")
        for i, (a, b) in enumerate(zip(jp, ko)):
            yield f"ebm:{rel}:{i}", a, b

    tr_root = REPO / "translations" / "romfs" / "Saves"
    src_root = REPO / "originalText" / "romfs" / "Saves"
    for tr in sorted(tr_root.rglob("*.xml")):
        src = src_root / tr.relative_to(tr_root)
        if not src.is_file():
            continue
        rel_xml = tr.relative_to(REPO).as_posix()
        for i, (a, b) in enumerate(aligned_xml_attrs(src, tr)):
            yield f"xml:{rel_xml}:{i}", a, b

    src = REPO / "originalText" / "romfs" / "Event" / "balloonsel" / "balloonseldata.json"
    tr = REPO / "translations" / "romfs" / "Event" / "balloonsel" / "balloonseldata.json"
    if src.is_file() and tr.is_file():
        ja = json.loads(src.read_text(encoding="utf-8"))
        ko = json.loads(tr.read_text(encoding="utf-8"))
        if len(ja) != len(ko):
            raise ValueError(f"balloonsel group-count mismatch: jp={len(ja)} ko={len(ko)}")
        for gi, (jg, kg) in enumerate(zip(ja, ko)):
            if len(jg) != len(kg):
                raise ValueError(
                    f"balloonsel option-count mismatch at group {gi}: jp={len(jg)} ko={len(kg)}"
                )
            for oi, (a, b) in enumerate(zip(jg, kg)):
                yield f"balloonsel:{gi}:{oi}", a, b


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-extra", type=int, default=1)
    ap.add_argument("--contexts", type=int, default=8)
    ap.add_argument("--term", help="Korean or Japanese glossary title to audit")
    ap.add_argument("--simulate-fixes", action="store_true",
                    help="audit as if fix_glossary_false_links.py EBM fixes were applied")
    ap.add_argument("--simulate-build-normalization", action="store_true",
                    help="apply the same rename_term normalization used by runtime builders to glossary titles and Korean text")
    ap.add_argument("--embedded", action="store_true",
                    help="also report glossary titles embedded inside larger Hangul words")
    ap.add_argument("--nested-terms", action="store_true",
                    help="also report glossary titles nested inside other glossary titles")
    args = ap.parse_args()

    terms = glossary_terms()
    units = list(aligned_units())
    if args.simulate_build_normalization:
        from rename_term import normalize_main_translation, rename
        from source_honorifics import normalize_source_terms
        terms = [(jp, rename(ko)) for jp, ko in terms]
        normalized_units = []
        for uid, jp, ko in units:
            if uid.startswith("main:"):
                index = uid.split(":", 1)[1]
                ko = normalize_main_translation(index, ko, jp)
            else:
                ko = rename(ko)
                ko = normalize_source_terms(jp, ko)
            normalized_units.append((uid, jp, ko))
        units = normalized_units
    if args.simulate_fixes:
        from event_translation_review_fixes import FIXES as EVENT_REVIEW_FIXES
        from fix_glossary_false_links import FIXES as GLOSSARY_FIXES
        planned = {
            f"ebm:romfs/Event/event/{fix.path}:{fix.index}": fix.new
            for fix in [*EVENT_REVIEW_FIXES, *GLOSSARY_FIXES]
        }
        units = [(uid, jp, planned.get(uid, ko)) for uid, jp, ko in units]
    print(f"glossary terms: {len(terms)} / aligned units: {len(units)}")
    findings = []
    for jp_term, ko_term in terms:
        if args.term and args.term not in {jp_term, ko_term}:
            continue
        total = 0
        rows = []
        for uid, jp, ko in units:
            k = ko.count(ko_term)
            if not k:
                continue
            # Skip untranslated/internal enum-style identifiers.  A glossary
            # title such as INSTALL can otherwise look like a collision inside
            # SONG_TOYINSTALLER even though the value is never display text.
            if jp == ko and ASCII_IDENTIFIER.fullmatch(jp):
                continue
            extra = max(
                0,
                k
                - japanese_term_count(jp, jp_term)
                - intentional_alias_count(jp, jp_term, ko_term),
            )
            if not extra:
                continue
            total += extra
            rows.append((uid, jp, ko, extra))
        if total >= args.min_extra:
            findings.append((total, jp_term, ko_term, rows))

    findings.sort(reverse=True, key=lambda x: x[0])
    for total, jp_term, ko_term, rows in findings:
        sources = defaultdict(int)
        for uid, _jp, _ko, extra in rows:
            sources[uid.split(":", 1)[0]] += extra
        src_text = ", ".join(f"{k}={v}" for k, v in sorted(sources.items()))
        print(f"\n[{total:4d}] {jp_term} => {ko_term}  ({len(rows)} units; {src_text})")
        for uid, jp, ko, extra in rows[:args.contexts]:
            print(f"  {uid} (+{extra})")
            print(f"    JP: {jp[:180]}")
            print(f"    KO: {ko[:180]}")
    print(f"\nfindings: {len(findings)} terms / {sum(x[0] for x in findings)} extra matches")

    if args.nested_terms:
        nested = []
        for outer_jp, outer_ko in terms:
            for inner_jp, inner_ko in terms:
                if (outer_jp, outer_ko) == (inner_jp, inner_ko):
                    continue
                if inner_ko and inner_ko in outer_ko:
                    nested.append((inner_jp, inner_ko, outer_jp, outer_ko))
        print(f"\nnested glossary-title pairs: {len(nested)}")
        for inner_jp, inner_ko, outer_jp, outer_ko in nested:
            print(f"  {inner_jp} => {inner_ko}  IN  {outer_jp} => {outer_ko}")

    if args.embedded:
        embedded = []
        for jp_term, ko_term in terms:
            if args.term and args.term not in {jp_term, ko_term}:
                continue
            for uid, jp, ko in units:
                start = 0
                while True:
                    pos = ko.find(ko_term, start)
                    if pos < 0:
                        break
                    left = ko[pos - 1] if pos > 0 else ""
                    right_pos = pos + len(ko_term)
                    right = ko[right_pos] if right_pos < len(ko) else ""
                    if (left and HANGUL.fullmatch(left)) or (right and HANGUL.fullmatch(right)):
                        embedded.append((jp_term, ko_term, uid, jp, ko, left, right))
                    start = pos + max(1, len(ko_term))
        print(f"\nembedded Hangul occurrences: {len(embedded)}")
        for jp_term, ko_term, uid, jp, ko, left, right in embedded[:args.contexts]:
            print(f"  {jp_term} => {ko_term}  {uid}  boundary={left!r}/{right!r}")
            print(f"    JP: {jp[:180]}")
            print(f"    KO: {ko[:180]}")


if __name__ == "__main__":
    main()
