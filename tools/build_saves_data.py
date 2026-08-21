#!/usr/bin/env python3
"""Build game-ready Saves/*.xml.e files from translated plain XML.

`translations/romfs/Saves/systemMessage` and `.../ui` stay plain XML in the
game's romfs and are built by build_system_message.py. Every other Saves
subfolder (item, misogi, tweet, achievement, chara, field, ...) is stored by
the game as scrambled+compressed `.xml.e` (see tools/decode_saves_xml_e.py),
so translated copies of those files need one extra step before they can be
installed: substitute the Hangul font stand-in characters, then re-encode.

translate_saves_with_ollama.py already walks all of originalText/romfs/Saves
(recursively, skipping only systemMessage) and writes translated plain XML to
the matching translations/romfs/Saves/<path> -- including these subfolders --
so the only change it needed was per-file encoding detection (most of these
files are genuinely CP932, but everything under field/ turned out to be UTF-8
despite an XML header that still (incorrectly) claims Shift-JIS). This script
re-derives the same per-file target encoding by sniffing the matching file
under originalText/, then re-encodes into the .xml.e format the game expects.
"""
import argparse
import json
from pathlib import Path

from decode_saves_xml_e import encode_file, detect_text_encoding

SKIP_DIRS = {"systemMessage", "ui"}


# The local model sometimes reaches for ASCII-adjacent punctuation instead of
# the CP932-safe full-width form the original Japanese text actually uses
# (e.g. half-width U+00B7 MIDDLE DOT instead of U+30FB KATAKANA MIDDLE DOT,
# which is what "サーリとのこと・１" etc. use in the source files). Normalize
# known substitutions before encoding rather than crashing the whole batch.
CP932_PUNCTUATION_FIXUPS = {
    "·": "・",  # U+00B7 MIDDLE DOT -> U+30FB KATAKANA MIDDLE DOT
    "—": "―",  # U+2014 EM DASH -> U+2015 HORIZONTAL BAR
}


def normalize_punctuation(text):
    for bad, good in CP932_PUNCTUATION_FIXUPS.items():
        text = text.replace(bad, good)
    return text


def substitute_hangul(text, mapping, source_label):
    missing = sorted({c for c in text if "가" <= c <= "힣" and c not in mapping})
    if missing:
        raise SystemExit(f"{source_label}: 폰트 매핑에 없는 한글 음절: {''.join(missing)}")
    return "".join(mapping.get(c, c) for c in text)


def main():
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=repo / "translations" / "romfs" / "Saves")
    parser.add_argument("--original", type=Path, default=repo / "originalText" / "romfs" / "Saves",
                        help="원문 XML 루트. 파일별 실제 출력 인코딩(UTF-8/CP932)을 판단하는 데 사용")
    parser.add_argument("--mapping", type=Path, default=repo / "build" / "final_mod_report.json")
    parser.add_argument("--output", type=Path,
                        default=repo / "atmosphere" / "contents" / "01003CF0128DE000" / "romfs" / "Saves")
    args = parser.parse_args()

    report = json.loads(args.mapping.read_text(encoding="utf-8"))
    mapping = report["hangul_to_standin"]

    built = 0
    for source in sorted(args.input.rglob("*.xml")):
        relative = source.relative_to(args.input)
        if relative.parts[0] in SKIP_DIRS:
            continue
        # newline="" preserves the game's literal \r\n line endings -- universal
        # newline translation on read would silently drop the \r and shift
        # every subsequent byte, breaking the game's fixed-format parser.
        text = source.read_text(encoding="utf-8", newline="")
        text = normalize_punctuation(text)
        text = substitute_hangul(text, mapping, str(relative))

        original_path = args.original / relative
        if not original_path.is_file():
            raise SystemExit(f"원문 파일을 찾을 수 없습니다(인코딩 판단용): {original_path}")
        target_encoding = detect_text_encoding(original_path.read_bytes())
        try:
            payload = text.encode(target_encoding)
        except UnicodeEncodeError as exc:
            around = text[max(0, exc.start - 30):exc.start + 30]
            raise SystemExit(
                f"{relative}: {target_encoding}로 인코딩할 수 없는 문자 "
                f"U+{ord(text[exc.start]):04X} ({text[exc.start]!r}) 발견, 주변: {around!r}"
            ) from None

        encoded = encode_file(payload)
        destination = args.output / relative.with_suffix(relative.suffix + ".e")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(encoded)
        built += 1
        print(f"built: {destination}")

    if built == 0:
        print(f"변환할 XML이 없습니다 (systemMessage/ui 제외): {args.input}")


if __name__ == "__main__":
    main()
