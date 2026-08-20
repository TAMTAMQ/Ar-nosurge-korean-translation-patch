#!/usr/bin/env python3
"""아르노사쥬/아르노서지 DX 한국어 패치 전체 빌드 도구.

translations/romfs의 한국어 EBM과 Saves XML을 한 번에 변환하고,
한글 폰트를 생성해 atmosphere/contents/<Title ID>/romfs에 출력합니다.
"""

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TITLE_ID = "01003CF0128DE000"
TRANSLATIONS = ROOT / "translations"
SAVES_TRANSLATIONS = TRANSLATIONS / "romfs" / "Saves"
SYSTEM_MESSAGES = SAVES_TRANSLATIONS / "systemMessage"
ATMOSPHERE = ROOT / "atmosphere" / "contents" / TITLE_ID
BUILD_REPORT = ROOT / "build" / "final_mod_report.json"


def find_original_font(explicit):
    if explicit:
        path = explicit.resolve()
        if not path.is_file():
            raise SystemExit(f"원본 폰트를 찾을 수 없습니다: {path}")
        return path
    candidates = [
        ROOT / "original" / "romfs" / "Data" / "NX" / "Font" / "MainFont_nx_0.g1t",
        ROOT / "original" / "MainFont_nx_0.g1t",
        ROOT / "MainFont_nx_0.g1t",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise SystemExit(
        "원본 MainFont_nx_0.g1t를 찾을 수 없습니다.\n"
        "original/romfs/Data/NX/Font/MainFont_nx_0.g1t에 넣거나 "
        "--original-font로 경로를 지정하세요."
    )


def run(command):
    print("\n> " + " ".join(str(x) for x in command), flush=True)
    subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-font", type=Path, help="정품 게임에서 추출한 원본 MainFont_nx_0.g1t")
    args = parser.parse_args()
    original_font = find_original_font(args.original_font)

    event_dir = TRANSLATIONS / "romfs" / "Event" / "event"
    if not event_dir.is_dir():
        raise SystemExit(f"한국어 EBM 폴더가 없습니다: {event_dir}")
    if not SYSTEM_MESSAGES.is_dir():
        raise SystemExit(f"한국어 시스템 메시지 폴더가 없습니다: {SYSTEM_MESSAGES}")

    print("=== 1/3 이벤트 대사 EBM과 한글 폰트 생성 ===")
    run([
        sys.executable, str(ROOT / "tools" / "build_final_korean_mod.py"),
        "--translated-mod", str(TRANSLATIONS),
        "--original-font", str(original_font),
        "--extra-text-dir", str(TRANSLATIONS),
        "--output", str(ATMOSPHERE),
        "--report", str(BUILD_REPORT),
    ])

    print("\n=== 2/3 시스템 메시지와 UI XML 생성 ===")
    run([
        sys.executable, str(ROOT / "tools" / "build_system_message.py"),
        "--input", str(SAVES_TRANSLATIONS),
        "--mapping", str(BUILD_REPORT),
        "--output", str(ATMOSPHERE / "romfs" / "Saves"),
    ])

    print("\n=== 3/3 업데이트 1.0.1 동적 UI 패치 생성 ===")
    run([
        sys.executable, str(ROOT / "tools" / "build_main_text_patch.py"),
        "--translations", str(TRANSLATIONS / "exefs" / "main_1.0.1.csv"),
        "--mapping", str(BUILD_REPORT),
        "--output", str(ROOT / "atmosphere"),
    ])

    print("\n전체 빌드 완료")
    print(f"출력: {ATMOSPHERE}")
    print(f"매핑 보고서: {BUILD_REPORT}")


if __name__ == "__main__":
    main()
