#!/usr/bin/env python3
"""Keep キャス (캐스) and キャスティ (캐스티) apart.

キャス is the nickname everyone uses for キャスティ. They are different strings
in the original and have to stay different in Korean, but the model normalised
most of them to the full name — `キャスが起こしに来たんだろうが` came out as
"캐스티가 깨우러 온 거잖아".

The decision is made per unit from the Japanese side:

* the unit mentions only キャス  -> every 캐스티 becomes 캐스
* the unit mentions only キャスティ -> every bare 캐스 becomes 캐스티
* the unit mentions both -> left alone and reported, because a blind rewrite
  would collapse the very distinction being restored

`main` rows sit in fixed slots, so a row that would overflow keeps its current
text and is reported.
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

FULL_JP = re.compile("キャスティ")
SHORT_JP = re.compile("キャス(?!ティ)")
FULL_KO = re.compile("캐스티")
SHORT_KO = re.compile("캐스(?!티)")

ambiguous = []


def correct(japanese, korean, tag):
    full = len(FULL_JP.findall(japanese))
    short = len(SHORT_JP.findall(japanese))
    if full and short:
        if FULL_KO.search(korean) or SHORT_KO.search(korean):
            ambiguous.append((tag, japanese, korean))
        return korean
    if short and not full:
        return FULL_KO.sub("캐스", korean)
    if full and not short:
        return SHORT_KO.sub("캐스티", korean)
    return korean


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
        new = correct(row["original"], row["translation"], "main " + row["index"])
        if new == row["translation"]:
            continue
        if byte_length(new) > int(row["capacity_bytes"]):
            print(f"  용량 초과로 건너뜀 [{row['index']}] {new}")
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
        for index, ((_, japanese), record) in enumerate(zip(originals, records)):
            new = correct(japanese, record[1], f"{translated.name}[{index}]")
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
            new = correct(source_value, value, translated.name)
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
            new = correct(japanese, korean, "balloonsel")
            if new != korean:
                group[position] = new
                changed += 1
    if changed and not args.dry_run:
        translated_path.write_text(json.dumps(groups, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    totals["balloonsel"] = changed

    print("  " + "  ".join(f"{k} {v}" for k, v in totals.items())
          + f"  (건너뜀 {skipped})")
    if ambiguous:
        print(f"\n원문에 キャス와 キャスティ가 함께 있어 자동 판단하지 않은 단위 {len(ambiguous)}:")
        for tag, japanese, korean in ambiguous[:20]:
            print(f"  [{tag}] {japanese[:56]!r}\n      {korean[:56]!r}")


if __name__ == "__main__":
    main()
