#!/usr/bin/env python3
"""PC(Steam)판 ArnosurgeDX.exe 안의 표시 문자열을 한국어로 교체한다.

스위치용 build_main_text_patch.py 는 NSO 를 풀고 IPS 를 만드는 도구라 PE 에는
쓸 수 없다. 여기서는 exe 를 직접 고친다. 빌드 ID 개념이 없으므로 IPS 도 필요
없다.

번역 CSV 의 memory_address / capacity_bytes 는 스위치 NSO 기준이라 PC 에서는
쓸 수 없다. 그래서 원문 일본어의 UTF-8 바이트를 PE 의 읽기 전용 섹션에서 직접
찾고, 그 자리의 용량을 새로 잰다.

용량은 "문자열 시작부터 NUL 패딩이 끝나고 다음 데이터가 시작되기 직전까지"다.
링커가 문자열을 정렬하며 남긴 패딩까지 쓸 수 있다. 종단 NUL 한 바이트는 항상
남겨 둔다.

한 문자열이 여러 곳에 독립적으로 놓여 있으면 전부 교체한다. 한 군데만 고치면
같은 메뉴가 화면에 따라 일본어로 남는다.
"""
import argparse
import csv
import json
import pathlib
import struct
import sys
from collections import defaultdict


# PC판 .rdata에는 일부 표시 문자열이 앞 NUL 없이 구조체/테이블 데이터 바로 뒤에
# 놓여 있다. 일반 검색의 앞 NUL 조건을 풀면 더 긴 문자열의 꼬리를 오인할 수 있으므로,
# 실제 1.0.1 원본 EXE에서 확인한 세 항목만 파일 오프셋을 고정한다. 사용 시에는 아래
# 오프셋의 원문 바이트와 뒤 NUL을 다시 검증하므로 다른 EXE에서는 조용히 잘못 쓰지 않는다.
PACKED_STRING_OFFSETS = {
    489: 0x46F8B0,   # いいよ！
    2640: 0x56B920,  # ダミー
    2777: 0x56EAE8,  # 結城　柑菜
}


