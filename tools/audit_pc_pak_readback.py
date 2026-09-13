#!/usr/bin/env python3
"""Extract installed PC PACK01/PACK02 and compare them with rebuilt staging.

The offsets printed by gust_pak -l are container metadata and are not a safe
substitute for extraction/readback on PACK01/PACK02.  This audit copies each
installed PAK into a disposable build directory, extracts it with gust_pak,
and byte-compares every file that install_pc_text_data.py overlays.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from build_pc_package import extract_pak


REPO = Path(__file__).resolve().parents[1]


def compare_tree(expected: Path, actual: Path, label: str) -> tuple[int, int, int]:
    actual_files = {
        path.relative_to(actual).as_posix().lower(): path
        for path in actual.rglob("*")
        if path.is_file()
    }
    total = 0
    missing: list[str] = []
    mismatched: list[str] = []
    for source in sorted(path for path in expected.rglob("*") if path.is_file()):
        total += 1
        rel = source.relative_to(expected).as_posix()
        target = actual_files.get(rel.lower())
        if target is None:
            missing.append(rel)
            continue
        if source.read_bytes() != target.read_bytes():
            mismatched.append(rel)

    print(
        f"{label}: expected={total} exact={total - len(missing) - len(mismatched)} "
        f"missing={len(missing)} mismatch={len(mismatched)}"
    )
    for rel in missing[:10]:
        print(f"  missing: {rel}")
    for rel in mismatched[:10]:
        print(f"  mismatch: {rel}")
    return total, len(missing), len(mismatched)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game-dir", type=Path, default=REPO / "Ar.Nosurge.DX_PC")
    ap.add_argument("--work", type=Path, default=REPO / "build" / "pc")
    ap.add_argument("--gust-pak", type=Path, default=Path("D:/trans/gust_tools/gust_pak.exe"))
    ap.add_argument("--event", type=Path, default=REPO / "build" / "pc" / "event")
    ap.add_argument("--saves", type=Path, default=REPO / "build" / "pc" / "saves_out")
    args = ap.parse_args()

    if not args.gust_pak.is_file():
        raise SystemExit(f"gust_pak.exe가 없습니다: {args.gust_pak}")

    cases = [
        ("PACK01 Event", args.game_dir / "Data" / "PACK01.PAK", args.event, "event", "PACK01"),
        ("PACK02 Saves", args.game_dir / "Data" / "PACK02.PAK", args.saves, "saves", "PACK02"),
    ]

    failures = 0
    for label, pak, expected, subdir, name in cases:
        if not pak.is_file():
            raise SystemExit(f"설치 PAK가 없습니다: {pak}")
        if not expected.is_dir():
            raise SystemExit(f"비교 staging이 없습니다: {expected}")
        readback = args.work / "pak_readback" / name
        if readback.exists():
            shutil.rmtree(readback)
        manifest = extract_pak(args.gust_pak, pak, readback)
        _total, missing, mismatch = compare_tree(expected, manifest.parent / subdir, label)
        failures += missing + mismatch

    if failures:
        raise SystemExit(f"PC PAK readback 실패: {failures}개")
    print("PC PAK readback PASS")


if __name__ == "__main__":
    main()
