#!/usr/bin/env python3
"""Undo compaction on `main` strings that actually had room to spare.

`compact_main_translations.py` strips spaces and abbreviates words so a
translation fits its fixed rodata slot. It ran before the final glyph mapping
existed, so a lot of rows ended up far shorter than the slot allows — row 6119
used 168 of 242 bytes while reading like a telegram.

This pass re-translates only the rows that still have headroom, tells the model
the exact byte budget, and keeps the new text only when it fits and is
genuinely more natural (more spacing, no lost control tokens).
"""

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from translate_saves_with_ollama import GLOSSARY, JP, local_chat, lock_tokens, unlock_tokens

REPO = Path(__file__).resolve().parents[1]
CSV_PATH = REPO / "translations" / "exefs" / "main_1.0.1.csv"
MAPPING = REPO / "build" / "final_mod_report.json"
CACHE = REPO / "build" / "main_expand_cache.json"

CTRL_ANY = re.compile(r"<[^>]{1,20}>")
HONORIFIC = re.compile(r"씨|님|짱|쨩|군|선배|선생님")
# Japanese honorifics that legitimately license a Korean one.
JP_HONORIFIC = re.compile(r"さん|様|ちゃん|くん|君|先輩|先生")
# Spellings already established across the rest of the patch. A re-translation
# must not reintroduce a variant (e.g. 제놈라이 for ジェノミライ).
NAME_RULES = {
    "ジェノミライ": "제노미라이", "アルシエル": "아르시엘", "サーリ": "살리",
    "にゅろきー": "뉴로키", "レナルル": "레나루루", "ネィアフラスク": "네이아플라스크",
    "カノイール": "카노일", "ククルル": "쿠쿠루루", "リアノイト": "리어노이트",
    "タータルカ": "타타르카", "コーザル": "코잘", "シュレリア": "슈레리아",
    "プリシェール": "프리셰르", "白鷹": "시로타카", "ジェノム": "제놈",
    "ソレイル": "소레일", "シャール": "샤르",
}


def quote_counts(text):
    return tuple(text.count(c) for c in "「」『』")


def content_bytes(text, mapping):
    return len("".join(mapping.get(c, c) for c in text if c != " ").encode("utf-8"))


def byte_length(text, mapping):
    return len("".join(mapping.get(c, c) for c in text).encode("utf-8"))


def tokens_of(text):
    return CTRL_ANY.findall(text)


