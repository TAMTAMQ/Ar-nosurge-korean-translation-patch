#!/usr/bin/env python3
"""main NSO 문자열 참조와 재배치 후보 0영역을 읽기 전용으로 분석한다."""

import argparse
import csv
import json
import struct
from pathlib import Path

from build_patched_main import lz4_decompress


SEGMENTS = (("text", 0x10, 0x60), ("rodata", 0x20, 0x64), ("data", 0x30, 0x68))


def load_segments(nso):
    result = []
    for name, header, compressed_header in SEGMENTS:
        file_offset, memory_offset, decompressed_size = struct.unpack_from("<III", nso, header)
        compressed_size = struct.unpack_from("<I", nso, compressed_header)[0]
        raw = bytes(nso[file_offset:file_offset + compressed_size])
        data = lz4_decompress(raw, decompressed_size)
        result.append({"name": name, "file_offset": file_offset,
                       "memory_offset": memory_offset, "data": data})
    return result


def all_offsets(data, needle):
    start = 0
    while True:
        found = data.find(needle, start)
        if found < 0:
            return
        yield found
        start = found + 1


def sign_extend(value, bits):
    sign = 1 << (bits - 1)
    return (value & (sign - 1)) - (value & sign)


def aarch64_string_refs(text_segment, targets):
    data = text_segment["data"]
    base = text_segment["memory_offset"]
    refs = {target: [] for target in targets}
    for offset in range(0, len(data) - 8, 4):
        adrp, add = struct.unpack_from("<II", data, offset)
        if adrp & 0x9F000000 != 0x90000000:
            continue
        rd = adrp & 31
        if add & 0x7F000000 != 0x11000000 or ((add >> 5) & 31) != rd:
            continue
        imm21 = ((adrp >> 5) & 0x7FFFF) << 2 | ((adrp >> 29) & 3)
        instruction_address = base + offset
        page = (instruction_address & ~0xFFF) + (sign_extend(imm21, 21) << 12)
        immediate = (add >> 10) & 0xFFF
        if (add >> 22) & 1:
            immediate <<= 12
        target = page + immediate
        if target in refs:
            refs[target].append({"instruction_address": f"0x{instruction_address:08X}",
                                 "adrp": f"0x{adrp:08X}", "add": f"0x{add:08X}"})
    return refs


def zero_runs(segment, minimum):
    data = segment["data"]
    runs = []
    start = None
    for index, value in enumerate(data + b"\1"):
        if value == 0 and start is None:
            start = index
        elif value != 0 and start is not None:
            size = index - start
            if size >= minimum:
                runs.append({"segment": segment["name"],
                             "memory_address": f'0x{segment["memory_offset"] + start:08X}',
                             "segment_offset": f"0x{start:08X}", "size": size})
            start = None
    return runs


def main():
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main", type=Path, required=True)
    parser.add_argument("--translations", type=Path,
                        default=repo / "translations" / "exefs" / "main_1.0.1.csv")
    parser.add_argument("--patch-report", type=Path,
                        default=repo / "build" / "main_1.0.1_patch_report.json")
    parser.add_argument("--output", type=Path,
                        default=repo / "build" / "main_1.0.1_reference_analysis.json")
    args = parser.parse_args()

    nso = args.main.read_bytes()
    segments = load_segments(nso)
    skipped = json.loads(args.patch_report.read_text(encoding="utf-8"))["skipped"]
    overflow_addresses = {int(item["address"], 16) for item in skipped
                          if item.get("reason") == "overflow"}
    translations = {}
    csv.field_size_limit(1 << 30)
    with args.translations.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            address = int(row["memory_address"], 16)
            if address in overflow_addresses:
                translations[address] = row

    direct = {target: [] for target in overflow_addresses}
    for segment in segments:
        for target in overflow_addresses:
            for width in (8, 4):
                needle = target.to_bytes(width, "little")
                for offset in all_offsets(segment["data"], needle):
                    direct[target].append({"segment": segment["name"], "width": width,
                                           "memory_address": f'0x{segment["memory_offset"] + offset:08X}'})
    code = aarch64_string_refs(next(x for x in segments if x["name"] == "text"),
                               overflow_addresses)
    records = []
    for address in sorted(overflow_addresses):
        row = translations[address]
        records.append({"index": int(row["index"]), "address": f"0x{address:08X}",
                        "original": row["original"], "translation": row["translation"],
                        "direct_pointer_refs": direct[address], "adrp_add_refs": code[address],
                        "reference_count": len(direct[address]) + len(code[address])})
    runs = []
    for segment in segments:
        runs.extend(zero_runs(segment, 64))
    runs.sort(key=lambda item: item["size"], reverse=True)
    report = {"main": str(args.main), "overflow_records": len(records),
              "records_with_reference": sum(x["reference_count"] > 0 for x in records),
              "direct_pointer_records": sum(bool(x["direct_pointer_refs"]) for x in records),
              "adrp_add_records": sum(bool(x["adrp_add_refs"]) for x in records),
              "zero_runs_at_least_64": runs, "records": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"records", "zero_runs_at_least_64"}},
                     ensure_ascii=False, indent=2))
    print("largest zero runs:")
    print(json.dumps(runs[:10], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
