#!/usr/bin/env python3
"""main 1.0.1 번역 CSV에서 안전한 고정 길이 IPS 패치를 생성한다."""

import argparse
import csv
import json
import struct
import sys
from pathlib import Path

from build_exefs_ui_patch import BUILD_ID, PATCHES
from build_patched_main import lz4_decompress
from inline_tail_fix import build_text_patches


def encode(text, mapping):
    missing = sorted({ch for ch in text if "가" <= ch <= "힣" and ch not in mapping})
    if missing:
        raise ValueError(f"폰트 매핑에 없는 한글: {''.join(missing)}")
    return "".join(mapping.get(ch, ch) for ch in text).encode("utf-8")


def main():
    csv.field_size_limit(1 << 30)
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translations", type=Path,
                        default=repo / "translations" / "exefs" / "main_1.0.1.csv")
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--main", type=Path,
                        help="원본 exefs/main. 지정하면 컴파일러가 .text에 인라인해 둔 "
                             "짧은 문자열의 꼬리 바이트까지 함께 패치한다.")
    parser.add_argument("--report", type=Path,
                        default=repo / "build" / "main_1.0.1_patch_report.json")
    args = parser.parse_args()

    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))["hangul_to_standin"]
    accepted = {}
    skipped = []
    with args.translations.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["status"] != "needs_review" or not row["translation"]:
                continue
            address = int(row["memory_address"], 16)
            capacity = int(row["capacity_bytes"])
            try:
                payload = encode(row["translation"], mapping)
            except ValueError as exc:
                skipped.append({"index": int(row["index"]), "address": row["memory_address"],
                                "reason": str(exc)})
                continue
            if len(payload) > capacity:
                skipped.append({"index": int(row["index"]), "address": row["memory_address"],
                                "capacity": capacity, "translated_bytes": len(payload),
                                "reason": "overflow", "original": row["original"],
                                "translation": row["translation"]})
                continue
            accepted[address] = payload.ljust(capacity, b"\0")

    # 기존에 게임에서 확인한 UI 번역은 모델 초안보다 우선한다.
    for address, capacity, translated in PATCHES:
        payload = encode(translated, mapping)
        if len(payload) > capacity:
            raise SystemExit(f"검증 UI 문자열 공간 초과: {translated}")
        accepted[address] = payload.ljust(capacity, b" ")

    # Short strings are constructed inline: the compiler loads only the first
    # 8 bytes from .rodata and bakes the remaining bytes (and the SSO length)
    # into MOV/MOVK immediates. Those immediates have to be patched too, or the
    # tail of every such string stays Japanese. See inline_tail_fix.
    text_patches = {}
    if args.main:
        nso = args.main.read_bytes()
        segments = {}
        for name, header, compressed_header in (("text", 0x10, 0x60), ("rodata", 0x20, 0x64)):
            file_offset, memory_offset, decompressed_size = struct.unpack_from("<III", nso, header)
            compressed_size = struct.unpack_from("<I", nso, compressed_header)[0]
            data = lz4_decompress(bytes(nso[file_offset:file_offset + compressed_size]),
                                  decompressed_size)
            segments[name] = (memory_offset, data)
        text_base, text_data = segments["text"]
        rodata_base, rodata_data = segments["rodata"]
        text_patches = build_text_patches(
            text_data, text_base, rodata_data, rodata_base,
            [(address, payload) for address, payload in accepted.items()
             if rodata_base <= address < rodata_base + len(rodata_data)])

    ips = bytearray(b"PATCH")
    combined = {address: payload for address, payload in accepted.items()}
    for address, word in text_patches.items():
        combined[address] = struct.pack("<I", word)
    for address, payload in sorted(combined.items()):
        ips += (address + 0x100).to_bytes(3, "big")
        ips += len(payload).to_bytes(2, "big")
        ips += payload
    ips += b"EOF"

    output = args.output / "exefs_patches" / "ArNosurgeKoreanUI" / f"{BUILD_ID}.ips"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(ips)
    report = {
        "build_id": BUILD_ID,
        "patched_records": len(accepted),
        "inlined_tail_instructions_patched": len(text_patches),
        "skipped_records": len(skipped),
        "skipped": skipped,
        "output": str(output),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "skipped"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
