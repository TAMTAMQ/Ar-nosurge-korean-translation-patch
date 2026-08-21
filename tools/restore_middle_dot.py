#!/usr/bin/env python3
"""원문의 `・`(U+30FB)를 번역문에 되돌린다.

`・`는 일본어 문자가 아니라 고유명사를 잇는 구분 기호다. 그런데 번역이
`タワーリング・ギロティーヌ`를 "타워링 기로틴"처럼 공백으로, `シールド・弱`을
"실드(약)"처럼 괄호로 바꿔 놓았다.

어느 공백이 원문의 `・` 자리인지 알아야 하므로, 번역이 유지한 강한 구분자
(`：`, `【】`, `「」`, `『』`, `（）`, 제어 코드, `<CR>`)로 원문과 번역을 같은
수의 덩어리로 쪼갠 뒤 짝을 맞춘다. 덩어리 안에서만 다음을 시도한다.

* `X(약)` 형태 -> `X・약`  (원문이 `X・弱` 일 때)
* 공백으로 나뉜 조각 수가 원문의 `・` 조각 수와 같을 때만 공백을 `・`로

짝이 맞지 않거나 조각 수가 다르면 손대지 않고 남긴다. 잘못 찍느니 남기는 쪽이
낫기 때문이다.
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

# 번역이 그대로 유지하는 구분자. 이걸 기준으로 원문과 번역을 같이 쪼갠다.
SPLITTER = re.compile(r"(<[^>]{1,20}>|[：:【】「」『』（）()\[\]／/、。,.!！?？\n]|　)")
LEVEL = {"弱": "약", "中": "중", "強": "강", "小": "소", "大": "대"}


def restore_chunk(japanese, korean):
    if "・" not in japanese or "・" in korean:
        return korean
    parts = japanese.split("・")
    # X・弱 -> X(약) 로 바뀐 경우
    if len(parts) == 2 and parts[1] in LEVEL:
        match = re.fullmatch(r"(.*?)\s*\((%s)\)\s*" % LEVEL[parts[1]], korean)
        if match:
            return f"{match.group(1).rstrip()}・{match.group(2)}"
    chunks = korean.split(" ")
    if len(chunks) == len(parts) and all(chunks):
        return "・".join(chunks)
    return korean


def restore(japanese, korean):
    if "・" not in japanese:
        return korean
    if japanese.count("・") <= korean.count("・"):
        return korean
    source = SPLITTER.split(japanese)
    target = SPLITTER.split(korean)
    if len(source) != len(target):
        return korean
    out = []
    for index, (piece, translated) in enumerate(zip(source, target)):
        if index % 2 == 1:                       # 구분자 자리
            out.append(translated)
            continue
        out.append(restore_chunk(piece.strip(), translated.strip())
                   if piece.strip() and translated.strip() else translated)
        if out[-1] != translated:
            leading = translated[:len(translated) - len(translated.lstrip())]
            trailing = translated[len(translated.rstrip()):]
            out[-1] = leading + out[-1] + trailing
    return "".join(out)


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
        new = restore(row["original"], row["translation"])
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

    print("  " + "  ".join(f"{k} {v}" for k, v in totals.items()) + f"  (용량으로 건너뜀 {skipped})")


if __name__ == "__main__":
    main()
