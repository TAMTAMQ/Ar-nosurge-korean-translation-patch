#!/usr/bin/env python3
"""PC판 이벤트 메시지와 메시지 로그의 런타임 자동 줄바꿈을 24자로 확장한다.

ArnosurgeDX.exe는 XML의 line_char_length/limit_width가 24여도 이벤트 대화와
메시지 로그에서 각각 별도 런타임 코드로 다음 값을 다시 20 기준으로 설정한다.

- float 폭: 기준 스케일 * 20.0
- 줄당 글자 수: 20

20.0 상수는 다른 코드에서도 공유되므로 전역 상수 자체를 바꾸지 않는다. 두
텍스트 경로의 mulss 명령만 EXE 안의 기존 24.0 상수를 참조하도록 바꾸고, 각
루틴의 정수 20만 24로 바꾼다.

대상은 현재 프로젝트에서 사용하는 Ar nosurge DX PC 실행 파일 버전이다. 예상
바이트가 다르면 즉시 중단한다.
"""

import argparse
import shutil
import struct
from pathlib import Path

import pefile


# 현재 PC 실행 파일에서 확인한 런타임 텍스트 폭/글자수 루틴의 파일 오프셋.
# message_log 쪽은 msg_text 노드를 순회하는 0x140030ED1 호출에서 진입하는
# 0x1401064F0 함수이며, 이벤트 대화와 별도로 20 기준을 다시 설정한다.
MESSAGE_LOG_MULSS_FILE_OFFSET = 0x105906
MESSAGE_LOG_CHAR_LIMIT_FILE_OFFSET = 0x10592B
EVENT_MULSS_FILE_OFFSET = 0x107D67
EVENT_CHAR_LIMIT_FILE_OFFSET = 0x107D81
# .rdata 안에 이미 존재하는 정렬된 24.0f 상수. 새 섹션/데이터를 추가하지 않는다.
FLOAT24_FILE_OFFSET = 0x5D04DC

OLD_MESSAGE_LOG_MULSS = bytes.fromhex("F3 0F 59 0D D6 53 37 00")
OLD_EVENT_MULSS = bytes.fromhex("F3 0F 59 0D 75 2F 37 00")
OLD_CHAR_LIMIT = bytes.fromhex("BA 14 00 00 00")
NEW_CHAR_LIMIT = bytes.fromhex("BA 18 00 00 00")


def _patch_width_pair(data, pe, exe_path, label, mulss_offset, limit_offset, old_mulss):
    base = pe.OPTIONAL_HEADER.ImageBase
    mulss_va = base + pe.get_rva_from_offset(mulss_offset)
    next_va = mulss_va + 8
    float24_va = base + pe.get_rva_from_offset(FLOAT24_FILE_OFFSET)
    new_disp = float24_va - next_va
    if not -(1 << 31) <= new_disp < (1 << 31):
        raise SystemExit("24.0f 상수가 RIP-relative disp32 범위를 벗어났습니다.")
    new_mulss = b"\xF3\x0F\x59\x0D" + struct.pack("<i", new_disp)

    current_mulss = bytes(data[mulss_offset:mulss_offset + 8])
    current_limit = bytes(data[limit_offset:limit_offset + 5])
    changed = False
    if current_mulss == old_mulss:
        data[mulss_offset:mulss_offset + 8] = new_mulss
        changed = True
    elif current_mulss != new_mulss:
        raise SystemExit(
            f"{exe_path}: {label} 폭 mulss 시그니처가 예상과 다릅니다: {current_mulss.hex(' ')}"
        )

    if current_limit == OLD_CHAR_LIMIT:
        data[limit_offset:limit_offset + 5] = NEW_CHAR_LIMIT
        changed = True
    elif current_limit != NEW_CHAR_LIMIT:
        raise SystemExit(
            f"{exe_path}: {label} 글자수 시그니처가 예상과 다릅니다: {current_limit.hex(' ')}"
        )

    if bytes(data[mulss_offset:mulss_offset + 8]) != new_mulss:
        raise SystemExit(f"{label} 폭 24.0 패치 검증 실패")
    if bytes(data[limit_offset:limit_offset + 5]) != NEW_CHAR_LIMIT:
        raise SystemExit(f"{label} 24자 패치 검증 실패")
    return changed


def patch_bytes(data: bytearray, exe_path: Path) -> tuple[bytearray, bool]:
    pe = pefile.PE(data=bytes(data), fast_load=True)
    if data[FLOAT24_FILE_OFFSET:FLOAT24_FILE_OFFSET + 4] != struct.pack("<f", 24.0):
        raise SystemExit(
            f"{exe_path}: 예상한 24.0f 상수가 0x{FLOAT24_FILE_OFFSET:X}에 없습니다."
        )

    changed = _patch_width_pair(
        data, pe, exe_path, "메시지 로그",
        MESSAGE_LOG_MULSS_FILE_OFFSET, MESSAGE_LOG_CHAR_LIMIT_FILE_OFFSET,
        OLD_MESSAGE_LOG_MULSS,
    )
    changed = _patch_width_pair(
        data, pe, exe_path, "이벤트 메시지",
        EVENT_MULSS_FILE_OFFSET, EVENT_CHAR_LIMIT_FILE_OFFSET,
        OLD_EVENT_MULSS,
    ) or changed
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
        f"이벤트 메시지/로그 런타임 폭: {'20→24 적용' if changed else '이미 24자'} "
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
