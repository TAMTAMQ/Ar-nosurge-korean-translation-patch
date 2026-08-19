#!/usr/bin/env python3
"""Build game-ready system-message XML from editable Korean XML files."""

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_args():
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Convert readable Korean system-message XML to the font stand-in characters."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=repo / "translations" / "romfs" / "Saves" / "systemMessage",
    )
    parser.add_argument("--mapping", type=Path, default=repo / "build" / "final_mod_report.json")
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
    for source in sorted(args.input.glob("*.xml")):
        root = ET.parse(source).getroot()
        for index, element in enumerate(root):
            text = element.attrib.get("Text", "")
            missing = sorted({c for c in text if "가" <= c <= "힣" and c not in mapping})
            if missing:
                chars = "".join(missing)
                raise SystemExit(f"{source.name}:{index}: 폰트 매핑에 없는 한글 음절: {chars}")
            element.set("Text", "".join(mapping.get(c, c) for c in text))

        tree = ET.ElementTree(root)
        ET.indent(tree, space="\t")
        destination = args.output / source.name
        tree.write(destination, encoding="utf-8", xml_declaration=True, short_empty_elements=True)
        ET.parse(destination)
        built += 1
        print(f"built: {destination}")

    if built == 0:
        raise SystemExit(f"입력 XML이 없습니다: {args.input}")


if __name__ == "__main__":
    main()
