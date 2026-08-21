#!/usr/bin/env python3
"""남은 `・` 손실을 대응표를 배워서 채운다.

`restore_middle_dot.py`는 원문과 번역을 같은 수의 덩어리로 쪼갤 수 있을 때만
`・`를 되돌린다. 그래서 이름이 긴 문장 안에 묻혀 있으면 남는다.

여기서는 이미 복원된 곳에서 "일본어 복합어 -> 점 있는 한국어" 대응을 읽어낸 뒤,
그 복합어가 원문에 있는 단위에 한해 점 없는 형태를 점 있는 형태로 바꾼다.
원문에 해당 복합어가 없으면 건드리지 않으므로 엉뚱한 곳이 바뀌지 않는다.
"""

import argparse
import csv
import html
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO = Path(__file__).resolve().parents[1]
RECORD_HEADER = 32
ATTR = re.compile(r'''(?P<head>\s[\w:.-]+\s*=\s*)(?P<q>["'])(?P<value>.*?)(?P=q)''', re.DOTALL)
COMPOUND = re.compile(r"[ぁ-ヿ一-鿿A-Za-zＡ-Ｚａ-ｚ0-9０-９]+(?:・[ぁ-ヿ一-鿿A-Za-zＡ-Ｚａ-ｚ0-9０-９]+)+")
KOREAN_DOTTED = re.compile(r"[가-힣A-Za-z0-9]+(?:・[가-힣A-Za-z0-9]+)+")


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


def collect_units():
    units = []
    csv.field_size_limit(1 << 30)
    path = REPO / "translations" / "exefs" / "main_1.0.1.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["translation"]:
                units.append((row["original"], row["translation"]))
    for translated in sorted((REPO / "translations" / "romfs" / "Event" / "event").rglob("*.ebm")):
        relative = translated.relative_to(REPO / "translations").as_posix()
        source = REPO / "originalText" / relative.replace("romfs/Event", "romfs/EVENT")
        if source.is_file():
            for (_, japanese), (_, korean) in zip(parse_ebm(source.read_bytes()),
                                                  parse_ebm(translated.read_bytes())):
                units.append((japanese, korean))
    root = REPO / "translations" / "romfs" / "Saves"
    origin = REPO / "originalText" / "romfs" / "Saves"
    for translated in sorted(root.rglob("*.xml")):
        source = origin / translated.relative_to(root)
        if not source.is_file():
            continue
        japanese = [html.unescape(m.group("value")) for m in ATTR.finditer(read_original_xml(source))]
        korean = [html.unescape(m.group("value"))
                  for m in ATTR.finditer(translated.read_text(encoding="utf-8", newline=""))]
        units.extend(zip(japanese, korean))
    return units


def learn(units):
    """복원이 끝난 단위에서 일본어 복합어 -> 점 있는 한국어 대응을 읽는다."""
    table = defaultdict(Counter)
    for japanese, korean in units:
        compounds = COMPOUND.findall(japanese)
        dotted = KOREAN_DOTTED.findall(korean)
        if len(compounds) == 1 and len(dotted) == 1:
            table[compounds[0]][dotted[0]] += 1
    learned = {}
    for compound, candidates in table.items():
        korean = candidates.most_common(1)[0][0]
        plain = korean.replace("・", " ")
        if plain != korean:
            learned[compound] = (plain, korean)
    return learned


WORD = r"[가-힣A-Za-z0-9]+"


def head_anchors(learned):
    """두 조각짜리 이름의 앞 조각. 뒤 조각의 표기가 조금 달라도 잡기 위해서다."""
    anchors = {}
    for compound, (_, dotted) in learned.items():
        parts = dotted.split("・")
        if len(parts) == 2:
            anchors[compound] = parts[0]
    return anchors


def apply(learned, japanese, korean, anchors=None):
    for compound, (plain, dotted) in learned.items():
        if compound in japanese and plain in korean:
            korean = korean.replace(plain, dotted)
    if anchors and japanese.count("・") > korean.count("・"):
        for compound, head in anchors.items():
            if compound not in japanese:
                continue
            korean = re.sub(rf"(?<![가-힣]){re.escape(head)} ({WORD})",
                            lambda m: f"{head}・{m.group(1)}",
                            korean, count=japanese.count(compound))
    return korean


def main():
    csv.field_size_limit(1 << 30)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    learned = learn(collect_units())
    anchors = head_anchors(learned)
    print(f"배운 대응 {len(learned)}종 (앞 조각 기준 {len(anchors)}종)")
    for compound, (plain, dotted) in list(learned.items())[:12]:
        print(f"  {compound!r} : {plain!r} -> {dotted!r}")

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
        new = apply(learned, row["original"], row["translation"], anchors)
        if new == row["translation"]:
            continue
        if byte_length(new) > int(row["capacity_bytes"]):
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
            new = apply(learned, japanese, record[1], anchors)
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
        japanese = [html.unescape(m.group("value")) for m in ATTR.finditer(read_original_xml(source))]
        text = translated.read_text(encoding="utf-8", newline="")
        index = 0
        hits = 0

        def replace(match):
            nonlocal index, hits
            value = html.unescape(match.group("value"))
            source_value = japanese[index] if index < len(japanese) else ""
            index += 1
            new = apply(learned, source_value, value, anchors)
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
            new = apply(learned, japanese, korean, anchors)
            if new != korean:
                group[position] = new
                changed += 1
    if changed and not args.dry_run:
        translated_path.write_text(json.dumps(groups, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    totals["balloonsel"] = changed

    print("  " + "  ".join(f"{k} {v}" for k, v in totals.items()) + f"  (용량으로 건너뜀 {skipped})")


if __name__ == "__main__":
    main()
