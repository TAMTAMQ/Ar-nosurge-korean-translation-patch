#!/usr/bin/env python3
"""Validate record-guarded Event translation review fixes without writing EBM files."""
from __future__ import annotations

import re
from pathlib import Path

from event_translation_review_fixes import FIXES
from text_layout import EVENT_LINE_WRAP_CHARS, MAX_LINES, reflow_event_dialogue_layout, rendered_line_count

REPO = Path(__file__).resolve().parents[1]
EVENT_ROOT = REPO / "translations" / "romfs" / "Event" / "event"
RECORD_HEADER = 32
CONTROL = re.compile(r"<(?!CR>)[^<>]+>")


def read_records(path: Path) -> list[str]:
    data = path.read_bytes()
    count = int.from_bytes(data[:4], "little")
    pos = 4
    records: list[str] = []
    for index in range(count):
        if pos + RECORD_HEADER + 4 > len(data):
            raise RuntimeError(f"header truncated: {path}:{index}")
        length = int.from_bytes(data[pos + RECORD_HEADER:pos + RECORD_HEADER + 4], "little")
        start = pos + RECORD_HEADER + 4
        end = start + length
        payload = data[start:end]
        if end > len(data) or not payload.endswith(b"\x00"):
            raise RuntimeError(f"framing error: {path}:{index}")
        records.append(payload[:-1].decode("utf-8"))
        pos = end
    if pos != len(data):
        raise RuntimeError(f"trailing bytes: {path}:{len(data) - pos}")
    return records


def main() -> None:
    duplicate_keys: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    guard_failures: list[str] = []
    control_failures: list[str] = []
    layout_failures: list[str] = []
    cache: dict[str, list[str]] = {}

    for fix in FIXES:
        key = (fix.path, fix.index)
        if key in seen:
            duplicate_keys.append(key)
        seen.add(key)

        records = cache.setdefault(fix.path, read_records(EVENT_ROOT / fix.path))
        if fix.index >= len(records):
            guard_failures.append(f"{fix.path}:{fix.index}: index >= {len(records)}")
            continue
        current = records[fix.index]
        if current not in {fix.old, fix.new}:
            guard_failures.append(
                f"{fix.path}:{fix.index}: guard mismatch\n"
                f"  current={current!r}\n  old={fix.old!r}\n  new={fix.new!r}"
            )

        old_controls = CONTROL.findall(fix.old)
        new_controls = CONTROL.findall(fix.new)
        if old_controls != new_controls:
            control_failures.append(
                f"{fix.path}:{fix.index}: {old_controls!r} != {new_controls!r}"
            )

        laid_out = reflow_event_dialogue_layout(fix.new)
        lines = rendered_line_count(laid_out, EVENT_LINE_WRAP_CHARS)
        if lines > MAX_LINES:
            layout_failures.append(
                f"{fix.path}:{fix.index}: {lines} lines after reflow: {laid_out!r}"
            )

    print(
        f"fixes={len(FIXES)} unique={len(seen)} duplicates={len(duplicate_keys)} "
        f"guard_failures={len(guard_failures)} control_failures={len(control_failures)} "
        f"layout_failures={len(layout_failures)}"
    )
    for title, failures in (
        ("duplicate", [f"{p}:{i}" for p, i in duplicate_keys]),
        ("guard", guard_failures),
        ("control", control_failures),
        ("layout", layout_failures),
    ):
        for failure in failures[:50]:
            print(f"[{title}] {failure}")

    if duplicate_keys or guard_failures or control_failures or layout_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
