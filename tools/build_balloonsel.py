#!/usr/bin/env python3
"""Build the game-ready balloonseldata.bsb from the translated JSON.

Mirrors build_saves_data.py: substitute the Hangul stand-in characters that the
patched font atlas actually carries, then re-emit the binary. The choice
balloons are length prefixed, so unlike the `main` slots there is no capacity
limit to respect.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from balloonsel import build, parse

REPO = Path(__file__).resolve().parents[1]


def substitute(text, mapping):
    missing = sorted({c for c in text if "가" <= c <= "힣" and c not in mapping})
    if missing:
        raise SystemExit(f"폰트 매핑에 없는 한글: {''.join(missing)}")
    return "".join(mapping.get(c, c) for c in text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=REPO / "translations" / "romfs" / "Event"
                        / "balloonsel" / "balloonseldata.json")
    parser.add_argument("--original", type=Path, required=True,
                        help="원본 balloonseldata.bsb (구조 검증용)")
    parser.add_argument("--mapping", type=Path,
                        default=REPO / "build" / "final_mod_report.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if not args.input.is_file():
        raise SystemExit(f"번역 JSON이 없습니다: {args.input}")
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))["hangul_to_standin"]
    groups = json.loads(args.input.read_text(encoding="utf-8"))

    reference = parse(args.original.read_bytes())
    if len(reference) != len(groups):
        raise SystemExit(f"그룹 수 불일치: 원본 {len(reference)} != 번역 {len(groups)}")
    for index, (a, b) in enumerate(zip(reference, groups)):
        if len(a) != len(b):
            raise SystemExit(f"그룹 {index} 선택지 수 불일치: {len(a)} != {len(b)}")

    encoded = [[substitute(option, mapping) for option in group] for group in groups]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    data = build(encoded)
    args.output.write_bytes(data)
    if parse(data) != encoded:
        raise SystemExit("재파싱 결과가 입력과 다릅니다")
    total = sum(len(g) for g in encoded)
    print(f"built: {args.output} (그룹 {len(encoded)} / 선택지 {total} / {len(data)}바이트)")


if __name__ == "__main__":
    main()
