#!/usr/bin/env python3
"""아르노사쥬/아르노서지 DX 한국어 패치 전체 빌드 도구.

translations/romfs의 한국어 EBM, 시스템 메시지/UI XML, 대화 선택지, 번역한 UI 텍스처,
게임 데이터
Saves/*.xml.e(아이템명·업적·미소기 대화 등)를 한 번에 변환하고,
한글 폰트와 main 실행 파일 패치를 생성해 atmosphere/contents/<Title ID>에
출력합니다. Saves/*.xml.e 쪽은 아직 번역이 없으면 해당 단계만 건너뜁니다.
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
BALLOONSEL = TRANSLATIONS / "romfs" / "Event" / "balloonsel" / "balloonseldata.json"
UI_IMAGES = ROOT / "translateImage"
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
    parser.add_argument("--original-balloonsel", type=Path,
                        help="원본 romfs/Event/balloonsel/balloonseldata.bsb. 대화 선택지를 "
                             "한국어로 바꾸려면 구조 검증용으로 필요하다.")
    parser.add_argument("--original-ui-images", type=Path,
                        help="언팩된 romfs의 Data/NX/ui 폴더. 직접 번역한 텍스처의 크기가 "
                             "원본과 같은지 대조하는 데 쓴다.")
    parser.add_argument("--original-event", type=Path,
                        help="언팩된 romfs의 Event 폴더. 이벤트 스크립트(.ebd)가 직접 띄우는 "
                             "SYS:MESS 시스템 메시지를 번역하려면 필요하다.")
    parser.add_argument("--original-main", type=Path,
                        help="업데이트 1.0.1의 원본 exefs/main. 지정하면 컴파일러가 .text에 "
                             "인라인해 둔 짧은 문자열의 꼬리 바이트까지 함께 패치한다.")
    args = parser.parse_args()
    original_font = find_original_font(args.original_font)

    event_dir = TRANSLATIONS / "romfs" / "Event" / "event"
    if not event_dir.is_dir():
        raise SystemExit(f"한국어 EBM 폴더가 없습니다: {event_dir}")
    if not SYSTEM_MESSAGES.is_dir():
        raise SystemExit(f"한국어 시스템 메시지 폴더가 없습니다: {SYSTEM_MESSAGES}")

    print("=== 1/8 이벤트 대사 EBM과 한글 폰트 생성 ===")
    run([
        sys.executable, str(ROOT / "tools" / "build_final_korean_mod.py"),
        "--translated-mod", str(TRANSLATIONS),
        "--original-font", str(original_font),
        "--extra-text-dir", str(TRANSLATIONS),
        "--output", str(ATMOSPHERE),
        "--report", str(BUILD_REPORT),
    ])

    print("\n=== 2/8 시스템 메시지와 UI XML 생성 ===")
    run([
        sys.executable, str(ROOT / "tools" / "build_system_message.py"),
        "--input", str(SAVES_TRANSLATIONS),
        "--mapping", str(BUILD_REPORT),
        "--output", str(ATMOSPHERE / "romfs" / "Saves"),
    ])

    print("\n=== 3/8 업데이트 1.0.1 동적 UI 패치 생성 ===")
    command = [
        sys.executable, str(ROOT / "tools" / "build_main_text_patch.py"),
        "--translations", str(TRANSLATIONS / "exefs" / "main_1.0.1.csv"),
        "--mapping", str(BUILD_REPORT),
        "--output", str(ROOT / "atmosphere"),
    ]
    if args.original_main:
        command += ["--main", str(args.original_main)]
    else:
        print("경고: --original-main 을 지정하지 않았습니다. 짧은 문자열은 컴파일러가 뒷부분을\n"
              "      .text에 상수로 심어두기 때문에, 지정하지 않으면 '용어집'처럼 짧은 메뉴 항목의\n"
              "      끝부분이 일본어로 남거나 빈 네모로 표시됩니다.")
    run(command)

    other_saves = [
        p for p in SAVES_TRANSLATIONS.glob("*")
        if p.is_dir() and p.name not in {"systemMessage", "ui"}
    ]
    print("\n=== 4/8 게임 데이터 Saves/*.xml.e 생성 ===")
    if other_saves:
        run([
            sys.executable, str(ROOT / "tools" / "build_saves_data.py"),
            "--input", str(SAVES_TRANSLATIONS),
            "--original", str(ROOT / "originalText" / "romfs" / "Saves"),
            "--mapping", str(BUILD_REPORT),
            "--output", str(ATMOSPHERE / "romfs" / "Saves"),
        ])
    else:
        print(f"건너뜀: {SAVES_TRANSLATIONS}에 systemMessage/ui 외의 번역이 아직 없습니다 "
              "(item, misogi, tweet 등은 originalText에서 추출만 된 상태).")

    print("\n=== 5/8 대화 선택지 balloonseldata.bsb 생성 ===")
    if BALLOONSEL.is_file() and args.original_balloonsel:
        run([
            sys.executable, str(ROOT / "tools" / "build_balloonsel.py"),
            "--input", str(BALLOONSEL),
            "--original", str(args.original_balloonsel),
            "--mapping", str(BUILD_REPORT),
            "--output", str(ATMOSPHERE / "romfs" / "Event" / "balloonsel" / "balloonseldata.bsb"),
        ])
    elif not BALLOONSEL.is_file():
        print(f"건너뜀: 선택지 번역이 없습니다 ({BALLOONSEL})")
    else:
        print("경고: --original-balloonsel 을 지정하지 않았습니다. 대화 선택지가 일본어로 남고,\n"
              "      그 안의 한자 일부가 한글 대체 셀과 겹쳐 엉뚱한 한글로 표시됩니다.")

    print("\n=== 6/8 이벤트 스크립트 SYS:MESS 번역 ===")
    if args.original_event:
        run([
            sys.executable, str(ROOT / "tools" / "build_event_sysmess.py"),
            "--original", str(args.original_event),
            "--mapping", str(BUILD_REPORT),
            "--output", str(ATMOSPHERE / "romfs" / "Event"),
        ])
    else:
        print("경고: --original-event 를 지정하지 않았습니다. 이벤트 스크립트(.ebd)가 직접\n"
              "      띄우는 시스템 메시지가 일본어로 남고, 그 한자가 한글 대체 셀과 겹쳐\n"
              "      엉뚱한 한글로 표시됩니다.")

    print("\n=== 7/8 번역한 UI 텍스처 적용 ===")
    if UI_IMAGES.is_dir() and any(UI_IMAGES.glob("*.g1t")):
        command = [
            sys.executable, str(ROOT / "tools" / "build_ui_images.py"),
            "--input", str(UI_IMAGES),
            "--output", str(ATMOSPHERE / "romfs"),
        ]
        if args.original_ui_images:
            command += ["--original", str(args.original_ui_images)]
        run(command)
    else:
        print(f"건너뜀: 번역한 .g1t 가 없습니다 ({UI_IMAGES})")

    print("\n=== 8/8 60FPS 제한 해제 IPS 생성 ===")
    command = [
        sys.executable, str(ROOT / "tools" / "build_fps_unlock_patch.py"),
        "--output", str(ROOT / "atmosphere"),
    ]
    if args.original_main:
        command += ["--main", str(args.original_main)]
    run(command)

    print("\n전체 빌드 완료")
    print(f"출력: {ATMOSPHERE}")
    print(f"매핑 보고서: {BUILD_REPORT}")


if __name__ == "__main__":
    main()
