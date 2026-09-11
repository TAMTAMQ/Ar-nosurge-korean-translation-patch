#!/usr/bin/env python3
"""현재 PC 설치본의 대사 레이아웃만 안전하게 갱신한다.

기존 PACK01/02를 그대로 입력으로 사용하므로 최근 번역·UI 수정분을 잃지 않는다.
- PACK01 Event/*.ebm: 이벤트 대사를 24자×최대 3줄 기준으로 재배치
- PACK02 tweet/fm_talk_data.xml.e: 22자×최대 3줄 기준으로 재배치
- PACK02 ui/fieldmap/uil_fm_tweet.xml: line_char_length 20 -> 22
- PACK02 ui/message_window/uil_message_window.xml: 이벤트 본문 폭을 약 20자 -> 24자로 확장
"""

import argparse
import json
import pathlib
import shutil
import sys

from build_final_korean_mod import rebuild_ebm_with_layout
from build_pc_package import extract_pak, repack_pak
from build_saves_data import (apply_text_layout, normalize_punctuation,
                              substitute_hangul)
from decode_saves_xml_e import detect_text_encoding, encode_file
from patch_pc_event_message_width import patch_file as patch_event_message_width
from text_layout import FM_TALK_LINE_WRAP_CHARS


def backup_once(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copyfile(source, destination)
        print(f"backup: {destination}")


def ebm_header_signature(data, path):
    if len(data) < 4:
        raise ValueError(f"EBM이 너무 짧습니다: {path}")
    count = int.from_bytes(data[:4], "little")
    pos = 4
    headers = []
    for index in range(count):
        if pos + 36 > len(data):
            raise ValueError(f"EBM 헤더가 잘렸습니다: {path}:{index}")
        headers.append(data[pos:pos + 32])
        length = int.from_bytes(data[pos + 32:pos + 36], "little")
        pos += 36 + length
    if pos != len(data):
        raise ValueError(f"EBM 구조가 맞지 않습니다: {path}")
    return count, tuple(headers)


def patch_pack01(game_dir, gust_pak, work, translated_event, mapping_path):
    source = game_dir / "Data" / "PACK01.PAK"
    backup_once(source, work / "backup" / "PACK01.before_text_layout.PAK")
    staging = work / "PACK01"
    if staging.exists():
        shutil.rmtree(staging)
    manifest = extract_pak(gust_pak, source, staging)
    event_root = manifest.parent / "event"

    authority = {
        p.relative_to(translated_event).as_posix().lower(): p
        for p in translated_event.rglob("*.ebm")
    }
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))["hangul_to_standin"]

    files = changed = removed_total = 0
    authority_used = authority_skipped = 0
    changed_paths = []
    for path in sorted(event_root.rglob("*.ebm")):
        files += 1
        rel = path.relative_to(event_root).as_posix()
        source_path = authority.get(rel.lower())
        before = path.read_bytes()
        same_structure = False
        if source_path is not None:
            source_data = source_path.read_bytes()
            try:
                same_structure = (ebm_header_signature(before, path) ==
                                  ebm_header_signature(source_data, source_path))
            except ValueError:
                same_structure = False
        if same_structure:
            layout_source = source_data
            layout_path = source_path
            authority_used += 1
        else:
            layout_source = before
            layout_path = path
            authority_skipped += 1
        after, removed = rebuild_ebm_with_layout(layout_source, layout_path)
        removed_total += removed
        for ko, ja in mapping.items():
            after = after.replace(ko.encode("utf-8"), ja.encode("utf-8"))
        if after != before:
            path.write_bytes(after)
            changed += 1
            changed_paths.append(rel)

    built = repack_pak(gust_pak, manifest)
    shutil.copyfile(built, source)
    print(f"PACK01: EBM {files}개, 권위본 사용 {authority_used}개, 안전 유지 {authority_skipped}개, "
          f"변경 {changed}개, 제거된 강제 CR {removed_total}개")
    if changed_paths and len(changed_paths) <= 10:
        for name in changed_paths:
            print(f"  변경: {name}")