def sections(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    optsz = struct.unpack_from("<H", data, pe + 20)[0]
    base = struct.unpack_from("<Q", data, pe + 24 + 24)[0]
    out = []
    off = pe + 24 + optsz
    for _ in range(nsec):
        name = data[off:off + 8].rstrip(b"\0").decode(errors="replace")
        vsize, vaddr, rsize, roff = struct.unpack_from("<IIII", data, off + 8)
        out.append({"name": name, "vaddr": vaddr, "vsize": vsize,
                    "roff": roff, "rsize": rsize})
        off += 40
    return base, out


def encode(text, mapping):
    missing = sorted({c for c in text if "가" <= c <= "힣" and c not in mapping})
    if missing:
        raise ValueError("폰트 매핑에 없는 한글: " + "".join(missing))
    return "".join(mapping.get(c, c) for c in text).encode("utf-8")


def find_slots(blob, needle, limit):
    """needle 이 독립된 NUL 종단 문자열로 놓인 자리를 모두 찾는다.

    앞이 NUL 이고 뒤도 NUL 이어야 한다. 더 긴 문자열의 꼬리를 잡아
    남의 데이터를 덮어쓰는 사고를 막는다.
    """
    hits = []
    start = 0
    while True:
        i = blob.find(needle, start)
        if i < 0 or i >= limit:
            break
        start = i + 1
        if i > 0 and blob[i - 1] != 0:
            continue
        end = i + len(needle)
        if end >= len(blob) or blob[end] != 0:
            continue
        hits.append(i)
    return hits


def slot_capacity(blob, start, length):
    """문자열 시작부터 다음 데이터 직전까지의 바이트 수."""
    j = start + length
    while j < len(blob) and blob[j] == 0:
        j += 1
    return j - start


def main():
    csv.field_size_limit(1 << 30)
    repo = pathlib.Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe", required=True, type=pathlib.Path)
    ap.add_argument("--translations", type=pathlib.Path,
                    default=repo / "translations" / "exefs" / "main_1.0.1.csv")
    ap.add_argument("--mapping", required=True, type=pathlib.Path)
    ap.add_argument("--output", type=pathlib.Path,
                    help="패치된 exe 를 쓸 경로. 생략하면 분석만 한다.")
    ap.add_argument("--report", type=pathlib.Path,
                    default=repo / "build" / "pc_main_text_patch_report.json")
    ap.add_argument("--section", default=".rdata",
                    help="문자열을 찾을 섹션 (기본 .rdata)")
    ap.add_argument("--allow-padding", action="store_true",
                    help="원문 뒤의 링커 정렬 패딩까지 써서 원문보다 긴 번역을 넣는다. "
                         "패딩이 인접 구조의 0 바이트일 수도 있으므로 기본은 끈다. "
                         "현재 번역은 전부 원문 바이트 안에 들어가므로 필요 없다.")
    args = ap.parse_args()

    data = bytearray(args.exe.read_bytes())
    base, secs = sections(data)
    sec = next((s for s in secs if s["name"] == args.section), None)
    if sec is None:
        sys.exit(f"오류: 섹션을 찾지 못했습니다: {args.section}")
    lo, hi = sec["roff"], sec["roff"] + sec["rsize"]
    print(f"{args.section}: 파일 {lo:#x}..{hi:#x} ({sec['rsize']} 바이트), "
          f"이미지 베이스 {base:#x}")

    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))["hangul_to_standin"]

    rows = []
    with args.translations.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["status"] != "needs_review" or not row["translation"]:
                continue
            rows.append(row)
    print(f"번역 대상 행: {len(rows)}")

    writes = {}            # 파일 오프셋 -> payload
    stats = defaultdict(int)
    overflow, notfound, unmapped = [], [], []
    packed_slots_used = []

    for row in rows:
        row_index = int(row["index"])
        original = row["original"]
        translation = row["translation"]

        # 추출 당시의 CSV 는 개행을 CRLF 로 담고 있는데 PE 안의 문자열은 LF 만
        # 쓴다. 원문 그대로는 찾지 못하므로 개행을 맞춰 한 번 더 본다. 이때
        # 번역문의 개행도 같이 맞춰야 원문과 같은 줄 수가 유지된다.
        candidates = [(original, translation)]
        if "\r\n" in original:
            candidates.append((original.replace("\r\n", "\n"),
                               translation.replace("\r\n", "\n")))

        hits, needle, chosen = [], None, translation
        for cand_original, cand_translation in candidates:
            probe = cand_original.encode("utf-8")
            found = [h for h in find_slots(data, probe, hi) if lo <= h < hi]
            if found:
                hits, needle, chosen = found, probe, cand_translation
                break

        if not hits and row_index in PACKED_STRING_OFFSETS:
            # 이 세 항목은 앞 NUL이 없는 테이블 항목이다. 정확한 원문과 뒤 NUL을
            # 동시에 확인한 경우에만 예외 슬롯으로 인정한다.
            manual = PACKED_STRING_OFFSETS[row_index]
            probe = original.encode("utf-8")
            end = manual + len(probe)
            if (lo <= manual < hi and end < hi and
                    data[manual:end] == probe and data[end] == 0):
                hits, needle, chosen = [manual], probe, translation
                packed_slots_used.append({
                    "index": row_index,
                    "offset": hex(manual),
                    "original": original,
                })
                stats["packed_slot"] += 1

        if not hits:
            notfound.append({"index": row["index"], "original": original})
            stats["notfound"] += 1
            continue

        try:
            payload = encode(chosen, mapping)
        except ValueError as exc:
            unmapped.append({"index": row["index"], "original": original,
                             "reason": str(exc)})
            stats["unmapped"] += 1
            continue

        placed = False
        for h in hits:
            # 기본은 원문이 차지하던 바이트와 그 종단 NUL 만 쓴다. 뒤의 정렬
            # 패딩은 인접 구조의 0 바이트일 수도 있어 건드리지 않는다.
            cap = (slot_capacity(data, h, len(needle)) if args.allow_padding
                   else len(needle) + 1)
            if len(payload) + 1 > cap:          # 종단 NUL 한 바이트는 남긴다
                overflow.append({"index": row["index"], "original": original,
                                 "translation": row["translation"],
                                 "offset": hex(h), "capacity": cap,
                                 "needed": len(payload) + 1})
                stats["overflow"] += 1
                continue
            writes[h] = payload.ljust(cap, b"\0")
            placed = True
        if placed:
            stats["placed"] += 1
            stats["slots"] += len([h for h in hits if h in writes])

    print(json.dumps({k: v for k, v in sorted(stats.items())},
                     ensure_ascii=False, indent=2))

    if args.output:
        for off, payload in writes.items():
            data[off:off + len(payload)] = payload
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(bytes(data))
        print(f"기록: {args.output} ({len(data)} 바이트)")

    report = {
        "exe": str(args.exe),
        "section": args.section,
        "rows_considered": len(rows),
        "strings_placed": stats["placed"],
        "slots_written": len(writes),
        "overflow": len(overflow),
        "not_found": len(notfound),
        "unmapped": len(unmapped),
        "overflow_detail": overflow[:200],
        "not_found_detail": notfound[:200],
        "unmapped_detail": unmapped[:200],
        "packed_string_slots_used": packed_slots_used,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"보고서: {args.report}")


if __name__ == "__main__":
    main()
