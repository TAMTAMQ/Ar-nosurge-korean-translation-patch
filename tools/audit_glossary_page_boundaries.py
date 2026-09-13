#!/usr/bin/env python3
"""Audit glossary page text against the confirmed glossary layout.

Glossary page 1 has five visible text rows total.  The first row is occupied by
``【category】``, therefore description text may use only four rows.  Page 2 has
12 rows.  Both pages wrap at 23 visible units per row.

The executable stores long glossary entries as adjacent fixed-size strings.  A
Japanese record boundary is not a valid Korean sentence boundary, so this audit
also reports first/second page text that exceeds the Korean display budget.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
MAIN = REPO / "translations" / "exefs" / "main_1.0.1.csv"
PREFIX = "<CLEG>【"
LINE_CHARS = 23
PAGE1_BODY_LINES = 4
PAGE2_LINES = 12
PAGE1_BODY_UNITS = LINE_CHARS * PAGE1_BODY_LINES
PAGE2_UNITS = LINE_CHARS * PAGE2_LINES
CONTROL = re.compile(r"<#[0-9A-Fa-f]+>|<[A-Za-z][A-Za-z0-9_]*>")


def visible_units(text: str) -> int:
    return len(CONTROL.sub("", text))


def category_and_body(text: str) -> tuple[str, str]:
    if "<CR>" not in text:
        return text, ""
    category, body = text.split("<CR>", 1)
    return category, body


JP_TERMINAL = tuple("。！？）」』】")


def is_continuation(first_original: str, next_original: str) -> bool:
    """True when the Japanese first-page record visibly continues in next record."""
    return (
        bool(first_original)
        and not first_original.rstrip().endswith(JP_TERMINAL)
        and bool(next_original)
        and not next_original.startswith(PREFIX)
        and not next_original.startswith("<CLEG>")
    )


def main() -> int:
    csv.field_size_limit(1 << 30)
    with MAIN.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    first_over = []
    second_over = []
    split_blocks = []

    for i, row in enumerate(rows):
        original = row["original"]
        translation = row["translation"]
        if not original.startswith(PREFIX) or not translation:
            continue

        category, body = category_and_body(translation)
        body_units = visible_units(body)
        continuation = None
        if i + 1 < len(rows) and is_continuation(original, rows[i + 1]["original"]):
            continuation = rows[i + 1]

        if body_units > PAGE1_BODY_UNITS:
            first_over.append((row, category, body_units, continuation))

        if continuation is not None:
            split_blocks.append((row, continuation))
            second_units = visible_units(continuation["translation"])
            if second_units > PAGE2_UNITS:
                second_over.append((row, continuation, second_units))

    print(
        f"page1 body budget: {LINE_CHARS}x{PAGE1_BODY_LINES}={PAGE1_BODY_UNITS} / "
        f"page2 budget: {LINE_CHARS}x{PAGE2_LINES}={PAGE2_UNITS}"
    )
    print(f"split glossary blocks: {len(split_blocks)}")
    print(f"page1 overflow: {len(first_over)}")
    for row, category, units, continuation in first_over:
        next_index = continuation["index"] if continuation else "-"
        print(
            f"P1_OVER index={row['index']} units={units} next={next_index} "
            f"category={category} ko={row['translation']!r}"
        )
    print(f"page2 overflow: {len(second_over)}")
    for first, second, units in second_over:
        print(
            f"P2_OVER first={first['index']} index={second['index']} units={units} "
            f"ko={second['translation']!r}"
        )

    return 1 if first_over or second_over else 0


if __name__ == "__main__":
    raise SystemExit(main())
