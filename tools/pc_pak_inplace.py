#!/usr/bin/env python3
"""PC판 PAK 안의 파일을 크기가 같을 때 제자리에서 교체한다.

PACK00_01 은 1.4GB 라서 폰트 한 개 때문에 통째로 재포장하는 것은 비싸다.
교체본이 원본과 바이트 수가 같으면 인덱스의 오프셋·크기가 그대로이므로
해당 구간만 덮어쓰면 된다. 크기가 다르면 재포장해야 하므로 거부한다.

오프셋은 gust_pak -l 로 확인한 값을 넘긴다.
"""
import argparse
import hashlib
import pathlib
import sys


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pak", required=True, type=pathlib.Path)
    ap.add_argument("--offset", required=True,
                    help="PAK 안에서의 파일 시작 오프셋 (0x... 또는 10진수)")
    ap.add_argument("--replacement", required=True, type=pathlib.Path)
    ap.add_argument("--expect-sha256",
                    help="덮어쓰기 전 그 자리에 있어야 할 원본의 sha256. "
                         "엉뚱한 오프셋에 쓰는 사고를 막는다.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    off = int(args.offset, 0)
    new = args.replacement.read_bytes()

    with open(args.pak, "r+b") as f:
        f.seek(off)
        cur = f.read(len(new))
        if len(cur) != len(new):
            sys.exit(f"오류: PAK 끝을 넘어선다. offset={off:#x} size={len(new)}")

        print(f"PAK        : {args.pak}")
        print(f"오프셋     : {off:#x}")
        print(f"현재 sha256: {sha(cur)}")
        print(f"교체 sha256: {sha(new)}")

        if args.expect_sha256 and sha(cur) != args.expect_sha256:
            sys.exit("오류: 그 자리의 원본 해시가 기대값과 다릅니다. "
                     "오프셋이 틀렸거나 이미 교체된 PAK 입니다.\n"
                     f"      기대: {args.expect_sha256}\n"
                     f"      실제: {sha(cur)}")

        if cur == new:
            print("=> 이미 동일한 내용입니다. 아무것도 하지 않습니다.")
            return
        if args.dry_run:
            print("=> --dry-run 이므로 쓰지 않았습니다.")
            return

        f.seek(off)
        f.write(new)
        f.flush()

    with open(args.pak, "rb") as f:
        f.seek(off)
        back = f.read(len(new))
    if back != new:
        sys.exit("오류: 되읽기 검증 실패. PAK 가 손상되었을 수 있습니다.")
    print(f"=> {len(new)} 바이트 기록 완료, 되읽기 검증 통과")


if __name__ == "__main__":
    main()
