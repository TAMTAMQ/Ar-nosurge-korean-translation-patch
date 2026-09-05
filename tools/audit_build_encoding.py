#!/usr/bin/env python3
"""빌드한 Saves 파일이 원본과 같은 인코딩인지 전수 대조한다.

이 게임의 Saves 데이터는 파일마다 CP932 와 UTF-8 이 섞여 있다. 스위치에는
ANSI 코드페이지 개념이 없어서 어긋나도 드러나지 않지만, PC 판은 이 문자열을
CP_ACP 로 변환하므로 원본과 다른 인코딩으로 쓰면 세 바이트짜리 대체문자가
통째로 깨진다.

실제로 systemMessage/SysMess.xml 이 원본 CP932 인데 UTF-8 로 빌드되어 튜토리얼과
도움말, 미션 문구가 전부 깨졌다. 사람이 눈으로 잡기 어려운 종류의 문제라 빌드가
직접 검사하게 한다. 어긋난 것이 하나라도 있으면 실패로 끝낸다.
"""
import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from decode_saves_xml_e import detect_text_encoding, decode_file

DECL = re.compile(rb'encoding\s*=\s*["\']([\w\-]+)["\']', re.I)


def describe(raw):
    match = DECL.search(raw[:200])
    declared = match.group(1).decode().lower().replace("-", "_") if match else "없음"
    return detect_text_encoding(raw), declared


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--built", required=True, type=pathlib.Path,
                    help="빌드한 Saves 폴더")
    ap.add_argument("--original", required=True, type=pathlib.Path,
                    help="originalText 의 Saves 폴더 (평문 XML)")
    args = ap.parse_args()

    mismatched, matched, skipped = [], 0, []
    for built in sorted(p for p in args.built.rglob("*") if p.is_file()):
        relative = built.relative_to(args.built)
        if relative.suffix == ".e":
            original = args.original / relative.with_suffix("")
            try:
                built_bytes = decode_file(built)
            except Exception as exc:
                skipped.append((relative, f"복호 실패: {exc}"))
                continue
        else:
            original = args.original / relative
            built_bytes = built.read_bytes()
        if not original.is_file():
            skipped.append((relative, "원본 없음"))
            continue
        want = describe(original.read_bytes())
        got = describe(built_bytes)
        if want != got:
            mismatched.append((relative.as_posix(), want, got))
        else:
            matched += 1

    print(f"인코딩 대조: 일치 {matched} / 불일치 {len(mismatched)} / 건너뜀 {len(skipped)}")
    for relative, why in skipped:
        print(f"  건너뜀: {relative}  ({why})")
    if mismatched:
        print("\n원본과 인코딩이 다른 파일:")
        for relative, want, got in mismatched:
            print(f"  {relative}\n    원본 {want[0]}/{want[1]}  ->  빌드 {got[0]}/{got[1]}")
        sys.exit("오류: 인코딩이 어긋난 파일이 있습니다. PC 판에서 글자가 깨집니다.")


if __name__ == "__main__":
    main()
