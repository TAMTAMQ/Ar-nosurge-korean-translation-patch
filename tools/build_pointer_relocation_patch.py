#!/usr/bin/env python3
"""검증용: 길이 초과 문자열을 rodata 풀로 옮기고 참조를 수정한다."""

import argparse
import json
import struct
from pathlib import Path


BUILD_ID = "28F3C3965CEB60AC18A23E2B2C0C4BEEE3C81D8B"


def ips_record(address, payload):
    return (address + 0x100).to_bytes(3, "big") + len(payload).to_bytes(2, "big") + payload


def patch_adrp_add(ref, target):
    adrp = int(ref["adrp"], 16)
    add = int(ref["add"], 16)
    pc = int(ref["instruction_address"], 16)
    pages = ((target & ~0xFFF) - (pc & ~0xFFF)) >> 12
    if not -(1 << 20) <= pages < (1 << 20):
        raise ValueError("ADRP 범위를 벗어남")
    encoded = pages & 0x1FFFFF
    new_adrp = (adrp & ~((3 << 29) | (0x7FFFF << 5)))
    new_adrp |= (encoded & 3) << 29 | ((encoded >> 2) & 0x7FFFF) << 5
    new_add = add & ~((0xFFF << 10) | (1 << 22))
    new_add |= (target & 0xFFF) << 10
    return pc, struct.pack("<II", new_adrp, new_add)


def main():
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path,
                        default=repo / "build" / "main_1.0.1_reference_analysis.json")
    parser.add_argument("--mapping", type=Path,
                        default=repo / "build" / "final_mod_report.json")
    parser.add_argument("--base-ips", type=Path,
                        default=repo / "atmosphere" / "exefs_patches" /
                        "ArNosurgeKoreanUI" / f"{BUILD_ID}.ips")
    parser.add_argument("--output", type=Path,
                        default=repo / "build" / "pointer_test" / f"{BUILD_ID}.ips")
    parser.add_argument("--report", type=Path,
                        default=repo / "build" / "pointer_test" / "report.json")
    parser.add_argument("--limit", type=int,
                        help="앞에서 지정한 수만 시험한다. 생략하면 전체를 처리한다.")
    args = parser.parse_args()

    analysis = json.loads(args.analysis.read_text(encoding="utf-8"))
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))["hangul_to_standin"]
    candidates = analysis["records"][:args.limit] if args.limit else analysis["records"]
    runs = [x for x in analysis["zero_runs_at_least_64"] if x["segment"] == "rodata"]
    if not runs:
        raise SystemExit("rodata 문자열 풀 후보가 없습니다")
    run_index = 0
    pool_start = int(runs[0]["memory_address"], 16) + 16
    pool_end = int(runs[0]["memory_address"], 16) + runs[0]["size"]
    cursor = pool_start
    pools = [{"start": f"0x{pool_start:08X}", "capacity": pool_end - pool_start,
              "used": 0}]
    records = []
    relocated = []

    for item in candidates:
        text = "".join(mapping.get(ch, ch) for ch in item["translation"])
        payload = text.encode("utf-8") + b"\0"
        while cursor + len(payload) > pool_end:
            pools[-1]["used"] = cursor - int(pools[-1]["start"], 16)
            run_index += 1
            if run_index >= len(runs):
                raise SystemExit("문자열 풀이 부족합니다")
            pool_start = int(runs[run_index]["memory_address"], 16) + 16
            pool_end = int(runs[run_index]["memory_address"], 16) + runs[run_index]["size"]
            cursor = pool_start
            pools.append({"start": f"0x{pool_start:08X}",
                          "capacity": pool_end - pool_start, "used": 0})
        target = cursor
        records.append((target, payload))
        cursor += len(payload)

        direct = item["direct_pointer_refs"]
        locations = {}
        for ref in direct:
            location = int(ref["memory_address"], 16)
            locations[location] = max(locations.get(location, 0), int(ref["width"]))
        for location, width in locations.items():
            records.append((location, target.to_bytes(width, "little")))
        for ref in item["adrp_add_refs"]:
            records.append(patch_adrp_add(ref, target))
        relocated.append({"index": item["index"], "old_address": item["address"],
                          "new_address": f"0x{target:08X}", "bytes": len(payload),
                          "direct_refs": len(locations),
                          "adrp_add_refs": len(item["adrp_add_refs"]),
                          "original": item["original"], "translation": item["translation"]})

    base = args.base_ips.read_bytes()
    if not base.startswith(b"PATCH") or not base.endswith(b"EOF"):
        raise SystemExit("기본 IPS 형식이 올바르지 않습니다")
    output = bytearray(base[:-3])
    for address, payload in records:
        output += ips_record(address, payload)
    output += b"EOF"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output)
    pools[-1]["used"] = cursor - int(pools[-1]["start"], 16)
    report = {"experimental": True, "base_ips": str(args.base_ips),
              "output": str(args.output), "pool_count": len(pools),
              "pool_used": sum(x["used"] for x in pools),
              "pool_capacity": sum(x["capacity"] for x in pools), "pools": pools,
              "relocated": relocated}
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "relocated"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
