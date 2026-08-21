#!/usr/bin/env python3
"""Put back the full-width punctuation the model quietly converted to ASCII.

Only Japanese text is supposed to change. The model nonetheless rewrote 「！」
「？」「（）」「～」 as ASCII across every target, which is a silent edit to
characters that were never Japanese to begin with.

Restoration is decided per unit (one CSV row, one EBM record, one XML attribute,
one balloon option): a full-width form is put back only when the original used
that full-width form and did **not** also use its ASCII counterpart, so units
that genuinely mixed both are left alone.

`main` strings live in fixed slots and a full-width mark costs three bytes
instead of one, so rows that would overflow keep the ASCII form and are
reported.
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

PAIRS = [("！", "!"), ("？", "?"), ("（", "("), ("）", ")"),
         ("～", "~"), ("％", "%"), ("＆", "&"), ("＋", "+"),
         ("：", ":"), ("．", "."), ("＝", "=")]


def restore(original, translated):
    for full, ascii_form in PAIRS:
        if full in original and ascii_form not in original:
            translated = translated.replace(ascii_form, full)
    return translated


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

    # main: fixed slots, so a restore can overflow.
    path = REPO / "translations" / "exefs" / "main_1.0.1.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = list(reader)
    changed = skipped = 0
    for row in rows:
        if not row["translation"]:
            continue
        new = restore(row["original"], row["translation"])
        if new == row["translation"]:
            continue
        if byte_length(new) > int(row["capacity_bytes"]):
            skipped += 1
            continue
        row["translation"] = new
        changed += 1
    totals["main"] = (changed, skipped)
    if not args.dry_run and changed:
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    # EBM: length prefixed, no capacity limit.
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
            new = restore(japanese, record[1])
            if new != record[1]:
                record[1] = new
                dirty = True
                changed += 1
        if dirty and not args.dry_run:
            translated.write_bytes(build_ebm(records))
    totals["ebm"] = (changed, 0)

    # Saves XML.
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
            new = restore(source_value, value)
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
    totals["saves"] = (changed, 0)

    # Balloon choices.
    original_path = REPO / "originalText" / "romfs" / "Event" / "balloonsel" / "balloonseldata.json"
    translated_path = REPO / "translations" / "romfs" / "Event" / "balloonsel" / "balloonseldata.json"
    changed = 0
    if original_path.is_file() and translated_path.is_file():
        originals = json.loads(original_path.read_text(encoding="utf-8"))
        groups = json.loads(translated_path.read_text(encoding="utf-8"))
        for source_group, group in zip(originals, groups):
            for position, (japanese, korean) in enumerate(zip(source_group, group)):
                new = restore(japanese, korean)
                if new != korean:
                    group[position] = new
                    changed += 1
        if changed and not args.dry_run:
            translated_path.write_text(json.dumps(groups, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
            cache = REPO / "build" / "balloonsel_translation_cache.json"
            if cache.is_file():
                entries = json.loads(cache.read_text(encoding="utf-8"))
                for source_group, group in zip(originals, groups):
                    for japanese, korean in zip(source_group, group):
                        entries[japanese] = korean
                cache.write_text(json.dumps(entries, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
    totals["balloonsel"] = (changed, 0)

    for name, (changed, skipped) in totals.items():
        note = f" / 용량 부족으로 유지 {skipped}" if skipped else ""
        print(f"  {name:11} 복원 {changed}{note}")


if __name__ == "__main__":
    main()
