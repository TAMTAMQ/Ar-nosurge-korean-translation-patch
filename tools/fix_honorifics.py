#!/usr/bin/env python3
"""원문의 호칭에 맞춰 번역의 호칭을 고치고 띄어쓰기를 없앤다.

규칙은 원문이 정한다. さん 은 씨, ちゃん 은 쨩, 君/くん 은 군, 様/さま 는 님이고,
원문에서 이름과 호칭이 붙어 있으므로 번역도 붙여 쓴다.

치환은 한국어가 아니라 원문을 보고 한다. 한 레코드의 원문에 서로 다른 호칭이
섞여 있으면 어느 것을 적용할지 알 수 없으므로 건드리지 않는다.

띄어 쓴 형태(`델타 님`)만 고친다. 붙어 있는 형태는 누님, 형님, 손님, 아저씨,
아가씨 처럼 호칭이 아닌 일반어일 수 있어 손대지 않는다.
"""
import argparse
import csv
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_final_korean_mod import RECORD_HEADER

HONORIFIC = {"さん": "씨", "ちゃん": "쨩", "君": "군", "くん": "군",
             "様": "님", "さま": "님"}
NAME = r"[ァ-ヺー]{2,}"
SPACED = re.compile(r"([가-힣]+)\s+(씨|님|쨩|군)")


def wanted(original):
    """원문에 이름과 함께 쓰인 호칭이 한 종류일 때만 그 한국어 표기를 낸다."""
    found = {HONORIFIC[h] for h in HONORIFIC
             if re.search(NAME + re.escape(h), original)}
    return found.pop() if len(found) == 1 else None


def fix(original, translated):
    target = wanted(original)
    if target is None:
        return translated, 0
    fixed, count = SPACED.subn(lambda m: m.group(1) + target, translated)
    return fixed, count


def records(data, path):
    """EBM 을 (헤더, 텍스트) 목록으로 읽는다."""
    count = int.from_bytes(data[:4], "little")
    out, pos = [], 4
    for index in range(count):
        header = data[pos:pos + RECORD_HEADER]
        length = int.from_bytes(data[pos + RECORD_HEADER:pos + RECORD_HEADER + 4], "little")
        start = pos + RECORD_HEADER + 4
        payload = data[start:start + length]
        if not payload.endswith(b"\x00"):
            raise RuntimeError(f"EBM framing error: {path}:{index}")
        out.append((header, payload[:-1].decode("utf-8")))
        pos = start + length
    if pos != len(data):
        raise RuntimeError(f"EBM trailing bytes: {path}")
    return out


def pack(items, head):
    out = bytearray(head)
    for header, text in items:
        encoded = text.encode("utf-8") + b"\x00"
        out += header + len(encoded).to_bytes(4, "little") + encoded
    return bytes(out)


def main():
    repo = pathlib.Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--original-event", required=True, type=pathlib.Path,
                    help="원본 일본어 EBM 이 있는 event 폴더")
    ap.add_argument("--translated-event", type=pathlib.Path,
                    default=repo / "translations" / "romfs" / "Event" / "event")
    ap.add_argument("--csv", type=pathlib.Path,
                    default=repo / "translations" / "exefs" / "main_1.0.1.csv")
    ap.add_argument("--balloonsel-cache", type=pathlib.Path,
                    default=repo / "build" / "balloonsel_translation_cache.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    samples, total, touched = [], 0, 0

    for translated_path in sorted(args.translated_event.rglob("*.ebm")):
        relative = translated_path.relative_to(args.translated_event)
        original_path = args.original_event.joinpath(*[p.lower() for p in relative.parts])
        if not original_path.is_file():
            continue
        source = records(original_path.read_bytes(), original_path)
        target = records(translated_path.read_bytes(), translated_path)
        if len(source) != len(target):
            continue
        changed = 0
        rebuilt = []
        for (_, japanese), (header, korean) in zip(source, target):
            new, n = fix(japanese, korean)
            if n and len(samples) < 8:
                samples.append((japanese[:20], korean[:24], new[:24]))
            changed += n
            rebuilt.append((header, new))
        if changed and not args.dry_run:
            translated_path.write_bytes(pack(rebuilt, translated_path.read_bytes()[:4]))
        total += changed
        touched += 1 if changed else 0
    print(f"EBM: {touched}파일 {total}건")

    csv.field_size_limit(1 << 30)
    rows = list(csv.DictReader(args.csv.open(encoding="utf-8-sig", newline="")))
    fields = list(rows[0].keys())
    n_csv = 0
    for row in rows:
        if not row["translation"]:
            continue
        new, n = fix(row["original"], row["translation"])
        row["translation"] = new
        n_csv += n
    if not args.dry_run:
        with args.csv.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    print(f"exe CSV: {n_csv}건")

    cache = json.loads(args.balloonsel_cache.read_text(encoding="utf-8"))
    n_sel = 0
    for japanese, korean in list(cache.items()):
        if not isinstance(korean, str):
            continue
        new, n = fix(japanese, korean)
        cache[japanese] = new
        n_sel += n
    if not args.dry_run:
        args.balloonsel_cache.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"선택지: {n_sel}건")

    print(f"\n합계 {total + n_csv + n_sel}건" + ("  (--dry-run, 쓰지 않음)" if args.dry_run else ""))
    for japanese, before, after in samples:
        print(f"  {japanese}\n    {before!r} -> {after!r}")


if __name__ == "__main__":
    main()