def patch_pack02(game_dir, gust_pak, work, translated_saves, original_saves, mapping_path):
    source = game_dir / "Data" / "PACK02.PAK"
    backup_once(source, work / "backup" / "PACK02.before_text_layout.PAK")
    staging = work / "PACK02"
    if staging.exists():
        shutil.rmtree(staging)
    manifest = extract_pak(gust_pak, source, staging)
    saves = manifest.parent / "saves"

    fm = saves / "tweet" / "fm_talk_data.xml.e"
    if not fm.is_file():
        raise SystemExit(f"fm_talk_data.xml.e를 찾을 수 없습니다: {fm}")
    fm_source = translated_saves / "tweet" / "fm_talk_data.xml"
    fm_original = original_saves / "tweet" / "fm_talk_data.xml"
    if not fm_source.is_file() or not fm_original.is_file():
        raise SystemExit("fm_talk_data 권위본 또는 원문을 찾을 수 없습니다.")
    with fm_source.open("r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    text = normalize_punctuation(text)
    laid_out = apply_text_layout(
        text,
        "tweet/fm_talk_data.xml",
        line_wrap_chars=FM_TALK_LINE_WRAP_CHARS,
    )
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))["hangul_to_standin"]
    encoded_text = substitute_hangul(laid_out, mapping, "tweet/fm_talk_data.xml")
    encoding = detect_text_encoding(fm_original.read_bytes())
    payload = encode_file(encoded_text.encode(encoding))
    fm_changed = fm.read_bytes() != payload
    if fm_changed:
        fm.write_bytes(payload)

    ui = saves / "ui" / "fieldmap" / "uil_fm_tweet.xml"
    if not ui.is_file():
        raise SystemExit(f"uil_fm_tweet.xml을 찾을 수 없습니다: {ui}")
    ui_data = ui.read_bytes()
    old = b'line_char_length="20"'
    new = b'line_char_length="22"'
    if old in ui_data:
        if ui_data.count(old) != 1:
            raise SystemExit("uil_fm_tweet.xml의 line_char_length=20이 1개가 아닙니다.")
        ui.write_bytes(ui_data.replace(old, new, 1))
        ui_changed = True
    elif new in ui_data:
        ui_changed = False
    else:
        raise SystemExit("uil_fm_tweet.xml에서 line_char_length 20/22를 찾지 못했습니다.")

    event_ui = saves / "ui" / "message_window" / "uil_message_window.xml"
    normal_ui = saves / "ui" / "message_window" / "uil_message_window_normal.xml"
    if not event_ui.is_file() or not normal_ui.is_file():
        raise SystemExit("이벤트 message_window UI 파일을 찾을 수 없습니다.")

    event_data = event_ui.read_bytes()
    # 이벤트 대화창 외형(패널/위치/장식)은 원본 크기를 유지한다. 실제 24자 표시에는
    # 문자 수 상한(line_char_length)과 픽셀 폭 상한(limit_width)을 둘 다 넓혀야 한다.
    restorations = [
        (b'pos="170.333,370"', b'pos="232,370"'),
        (b'size_wh="870,226.667"', b'size_wh="746.667,226.667"'),
        (b'pos="670,210.667"', b'pos="546.667,210.667"'),
        (b'pos="917,105"', b'pos="793.667,105"'),
    ]
    event_ui_changed = False
    for widened, original in restorations:
        if widened in event_data:
            if event_data.count(widened) != 1:
                raise SystemExit(f"uil_message_window.xml에서 {widened!r}가 1개가 아닙니다.")
            event_data = event_data.replace(widened, original, 1)
            event_ui_changed = True
        elif original not in event_data:
            raise SystemExit(f"uil_message_window.xml에서 {widened!r}/{original!r}를 찾지 못했습니다.")

    old_main = b'limit_width="616" line_char_length="24"'
    new_main = b'limit_width="740" line_char_length="24"'
    if new_main not in event_data:
        if event_data.count(old_main) != 1:
            raise SystemExit("uil_message_window.xml에서 616/24 또는 740/24 조합을 찾지 못했습니다.")
        event_data = event_data.replace(old_main, new_main, 1)
        event_ui_changed = True
    if event_ui_changed:
        event_ui.write_bytes(event_data)

    normal_data = normal_ui.read_bytes()
    old_normal = b'line_char_length="20"'
    new_normal = b'line_char_length="24"'
    normal_ui_changed = False
    if old_normal in normal_data:
        if normal_data.count(old_normal) != 1:
            raise SystemExit("uil_message_window_normal.xml의 line_char_length=20이 1개가 아닙니다.")
        normal_ui.write_bytes(normal_data.replace(old_normal, new_normal, 1))
        normal_ui_changed = True
    elif new_normal not in normal_data:
        raise SystemExit("uil_message_window_normal.xml에서 line_char_length 20/24를 찾지 못했습니다.")

    built = repack_pak(gust_pak, manifest)
    shutil.copyfile(built, source)
    print(f"PACK02: fm_talk_data {'변경' if fm_changed else '이미 동일'}, "
          f"fm_tweet UI {'변경' if ui_changed else '이미 22자'}, "
          f"event UI {'변경' if event_ui_changed or normal_ui_changed else '이미 24자'}")


def main():
    repo = pathlib.Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game-dir", required=True, type=pathlib.Path)
    ap.add_argument("--gust-pak", type=pathlib.Path,
                    default=pathlib.Path("D:/trans/gust_tools/gust_pak.exe"))
    ap.add_argument("--work", type=pathlib.Path,
                    default=repo / "build" / "pc" / "text_layout_update")
    ap.add_argument("--translated-saves", type=pathlib.Path,
                    default=repo / "translations" / "romfs" / "Saves")
    ap.add_argument("--original-saves", type=pathlib.Path,
                    default=repo / "originalText" / "romfs" / "Saves")
    ap.add_argument("--mapping", type=pathlib.Path,
                    default=repo / "build" / "final_mod_report.json")
    args = ap.parse_args()

    if not args.game_dir.is_dir():
        raise SystemExit(f"게임 폴더가 없습니다: {args.game_dir}")
    if not args.gust_pak.is_file():
        raise SystemExit(f"gust_pak.exe가 없습니다: {args.gust_pak}")
    args.work.mkdir(parents=True, exist_ok=True)

    patch_pack01(args.game_dir, args.gust_pak, args.work,
                 repo / "translations" / "romfs" / "Event", args.mapping)
    patch_pack02(args.game_dir, args.gust_pak, args.work,
                 args.translated_saves, args.original_saves, args.mapping)
    patch_event_message_width(args.game_dir / "ArnosurgeDX.exe")
    print("완료")


if __name__ == "__main__":
    main()
