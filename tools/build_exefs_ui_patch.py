#!/usr/bin/env python3
"""업데이트 1.0.1의 동적 노래 선택 UI 문자열 IPS 패치를 생성한다."""

import argparse
import json
from pathlib import Path


BUILD_ID = "28F3C3965CEB60AC18A23E2B2C0C4BEEE3C81D8B"

# NSO가 메모리에 적재된 뒤의 오프셋, 원문 바이트 수, 번역문.
PATCHES = (
    (0x6957A4, 12, "사용가능"),
    (0x6957B9, 15, "충전 중"),
    (0x695823, 12, "S 경향:"),
    (0x695830, 15, "시마법강화"),
    (0x695840, 12, "M 경향:"),
    (0x69584D, 15, "경감 강화"),
    (0x69586D, 12, "I 경향:"),
    (0x69587A, 15, "내구력재생"),
    (0x69588A, 12, "O 경향:"),
    (0x695897, 18, "보조영창강화"),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = json.loads(args.mapping.read_text(encoding="utf-8"))
    mapping = report["hangul_to_standin"]
    records = bytearray(b"PATCH")

    for offset, capacity, translated in PATCHES:
        missing = sorted({char for char in translated if "가" <= char <= "힣" and char not in mapping})
        if missing:
            raise SystemExit(f"폰트 매핑에 없는 한글: {''.join(missing)} ({translated})")
        encoded_text = "".join(mapping.get(char, char) for char in translated).encode("utf-8")
        if len(encoded_text) > capacity:
            raise SystemExit(f"문자열 공간 초과: {translated} ({len(encoded_text)} > {capacity})")
        payload = encoded_text.ljust(capacity, b" ")
        # Atmosphere/Ryujinx IPS의 NSO 오프셋에는 0x100바이트 헤더가 포함된다.
        records += (offset + 0x100).to_bytes(3, "big")
        records += len(payload).to_bytes(2, "big")
        records += payload

    records += b"EOF"
    output = args.output / "exefs_patches" / "ArNosurgeKoreanUI" / f"{BUILD_ID}.ips"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(records)
    print(f"동적 UI IPS 생성: {output}")
    print(f"패치 문자열: {len(PATCHES)}개")


if __name__ == "__main__":
    main()
