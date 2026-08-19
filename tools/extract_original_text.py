#!/usr/bin/env python3
"""Saves에서 번역할 일본어가 포함된 원본 XML을 originalText로 추출한다."""

import argparse
import json
import re
import shutil
from pathlib import Path


JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
TAG = re.compile(r"<[^>]+>", re.DOTALL)
ATTR_VALUE = re.compile(r'''\s[\w:.-]+\s*=\s*(["'])(.*?)\1''', re.DOTALL)


def has_translatable_japanese(path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    text = COMMENT.sub("", text)
    values = [match.group(2) for match in ATTR_VALUE.finditer(text)]
    # 태그 사이의 요소 본문도 번역 후보로 본다.
    body = TAG.sub("\n", text)
    values.extend(body.splitlines())
    return any(JAPANESE.search(value) for value in values)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--translated", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    copied = []
    skipped_translated = []
    for source in sorted(args.input.rglob("*.xml")):
        relative = source.relative_to(args.input)
        if (args.translated / relative).is_file():
            skipped_translated.append(relative.as_posix())
            continue
        if not has_translatable_japanese(source):
            continue
        destination = args.output / "romfs" / "Saves" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(relative.as_posix())

    manifest = {
        "source": str(args.input),
        "copied_xml_files": len(copied),
        "excluded_already_translated": skipped_translated,
        "files": copied,
        "notes": [
            "원본 XML을 수정하지 않고 상대 경로 그대로 복사했습니다.",
            "XML 주석에만 일본어가 있는 파일은 제외했습니다.",
            "컴파일된 *.xml.e 및 *.bin 파일은 편집용 텍스트가 아니므로 제외했습니다.",
        ],
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"copied_xml_files": len(copied), "excluded_already_translated": len(skipped_translated)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
