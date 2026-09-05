#!/usr/bin/env python3
"""번역에서 한글로 옮겨진 라틴 문자를 원문 표기로 되돌린다.

철칙: 일본어가 아닌 문자는 원문 그대로 둔다. 휨노스 시 구절이나 제품명처럼
원문이 라틴 문자로 쓴 것은 번역 대상이 아니다. 모델이 음역하거나 의역해 버린
곳을 원문 표기로 되돌린다.

교체는 (원문에 그 라틴 문자열이 있을 때만) 적용한다. 한국어만 보고 바꾸면
엉뚱한 곳까지 건드린다.
"""
import argparse
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fix_honorifics import records, pack

# (원문에 있어야 하는 라틴, 번역에서 찾을 문자열, 되돌릴 문자열)
RULES = [
    # 휨노스 시 구절. 원문이 라틴이므로 음역하면 안 된다.
    ("em-pyei-n vari-fen jang;", "엠페이언 바리펜 장", "em-pyei-n vari-fen jang;"),
    ("em-pyei-n vari-fen jang;", "엠피엔 바리펜 장;", "em-pyei-n vari-fen jang;"),
    # 원문이 라틴으로 쓴 낱말. 게임은 전각 영문을 쓰므로 전각 그대로 되돌린다.
    ("MOE", "내 취향인 작품", "내가 MOE하는 작품"),
    # 슬롯이 33바이트라 "수가"를 "수"로 줄여 맞춘다.
    ("Ｈｉｔ", "타수가 많은", "Ｈｉｔ수 많은"),
    ("ＷＥＢ", "공식 웹 등에서", "공식 ＷＥＢ 등에서"),
    ("ＨＵＧ", "허그해 허니", "ＨＵＧ해 허니"),
    # 슬롯이 원문과 같은 29바이트라 "신록의 대지"의 공백을 뺀다. 라틴 부분을
    # 원문대로 되돌리는 것이 우선이다.
    ("for Arnosurge", "신록의 대지 (Ar nosurge)", "신록의대지 for Arnosurge"),
    ("Style", "오리카 스타일", "오리카Style"),
    # 철자가 망가진 것
    # 슬롯이 원문과 같은 24바이트라 공백을 뺀다.
    ("ＰＬＡＳＭＡ", "ＰＬＡＳＭ 본부", "ＰＬＡＳＭＡ본부"),
    ("ＴｘＢＩＯＳ", "ＴｘＢＯＩＳ", "ＴｘＢＩＯＳ"),
]


def apply(japanese, korean):
    changed = 0
    for needs, before, after in RULES:
        if needs in japanese and before in korean:
            korean = korean.replace(before, after)
            changed += 1
    return korean, changed


def main():
    repo = pathlib.Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--original-event", required=True, type=pathlib.Path)
    ap.add_argument("--translated-event", type=pathlib.Path,
                    default=repo / "translations" / "romfs" / "Event" / "event")
    ap.add_argument("--csv", type=pathlib.Path,
                    default=repo / "translations" / "exefs" / "main_1.0.1.csv")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    total = 0
    for translated_path in sorted(args.translated_event.rglob("*.ebm")):
        relative = translated_path.relative_to(args.translated_event)
        original_path = args.original_event.joinpath(*[p.lower() for p in relative.parts])
        if not original_path.is_file():
            continue
        source = records(original_path.read_bytes(), original_path)
        target = records(translated_path.read_bytes(), translated_path)
        if len(source) != len(target):
            continue
        rebuilt, changed = [], 0
        for (_, japanese), (header, korean) in zip(source, target):
            new, n = apply(japanese, korean)
            if n:
                print(f"  EBM {relative.name}: {korean[:26]!r} -> {new[:26]!r}")
            changed += n
            rebuilt.append((header, new))
        if changed and not args.dry_run:
            translated_path.write_bytes(pack(rebuilt, translated_path.read_bytes()[:4]))
        total += changed

    csv.field_size_limit(1 << 30)
    rows = list(csv.DictReader(args.csv.open(encoding="utf-8-sig", newline="")))
    fields = list(rows[0].keys())
    for row in rows:
        if not row["translation"]:
            continue
        new, n = apply(row["original"], row["translation"])
        if n:
            print(f"  exe#{row['index']}: {row['translation'][:26]!r} -> {new[:26]!r}")
            # 실행 파일은 고정 슬롯이라 늘어나면 안 된다.
            if len(new.encode("utf-8")) > len(row["original"].encode("utf-8")):
                sys.exit(f"오류: exe#{row['index']} 가 원문보다 길어집니다.")
            row["translation"] = new
        total += n
    if not args.dry_run:
        with args.csv.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    print(f"\n합계 {total}건" + ("  (--dry-run)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
