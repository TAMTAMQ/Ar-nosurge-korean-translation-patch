#!/usr/bin/env python3
"""직접 번역한 UI 텍스처(`translateImage/*.g1t`)를 설치 폴더에 넣는다.

메뉴·시스템 화면의 일본어 상당수는 텍스트가 아니라 텍스처에 그려져 있어서
텍스트 패치로는 손댈 수 없다. 그 부분은 GIMP로 직접 고쳐 `translateImage/`에
`.g1t` 로 두고, 이 단계에서 `romfs/Data/NX/ui/` 로 복사한다.

`.png`/`.xcf` 는 작업 원본이라 복사하지 않는다.

넣기 전에 두 가지를 확인한다.

* G1T 매직(`GT1G`)이 맞는지 — 엉뚱한 파일을 넣어 게임이 죽는 것을 막는다.
* 원본과 크기가 같은지 — 이 텍스처들은 자리를 그대로 두고 픽셀만 고치는
  방식이라, 크기가 달라졌다면 구조가 깨졌다는 뜻이다.

원본 romfs 경로를 주지 않으면 크기 검사는 건너뛰고 매직만 확인한다.
"""

import argparse
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAGIC = b"GT1G"
UI_SUBPATH = Path("Data") / "NX" / "ui"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=REPO / "translateImage",
                        help="번역한 .g1t 가 든 폴더")
    parser.add_argument("--original", type=Path,
                        help="언팩된 romfs의 Data/NX/ui 폴더. 주면 크기를 대조한다.")
    parser.add_argument("--output", type=Path, required=True,
                        help="설치용 romfs 폴더 (Data/NX/ui 를 그 아래에 만든다)")
    args = parser.parse_args()

    if not args.input.is_dir():
        print(f"건너뜀: 번역 이미지 폴더가 없습니다 ({args.input})")
        return

    images = sorted(args.input.glob("*.g1t"))
    if not images:
        print(f"건너뜀: {args.input}에 .g1t 가 없습니다")
        return

    destination = args.output / UI_SUBPATH
    destination.mkdir(parents=True, exist_ok=True)
    for image in images:
        data = image.read_bytes()
        if not data.startswith(MAGIC):
            raise SystemExit(f"G1T 파일이 아닙니다: {image} (앞 4바이트 {data[:4]!r})")
        if args.original:
            source = args.original / image.name
            if not source.is_file():
                raise SystemExit(f"원본에 없는 텍스처입니다: {image.name}")
            if source.stat().st_size != len(data):
                raise SystemExit(
                    f"{image.name}: 크기가 원본과 다릅니다 "
                    f"({len(data)} != {source.stat().st_size}). 구조가 깨졌을 수 있습니다.")
        shutil.copy2(image, destination / image.name)
        print(f"built: {destination / image.name} ({len(data):,}바이트)")
    print(f"UI 텍스처 {len(images)}개 적용")


if __name__ == "__main__":
    main()
