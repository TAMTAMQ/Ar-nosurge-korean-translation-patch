#!/usr/bin/env python3
"""main 번역을 고정 슬롯에 맞게 공백 제거 후 의미 보존 축약한다."""

import argparse
import csv
import json
import re
import time
import urllib.request
from pathlib import Path

from translate_main_japanese import JP, PROTECTED, GLOSSARY, protected_tokens


def byte_len(text):
    return len(text.encode("utf-8"))


def call_model(args, rows, reasons):
    items = [{"id": row["index"], "japanese": row["original"],
              "current_korean": row["translation"],
              "capacity_bytes": int(row["capacity_bytes"]),
              "maximum_korean_syllables": int(row["capacity_bytes"]) // 3,
              "retry_reason": reasons.get(row["index"], "")}
             for row in rows]
    system = f"""일본어 게임 문구를 매우 짧고 자연스러운 한국어로 축약한다.
반드시 {{"translations":[{{"id":"id","translation":"결과"}}]}} JSON만 출력한다.
모든 id를 정확히 한 번 반환한다. 번역은 UTF-8 capacity_bytes 이하여야 한다.
한국어 음절은 3바이트, ASCII 문자는 1바이트다. 띄어쓰기는 사용하지 않는다.
조사·주어·종결어미를 생략하고 짧은 동의어를 사용하되 핵심 의미는 보존한다.
단어 중간을 자르거나 불완전한 문장을 만들지 않는다.
<CR>, <IM00>, printf 형식 등 원문의 제어 토큰은 철자·개수·순서를 그대로 유지한다.
일본어 문자를 남기지 않는다. maximum_korean_syllables를 절대로 넘지 않는다.
예: 선택 시작→선택개시, 내가 싸우겠다!→내가싸운다!, 아무것도 하지 않는다→대기.
용어집: {GLOSSARY}"""
    body = {"model": args.model, "temperature": 0.1, "max_tokens": 4096,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": json.dumps(items, ensure_ascii=False)}]}
    request = urllib.request.Request(args.base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=900) as response:
        outer = json.loads(response.read().decode())
    content = outer["choices"][0]["message"]["content"].strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I)
    parsed = json.JSONDecoder().raw_decode(content)[0]
    if isinstance(parsed, dict):
        parsed = parsed.get("translations")
    return {str(item["id"]): str(item["translation"]) for item in parsed}


def valid(row, text):
    errors = []
    if not text:
        errors.append("empty")
    if byte_len(text) > int(row["capacity_bytes"]):
        errors.append(f'overflow:{byte_len(text)}>{row["capacity_bytes"]}')
    if JP.search(text):
        errors.append("japanese_remaining")
    if protected_tokens(text) != protected_tokens(row["original"]):
        errors.append("protected_token_mismatch")
    return errors


def save(path, rows, fields):
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def main():
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=repo / "translations" / "exefs" / "main_1.0.1.csv")
    parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", default="gemma-4-26b-a4b-it-qat")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--attempts", type=int, default=6)
    parser.add_argument("--retry-manual", action="store_true")
    args = parser.parse_args()
    csv.field_size_limit(1 << 30)
    with args.input.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = list(reader)

    removed_spaces = 0
    pending = []
    for row in rows:
        eligible = row["status"] == "needs_review" or (
            args.retry_manual and row["status"] == "needs_manual_translation"
        )
        if not eligible:
            continue
        if row["status"] == "needs_review" and row["translation"] and (
                byte_len(row["translation"]) <= int(row["capacity_bytes"])):
            continue
        compact = re.sub(r"[ \u3000]+", "", row["translation"] or "")
        if compact and not valid(row, compact):
            row["translation"] = compact
            row["notes"] = "compacted:spaces_removed"
            removed_spaces += 1
        else:
            pending.append(row)
    save(args.input, rows, fields)
    print(f"spaces_removed={removed_spaces}; needs_word_compaction={len(pending)}", flush=True)

    for start in range(0, len(pending), args.batch_size):
        unresolved = pending[start:start + args.batch_size]
        reasons = {}
        accepted = {}
        for attempt in range(args.attempts):
            if not unresolved:
                break
            try:
                results = call_model(args, unresolved, reasons)
            except Exception as exc:
                print(f"retry {attempt + 1}: {exc}", flush=True)
                time.sleep(1)
                continue
            again = []
            reasons = {}
            for row in unresolved:
                rid = row["index"]
                text = re.sub(r"[ \u3000]+", "", results.get(rid, "").strip())
                errors = valid(row, text)
                if errors:
                    reasons[rid] = ",".join(errors)
                    again.append(row)
                else:
                    accepted[rid] = text
            unresolved = again
        for row in pending[start:start + args.batch_size]:
            if row["index"] in accepted:
                row["translation"] = accepted[row["index"]]
                row["status"] = "needs_review"
                row["notes"] = "compacted:word_abbreviation"
            else:
                row["status"] = "needs_manual_translation"
                row["notes"] = "compaction_failed:" + reasons.get(row["index"], "model_failed")
        save(args.input, rows, fields)
        print(f"compacted={min(start + args.batch_size, len(pending))}/{len(pending)}; "
              f"batch_failed={len(unresolved)}", flush=True)

    overflows = sum(row["translation"] and byte_len(row["translation"]) > int(row["capacity_bytes"])
                    for row in rows if row["status"] == "needs_review")
    manual = sum(row["status"] == "needs_manual_translation" for row in rows)
    print(json.dumps({"overflows": overflows, "needs_manual_translation": manual},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
