#!/usr/bin/env python3
"""고유명사 표기를 원문 기준으로 통일한다. 조사도 받침에 맞춰 함께 고친다.

번역 전에 용어집을 확정하지 않아 표기가 갈렸고, 일부는 서로 다른 인물이 뒤섞였다.

  フェリエ(인물)   -> 펠리온 42줄 / 페리에 29줄   ** 도시 フェリオン 과 혼동 **
  プラム(인물)     -> 프림 6줄 / 프람 5줄         ** 다른 인물 プリム 와 혼동 **
  プランク         -> 프랭크 19 / 플랑크 11 / 플랭크 10 / 프랑크 7
  菩提命王         -> 보대명왕 14 / 보다이메이오 7 / 보디명왕 4

`펠리온` 을 그냥 치환하면 진짜 도시 이름까지 망가진다. 그래서 모든 규칙은
**원문에 해당 일본어가 있을 때만** 발동한다. 원문과 짝지을 수 없는 자리는
건드리지 않는다.

표기를 바꾸면 받침이 달라져 조사가 어긋난다. `펠리온이랑` 은 `펠리에랑`,
`보다이메이오는` 은 `보리명왕은` 이 되어야 한다.
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

# jp        원문에 이게 있을 때만 발동한다
# not_jp    원문에 이게 같이 있으면 건드리지 않는다 (두 인물이 한 줄에 나오는 경우)
# sources   바꿀 표기들
# target    확정 표기
RULES = [
    {"jp": "フェリエ", "not_jp": "フェリオン",
     "sources": ["펠리온", "페리에"], "target": "펠리에"},
    {"jp": "プラム", "not_jp": "プリム",
     "sources": ["프림", "플럼"], "target": "프람"},
    {"jp": "プランク", "not_jp": None,
     "sources": ["프랭크", "플랑크", "프랑크"], "target": "플랭크"},
    {"jp": "菩提命王", "not_jp": None,
     "sources": ["보대명왕", "보다이메이오", "보데이메이오", "보디명왕",
                 "보티메이오우", "보제명왕"],
     "target": "보리명왕"},
    # 두 번째 판. 전수 조사에서 더 나온 변형들이다. `아르 시엘` 처럼 아예 다른
    # 이름이 된 것도 있어서, 표기 흔들림이 아니라 오역이다.
    {"jp": "アーシェス", "not_jp": None,
     "sources": ["아르 시엘", "아르시엘", "아르셰스", "아스헤스"], "target": "아셰스"},
    # イオナサル(본명) 과 イオン(애칭) 은 같은 인물이다 - "イオンって呼んでね".
    # 둘이 같이 나오는 줄은 원문이 두 이름을 구분해 쓰고 있으므로 건드리지 않는다.
    {"jp": "イオナサル", "not_jp": "イオン",
     "sources": ["이오나사루", "이온살", "이온사르", "이온"], "target": "이오나사르"},
    {"jp": "プラム", "not_jp": "プリム",
     "sources": ["프룸"], "target": "프람"},
    {"jp": "カノイール", "not_jp": None,
     "sources": ["카누아르"], "target": "카노일"},
    {"jp": "ジェノメトリクス", "not_jp": None,
     "sources": ["제노메트리카"], "target": "제노메트릭스"},
]

# 받침이 없을 때 쓰는 형태. 긴 것부터 봐야 `이랑` 이 `이` 에 잡아먹히지 않는다.
NO_BATCHIM_FORMS = [
    ("이라면", "라면"), ("이라고", "라고"), ("이라는", "라는"), ("이라도", "라도"),
    ("이었", "였"), ("이에요", "예요"), ("이었다", "였다"),
    ("이란", "란"), ("이랑", "랑"), ("이야", "야"), ("이여", "여"),
    ("으로", "로"), ("은", "는"), ("이", "가"), ("을", "를"), ("과", "와"),
]


def has_batchim(char):
    if not ("가" <= char <= "힣"):
        return False
    return (ord(char) - 0xAC00) % 28 != 0


def swap(text, source, target):
    """표기를 바꾸고, 받침 유무가 달라지면 뒤따르는 조사도 맞춘다."""
    if source not in text:
        return text
    was, now = has_batchim(source[-1]), has_batchim(target[-1])
    if was == now:
        return text.replace(source, target)
    forms = NO_BATCHIM_FORMS if not now else [(b, a) for a, b in NO_BATCHIM_FORMS]
    pieces = text.split(source)
    rebuilt = [pieces[0]]
    for tail in pieces[1:]:
        for a, b in forms:
            if tail.startswith(a):
                tail = b + tail[len(a):]
                break
        rebuilt.append(tail)
    return target.join(rebuilt)


def unify(japanese, korean):
    text = korean
    for rule in RULES:
        if rule["jp"] not in japanese:
            continue
        if rule["not_jp"] and rule["not_jp"] in japanese:
            continue
        for source in rule["sources"]:
            if source == rule["target"]:
                continue
            text = swap(text, source, rule["target"])
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
    edits = {}

    # --- main 실행 파일 문자열 --------------------------------------------
    path = REPO / "translations" / "exefs" / "main_1.0.1.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    for row in rows:
        if not row["translation"]:
            continue
        new = unify(row["original"], row["translation"])
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
            new = unify(japanese, row[1])
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
            new = unify(source_value, value)
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
    original_path = REPO / "originalText" / "romfs" / "Event" / "balloonsel" / "balloonseldata.json"
    translated_path = REPO / "translations" / "romfs" / "Event" / "balloonsel" / "balloonseldata.json"
    if original_path.is_file() and translated_path.is_file():
        originals = json.loads(original_path.read_text(encoding="utf-8"))
        groups = json.loads(translated_path.read_text(encoding="utf-8"))
        changed = 0
        for source_group, group in zip(originals, groups):
            for position, (japanese, korean) in enumerate(zip(source_group, group)):
                new = unify(japanese, korean)
                if new != korean:
                    print(f"  [balloonsel] {korean[:70]!r}")
                    print(f"        -> {new[:70]!r}")
                    edits[korean] = new
                    group[position] = new
                    changed += 1
        if changed and not args.dry_run:
            translated_path.write_text(json.dumps(groups, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
        totals["balloonsel"] = changed

    # --- 번역 캐시 --------------------------------------------------------
    # 파일만 고치면 다음 빌드에서 되돌아간다.
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
