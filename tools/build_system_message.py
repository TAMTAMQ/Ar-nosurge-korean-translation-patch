#!/usr/bin/env python3
"""Build game-ready Saves XML files from editable Korean XML files."""

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from text_layout import strip_wrap_boundary_breaks


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
        root = ET.parse(source).getroot()
        for index, element in enumerate(root.iter()):
            for attribute in ("Text", "text"):
                if attribute not in element.attrib:
                    continue
                text = element.attrib[attribute]
                text = strip_wrap_boundary_breaks(text)
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
        # SysInfo is loaded by a legacy path that treats the byte stream as
        # Shift-JIS regardless of the XML declaration.  Writing it as UTF-8
        # turns every three-byte stand-in character into mojibake in HELP.
        output_encoding = "shift_jis" if source.name.casefold() == "sysinfo.xml" else "utf-8"
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
