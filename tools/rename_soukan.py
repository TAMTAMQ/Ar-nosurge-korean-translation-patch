#!/usr/bin/env python3
"""Rename the 想観 plot term so it stops colliding with the word 상관.

想観 (そうかん) is a registered glossary/도감 term, and the game highlights
registered terms wherever they appear in text. Translating it as 상관 made every
ordinary "상관없어" (from 関係ない / どうでもいい) look like the term to the
game, so the encyclopedia notification fired constantly — 490 lines contain
상관 without the term being present at all.

Renaming the term is far cheaper than rewording 490 lines, so it becomes 소칸,
the Japanese reading, which no ordinary Korean word collides with.

The replacement count is taken from the Japanese side. 母胎想観 is handled
first, and only the leftover bare 想観 occurrences license further rewrites —
otherwise a line like `関係なくないよ…母胎想観に` (translated "상관있어 …
모태상관에") would lose its ordinary 상관 too.
"""

import argparse
import csv
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO = Path(__file__).resolve().parents[1]
RECORD_HEADER = 32
ATTR = re.compile(r'''(?P<head>\s[\w:.-]+\s*=\s*)(?P<q>["'])(?P<value>.*?)(?P=q)''', re.DOTALL)

TERM = re.compile("想観")
COMPOUND = re.compile("母[胎体]想観")


def rename(japanese, korean):
    total = len(TERM.findall(japanese))
    if not total:
        return korean
    compound = len(COMPOUND.findall(japanese))
    text = korean.replace("모태상관", "모태소칸")
    bare = total - compound
    if bare > 0 and "상관" in text:
        text = text.replace("상관", "소칸", bare)
    return text


def parse_ebm(data):
    count = int.from_bytes(data[:4], "little")
    position = 4
    records = []
    for _ in range(count):
        header = data[position:position + RECORD_HEADER]
        length = int.from_bytes(data[position + RECORD_HEADER:position + RECORD_HEADER + 4], "little")
        start = position + RECORD_HEADER + 4
        end = start + length
        records.append([header, data[start:end - 1].decode("utf-8")])
        position = end
    return records


def build_ebm(records):
    out = bytearray(len(records).to_bytes(4, "little"))
    for header, text in records:
        payload = text.encode("utf-8") + bytes(1)
        out += header + len(payload).to_bytes(4, "little") + payload
    return bytes(out)


def read_original_xml(path):
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp932")


def main():
    csv.field_size_limit(1 << 30)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    mapping = json.loads((REPO / "build" / "final_mod_report.json")
                         .read_text(encoding="utf-8"))["hangul_to_standin"]

    def byte_length(text):
        return len("".join(mapping.get(c, c) for c in text).encode("utf-8"))

    totals = {}
    skipped = 0

    path = REPO / "translations" / "exefs" / "main_1.0.1.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = list(reader)
    changed = 0
    for row in rows:
        if not row["translation"]:
            continue
        new = rename(row["original"], row["translation"])
        if new == row["translation"]:
            continue
        if byte_length(new) > int(row["capacity_bytes"]):
            print(f"  용량 초과로 건너뜀 [{row['index']}]")
            skipped += 1
            continue
        row["translation"] = new
        changed += 1
    totals["main"] = changed
    if not args.dry_run and changed:
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    changed = 0
    for translated in sorted((REPO / "translations" / "romfs" / "Event" / "event").rglob("*.ebm")):
        relative = translated.relative_to(REPO / "translations").as_posix()
        source = REPO / "originalText" / relative.replace("romfs/Event", "romfs/EVENT")
        if not source.is_file():
            continue
        originals = parse_ebm(source.read_bytes())
        records = parse_ebm(translated.read_bytes())
        dirty = False
        for (_, japanese), record in zip(originals, records):
            new = rename(japanese, record[1])
            if new != record[1]:
                record[1] = new
                dirty = True
                changed += 1
        if dirty and not args.dry_run:
            translated.write_bytes(build_ebm(records))
    totals["ebm"] = changed

    changed = 0
    root = REPO / "translations" / "romfs" / "Saves"
    origin = REPO / "originalText" / "romfs" / "Saves"
    for translated in sorted(root.rglob("*.xml")):
        source = origin / translated.relative_to(root)
        if not source.is_file():
            continue
        japanese = [html.unescape(m.group("value"))
                    for m in ATTR.finditer(read_original_xml(source))]
        text = translated.read_text(encoding="utf-8", newline="")
        index = 0
        hits = 0

        def replace(match):
            nonlocal index, hits
            value = html.unescape(match.group("value"))
            source_value = japanese[index] if index < len(japanese) else ""
            index += 1
            new = rename(source_value, value)
            if new == value:
                return match.group(0)
            hits += 1
            quote = match.group("q")
            escaped = (new.replace("&", "&amp;").replace("<", "&lt;")
                       .replace(">", "&gt;").replace(quote, "&quot;" if quote == '"' else "&apos;"))
            return match.group("head") + quote + escaped + quote

        updated = ATTR.sub(replace, text)
        if hits and not args.dry_run:
            translated.write_text(updated, encoding="utf-8", newline="")
        changed += hits
    totals["saves"] = changed

    original_path = REPO / "originalText" / "romfs" / "Event" / "balloonsel" / "balloonseldata.json"
    translated_path = REPO / "translations" / "romfs" / "Event" / "balloonsel" / "balloonseldata.json"
    changed = 0
    originals = json.loads(original_path.read_text(encoding="utf-8"))
    groups = json.loads(translated_path.read_text(encoding="utf-8"))
    for source_group, group in zip(originals, groups):
        for position, (japanese, korean) in enumerate(zip(source_group, group)):
            new = rename(japanese, korean)
            if new != korean:
                group[position] = new
                changed += 1
    if changed and not args.dry_run:
        translated_path.write_text(json.dumps(groups, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    totals["balloonsel"] = changed

    print("  " + "  ".join(f"{k} {v}" for k, v in totals.items()) + f"  (건너뜀 {skipped})")


if __name__ == "__main__":
    main()
