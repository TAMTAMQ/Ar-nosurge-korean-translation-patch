#!/usr/bin/env python3
"""업데이트 main NSO의 .rodata에서 일본어 UTF-8 문자열을 추출한다."""

import argparse
import csv
import json
import re
import struct
from pathlib import Path

from build_exefs_ui_patch import BUILD_ID
from build_patched_main import lz4_decompress


JAPANESE = re.compile(r"[ぁ-んァ-ヶ一-龯々〆ヵヶ]")
KANA = re.compile(r"[ぁ-んァ-ヶ]")


def parse_args():
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main", type=Path, required=True,
                        help="정품 업데이트 1.0.1에서 추출한 main NSO")
    parser.add_argument("--output", type=Path,
                        default=repo / "originalText" / "exefs",
                        help="JSON/CSV 출력 폴더")
    return parser.parse_args()


def classify(text):
    if KANA.search(text):
        return "text"
    if len(text) >= 2:
        return "kanji_only"
    return "single_kanji"


def main():
    args = parse_args()
    nso = args.main.read_bytes()
    if len(nso) < 0x100 or nso[:4] != b"NSO0":
        raise SystemExit(f"유효한 NSO main이 아닙니다: {args.main}")

    actual_build_id = nso[0x40:0x54].hex().upper()
    if actual_build_id != BUILD_ID:
        raise SystemExit(
            f"지원하지 않는 Build ID: {actual_build_id} (필요: {BUILD_ID})"
        )

    ro_file, ro_memory, ro_size = struct.unpack_from("<III", nso, 0x20)
    ro_compressed_size = struct.unpack_from("<I", nso, 0x64)[0]
    rodata = lz4_decompress(
        nso[ro_file:ro_file + ro_compressed_size], ro_size
    )

    records = []
    position = 0
    while position < len(rodata):
        end = rodata.find(b"\x00", position)
        if end < 0:
            break
        raw = rodata[position:end]
        if raw:
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = ""
            if text and JAPANESE.search(text):
                records.append({
                    "index": len(records) + 1,
                    "memory_address": f"0x{ro_memory + position:08X}",
                    "rodata_offset": f"0x{position:08X}",
                    "capacity_bytes": len(raw),
                    "classification": classify(text),
                    "original": text,
                    "translation": "",
                    "status": "pending",
                    "notes": "",
                })
        position = end + 1

    args.output.mkdir(parents=True, exist_ok=True)
    json_path = args.output / "main_1.0.1_japanese.json"
    csv_path = args.output / "main_1.0.1_japanese.csv"
    metadata = {
        "build_id": actual_build_id,
        "source_name": args.main.name,
        "rodata_memory_address": f"0x{ro_memory:08X}",
        "rodata_size": len(rodata),
        "record_count": len(records),
        "records": records,
    }
    json_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)

    counts = {}
    for record in records:
        key = record["classification"]
        counts[key] = counts.get(key, 0) + 1
    print(f"Build ID: {actual_build_id}")
    print(f".rodata: 0x{ro_memory:08X}, {len(rodata)} bytes")
    print(f"추출 문자열: {len(records)}개 {counts}")
    print(f"JSON: {json_path}")
    print(f"CSV:  {csv_path}")


if __name__ == "__main__":
    main()
