#!/usr/bin/env python3
"""Build Event EBM files with the existing verified Hangul mapping.

This is useful for PC test installs when text changed but no new Hangul glyphs
were introduced. It applies the same event layout rules and confirmed glossary
false-link fixes as build_final_korean_mod.py, then substitutes Hangul with the
already verified stand-in mapping without regenerating the font.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_final_korean_mod import rebuild_ebm_with_layout
from fix_glossary_false_links import FIXES as GLOSSARY_FALSE_LINK_FIXES


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--input",
        type=Path,
        default=repo / "translations" / "romfs" / "Event" / "event",
    )
    ap.add_argument(
        "--mapping",
        type=Path,
        default=repo / "build" / "final_mod_report.json",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=repo / "build" / "pc" / "event" / "event",
    )
    args = ap.parse_args()

    report = json.loads(args.mapping.read_text(encoding="utf-8"))
    mapping = report["hangul_to_standin"]
    sources = sorted(args.input.rglob("*.ebm"))
    if not sources:
        raise SystemExit(f"EBM이 없습니다: {args.input}")

    built = 0
    replaced = 0
    removed_cr = 0
    glossary_fixed = 0
    for src in sources:
        rel = src.relative_to(args.input)
        data, removed, fixed = rebuild_ebm_with_layout(
            src.read_bytes(), src, rel.as_posix()
        )
        removed_cr += removed
        glossary_fixed += fixed
        for ko, standin in mapping.items():
            old = ko.encode("utf-8")
            count = data.count(old)
            if count:
                data = data.replace(old, standin.encode("utf-8"))
                replaced += count
        text = data.decode("utf-8", "ignore")
        remaining = sorted({c for c in text if "가" <= c <= "힣"})
        if remaining:
            raise SystemExit(
                f"{rel.as_posix()}: 매핑되지 않은 한글이 남았습니다: {''.join(remaining)}"
            )
        dst = args.output / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        built += 1

    print(
        f"built={built} replaced={replaced} removed_cr={removed_cr} "
        f"glossary_fixed={glossary_fixed} output={args.output}"
    )
    expected_fixes = len(GLOSSARY_FALSE_LINK_FIXES)
    if glossary_fixed != expected_fixes:
        raise SystemExit(
            f"용어집 오탐 수정 적용 건수 불일치: {glossary_fixed} != {expected_fixes}"
        )


if __name__ == "__main__":
    main()
