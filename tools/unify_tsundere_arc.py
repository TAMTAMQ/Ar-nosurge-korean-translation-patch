#!/usr/bin/env python3
"""Unify the ツン / デレ wordplay names that were translated inconsistently.

The SWC01 arc is built on a pun: two nations named ツーン王国 and デレー帝国,
a language pair ツン語 / デレ語, and a translator character ツンデレイン. The
model kept guessing at these instead of transliterating them, and it also
expanded ツン into ツンデレ where the original deliberately split the word —
`ツン王国デレ帝国` became "츤데레 왕국 데레 제국", which destroys the joke.

`プッツンプリン` fared worse still, appearing as 푸슉/푸츈푸링/풋춘푸린/
푸춘푸춘/풋푼푸린/푸딩 푸딩 across different lines.

Every rule below is keyed on the Japanese original, so a line is only touched
when it actually contains the term being unified. The bare word プッツン (the
onomatopoeia) is normalised separately from the item name プッツンプリン.
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

ITEM_VARIANTS = ["푸츈푸츈 푸딩", "푸춘푸춘 푸딩", "푸딩 푸딩", "풋춘 푸딩", "푸슉 푸딩",
                 "푸츈푸링", "푸춘푸링", "풋춘푸린", "풋푼푸린", "푸츈푸츈", "푸춘푸춘"]
WORD_VARIANTS = ["푸츈푸츈", "푸춘푸춘", "풋춘", "푸춘", "풋푼"]

# (japanese marker, [(wrong, right), ...])
RULES = [
    ("ツン王国デレ帝国", [("츤데레 왕국 데레 제국", "츤 왕국 데레 제국")]),
    ("ツーン王国", [("츈 왕국", "츤 왕국"), ("츤데레 왕국", "츤 왕국")]),
    ("ツン王国", [("츈 왕국", "츤 왕국")]),
    ("ツン語", [("츤츤 언어", "츤어"), ("츈어", "츤어")]),
    ("デレ語", [("데레데레 언어", "데레어"), ("데레데레한 말", "데레어")]),
    ("ツンデレイン", [("츤데레 레이인", "츤데레인")]),
    ("デレー帝国", [("데레데레 제국", "데레 제국")]),
]


def unify(japanese, korean):
    text = korean
    for marker, pairs in RULES:
        if marker not in japanese:
            continue
        for wrong, right in pairs:
            text = text.replace(wrong, right)
    if "プッツンプリン" in japanese:
        for variant in ITEM_VARIANTS:
            text = text.replace(variant, "푸츈 푸딩")
    if "プッツン" in japanese:
        for variant in WORD_VARIANTS:
            text = text.replace(variant, "푸츈")
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

    path = REPO / "translations" / "exefs" / "main_1.0.1.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = list(reader)
    changed = skipped = 0
    for row in rows:
        if not row["translation"]:
            continue
        new = unify(row["original"], row["translation"])
        if new == row["translation"]:
            continue
        if byte_length(new) > int(row["capacity_bytes"]):
            print(f"  용량 초과로 건너뜀 [{row['index']}] {new}")
            skipped += 1
            continue
        print(f"  [main {row['index']}] {row['translation']!r} -> {new!r}")
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
        for index, ((_, japanese), record) in enumerate(zip(originals, records)):
            new = unify(japanese, record[1])
            if new != record[1]:
                print(f"  [{translated.name}[{index}]] {record[1][:50]!r} -> {new[:50]!r}")
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
            new = unify(source_value, value)
            if new == value:
                return match.group(0)
            hits += 1
            print(f"  [{translated.name}] {value[:50]!r} -> {new[:50]!r}")
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
    if original_path.is_file() and translated_path.is_file():
        originals = json.loads(original_path.read_text(encoding="utf-8"))
        groups = json.loads(translated_path.read_text(encoding="utf-8"))
        for source_group, group in zip(originals, groups):
            for position, (japanese, korean) in enumerate(zip(source_group, group)):
                new = unify(japanese, korean)
                if new != korean:
                    print(f"  [balloonsel] {korean[:50]!r} -> {new[:50]!r}")
                    group[position] = new
                    changed += 1
        if changed and not args.dry_run:
            translated_path.write_text(json.dumps(groups, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    totals["balloonsel"] = changed

    print("\n" + "  ".join(f"{k} {v}" for k, v in totals.items()))


if __name__ == "__main__":
    main()
