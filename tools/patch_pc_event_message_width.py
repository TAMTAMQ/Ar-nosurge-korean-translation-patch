#!/usr/bin/env python3
"""PC판 이벤트 메시지의 런타임 자동 줄바꿈을 20자에서 24자로 확장한다.

ArnosurgeDX.exe의 이벤트 메시지 렌더링 루틴은 XML의 line_char_length/limit_width를
읽은 뒤에도 런타임에서 다시 다음 값을 덮어쓴다.

- float 폭: 기준 스케일 * 20.0
- 줄당 글자 수: 20

20.0 상수는 다른 코드에서도 공유되므로 전역 상수 자체를 바꾸지 않는다. 이벤트
메시지 함수의 mulss 명령만 EXE 안의 기존 24.0 상수를 참조하도록 바꾸고, 같은
함수의 정수 20만 24로 바꾼다.

대상은 현재 프로젝트에서 사용하는 Ar nosurge DX PC 실행 파일 버전이다. 예상
바이트가 다르면 즉시 중단한다.
"""

import argparse
import shutil
import struct
from pathlib import Path

import pefile


# 현재 PC 실행 파일에서 확인한 이벤트 메시지 루틴의 파일 오프셋.
MULSS_FILE_OFFSET = 0x107D67
CHAR_LIMIT_FILE_OFFSET = 0x107D81
# .rdata 안에 이미 존재하는 정렬된 24.0f 상수. 새 섹션/데이터를 추가하지 않는다.
FLOAT24_FILE_OFFSET = 0x5D04DC

OLD_MULSS = bytes.fromhex("F3 0F 59 0D 75 2F 37 00")
OLD_CHAR_LIMIT = bytes.fromhex("BA 14 00 00 00")
NEW_CHAR_LIMIT = bytes.fromhex("BA 18 00 00 00")


def patch_bytes(data: bytearray, exe_path: Path) -> tuple[bytearray, bool]:
    pe = pefile.PE(data=bytes(data), fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase

    if data[FLOAT24_FILE_OFFSET:FLOAT24_FILE_OFFSET + 4] != struct.pack("<f", 24.0):
        raise SystemExit(
            f"{exe_path}: 예상한 24.0f 상수가 0x{FLOAT24_FILE_OFFSET:X}에 없습니다."
        )

    mulss_va = base + pe.get_rva_from_offset(MULSS_FILE_OFFSET)
    next_va = mulss_va + 8
    float24_va = base + pe.get_rva_from_offset(FLOAT24_FILE_OFFSET)
    new_disp = float24_va - next_va
    if not -(1 << 31) <= new_disp < (1 << 31):
        raise SystemExit("24.0f 상수가 RIP-relative disp32 범위를 벗어났습니다.")
    new_mulss = b"\xF3\x0F\x59\x0D" + struct.pack("<i", new_disp)

    current_mulss = bytes(data[MULSS_FILE_OFFSET:MULSS_FILE_OFFSET + 8])
    current_limit = bytes(data[CHAR_LIMIT_FILE_OFFSET:CHAR_LIMIT_FILE_OFFSET + 5])

    changed = False
    if current_mulss == OLD_MULSS:
        data[MULSS_FILE_OFFSET:MULSS_FILE_OFFSET + 8] = new_mulss
        changed = True
    elif current_mulss != new_mulss:
        raise SystemExit(
            f"{exe_path}: 이벤트 폭 mulss 시그니처가 예상과 다릅니다: {current_mulss.hex(' ')}"
        )

    if current_limit == OLD_CHAR_LIMIT:
        data[CHAR_LIMIT_FILE_OFFSET:CHAR_LIMIT_FILE_OFFSET + 5] = NEW_CHAR_LIMIT
        changed = True
    elif current_limit != NEW_CHAR_LIMIT:
        raise SystemExit(
            f"{exe_path}: 이벤트 글자수 시그니처가 예상과 다릅니다: {current_limit.hex(' ')}"
        )

    # 최종 바이트를 다시 검증한다.
    if bytes(data[MULSS_FILE_OFFSET:MULSS_FILE_OFFSET + 8]) != new_mulss:
        raise SystemExit("이벤트 폭 24.0 패치 검증 실패")
    if bytes(data[CHAR_LIMIT_FILE_OFFSET:CHAR_LIMIT_FILE_OFFSET + 5]) != NEW_CHAR_LIMIT:
        raise SystemExit("이벤트 24자 패치 검증 실패")

    return data, changed


def patch_file(exe: Path, output: Path | None = None) -> bool:
    exe = exe.resolve()
    output = (output or exe).resolve()
    data = bytearray(exe.read_bytes())
    data, changed = patch_bytes(data, exe)

    output.parent.mkdir(parents=True, exist_ok=True)
    if output != exe:
        output.write_bytes(data)
    elif changed:
        tmp = output.with_suffix(output.suffix + ".eventwidth.tmp")
        tmp.write_bytes(data)
        shutil.move(str(tmp), str(output))

    print(
        f"이벤트 메시지 런타임 폭: {'20→24 적용' if changed else '이미 24자'} "
        f"({output})"
    )
    return changed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exe", required=True, type=Path)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    patch_file(args.exe, args.output)


if __name__ == "__main__":
    main()
