#!/usr/bin/env python3
"""검수한 main 수동 축약표를 CSV에 적용하고 제약을 검증한다."""

import csv
import json
from pathlib import Path

from translate_main_japanese import JP, protected_tokens


def main():
    repo = Path(__file__).resolve().parents[1]
    csv_path = repo / "translations" / "exefs" / "main_1.0.1.csv"
    overrides_path = repo / "translations" / "exefs" / "main_1.0.1_manual_compaction.json"
    overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
    csv.field_size_limit(1 << 30)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = list(reader)
    found = set()
    for row in rows:
        index = row["index"]
        if index not in overrides:
            continue
        text = overrides[index]
        errors = []
        used = len(text.encode("utf-8"))
        if used > int(row["capacity_bytes"]):
            errors.append(f'overflow:{used}>{row["capacity_bytes"]}')
        if JP.search(text):
            errors.append("japanese_remaining")
        if protected_tokens(text) != protected_tokens(row["original"]):
            errors.append("protected_token_mismatch")
        if errors:
            raise SystemExit(f"index {index}: {','.join(errors)}: {text}")
        row["translation"] = text
        row["status"] = "needs_review"
        row["notes"] = "compacted:manual_override"
        found.add(index)
    missing = set(overrides) - found
    if missing:
        raise SystemExit(f"CSV에 없는 index: {sorted(missing)}")
    temp = csv_path.with_suffix(".csv.tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(csv_path)
    print(f"수동 축약 적용: {len(found)}개")


if __name__ == "__main__":
    main()