def main():
    csv.field_size_limit(1 << 30)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", default="gemma-4-26b-a4b-it-qat")
    parser.add_argument("--batch-size", type=int, default=6)
    parser.add_argument("--min-headroom", type=int, default=1,
                        help="이 바이트 수보다 여유가 큰 행만 손댄다")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))["hangul_to_standin"]
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = list(reader)

    targets = []
    for row in rows:
        if not row["notes"].startswith("compacted") or not row["translation"]:
            continue
        capacity = int(row["capacity_bytes"])
        used = byte_length(row["translation"], mapping)
        if capacity - used >= args.min_headroom:
            targets.append((row, capacity, used))
    print(f"대상 {len(targets)}행 (여유 >= {args.min_headroom}B)")

    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.is_file() else {}
    pending = [t for t in targets if t[0]["index"] not in cache]
    print(f"이번에 요청할 행 {len(pending)}개 (캐시 {len(cache)}개)")

    system_extra = (
        "각 항목에는 budget(바이트 예산)이 있다. 번역문은 반드시 예산 이내여야 한다.\n"
        "한글 한 글자는 3바이트, 공백과 숫자와 영문은 1바이트로 계산한다.\n"
        "예산이 허락하는 한 띄어쓰기를 정상적으로 넣고 자연스러운 문장으로 쓴다.\n"
        "예산을 넘길 것 같으면 어미를 줄이거나 조사를 생략해서 맞춘다.\n"
        "[[CTRL_n]] 토큰은 개수와 순서를 그대로 유지한다.\n"
        "원문의 「」 『』 는 그대로 「」 『』 로 옮긴다. 따옴표로 바꾸지 않는다.\n"
        "원문에 さん 様 ちゃん くん 先輩 先生 이 없으면 한국어에 씨/님/짱/군을 새로 붙이지 않는다.\n"
        "シャール는 종족명이므로 항상 그냥 샤르로 쓴다. ジェノミライ는 제노미라이, "
        "アルシエル는 아르시엘로 쓴다.\n"
        f"용어집: {GLOSSARY}"
    )

    for start in range(0, len(pending), args.batch_size):
        batch = pending[start:start + args.batch_size]
        items, locks = [], {}
        for row, capacity, used in batch:
            locked, toks = lock_tokens(row["original"])
            locks[row["index"]] = (row, capacity, toks)
            items.append({"id": row["index"], "source": locked,
                          "budget": capacity, "hint": system_extra if False else ""})
        payload = [{"id": i["id"], "source": i["source"], "budget": i["budget"]}
                   for i in items]
        for attempt in range(1, 5):
            try:
                answer = local_chat(args.base_url, args.model,
                                    [{"id": "_rules", "source": system_extra}] + payload)
            except Exception as error:                       # noqa: BLE001
                print(f"  재시도 {attempt}/4: {error}")
                time.sleep(2)
                continue
            break
        else:
            continue
        for index, (row, capacity, toks) in locks.items():
            if index not in answer:
                continue
            text = unlock_tokens(answer[index].strip(), toks)
            cache[index] = text
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  {min(start + args.batch_size, len(pending))}/{len(pending)}")

    # The model routinely overshoots the budget on the first pass. Feed the
    # measured byte count back and let it trim, rather than throwing the
    # candidate away and keeping the telegram-style text.
    def refit(row, capacity, text):
        for _ in range(4):
            size = byte_length(text, mapping)
            if size <= capacity:
                return text
            locked, toks = lock_tokens(text)
            request = [
                {"id": "_rules", "source":
                 "아래 한국어 문장을 예산 이내로 줄여라. 뜻은 유지한다.\n"
                 "한글 1글자=3바이트, 공백/숫자/영문=1바이트.\n"
                 "먼저 군더더기 어미와 조사를 줄이고, 그래도 넘치면 띄어쓰기를 지운다.\n"
                 "[[CTRL_n]] 토큰은 개수와 순서를 그대로 둔다.\n"
                 "출력은 줄인 한국어 문장만."},
                {"id": row["index"], "source": locked,
                 "budget": capacity, "current_bytes": size},
            ]
            try:
                answer = local_chat(args.base_url, args.model, request)
            except Exception:                                # noqa: BLE001
                return text
            if row["index"] not in answer:
                return text
            text = unlock_tokens(answer[row["index"]].strip(), toks)
        # Last resort: drop spaces from the right until it fits, so the row
        # keeps as much normal spacing as the slot can pay for.
        while byte_length(text, mapping) > capacity and " " in text:
            cut = text.rfind(" ")
            text = text[:cut] + text[cut + 1:]
        return text

    for row, capacity, used in targets:
        candidate = cache.get(row["index"])
        if candidate and byte_length(candidate, mapping) > capacity:
            fixed = refit(row, capacity, candidate)
            if byte_length(fixed, mapping) <= capacity:
                cache[row["index"]] = fixed
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    accepted = rejected = 0
    reasons = {}
    for row, capacity, used in targets:
        candidate = cache.get(row["index"])
        if not candidate:
            continue
        why = None
        if tokens_of(candidate) != tokens_of(row["original"]):
            why = "제어토큰 불일치"
        elif JP.search(candidate):
            why = "일본어 잔존"
        elif byte_length(candidate, mapping) > capacity:
            why = "용량 초과"
        elif quote_counts(candidate) != quote_counts(row["original"]):
            why = "「」 개수 불일치"
        elif (len(HONORIFIC.findall(candidate)) > len(HONORIFIC.findall(row["translation"]))
              and not JP_HONORIFIC.search(row["original"])):
            why = "없던 호칭 추가"
        elif any(ko not in candidate for jp, ko in NAME_RULES.items()
                 if jp in row["original"]):
            why = "고유명사 표기 불일치"
        elif content_bytes(candidate, mapping) < content_bytes(row["translation"], mapping) * 0.95:
            why = "내용 손실"
        elif (candidate.count(" ") < row["translation"].count(" ")
              or candidate == row["translation"]):
            why = "더 자연스럽지 않음"
        if why:
            rejected += 1
            reasons[why] = reasons.get(why, 0) + 1
            continue
        accepted += 1
        if not args.dry_run:
            row["translation"] = candidate
            row["notes"] = "expanded:refit_to_capacity"
    print(f"\n채택 {accepted} / 기각 {rejected}  {reasons}")
    if not args.dry_run and accepted:
        with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        print(f"기록: {CSV_PATH}")


if __name__ == "__main__":
    main()
