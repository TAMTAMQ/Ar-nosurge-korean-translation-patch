#!/usr/bin/env python3
"""사용자가 추출한 1.0.1 main NSO의 동적 UI 문자열을 로컬에서 패치한다."""

import argparse
import hashlib
import json
import struct
from pathlib import Path

from build_exefs_ui_patch import BUILD_ID, PATCHES


def lz4_decompress(src, expected):
    out = bytearray()
    i = 0
    while i < len(src):
        token = src[i]
        i += 1
        length = token >> 4
        if length == 15:
            while src[i] == 255:
                length += 255
                i += 1
            length += src[i]
            i += 1
        out.extend(src[i:i + length])
        i += length
        if i >= len(src):
            break
        offset = src[i] | src[i + 1] << 8
        i += 2
        length = token & 15
        if length == 15:
            while src[i] == 255:
                length += 255
                i += 1
            length += src[i]
            i += 1
        length += 4
        start = len(out) - offset
        for j in range(length):
            out.append(out[start + j])
    if len(out) != expected:
        raise ValueError(f"LZ4 크기 불일치: {len(out)} != {expected}")
    return bytes(out)


def lz4_literal(data):
    """압축률보다 호환성을 우선한 유효한 raw LZ4 리터럴 블록."""
    size = len(data)
    out = bytearray([0xF0])
    remaining = size - 15
    while remaining >= 255:
        out.append(255)
        remaining -= 255
    out.append(remaining)
    out.extend(data)
    return bytes(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main", type=Path, required=True, help="정품 업데이트 1.0.1에서 추출한 main")
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    nso = bytearray(args.main.read_bytes())
    actual_build_id = bytes(nso[0x40:0x54]).hex().upper()
    if actual_build_id != BUILD_ID:
        raise SystemExit(f"지원하지 않는 main Build ID: {actual_build_id} (필요: {BUILD_ID})")

    ro_file, ro_mem, ro_size = struct.unpack_from("<III", nso, 0x20)
    data_file = struct.unpack_from("<I", nso, 0x30)[0]
    ro_compressed = struct.unpack_from("<I", nso, 0x64)[0]
    rodata = bytearray(lz4_decompress(nso[ro_file:ro_file + ro_compressed], ro_size))
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))["hangul_to_standin"]

    for address, capacity, translated in PATCHES:
        encoded = "".join(mapping.get(char, char) for char in translated).encode("utf-8")
        if len(encoded) > capacity:
            raise SystemExit(f"문자열 공간 초과: {translated}")
        start = address - ro_mem
        rodata[start:start + capacity] = encoded.ljust(capacity, b" ")

    new_ro = lz4_literal(rodata)
    tail = bytes(nso[data_file:])
    rebuilt = bytearray(nso[:ro_file])
    rebuilt.extend(new_ro)
    new_data_file = len(rebuilt)
    rebuilt.extend(tail)
    struct.pack_into("<I", rebuilt, 0x30, new_data_file)
    struct.pack_into("<I", rebuilt, 0x64, len(new_ro))
    rebuilt[0xC0:0xE0] = hashlib.sha256(rodata).digest()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rebuilt)
    print(f"패치 main 생성: {args.output}")
    print(f"Build ID: {actual_build_id}, 문자열: {len(PATCHES)}개")


if __name__ == "__main__":
    main()
