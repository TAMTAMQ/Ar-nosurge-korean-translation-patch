#!/usr/bin/env python3
"""Build or install rebuilt Event/Saves text data for the PC game PAKs.

Unlike build_pc_package.py --install this intentionally does NOT touch
PACK00_01 (font/UI textures) or ArnosurgeDX.exe.  It rebuilds PACK01 and PACK02
from the preserved pristine backups and overlays the complete already-built PC
Event/Saves staging trees, so unrelated event-script patches remain present.
Pass --output-dir to build standalone PAK payloads without modifying the game.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from build_pc_package import backup, extract_pak, overlay, repack_pak

REPO = Path(__file__).resolve().parents[1]


def install_one(game_pak: Path, source_root: Path, work: Path, gust_pak: Path,
                staging_name: str, target_subdir: str, label: str,
                output_dir: Path | None = None) -> None:
    pristine = backup(game_pak, work)
    staging = work / "staging_text_only" / staging_name
    if staging.exists():
        shutil.rmtree(staging)
    manifest = extract_pak(gust_pak, pristine, staging)
    overlay(source_root, manifest.parent / target_subdir, label)
    built = repack_pak(gust_pak, manifest)
    destination = game_pak if output_dir is None else output_dir / game_pak.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(built, destination)
    if not destination.is_file() or destination.stat().st_size != built.stat().st_size:
        raise SystemExit(f"PAK 출력 후 크기 검증 실패: {destination}")
    action = "설치" if output_dir is None else "빌드"
    print(f"  {action}: {destination} ({destination.stat().st_size} bytes)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game-dir", type=Path,
                    default=REPO / "Ar.Nosurge.DX_PC")
    ap.add_argument("--work", type=Path, default=REPO / "build" / "pc")
    ap.add_argument("--gust-pak", type=Path,
                    default=Path("D:/trans/gust_tools/gust_pak.exe"))
    ap.add_argument("--event", type=Path, default=REPO / "build" / "pc" / "event")
    ap.add_argument("--saves", type=Path, default=REPO / "build" / "pc" / "saves_out")
    ap.add_argument("--output-dir", type=Path,
                    help="게임을 수정하지 않고 PACK01/02를 이 폴더에 빌드")
    args = ap.parse_args()

    if not args.game_dir.is_dir():
        raise SystemExit(f"게임 폴더가 없습니다: {args.game_dir}")
    if not args.gust_pak.is_file():
        raise SystemExit(f"gust_pak.exe가 없습니다: {args.gust_pak}")
    if not args.event.is_dir() or not args.saves.is_dir():
        raise SystemExit("PC Event/Saves staging을 먼저 빌드해야 합니다")

    print("[1/2] PACK01 Event 재포장")
    install_one(
        args.game_dir / "Data" / "PACK01.PAK",
        args.event,
        args.work,
        args.gust_pak,
        "PACK01",
        "event",
        "Event",
        args.output_dir,
    )

    print("\n[2/2] PACK02 Saves 재포장")
    install_one(
        args.game_dir / "Data" / "PACK02.PAK",
        args.saves,
        args.work,
        args.gust_pak,
        "PACK02",
        "saves",
        "Saves",
        args.output_dir,
    )

    if args.output_dir is None:
        print("\n완료: PACK00_01 / ArnosurgeDX.exe 변경 없음")
    else:
        print(f"\n완료: 게임 파일 변경 없이 출력: {args.output_dir}")


if __name__ == "__main__":
    main()
