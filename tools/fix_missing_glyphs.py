#!/usr/bin/env python3
"""Replace characters the game font has no glyph for.

The Korean patch draws Hangul into borrowed atlas cells; every other character
still has to exist in the original font. The model introduced punctuation the
game never used — most visibly `·` (U+00B7) in 조직·지명 style lists, which the
game draws as an empty box because its own text only ever uses `・` (U+30FB).

Each replacement below is a character proven to occur in the game's own text,
so it is guaranteed to have a glyph. Quotation marks the translator invented
are dropped rather than swapped, since the original had none.
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

# character -> replacement, all verified present in the original game text
SIMPLE = {
    "·": "・",   # · MIDDLE DOT        -> ・ (원본 844회)
    "—": "～",   # — EM DASH           -> ～ (원본 931회), 말끝 늘임 표기
    "ㅡ": "～",   # ㅡ 한글 자모         -> ～
    "،": ",",        # ، 아랍어 쉼표         -> ,
    "।": ".",        # । 데바나가리 마침표    -> .
    "‘": "",         # ‘ 원문에 없던 인용부호 -> 삭제
    "’": "",         # ’
}

# Quotation the translator added. The replacement depends on what the original
# actually used, so it is decided per unit.
APOSTROPHE = re.compile(r"'([^']{1,40})'")

# One-off rewrites where a straight substitution would read wrong.
MANUAL = [
    ("ペペンアットマーク", "페펜@마크", "페펜앳마크"),
    ("サ……ン……ジュ", "사……ㄴ……쥬", "사……안……쥬"),
]


def fix_apostrophes(japanese, korean):
    if "'" not in korean:
        return korean
    if "〝" in japanese:
        return APOSTROPHE.sub(r"〝\1〟", korean)
    if "＂" in japanese:
        return APOSTROPHE.sub(r"＂\1＂", korean)
    if "「" in japanese and korean.count("「") < japanese.count("「"):
        return APOSTROPHE.sub(r"「\1」", korean)
    # The original quoted nothing here; drop the invented marks.
    return korean.replace("'", "")


def fix(japanese, korean):
    text = korean
    for source, japanese_original, replacement in MANUAL:
        if source in japanese and japanese_original in text:
            text = text.replace(japanese_original, replacement)
    for wrong, right in SIMPLE.items():
        text = text.replace(wrong, right)
    return fix_apostrophes(japanese, text)


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
        new = fix(row["original"], row["translation"])
        if new == row["translation"]:
            continue
        capacity = int(row["capacity_bytes"])
        # `・` costs one byte more than `·`. A box on screen is worse than a
        # missing space, so buy the byte back from spacing before giving up.
        while byte_length(new) > capacity and " " in new:
            cut = new.rfind(" ")
            new = new[:cut] + new[cut + 1:]
        if byte_length(new) > capacity:
            print(f"  용량 초과로 건너뜀 [{row['index']}] {new[:60]}")
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
            new = fix(japanese, record[1])
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
            new = fix(source_value, value)
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
            new = fix(japanese, korean)
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
