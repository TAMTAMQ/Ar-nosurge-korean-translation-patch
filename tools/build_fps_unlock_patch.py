#!/usr/bin/env python3
"""30FPS 제한을 해제하는 IPS 패치를 생성한다.

게임은 프레임 대기 값을 레지스터로 넘겨 호출한다.

    0x3D07CC   mov  w1, w21     ; 대기 프레임 수(=1, 즉 30FPS)
    0x3D07D0   blr  x8          ; 프레임 대기 호출

여기서 ``w1`` 을 0으로 만들면 대기가 사라져 60FPS로 동작한다.
명령어 한 개(정확히는 1바이트)만 바꾸면 되므로 런타임 후킹이 필요 없다.

원리 확인에는 DeathChaos25의 영문 패치를 참고했다. 해당 패치는 Skyline
플러그인으로 같은 지점을 후킹하지만, 그 플러그인에는 영문 UI 치환 훅이
함께 들어 있어 한국어 패치와 함께 쓰기에 적합하지 않다. 이 도구는 동일한
결과를 내는 최소 IPS 패치만 생성한다.
"""

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


BUILD_ID = "28F3C3965CEB60AC18A23E2B2C0C4BEEE3C81D8B"

# NSO가 메모리에 적재된 뒤의 오프셋과, 그 자리의 원본/변경 명령어.
TARGET = 0x3D07CC
ORIGINAL = struct.pack("<I", 0x2A1503E1)   # mov w1, w21
PATCHED = struct.pack("<I", 0x2A1F03E1)    # mov w1, wzr


def verify(main_path: Path) -> None:
    """사용자가 추출한 main에서 대상 명령어가 실제로 그대로인지 확인한다."""
    # 저장소의 순수 파이썬 구현을 쓴다. lz4 패키지를 따로 설치하지 않아도
    # 빌드가 돌아가야 하기 때문이다.
    from build_patched_main import lz4_decompress

    data = main_path.read_bytes()
    if data[:4] != b"NSO0":
        raise SystemExit(f"NSO 파일이 아닙니다: {main_path}")
    flags = struct.unpack_from("<I", data, 0x0C)[0]
    text_off, _, text_size = struct.unpack_from("<III", data, 0x10)
    text_csize = struct.unpack_from("<I", data, 0x60)[0]
    raw = data[text_off:text_off + (text_csize if flags & 1 else text_size)]
    text = lz4_decompress(bytes(raw), text_size) if flags & 1 else raw

    found = text[TARGET:TARGET + 4]
    if found != ORIGINAL:
        raise SystemExit(
            f"대상 명령어가 예상과 다릅니다. 게임 버전이 1.0.1이 맞는지 확인하세요.\n"
            f"  기대: {ORIGINAL.hex()}  실제: {found.hex()}"
        )
    print(f"검증 통과: 0x{TARGET:X} = mov w1, w21")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--main", type=Path,
                        help="원본 exefs/main 경로(지정 시 대상 명령어를 검증)")
    args = parser.parse_args()

    if args.main:
        verify(args.main)

    diff = [i for i in range(4) if ORIGINAL[i] != PATCHED[i]]
    records = bytearray(b"PATCH")
    for i in diff:
        # Atmosphere/Ryujinx IPS의 NSO 오프셋에는 0x100바이트 헤더가 포함된다.
        records += (TARGET + i + 0x100).to_bytes(3, "big")
        records += (1).to_bytes(2, "big")
        records += bytes([PATCHED[i]])
    records += b"EOF"

    output = args.output / "exefs_patches" / "ArNosurgeFpsUnlock" / f"{BUILD_ID}.ips"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(records)
    print(f"60FPS IPS 생성: {output}")
    print(f"변경 바이트: {len(diff)}개 (mov w1, w21 -> mov w1, wzr)")


if __name__ == "__main__":
    main()
