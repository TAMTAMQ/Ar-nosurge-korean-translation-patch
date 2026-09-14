#!/usr/bin/env python3
"""Audit glossary substring collisions in built PC/Switch runtime outputs.

This is a readback companion to audit_glossary_substring_collisions.py.  Built
files replace Hangul with rare Japanese stand-in glyphs, and most Saves XML is
stored as version-1 .xml.e.  This tool reverses both transformations, aligns the
result with the Japanese originals, and applies the same glossary substring
check to what the game will actually load.
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_glossary_substring_collisions import (
    ATTR,
    ASCII_IDENTIFIER,
    TAG,
    glossary_terms,
    intentional_alias_count,
    japanese_term_count,
    parse_ebm,
    read_text,
)
from balloonsel import parse as parse_balloonsel
from decode_saves_xml_e import decode_file, detect_text_encoding
from rename_term import rename
from audit_switch_runtime_glossary_titles import decode_runtime, parse_ips, title_rows

REPO = Path(__file__).resolve().parents[1]
ORIGINAL_EVENT = REPO / "originalText" / "romfs" / "EVENT" / "event"
ORIGINAL_SAVES = REPO / "originalText" / "romfs" / "Saves"
ORIGINAL_BALLOON_JSON = (
    REPO / "originalText" / "romfs" / "Event" / "balloonsel" / "balloonseldata.json"
)


def inverse_mapping(path: Path) -> dict[str, str]:
    mapping = json.loads(path.read_text(encoding="utf-8"))["hangul_to_standin"]
    inverse = {standin: hangul for hangul, standin in mapping.items()}
    if len(inverse) != len(mapping):
        raise ValueError("stand-in mapping is not one-to-one")
    return inverse


def restore_hangul(text: str, inverse: dict[str, str]) -> str:
    return "".join(inverse.get(ch, ch) for ch in text)


def xml_tag_attrs_text(text: str) -> list[tuple[str, dict[str, str]]]:
    out: list[tuple[str, dict[str, str]]] = []
    for tag_match in TAG.finditer(text):
        attrs = {
            m.group("name"): html.unescape(m.group("value"))
            for m in ATTR.finditer(tag_match.group("body"))
        }
        out.append((tag_match.group("tag"), attrs))
    return out


def aligned_xml_texts(jp_text: str, ko_text: str, label: str):
    jp_tags = xml_tag_attrs_text(jp_text)
    ko_tags = xml_tag_attrs_text(ko_text)
    if len(jp_tags) != len(ko_tags):
        print(
            f"warning: XML structure differs; using attribute-value fallback: {label}: "
            f"jp={len(jp_tags)} ko={len(ko_tags)}"
        )
        jp_values = "\n".join(value for _tag, attrs in jp_tags for value in attrs.values())
        ko_values = "\n".join(value for _tag, attrs in ko_tags for value in attrs.values())
        yield f"{label}:ATTR_FALLBACK", jp_values, ko_values
        return
    for i, ((jp_tag, jp_attrs), (ko_tag, ko_attrs)) in enumerate(zip(jp_tags, ko_tags)):
        if jp_tag != ko_tag:
            print(
                f"warning: XML tag order differs; using attribute-value fallback: {label}: "
                f"#{i} {jp_tag} != {ko_tag}"
            )
            jp_values = "\n".join(value for _tag, attrs in jp_tags for value in attrs.values())
            ko_values = "\n".join(value for _tag, attrs in ko_tags for value in attrs.values())
            yield f"{label}:ATTR_FALLBACK", jp_values, ko_values
            return
        for name, ko_value in ko_attrs.items():
            if name in jp_attrs:
                yield f"{label}:{i}:{name}", jp_attrs[name], ko_value


def read_runtime_xml(path: Path, inverse: dict[str, str]) -> str:
    if path.name.endswith(".xml.e"):
        raw = decode_file(path)
        enc = detect_text_encoding(raw)
        text = raw.decode(enc)
    else:
        text = read_text(path)
    return restore_hangul(text, inverse)


def runtime_units(event_root: Path, saves_root: Path, balloon_path: Path | None,
                  inverse: dict[str, str], platform: str):
    for runtime in sorted(event_root.rglob("*.ebm")):
        rel = runtime.relative_to(event_root)
        original = ORIGINAL_EVENT / rel
        if not original.is_file():
            raise FileNotFoundError(f"missing original EBM: {rel}")
        jp = parse_ebm(original.read_bytes())
        ko = [restore_hangul(x, inverse) for x in parse_ebm(runtime.read_bytes())]
        if len(jp) != len(ko):
            raise ValueError(f"EBM record-count mismatch: {platform}:{rel}")
        for i, (a, b) in enumerate(zip(jp, ko)):
            yield f"{platform}:ebm:{rel.as_posix()}:{i}", a, b

    for runtime in sorted(saves_root.rglob("*.xml")) + sorted(saves_root.rglob("*.xml.e")):
        rel = runtime.relative_to(saves_root)
        original_rel = Path(str(rel)[:-2]) if runtime.name.endswith(".xml.e") else rel
        original = ORIGINAL_SAVES / original_rel
        if not original.is_file():
            # Runtime-only samples/debug UI do not contain translated story text.
            continue
        jp_text = read_text(original)
        ko_text = read_runtime_xml(runtime, inverse)
        label = f"{platform}:xml:{original_rel.as_posix()}"
        yield from aligned_xml_texts(jp_text, ko_text, label)

    if balloon_path and balloon_path.is_file() and ORIGINAL_BALLOON_JSON.is_file():
        jp = json.loads(ORIGINAL_BALLOON_JSON.read_text(encoding="utf-8"))
        ko = parse_balloonsel(balloon_path.read_bytes())
        if len(jp) != len(ko):
            raise ValueError(f"balloon group mismatch: {platform}")
        for gi, (jg, kg) in enumerate(zip(jp, ko)):
            if len(jg) != len(kg):
                raise ValueError(f"balloon option mismatch: {platform}:{gi}")
            for oi, (a, b) in enumerate(zip(jg, kg)):
                yield f"{platform}:balloon:{gi}:{oi}", a, restore_hangul(b, inverse)


def audit(units, terms, contexts: int):
    findings = []
    units = list(units)
    for jp_term, ko_term in terms:
        rows = []
        total = 0
        for uid, jp, ko in units:
            k = ko.count(ko_term)
            if not k:
                continue
            if jp == ko and ASCII_IDENTIFIER.fullmatch(jp):
                continue
            extra = max(
                0,
                k
                - japanese_term_count(jp, jp_term)
                - intentional_alias_count(jp, jp_term, ko_term),
            )
            if extra:
                total += extra
                rows.append((uid, jp, ko, extra))
        if total:
            findings.append((total, jp_term, ko_term, rows))
    findings.sort(reverse=True, key=lambda x: x[0])
    for total, jp_term, ko_term, rows in findings:
        print(f"\n[{total}] {jp_term} => {ko_term}")
        for uid, jp, ko, extra in rows[:contexts]:
            print(f"  {uid} (+{extra})")
            print(f"    JP: {jp[:180]}")
            print(f"    KO: {ko[:180]}")
    return len(units), findings


def switch_installed_terms(ips_path: Path, mapping: dict[str, str]) -> list[tuple[str, str]]:
    """Read the glossary title strings actually registered by the installed Switch IPS."""
    inverse = {standin: hangul for hangul, standin in mapping.items()}
    patch = parse_ips(ips_path.read_bytes())
    rows = title_rows(REPO / "translations" / "exefs" / "main_1.0.1.csv")
    terms = []
    for row in rows:
        offset = int(row["memory_address"], 16) + 0x100
        actual = patch.get(offset)
        if actual is None:
            raise ValueError(f"Switch IPS missing glossary title slot: index={row['index']} offset=0x{offset:X}")
        terms.append((row["original"], decode_runtime(actual, inverse)))
    if len(terms) != 76:
        raise ValueError(f"unexpected Switch glossary-title count: {len(terms)}")
    return terms


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mapping", type=Path, default=REPO / "build" / "final_mod_report.json")
    ap.add_argument("--platform", choices=["switch", "pc", "both"], default="both")
    ap.add_argument("--contexts", type=int, default=10)
    ap.add_argument("--switch-romfs", type=Path,
                    default=REPO / "atmosphere" / "contents" / "01003CF0128DE000" / "romfs")
    ap.add_argument("--switch-ips", type=Path,
                    default=REPO / "atmosphere" / "exefs_patches" / "ArNosurgeKoreanUI" /
                            "28F3C3965CEB60AC18A23E2B2C0C4BEEE3C81D8B.ips")
    ap.add_argument("--assume-current-titles", action="store_true",
                    help="use current normalized glossary titles instead of reading the installed Switch IPS")
    args = ap.parse_args()

    report = json.loads(args.mapping.read_text(encoding="utf-8"))
    mapping = report["hangul_to_standin"]
    inv = {standin: hangul for hangul, standin in mapping.items()}
    expected_terms = [(jp, rename(ko)) for jp, ko in glossary_terms()]
    configs = []
    if args.platform in {"switch", "both"}:
        root = args.switch_romfs
        switch_ips = args.switch_ips
        configs.append((
            "switch",
            root / "Event" / "event",
            root / "Saves",
            root / "Event" / "balloonsel" / "balloonseldata.bsb",
            expected_terms if args.assume_current_titles else switch_installed_terms(switch_ips, mapping),
        ))
    if args.platform in {"pc", "both"}:
        configs.append((
            "pc",
            REPO / "build" / "pc" / "event" / "event",
            REPO / "build" / "pc" / "saves_out",
            REPO / "build" / "pc" / "event" / "balloonsel" / "balloonseldata.bsb",
            expected_terms,
        ))

    grand_findings = 0
    for platform, event_root, saves_root, balloon, terms in configs:
        units = runtime_units(event_root, saves_root, balloon, inv, platform)
        count, findings = audit(units, terms, args.contexts)
        grand_findings += sum(x[0] for x in findings)
        print(
            f"\n{platform}: glossary terms={len(terms)} aligned runtime units={count} "
            f"false-link extras={sum(x[0] for x in findings)}"
        )
    if grand_findings:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
