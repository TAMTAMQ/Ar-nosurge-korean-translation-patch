#!/usr/bin/env python3
"""G1T 의 플랫폼 식별 바이트를 PC 용으로 바꾼다.

번역한 UI 텍스처는 스위치 원본 위에서 픽셀을 고쳐 만든 것이라 헤더 0x14 의
플랫폼 바이트가 Switch(0x10) 로 남아 있다. PC 판 원본은 같은 자리가 0x0a 다.
그대로 넣으면 PC 로더에 다른 플랫폼의 텍스처를 주는 셈이므로 이 값을 맞춘다.

크기와 나머지 바이트는 건드리지 않는다. G1T 매직을 확인하고, 이미 목표 값이면
아무것도 하지 않는다.
"""
import argparse
import pathlib
import shutil
import sys

MAGIC = b"GT1G"
PLATFORM_OFFSET = 0x14
PLATFORM = {"pc": 0x0A, "switch": 0x10}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, type=pathlib.Path,
                    help="g1t 파일 또는 폴더")
    ap.add_argument("--output", required=True, type=pathlib.Path,
                    help="결과를 쓸 폴더")
    ap.add_argument("--target", choices=sorted(PLATFORM), default="pc")
    args = ap.parse_args()

    want = PLATFORM[args.target]
    srcs = ([args.input] if args.input.is_file()
            else sorted(p for p in args.input.rglob("*.g1t")))
    if not srcs:
        sys.exit(f"오류: g1t 를 찾지 못했습니다: {args.input}")

    args.output.mkdir(parents=True, exist_ok=True)
    for src in srcs:
        data = bytearray(src.read_bytes())
        if data[:4] != MAGIC:
            sys.exit(f"오류: G1T 매직이 아닙니다: {src}")
        was = data[PLATFORM_OFFSET]
        data[PLATFORM_OFFSET] = want
        dst = args.output / src.name
        dst.write_bytes(bytes(data))
        note = "그대로" if was == want else f"0x{was:02x} -> 0x{want:02x}"
        print(f"{src.name:<16} {len(data):>10}바이트  플랫폼 {note}")


if __name__ == "__main__":
    main()
