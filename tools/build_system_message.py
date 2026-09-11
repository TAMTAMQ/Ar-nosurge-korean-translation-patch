#!/usr/bin/env python3
"""Build game-ready Saves XML files from editable Korean XML files."""

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from decode_saves_xml_e import detect_text_encoding
from text_layout import reflow_dialogue_layout

# Only these subfolders are genuinely plain XML in the game's romfs. Every
# other Saves subfolder (item, misogi, tweet, achievement, ...) is scrambled
# .xml.e and is built by build_saves_data.py instead.
PLAIN_XML_DIRS = {"systemMessage", "ui"}


def parse_args():
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Convert readable Korean Saves XML files to the font stand-in characters."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=repo / "translations" / "romfs" / "Saves",
    )
    parser.add_argument("--mapping", type=Path, default=repo / "build" / "final_mod_report.json")
    parser.add_argument(
        "--original",
        type=Path,
        default=repo / "originalText" / "romfs" / "Saves",
        help="원본 Saves 폴더. 각 파일을 원본과 같은 인코딩으로 쓰기 위해 참조한다.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=repo / "atmosphere" / "contents" / "01003CF0128DE000" / "romfs" / "Saves" / "systemMessage",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    report = json.loads(args.mapping.read_text(encoding="utf-8"))
    mapping = report["hangul_to_standin"]
    args.output.mkdir(parents=True, exist_ok=True)

    built = 0
    for source in sorted(args.input.rglob("*.xml")):
        relative = source.relative_to(args.input)
        if relative.parts[0] not in PLAIN_XML_DIRS:
            continue
        root = ET.parse(source).getroot()
        for index, element in enumerate(root.iter()):
            for attribute in ("Text", "text", "set_text"):
                if attribute not in element.attrib:
                    continue
                text = element.attrib[attribute]
                text = reflow_dialogue_layout(text)
                missing = sorted({c for c in text if "가" <= c <= "힣" and c not in mapping})
                if missing:
                    chars = "".join(missing)
                    raise SystemExit(f"{source.name}:{index}:{attribute}: 폰트 매핑에 없는 한글 음절: {chars}")
                text = "".join(mapping.get(c, c) for c in text)
                element.set(attribute, text)

        tree = ET.ElementTree(root)
        ET.indent(tree, space="\t")
        destination = args.output / source.relative_to(args.input)
        destination.parent.mkdir(parents=True, exist_ok=True)
        # 이 파일들은 XML 선언과 무관하게 바이트열을 그대로 해석하는 경로로
        # 읽힌다. PC 판에서는 그 경로가 CP_ACP 를 쓰므로 원본과 다른 인코딩으로
        # 쓰면 세 바이트짜리 대체문자가 통째로 깨진다. 스위치에는 ACP 개념이
        # 없어 드러나지 않았고, 그래서 SysInfo 만 예외 처리되어 있었다.
        # 파일명으로 예외를 두지 말고 원본과 같은 인코딩을 따라간다.
        original_path = args.original / relative
        if original_path.is_file():
            output_encoding = detect_text_encoding(original_path.read_bytes())
        else:
            output_encoding = ("shift_jis"
                               if source.name.casefold() == "sysinfo.xml" else "utf-8")
        if output_encoding == "cp932":
            output_encoding = "shift_jis"
        tree.write(
            destination,
            encoding=output_encoding,
            xml_declaration=True,
            short_empty_elements=True,
        )
        if output_encoding == "shift_jis":
            # ElementTree's file parser rejects a Shift-JIS declaration even
            # though it can parse the already-decoded XML text.
            ET.fromstring(destination.read_text(encoding="shift_jis"))
        else:
            ET.parse(destination)
        built += 1
        print(f"built: {destination}")

    if built == 0:
        raise SystemExit(f"입력 XML이 없습니다: {args.input}")


if __name__ == "__main__":
    main()
