#!/usr/bin/env python3
"""전투 튜토리얼 39개의 24자 재배치와 실제 생성본을 검증한다."""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_system_message import (
    BATTLE_TUTORIAL_FIRST_INDEX,
    BATTLE_TUTORIAL_LAST_INDEX,
)
from decode_saves_xml_e import detect_text_encoding
from rename_term import rename as normalize_terms
from text_layout import (
    EVENT_LINE_WRAP_CHARS,
    visible_units,
    wrap_words_with_explicit_breaks,
)

REPO = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO / "translations" / "romfs" / "Saves" / "systemMessage" / "SysMess.xml"
DEFAULT_BUILT = (
    REPO
    / "atmosphere"
    / "contents"
    / "01003CF0128DE000"
    / "romfs"
    / "Saves"
    / "systemMessage"
    / "SysMess.xml"
)
DEFAULT_MAPPING = REPO / "build" / "final_mod_report.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--built", type=Path, default=DEFAULT_BUILT)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    return parser.parse_args()


def load_root(path: Path) -> ET.Element:
    raw = path.read_bytes()
    encoding = detect_text_encoding(raw)
    return ET.fromstring(raw.decode(encoding))


def main() -> None:
    args = parse_args()
    source_root = load_root(args.source)
    source_rows = list(source_root)
    built_rows = list(load_root(args.built)) if args.built.is_file() else None
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))["hangul_to_standin"]

    expected_count = BATTLE_TUTORIAL_LAST_INDEX - BATTLE_TUTORIAL_FIRST_INDEX + 1
    failures = []
    max_width = 0
    max_lines = 0

    if len(source_rows) <= BATTLE_TUTORIAL_LAST_INDEX:
        raise SystemExit(
            f"SysMess 항목 수가 부족합니다: {len(source_rows)} <= {BATTLE_TUTORIAL_LAST_INDEX}"
        )
    if built_rows is not None and len(built_rows) != len(source_rows):
        failures.append(f"생성본 항목 수 불일치: {len(built_rows)} != {len(source_rows)}")

    for index in range(BATTLE_TUTORIAL_FIRST_INDEX, BATTLE_TUTORIAL_LAST_INDEX + 1):
        source = normalize_terms(source_rows[index].attrib.get("Text", ""))
        wrapped = wrap_words_with_explicit_breaks(source, EVENT_LINE_WRAP_CHARS)
        lines = wrapped.split("<CR>")
        widths = [visible_units(line) for line in lines]
        max_width = max(max_width, *widths)
        max_lines = max(max_lines, len(lines))

        if "<CR>" in source:
            failures.append(f"{index}: 권위본에 강제 <CR> 잔존")
        if source.replace("<CR>", " ").split() != wrapped.replace("<CR>", " ").split():
            failures.append(f"{index}: 단어 경계 왕복 불일치")
        if any(width > EVENT_LINE_WRAP_CHARS for width in widths):
            failures.append(f"{index}: 24자 초과 {widths}")
        if any(line.startswith((" ", "　")) for line in lines[1:]):
            failures.append(f"{index}: <CR> 뒤 선행 공백")

        if built_rows is not None:
            encoded = "".join(mapping.get(char, char) for char in wrapped)
            built = built_rows[index].attrib.get("Text", "")
            if encoded != built:
                failures.append(f"{index}: 실제 생성본 불일치")

    print(
        f"tutorial={expected_count} failures={len(failures)} "
        f"max_width={max_width} max_lines={max_lines} "
        f"built={'checked' if built_rows is not None else 'missing'}"
    )
    for failure in failures[:20]:
        print(f"  {failure}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
