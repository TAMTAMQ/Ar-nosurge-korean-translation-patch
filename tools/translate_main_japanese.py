#!/usr/bin/env python3
"""추출한 main 1.0.1 일본어 문자열에 로컬 모델 초벌 번역을 채운다."""

import argparse
import csv
import hashlib
import json
import re
import time
import urllib.request
from pathlib import Path


JP = re.compile(r"[ぁ-んァ-ヶ一-龯々〆ヵヶ]")
PROTECTED = re.compile(
    r"<[^<>]+>|"
    r"%(?:[-+ #0]*\d*(?:\.\d+)?(?:hh|h|ll|l|j|z|t|L)?[diuoxXfFeEgGaAcspn%])|"
    r"\\[nrt0]"
)

GLOSSARY = """
アルノサージュ/Ar nosurge=아르노사쥬, シェルノサージュ=세르노사쥬,
デルタ=델타, キャス=캐스, イオン=이온, イオナサル=이오나사르,
アーシェス=아셰스, サーリ=사리, ネイ=네이, ジル=질, プリム=프림,
カノン=카논, シュレリア=슈레리아, タットリア=타토리아,
ジェノム=제놈, ジェノメトリクス=제노메트릭스, シャール=샤르,
詩魔法=시마법, 想い=마음, ソレイル=소레일, ラシェーラ=라셸라,
セカイリンク=세카이 링크, TxBIOS=TxBIOS, バースト=버스트,
ハーモニクス=하모닉스, ガスト=가스트
""".strip()


def parse_args():
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path,
        default=repo / "originalText" / "exefs" / "main_1.0.1_japanese.json",
    )
    parser.add_argument(
        "--output", type=Path,
        default=repo / "originalText" / "exefs" / "main_1.0.1_korean_draft.json",
    )
    parser.add_argument(
        "--csv-output", type=Path,
        default=repo / "originalText" / "exefs" / "main_1.0.1_korean_draft.csv",
    )
    parser.add_argument(
        "--cache", type=Path,
        default=repo / "build" / "main_1.0.1_translation_cache.json",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", default="gemma-4-26b-a4b-it-qat")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-attempts", type=int, default=4)
    parser.add_argument(
        "--retry-manual", action="store_true",
        help="기존 needs_manual_translation 항목도 다시 요청한다.",
    )
    parser.add_argument(
        "--allow-overflow", action="store_true",
        help="용량 초과 번역도 초안으로 보존한다(직접 패치에는 사용 금지).",
    )
    return parser.parse_args()


def stable_key(record):
    digest = hashlib.sha256(record["original"].encode("utf-8")).hexdigest()
    return f'{record["memory_address"]}:{record["capacity_bytes"]}:{digest}'


def lock_tokens(text):
    tokens = []

    def replace(match):
        tokens.append(match.group(0))
        return f"[[PROTECTED_{len(tokens) - 1}]]"

    return PROTECTED.sub(replace, text), tokens


def unlock_tokens(text, tokens):
    for index, token in enumerate(tokens):
        text = text.replace(f"[[PROTECTED_{index}]]", token)
    return text


def protected_tokens(text):
    return PROTECTED.findall(text)


def parse_response(content):
    content = content.strip()
    content = re.sub(r"^```(?:json)?\s*", "", content, count=1, flags=re.I)
    content = re.sub(r"\s*```$", "", content, count=1)
    parsed = json.JSONDecoder().raw_decode(content)[0]
    if isinstance(parsed, dict):
        parsed = parsed.get("translations") or parsed.get("items") or parsed.get("results")
    if not isinstance(parsed, list):
        raise ValueError("응답이 translations 배열이 아닙니다")
    return {str(item["id"]): str(item["translation"]) for item in parsed}


def call_model(args, items, retry_reason=""):
    system = f"""일본어 게임 문자열을 자연스럽고 간결한 한국어로 번역한다.
반드시 {{"translations":[{{"id":"입력 id","translation":"한국어"}}]}} JSON 하나만 출력한다.
모든 id를 정확히 한 번씩 반환하며 설명이나 마크다운을 출력하지 않는다.
각 항목의 translation UTF-8 바이트 수는 capacity_bytes 이하여야 한다.
max_korean_chars는 공백과 문장부호를 전혀 쓰지 않을 때 들어갈 수 있는
한글 음절 수의 상한이다. 이전 결과가 넘쳤다면 조사·공백·문장부호를 줄이고
더 짧은 동의어를 사용해 반드시 이 상한 안의 완결된 표현으로 다시 쓴다.
원문의 의미, 인물 말투, 문장 완결성을 유지하되 공간이 부족하면 자연스럽게 축약한다.
prev_source와 next_source는 문맥 참고용이며 번역 결과에 합치지 않는다.
[[PROTECTED_0]] 같은 보호 토큰은 철자, 개수, 순서, 위치를 바꾸지 않는다.
줄바꿈, 영문 식별자, 숫자, 기호와 서식 지정자는 의미상 필요하지 않으면 유지한다.
일본어 문자를 결과에 남기지 않는다. 이름과 고유명사는 아래 용어집을 따른다.
번역 결과는 사람 검토 전 초안이다.
용어집: {GLOSSARY}
재시도 사유: {retry_reason or '없음'}"""
    body = {
        "model": args.model,
        "temperature": 0.1,
        "max_tokens": 8192,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(items, ensure_ascii=False)},
        ],
    }
    request = urllib.request.Request(
        args.base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=900) as response:
        outer = json.loads(response.read().decode("utf-8"))
    return parse_response(outer["choices"][0]["message"]["content"])


