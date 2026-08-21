#!/usr/bin/env python3
"""고유명사 표기를 통일한다. 이름을 바꾸면서 뒤따르는 조사도 받침에 맞춰 고친다.

번역 전에 용어집을 확정하지 않아서 같은 이름이 여러 표기로 갈렸다.

  アーシェス  -> 아셰스 291곳 / 아르셰스 122곳
  イオナサル  -> 이오나사르 669곳 / 이온살 11곳

표기만 바꾸면 조사가 어긋난다. 이온살(ㄹ받침) -> 이오나사르(받침 없음) 이므로
`이온살은` 은 `이오나사르는` 이 되어야 하고 `이온살이라면` 은 `이오나사르라면` 이
되어야 한다. 아셰스/아르셰스는 둘 다 받침이 없어 조사가 그대로다.

바꾼 뒤에는 반드시 scan_standin_collisions 를 다시 돌려라. 새 한글 음절이 생기면
폰트 대체 셀이 추가로 징발되어 전에는 멀쩡하던 곳이 새로 깨질 수 있다.
"""

import argparse
import csv
import html
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RECORD_HEADER = 32
ATTR = re.compile(r'(?P<head>\s[\w:.-]+\s*=\s*)(?P<q>["\'])(?P<value>.*?)(?P=q)', re.DOTALL)

# (바꿀 표기, 확정 표기)
RENAMES = [
    ("아르셰스", "아셰스"),
    ("이온살", "이오나사르"),
]

# 앞말에 받침이 없을 때 쓰는 형태. 긴 것부터 봐야 `이라면` 이 `이` 에 잡아먹히지 않는다.
NO_BATCHIM_FORMS = [
    ("이라면", "라면"), ("이라고", "라고"), ("이라는", "라는"), ("이라도", "라도"),
    ("이란", "란"), ("이랑", "랑"), ("이야", "야"), ("이여", "여"),
    ("으로", "로"), ("은", "는"), ("이", "가"), ("을", "를"), ("과", "와"),
]
BATCHIM_FORMS = {b: a for a, b in NO_BATCHIM_FORMS}


def has_batchim(char):
    if not ("가" <= char <= "힣"):
        return False
    return (ord(char) - 0xAC00) % 28 != 0


def rename(text):
    """이름을 바꾸고, 받침이 달라지면 뒤따르는 조사도 맞춘다."""
    for before, after in RENAMES:
        if before not in text:
            continue
        was = has_batchim(before[-1])
        now = has_batchim(after[-1])
        if was == now:
            text = text.replace(before, after)
            continue
        # 받침 유무가 바뀌었다. 이름 바로 뒤에 오는 조사를 함께 본다.
        forms = NO_BATCHIM_FORMS if not now else [(b, a) for a, b in NO_BATCHIM_FORMS]
        pieces = text.split(before)
        rebuilt = [pieces[0]]
        for tail in pieces[1:]:
            for source, target in forms:
                if tail.startswith(source):
                    tail = target + tail[len(source):]
                    break
            rebuilt.append(tail)
        text = after.join(rebuilt)
    return text


def parse_ebm(data):
    count = int.from_bytes(data[:4], "little")
    position, records = 4, []
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


def main():
    csv.field_size_limit(1 << 30)
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    mapping = json.loads((REPO / "build" / "final_mod_report.json")
                         .read_text(encoding="utf-8"))["hangul_to_standin"]

    def byte_length(text):
        return len("".join(mapping.get(c, c) for c in text).encode("utf-8"))

    totals = Counter()
    edits = {}

    # --- main 실행 파일 문자열 --------------------------------------------
    path = REPO / "translations" / "exefs" / "main_1.0.1.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    for row in rows:
        if not row["translation"]:
            continue
        new = rename(row["translation"])
        if new == row["translation"]:
            continue
        if byte_length(new) > int(row["capacity_bytes"]):
            print(f"  용량 초과로 건너뜀 [main {row['index']}] {new[:60]}")
            totals["skipped"] += 1
            continue
        print(f"  [main {row['index']}] {row['translation'][:70]!r}")
        print(f"        -> {new[:70]!r}")
        edits[row["translation"]] = new
        row["translation"] = new
        totals["main"] += 1
    if totals["main"] and not args.dry_run:
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    # --- 이벤트 대사 EBM --------------------------------------------------
    for translated in sorted((REPO / "translations" / "romfs" / "Event" / "event").rglob("*.ebm")):
        records = parse_ebm(translated.read_bytes())
        dirty = False
        for index, row in enumerate(records):
            new = rename(row[1])
            if new == row[1]:
                continue
            print(f"  [{translated.name}[{index}]] {row[1][:70]!r}")
            print(f"        -> {new[:70]!r}")
            edits[row[1]] = new
            row[1] = new
            dirty = True
            totals["ebm"] += 1
        if dirty and not args.dry_run:
            translated.write_bytes(build_ebm(records))

    # --- Saves XML --------------------------------------------------------
    for translated in sorted((REPO / "translations" / "romfs" / "Saves").rglob("*.xml")):
        text = translated.read_text(encoding="utf-8", newline="")
        state = {"hits": 0}

        def replace(match):
            value = html.unescape(match.group("value"))
            new = rename(value)
            if new == value:
                return match.group(0)
            state["hits"] += 1
            print(f"  [{translated.name}] {value[:70]!r}")
            print(f"        -> {new[:70]!r}")
            edits[value] = new
            quote = match.group("q")
            escaped = (new.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                       .replace(quote, "&quot;" if quote == '"' else "&apos;"))
            return match.group("head") + quote + escaped + quote

        updated = ATTR.sub(replace, text)
        if state["hits"] and not args.dry_run:
            translated.write_text(updated, encoding="utf-8", newline="")
        totals["saves"] += state["hits"]

    # --- 대화 선택지 ------------------------------------------------------
    balloon = REPO / "translations" / "romfs" / "Event" / "balloonsel" / "balloonseldata.json"
    if balloon.is_file():
        groups = json.loads(balloon.read_text(encoding="utf-8"))
        changed = 0
        for group in groups:
            for position, option in enumerate(group):
                new = rename(option)
                if new != option:
                    print(f"  [balloonsel] {option[:70]!r}")
                    print(f"        -> {new[:70]!r}")
                    edits[option] = new
                    group[position] = new
                    changed += 1
        if changed and not args.dry_run:
            balloon.write_text(json.dumps(groups, ensure_ascii=False, indent=1),
                               encoding="utf-8")
        totals["balloonsel"] = changed

    # --- 번역 캐시 --------------------------------------------------------
    for name in ("saves_translation_cache.json", "main_1.0.1_translation_cache.json",
                 "balloonsel_translation_cache.json", "three_line_shortening_cache.json",
                 "main_expand_cache.json"):
        cache_path = REPO / "build" / name
        if not cache_path.is_file():
            continue
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(cache, dict):
            continue
        changed = 0
        for key, value in list(cache.items()):
            if not isinstance(value, str):
                continue
            new = rename(value)
            if new != value:
                cache[key] = new
                changed += 1
        if changed:
            print(f"  캐시 {name}: {changed}건")
            totals["cache"] += changed
            if not args.dry_run:
                cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1),
                                      encoding="utf-8")

    print("\n" + "  ".join(f"{k} {v}" for k, v in totals.items()))
    if args.dry_run:
        print("(dry-run: 파일을 쓰지 않았습니다)")


if __name__ == "__main__":
    main()
