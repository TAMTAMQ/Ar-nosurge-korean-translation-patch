#!/usr/bin/env python3
"""포인터 재배치 IPS의 문자열 풀과 모든 참조 대상을 검증한다."""

import argparse
import json
import struct
from pathlib import Path


def parse_ips(path):
    data = path.read_bytes()
    if not data.startswith(b"PATCH") or not data.endswith(b"EOF"):
        raise ValueError("IPS 머리말/꼬리말 오류")
    memory = {}
    pos = 5
    records = 0
    while data[pos:pos + 3] != b"EOF":
        stored = int.from_bytes(data[pos:pos + 3], "big")
        size = int.from_bytes(data[pos + 3:pos + 5], "big")
        pos += 5
        if size == 0:
            raise ValueError("RLE IPS는 지원하지 않음")
        payload = data[pos:pos + size]
        if len(payload) != size:
            raise ValueError("잘린 IPS 레코드")
        address = stored - 0x100
        for index, value in enumerate(payload):
            memory[address + index] = value
        pos += size
        records += 1
    return memory, records


def read(memory, address, size):
    values = [memory.get(address + offset) for offset in range(size)]
    if any(value is None for value in values):
        raise KeyError(f"IPS에 필요한 바이트가 없음: 0x{address:08X}+{size}")
    return bytes(values)


def decode_adrp_add(data, pc):
    adrp, add = struct.unpack("<II", data)
    imm21 = ((adrp >> 5) & 0x7FFFF) << 2 | ((adrp >> 29) & 3)
    if imm21 & (1 << 20):
        imm21 -= 1 << 21
    page = (pc & ~0xFFF) + (imm21 << 12)
    immediate = ((add >> 10) & 0xFFF) << (12 if (add >> 22) & 1 else 0)
    return page + immediate


def main():
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ips", type=Path, required=True)
    parser.add_argument("--analysis", type=Path,
                        default=repo / "build" / "main_1.0.1_reference_analysis.json")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--mapping", type=Path,
                        default=repo / "build" / "final_mod_report.json")
    args = parser.parse_args()
    memory, ips_records = parse_ips(args.ips)
    analysis = json.loads(args.analysis.read_text(encoding="utf-8"))
    report = json.loads(args.report.read_text(encoding="utf-8"))
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))["hangul_to_standin"]
    source = {item["address"]: item for item in analysis["records"]}
    failures = []
    checked_refs = 0
    for relocated in report["relocated"]:
        item = source[relocated["old_address"]]
        target = int(relocated["new_address"], 16)
        expected = "".join(mapping.get(ch, ch) for ch in item["translation"]).encode() + b"\0"
        if read(memory, target, len(expected)) != expected:
            failures.append({"index": item["index"], "kind": "pool_payload"})
        locations = {}
        for ref in item["direct_pointer_refs"]:
            address = int(ref["memory_address"], 16)
            locations[address] = max(locations.get(address, 0), int(ref["width"]))
        for address, width in locations.items():
            if read(memory, address, width) != target.to_bytes(width, "little"):
                failures.append({"index": item["index"], "kind": "direct_pointer",
                                 "address": f"0x{address:08X}"})
            checked_refs += 1
        for ref in item["adrp_add_refs"]:
            address = int(ref["instruction_address"], 16)
            patched = read(memory, address, 8)
            if decode_adrp_add(patched, address) != target:
                failures.append({"index": item["index"], "kind": "adrp_add",
                                 "address": f"0x{address:08X}"})
            checked_refs += 1
    result = {"ips_records": ips_records, "relocated_strings": len(report["relocated"]),
              "checked_references": checked_refs, "failures": failures}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