def validate(record, translation, allow_overflow=False):
    errors = []
    if not translation.strip():
        errors.append("empty")
    if protected_tokens(translation) != protected_tokens(record["original"]):
        errors.append("protected_token_mismatch")
    if JP.search(translation):
        errors.append("japanese_remaining")
    used = len(translation.encode("utf-8"))
    if used > record["capacity_bytes"] and not allow_overflow:
        errors.append(f'overflow:{used}>{record["capacity_bytes"]}')
    return errors


def save_outputs(source_data, records, output, csv_output):
    result = dict(source_data)
    result["translation_state"] = "machine_draft_needs_human_review"
    result["records"] = records
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)


def main():
    args = parse_args()
    source_data = json.loads(args.input.read_text(encoding="utf-8"))
    records = source_data["records"]
    cache = (
        json.loads(args.cache.read_text(encoding="utf-8"))
        if args.cache.exists() else {}
    )
    # 중단 후 재개할 때 이미 최대 횟수까지 실패한 항목을 처음부터 다시
    # 요청하지 않는다. 기존 초안의 수동 번역 상태는 그대로 이어받는다.
    previous_manual = {}
    if args.output.exists():
        previous_data = json.loads(args.output.read_text(encoding="utf-8"))
        previous_manual = {
            stable_key(record): record
            for record in previous_data.get("records", [])
            if record.get("status") == "needs_manual_translation"
        }

    # 추출 단계에서 발견한 거대 연속 블록은 독립 문자열이 아니므로 별도
    # 구조 분석 전에는 번역하거나 IPS 대상으로 삼지 않는다.
    for record in records:
        if record["capacity_bytes"] > 4096:
            record["status"] = "blocked_structured_blob"
            record["notes"] = "NUL 문자열이 아닌 구조화 데이터 덩어리. 별도 파서 필요."
        elif record["classification"] == "single_kanji" and int(record["memory_address"], 16) < 0x00600000:
            record["status"] = "excluded_non_text"
            record["notes"] = "폰트/문자 테이블 영역의 단일 한자 후보."

    selectable = [
        record for record in records
        if record["status"] not in {"blocked_structured_blob", "excluded_non_text"}
        and record["index"] >= args.start
    ]
    if args.limit is not None:
        selectable = selectable[:args.limit]

    pending = []
    for record in selectable:
        key = stable_key(record)
        cached = cache.get(key)
        if cached and not validate(record, cached, args.allow_overflow):
            record["translation"] = cached
            record["status"] = "needs_review"
        elif key in previous_manual and not args.retry_manual:
            previous = previous_manual[key]
            record["translation"] = previous.get("translation", "")
            record["status"] = "needs_manual_translation"
            record["notes"] = previous.get("notes", "previous_model_failure")
        else:
            pending.append(record)

    total = len(pending)
    for batch_start in range(0, total, args.batch_size):
        batch = pending[batch_start:batch_start + args.batch_size]
        unresolved = list(batch)
        accepted = {}
        reasons = {}
        for attempt in range(args.max_attempts):
            if not unresolved:
                break
            request_items = []
            token_maps = {}
            for record in unresolved:
                locked, tokens = lock_tokens(record["original"])
                position = records.index(record)
                previous = records[position - 1]["original"] if position > 0 else ""
                following = records[position + 1]["original"] if position + 1 < len(records) else ""
                rid = str(record["index"])
                token_maps[rid] = tokens
                request_items.append({
                    "id": rid,
                    "source": locked,
                    "capacity_bytes": record["capacity_bytes"],
                    "max_korean_chars": record["capacity_bytes"] // 3,
                    "prev_source": previous[:500],
                    "next_source": following[:500],
                })
            retry_reason = "; ".join(
                f"{rid}={','.join(errors)}" for rid, errors in reasons.items()
            )
            try:
                response = call_model(args, request_items, retry_reason)
            except Exception as exc:
                print(f"batch retry {attempt + 1}: {exc}", flush=True)
                time.sleep(2)
                continue
            next_unresolved = []
            reasons = {}
            for record in unresolved:
                rid = str(record["index"])
                if rid not in response:
                    reasons[rid] = ["missing_result"]
                    next_unresolved.append(record)
                    continue
                translation = unlock_tokens(response[rid], token_maps[rid])
                errors = validate(record, translation, args.allow_overflow)
                if errors:
                    reasons[rid] = errors
                    next_unresolved.append(record)
                else:
                    accepted[rid] = translation
            unresolved = next_unresolved

        for record in batch:
            rid = str(record["index"])
            if rid in accepted:
                translation = accepted[rid]
                record["translation"] = translation
                record["status"] = "needs_review"
                record["notes"] = "local model first draft"
                cache[stable_key(record)] = translation
            else:
                record["status"] = "needs_manual_translation"
                record["notes"] = ",".join(reasons.get(rid, ["model_failed"]))

        args.cache.parent.mkdir(parents=True, exist_ok=True)
        args.cache.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        save_outputs(source_data, records, args.output, args.csv_output)
        done = min(batch_start + len(batch), total)
        failed = sum(r["status"] == "needs_manual_translation" for r in batch)
        print(f"translated {done}/{total}; batch_failed={failed}; cache={len(cache)}", flush=True)

    save_outputs(source_data, records, args.output, args.csv_output)
    summary = {}
    for record in records:
        summary[record["status"]] = summary.get(record["status"], 0) + 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
