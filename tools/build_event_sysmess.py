#!/usr/bin/env python3
"""Translate the system messages embedded in event scripts (`Event/**/*.ebd`).

`.ebd` holds the event graph. Almost every Japanese string in it is an authoring
label — node names, `説明`, `SEL／1／<line>` branch captions that just echo the
EBM dialogue — and none of those reach the screen. The exception is the string
that follows a `SYS:MESS` tag, which the script shows to the player directly.

Leaving it in Japanese is not merely a missing translation: the Korean patch
reuses rare kanji cells in the font atlas, so an untranslated kanji that happens
to own a borrowed cell renders as an unrelated Hangul syllable.

Strings are stored as `u32 length (including NUL) + CP932 bytes + NUL`. The
replacement is written at exactly the original byte length — padded with spaces
when shorter — so the length field and every following offset stay untouched.
"""

import argparse
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TAG = b"SYS:MESS\x00"
JAPANESE = re.compile(r"[぀-ヿ一-鿿]")

# Reviewed by hand: this is the only SYS:MESS text in the game's event scripts.
TRANSLATIONS = {
    "現在この扉はロック中です。暗証番号を入力してください。":
        "현재 이 문은 잠겨 있습니다. 비밀번호를 입력해 주세요.",
}


def read_string(data, offset):
    """Return (text, total_field_size) for the length-prefixed string at offset."""
    length = int.from_bytes(data[offset:offset + 4], "little")
    if length < 2 or offset + 4 + length > len(data):
        return None, 0
    raw = data[offset + 4:offset + 4 + length]
    if raw[-1] != 0:
        return None, 0
    try:
        return raw[:-1].decode("cp932"), 4 + length
    except UnicodeDecodeError:
        return None, 0


def substitute(text, mapping):
    missing = sorted({c for c in text if "가" <= c <= "힣" and c not in mapping})
    if missing:
        raise SystemExit(f"폰트 매핑에 없는 한글: {''.join(missing)}")
    return "".join(mapping.get(c, c) for c in text)


def patch_file(data, mapping, report):
    out = bytearray(data)
    position = 0
    while True:
        found = out.find(TAG, position)
        if found < 0:
            return bytes(out), report
        position = found + len(TAG)
        text, size = read_string(out, position)
        if text is None or not JAPANESE.search(text):
            continue
        korean = TRANSLATIONS.get(text)
        if korean is None:
            report.setdefault("untranslated", []).append(text)
            continue
        payload = substitute(korean, mapping).encode("cp932")
        room = size - 4 - 1                      # exclude length field and NUL
        if len(payload) > room:
            raise SystemExit(
                f"SYS:MESS 번역이 {len(payload)}바이트로 원문 {room}바이트를 넘습니다: {korean}")
        payload = payload.ljust(room, b" ")
        out[position + 4:position + 4 + room] = payload
        report["patched"] = report.get("patched", 0) + 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True,
                        help="언팩된 romfs의 Event 폴더")
    parser.add_argument("--mapping", type=Path,
                        default=REPO / "build" / "final_mod_report.json")
    parser.add_argument("--output", type=Path, required=True,
                        help="설치용 romfs/Event 출력 폴더")
    args = parser.parse_args()

    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))["hangul_to_standin"]
    report = {}
    written = 0
    for source in sorted(args.original.rglob("*.ebd")):
        data = source.read_bytes()
        if TAG not in data:
            continue
        patched, report = patch_file(data, mapping, report)
        if patched == data:
            continue
        if len(patched) != len(data):
            raise SystemExit(f"길이가 변했습니다: {source}")
        destination = args.output / source.relative_to(args.original)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(patched)
        written += 1
        print(f"built: {destination}")
    print(f"SYS:MESS 치환 {report.get('patched', 0)}건 / 파일 {written}개")
    left = sorted(set(report.get("untranslated", [])))
    if left:
        print(f"미번역 SYS:MESS {len(left)}종:")
        for text in left:
            print(f"  {text}")


if __name__ == "__main__":
    main()
