#!/usr/bin/env python3
"""exe 안의 UTF-8 문자열을 대체문자 변환 없이 그대로 바꾼다.

게임 화면에 나오는 글자는 게임이 자기 폰트 아틀라스로 그리므로 한글을 대체
문자(징발한 한자)로 바꿔 넣어야 한다. 하지만 창 제목처럼 **운영체제가 그리는**
문자열은 그 규칙이 반대다. 대체문자를 넣으면 제목 표시줄에 한자가 그대로
보인다. 이런 문자열에는 진짜 한글을 UTF-8 로 써야 한다.

build_pc_main_text_patch.py 와 마찬가지로 앞뒤가 NUL 인 독립 슬롯만 인정하고,
원문이 차지하던 바이트와 종단 NUL 안에서만 쓴다.

주의: 창 제목에는 한글을 쓸 수 없다. 제목 표시 경로가 와이드 문자열을
CP_ACP 로 되돌리는데, 이 패치는 게임 데이터 때문에 ACP 를 932 로 두어야 하고
CP932 에는 한글이 없다. 실제로 넣어 보면 글자 수만큼 '?' 로 치환된다.
ACP 를 65001 로 바꾸면 제목은 한글로 나오지만 CP932 로 저장된 Saves 파일들이
대신 깨진다. 그래서 제목은 원문 그대로 둔다. 이 도구는 ASCII 로만 이루어진
문자열처럼 코드페이지에 상관없이 안전한 경우를 위해 남긴다.
"""
import argparse
import json
import pathlib
import sys


def find_slots(blob, needle):
    hits, start = [], 0
    while True:
        i = blob.find(needle, start)
        if i < 0:
            break
        start = i + 1
        if i > 0 and blob[i - 1] != 0:
            continue
        end = i + len(needle)
        if end >= len(blob) or blob[end] != 0:
            continue
        hits.append(i)
    return hits


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe", required=True, type=pathlib.Path)
    ap.add_argument("--output", required=True, type=pathlib.Path)
    ap.add_argument("--replacements", required=True, type=pathlib.Path,
                    help='[{"original": "...", "replacement": "..."}] 를 담은 JSON')
    args = ap.parse_args()

    data = bytearray(args.exe.read_bytes())
    pairs = json.loads(args.replacements.read_text(encoding="utf-8"))
    total = 0
    for pair in pairs:
        old = pair["original"].encode("utf-8")
        new = pair["replacement"].encode("utf-8")
        hits = find_slots(data, old)
        if not hits:
            sys.exit(f"오류: 독립 슬롯을 찾지 못했습니다: {pair['original']!r}")
        # 원문 자기 영역과 종단 NUL 안에서만 쓴다
        room = len(old) + 1
        if len(new) + 1 > room:
            sys.exit(f"오류: 공간 부족 {len(new) + 1} > {room}: {pair['replacement']!r}")
        for h in hits:
            data[h:h + room] = new.ljust(room, b"\0")
            total += 1
        print(f"{pair['original']!r}\n  -> {pair['replacement']!r}"
              f"  ({len(old)} -> {len(new)} 바이트, 슬롯 {len(hits)}곳)")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(bytes(data))
    print(f"기록: {args.output} (슬롯 {total}곳)")


if __name__ == "__main__":
    main()
