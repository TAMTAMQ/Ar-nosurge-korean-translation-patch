#!/usr/bin/env python3
"""ASCII로 바뀐 전각 영숫자를 원본대로 되돌린다.

번역 대상은 일본어뿐인데 `Ｌｖ`, `０`, `ＲＮＡ`, `＿` 같은 전각 영숫자까지
반각으로 바뀌었다. 이 문자들은 애초에 일본어가 아니므로 원본을 따라야 한다.

판단은 단위(CSV 한 행 / EBM 한 레코드 / XML 속성 하나 / 선택지 하나)별로 한다.
**원본이 그 전각 형태를 쓰면서 반각 형태는 쓰지 않은 경우에만** 되돌리므로,
원본이 둘을 섞어 쓴 자리는 건드리지 않는다.

전각은 화면에서 반각의 두 배 폭을 차지하고 UTF-8로도 3바이트(반각은 1바이트)다.
`main` 문자열은 고정 슬롯이라 그대로 넣으면 넘치는 행이 많다. 그런 행은 먼저
띄어쓰기를 뒤에서부터 줄여 맞춰 보고, 그래도 안 되면 반각을 유지하고 보고한다.
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

# 전각 -> 반각. 되돌릴 때는 반대로 쓴다.
PAIRS = [(chr(code), chr(code - 0xFEE0))
         for code in list(range(0xFF10, 0xFF1A))      # ０-９
         + list(range(0xFF21, 0xFF3B))                # Ａ-Ｚ
         + list(range(0xFF41, 0xFF5B))]               # ａ-ｚ
PAIRS.append(("＿", "_"))


def restore(japanese, korean):
    for full, half in PAIRS:
        if full in japanese and half not in japanese and half in korean:
            korean = korean.replace(half, full)
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
    parser.add_argument("--no-squeeze", action="store_true",
                        help="슬롯이 모자라도 띄어쓰기를 줄이지 않는다")
    args = parser.parse_args()

    mapping = json.loads((REPO / "build" / "final_mod_report.json")
                         .read_text(encoding="utf-8"))["hangul_to_standin"]

    def byte_length(text):
        return len("".join(mapping.get(c, c) for c in text).encode("utf-8"))

    totals = {}
    squeezed = skipped = 0

    path = REPO / "translations" / "exefs" / "main_1.0.1.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = list(reader)
    changed = 0
    for row in rows:
        if not row["translation"]:
            continue
        new = restore(row["original"], row["translation"])
        if new == row["translation"]:
            continue
        capacity = int(row["capacity_bytes"])
        if byte_length(new) > capacity and not args.no_squeeze:
            trimmed = new
            while byte_length(trimmed) > capacity and " " in trimmed:
                cut = trimmed.rfind(" ")
                trimmed = trimmed[:cut] + trimmed[cut + 1:]
            if byte_length(trimmed) <= capacity:
                new = trimmed
                squeezed += 1
        if byte_length(new) > capacity:
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
            new = restore(japanese, record[1])
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
    totals["saves"] = changed

    original_path = REPO / "originalText" / "romfs" / "Event" / "balloonsel" / "balloonseldata.json"
    translated_path = REPO / "translations" / "romfs" / "Event" / "balloonsel" / "balloonseldata.json"
    changed = 0
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
    totals["balloonsel"] = changed

    print("  " + "  ".join(f"{k} {v}" for k, v in totals.items())
          + f"  (띄어쓰기 줄여 맞춘 행 {squeezed} / 용량으로 유지 {skipped})")


if __name__ == "__main__":
    main()
