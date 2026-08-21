#!/usr/bin/env python3
"""Translate balloonseldata.bsb選択肢 with the local model, then rebuild it."""

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from balloonsel import TRAILER, build, parse
from translate_saves_with_ollama import JP, local_chat, lock_tokens, unlock_tokens

REPO = Path(__file__).resolve().parents[1]
ORIGINAL = REPO / "originalText" / "romfs" / "Event" / "balloonsel" / "balloonseldata.json"
TRANSLATED = REPO / "translations" / "romfs" / "Event" / "balloonsel" / "balloonseldata.json"
CACHE = REPO / "build" / "balloonsel_translation_cache.json"

# Pure identifiers the game matches on, not prose. Leave them alone.
IDENTIFIER = re.compile(r"^[A-Z0-9_/.]+$")


def extract(source, destination):
    groups = parse(source.read_bytes())
    if build(groups) != source.read_bytes():
        raise SystemExit("round trip mismatch; refusing to continue")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(groups, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    total = sum(len(g) for g in groups)
    print(f"추출: 그룹 {len(groups)} / 선택지 {total} -> {destination}")
    return groups


def translatable(text):
    body = text.rstrip(TRAILER)
    return bool(JP.search(body)) and not IDENTIFIER.match(body)


def translate(groups, base_url, model, batch_size):
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.is_file() else {}
    pending = sorted({o for g in groups for o in g
                      if translatable(o) and o not in cache})
    print(f"번역 대상 {len(pending)}개 (캐시 {len(cache)}개 보유)")
    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]
        items, locks = [], {}
        for index, text in enumerate(batch):
            body = text.rstrip(TRAILER)
            locked, tokens = lock_tokens(body)
            key = f"b{start + index}"
            locks[key] = (text, tokens)
            items.append({"id": key, "source": locked})
        for attempt in range(1, 6):
            try:
                answer = local_chat(base_url, model, items)
            except Exception as error:                      # noqa: BLE001
                print(f"  재시도 {attempt}/5: {error}")
                time.sleep(2)
                continue
            missing = [k for k in locks if k not in answer]
            if missing and attempt < 5:
                print(f"  누락 {len(missing)}개, 재시도 {attempt}/5")
                continue
            for key, (original, tokens) in locks.items():
                if key not in answer:
                    continue
                value = unlock_tokens(answer[key].strip(), tokens)
                # The game pads balloons with the trailing ideographic space.
                if original.endswith(TRAILER):
                    value = value.rstrip(TRAILER) + TRAILER
                cache[original] = value
            break
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1),
                         encoding="utf-8")
        done = min(start + batch_size, len(pending))
        print(f"  {done}/{len(pending)}")
    return cache


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True,
                        help="원본 balloonseldata.bsb")
    parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", default="gemma-4-26b-a4b-it-qat")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--extract-only", action="store_true")
    args = parser.parse_args()

    groups = extract(args.source, ORIGINAL)
    if args.extract_only:
        return
    cache = translate(groups, args.base_url, args.model, args.batch_size)

    translated = [[cache.get(o, o) for o in g] for g in groups]
    TRANSLATED.parent.mkdir(parents=True, exist_ok=True)
    TRANSLATED.write_text(json.dumps(translated, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    left = sum(1 for g in translated for o in g if JP.search(o.rstrip(TRAILER)))
    print(f"기록: {TRANSLATED}")
    print(f"일본어 잔존 선택지: {left}")


if __name__ == "__main__":
    main()
