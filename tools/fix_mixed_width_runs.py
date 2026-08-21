#!/usr/bin/env python3
"""전각과 반각이 한 토큰 안에 섞인 영숫자 덩어리를 원문 표기로 되돌린다.

전각 영숫자 복원을 문자 단위로 돌린 탓에 두 가지가 망가졌다.

  삽입     Ｌｖ６  ->  Ｌlｖ６   (없던 l 이 끼어들었다)
  부분치환  ＲＮＡ  ->  RＮＡ    (앞 글자만 반각으로 남았다)

고치는 방법은 하나뿐이다 - 원문에서 같은 토큰을 찾아 그 표기를 그대로 쓴다.
번역문의 덩어리를 반각 대문자로 정규화한 뒤 원문 덩어리 중 같은 것을 찾는다.
바로 안 맞으면 글자 하나를 빼 보고 다시 맞춘다(삽입 사례). 그래도 못 찾는 소수는
MANUAL 표에 원문을 확인해 손으로 적어 두었다.

원문에 없는 덩어리(번역이 새로 만든 표기)는 건드리지 않는다.
"""

import argparse
import csv
import html
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RECORD_HEADER = 32
ATTR = re.compile(r'(?P<head>\s[\w:.-]+\s*=\s*)(?P<q>["\'])(?P<value>.*?)(?P=q)', re.DOTALL)
ALNUM_RUN = re.compile(r"[0-9A-Za-z０-９Ａ-Ｚａ-ｚ]{2,}")

# 원문에 대응 토큰이 없어 자동으로 못 맞추는 것들. 원문을 직접 확인하고 적었다.
# (번역에 나온 덩어리, 원문에서 확인한 올바른 표기, 원문에 있어야 하는 표식)
MANUAL = [
    # ＴＣ２１五十八極管 - ＴＣ２１ 은 원문 그대로, 五十八 은 주위에 맞춰 전각으로.
    ("ＴC２１58", "ＴＣ２１５８", "ＴＣ２１"),
    # （１ＷＡＶＥ最大９体） - 원문은 전부 전각.
    ("ＷＡＶE", "ＷＡＶＥ", "ＷＡＶＥ"),
    # ２次元 -> ２Ｄ. ２ 는 원문에서 온 전각이므로 Ｄ 도 전각으로 맞춘다.
    ("２D", "２Ｄ", "２次元"),
    # 約１０メートル -> 약 １０ｍ. １０ 은 원문 전각.
    ("１０m", "１０ｍ", "１０メートル"),
    # にゅーＦＯ - 알파벳 O 이지 숫자 0 이 아니다.
    ("Ｆ0", "ＦＯ", "ＦＯ"),
]

# ＷＡＶE -> ＷＡＶＥ 로 되돌리면 두 곳에서 4바이트가 늘어 슬롯을 넘긴다. 이 줄은
# 애초에 여유가 0 이었고 "수있는범위" 처럼 공백까지 눌러 담은 상태였다. 원문을 다시
# 보고 문장을 줄여 되돌릴 자리를 만든다.
OVERRIDES = {
    "5790": "<CLEG>・시마법 발동<CLNR><CR>히로인의 시마법으로 ＷＡＶＥ째로 적을 일소합니다."
            " 붉게 표시된 ＷＡＶＥ가 일소할 수 있는 범위입니다.",
    # シャールＡ・Ｌｖ１ - ・ 가 이름 앞으로 밀리고 그 자리에 _ 가 들어가 있었다.
    # 같은 계열의 다른 줄(2836 이후)은 샤르Ａ・Ｌｖ２ 로 제대로 되어 있다.
    "2832": "샤르Ａ・Ｌｖ１",
    "2833": "샤르Ｂ・Ｌｖ１",
    "2834": "샤르Ｃ・Ｌｖ１",
}

# 캐시에만 남은 옛 번역. 키가 주소·해시라 원문과 짝지을 수 없어 직접 적는다.
CACHE_FIXES = {
    "샤르C·Lｖ3": "샤르Ｃ・Ｌｖ３",
}


def to_key(text):
    """반각 대문자로 정규화한다. 폭과 대소문자를 무시하고 같은 토큰인지 보려는 것."""
    return unicodedata.normalize("NFKC", text).upper()


def is_fullwidth(char):
    return unicodedata.east_asian_width(char) in ("F", "W")


def mixed_runs(text):
    return [m.group(0) for m in ALNUM_RUN.finditer(text)
            if len({is_fullwidth(c) for c in m.group(0)}) > 1]


def resolve(run, japanese):
    """번역의 덩어리 run 을 원문 표기로 되돌린다. 못 찾으면 None."""
    candidates = {}
    for match in ALNUM_RUN.finditer(japanese):
        candidates.setdefault(to_key(match.group(0)), match.group(0))

    key = to_key(run)
    if key in candidates:
        found = candidates[key]
        return None if found == run else found

    # 삽입 사례: 글자 하나를 빼면 원문 토큰과 같아지는가.
    for index in range(len(run)):
        shortened = to_key(run[:index] + run[index + 1:])
        if shortened in candidates:
            return candidates[shortened]
    return None


def fix(japanese, korean):
    text = korean
    for run in mixed_runs(text):
        correct = resolve(run, japanese)
        if correct:
            text = text.replace(run, correct)
    for run, correct, marker in MANUAL:
        if run in text and marker in japanese:
            text = text.replace(run, correct)
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


def read_original_xml(path):
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp932")


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
    edits = {}          # 캐시도 같이 고치기 위해 (기존 번역 -> 새 번역) 을 모은다

    # --- main 실행 파일 문자열 --------------------------------------------
    path = REPO / "translations" / "exefs" / "main_1.0.1.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    for row in rows:
        if not row["translation"]:
            continue
        new = OVERRIDES.get(row["index"]) or fix(row["original"], row["translation"])
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
        relative = translated.relative_to(REPO / "translations").as_posix()
        source = REPO / "originalText" / relative.replace("romfs/Event", "romfs/EVENT")
        if not source.is_file():
            continue
        originals = parse_ebm(source.read_bytes())
        records = parse_ebm(translated.read_bytes())
        dirty = False
        for index, ((_, japanese), row) in enumerate(zip(originals, records)):
            new = fix(japanese, row[1])
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
    root = REPO / "translations" / "romfs" / "Saves"
    origin = REPO / "originalText" / "romfs" / "Saves"
    for translated in sorted(root.rglob("*.xml")):
        source = origin / translated.relative_to(root)
        if not source.is_file():
            continue
        japanese = [html.unescape(m.group("value"))
                    for m in ATTR.finditer(read_original_xml(source))]
        text = translated.read_text(encoding="utf-8", newline="")
        state = {"index": 0, "hits": 0}

        def replace(match):
            value = html.unescape(match.group("value"))
            source_value = japanese[state["index"]] if state["index"] < len(japanese) else ""
            state["index"] += 1
            new = fix(source_value, value)
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

    # --- 번역 캐시 --------------------------------------------------------
    # 파일만 고치고 캐시를 두면 다음 빌드에서 되돌아간다.
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
            new = value
            for before, after in edits.items():
                if before and before in new:
                    new = new.replace(before, after)
            new = CACHE_FIXES.get(new, new)
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
