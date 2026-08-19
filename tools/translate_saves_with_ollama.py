#!/usr/bin/env python3
"""Translate Ar nosurge Saves XML with an OpenAI-compatible local model."""

import argparse
import hashlib
import html
import json
import re
import shutil
import time
import urllib.request
from pathlib import Path


JP = re.compile(r"[\u3041-\u3096\u30a1-\u30fa\u30fd-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
CTRL = re.compile(r"<[A-Za-z][A-Za-z0-9_]*>")
ATTR = re.compile(r'''(?P<head>\s[\w:.-]+\s*=\s*)(?P<q>["'])(?P<value>.*?)(?P=q)''', re.DOTALL)
TEXT_ATTR = re.compile(r'''(?P<head>\bText\s*=\s*)(?P<q>["'])(?P<value>.*?)(?P=q)''', re.DOTALL)

GLOSSARY = """
Ar nosurge=아르노사쥬/아르노서지, デルタ=델타, キャス=캐스, イオン=이온,
アーシェス=아셰스, サーリ=사리, ネイ=네이, ジル=질, プリム=프림,
カノン=카논, ジェノム=제노므, ジェノメトリクス=제노메트릭스,
シャール=샤르, 詩魔法=시마법, 想い=마음, ソレイル=솔레이유,
ラシェーラ=라셸라, TxBIOS=TxBIOS, バースト=버스트, ハーモニクス=하모닉스
""".strip()

KANA_TEST_TABLE = str.maketrans({
    "あ": "아", "い": "이", "う": "우", "え": "에", "お": "오",
    "か": "카", "き": "키", "く": "쿠", "け": "케", "こ": "코",
    "さ": "사", "し": "시", "す": "스", "せ": "세", "そ": "소",
    "た": "타", "ち": "치", "つ": "츠", "て": "테", "と": "토",
    "な": "나", "に": "니", "ぬ": "누", "ね": "네", "の": "노",
    "は": "하", "ひ": "히", "ふ": "후", "へ": "헤", "ほ": "호",
})

# Reviewed overrides where line-break controls have semantic, fixed positions.
REVIEWED_OVERRIDES = {
    "sysmess:0281": "시간적 정합성을 유지하기<CR>위해 에피소드를 대기<CR>중입니다",
    "sysmess:0302": "전투가 시작되면, 우선 영창할 시마법 <CR>을 <IM00>로 결정합니다. 사용할 수 있는 시마법이 늘어났을 때는 <IM08>로 선택합니다",
    "sysmess:0336": "적을 격파하기 위해 보너스를 발생시켜 시<CR>마법의 차지량을 모으는 것이 전투를 유리<CR>하게 이끄는 데 중요합니다",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lock_tokens(text):
    tokens = []
    def repl(match):
        tokens.append(match.group(0))
        return f"[[CTRL_{len(tokens)-1}]]"
    return CTRL.sub(repl, text), tokens


def unlock_tokens(text, tokens):
    for index, token in enumerate(tokens):
        text = text.replace(f"[[CTRL_{index}]]", token)
    return text


def local_chat(base_url, model, items):
    system = f"""일본어 게임 UI/시스템 문구를 자연스럽고 간결한 한국어로 번역한다.
반드시 {{"translations":[{{"id":"입력 id","translation":"한국어"}}]}} 형식의 JSON 객체 하나만 출력한다.
입력 배열의 모든 항목을 한 번씩 번역하며 입력 개수와 translations 배열의 개수는 반드시 같아야 한다.
각 객체의 id는 입력값을 한 글자도 바꾸지 말고 그대로 복사한다.
[[CTRL_0]] 형태의 토큰은 철자, 개수, 순서, 주변 위치를 절대 바꾸지 않는다.
영문 식별자, 버튼명, 숫자와 기호는 필요하지 않으면 바꾸지 않는다.
스태프롤의 일본인 이름은 한국어 독음으로 옮긴다. 원문 일본어를 남기지 않는다.
의미 없는 글꼴·폭 시험 문자열도 예외 없이 모든 일본어 글자를 한국어 음가로 옮긴다.
용어집: {GLOSSARY}"""
    payload = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 8192,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(items, ensure_ascii=False)},
        ],
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=900) as response:
        outer = json.loads(response.read().decode("utf-8"))
    content = outer["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content, count=1, flags=re.I)
        content = re.sub(r"\s*```$", "", content, count=1)
    parsed = json.loads(content)
    if isinstance(parsed, dict) and set(parsed) == {"id", "translation"}:
        parsed = [parsed]
    if isinstance(parsed, dict):
        nested = parsed.get("translations") or parsed.get("items") or parsed.get("results")
        if nested is not None:
            parsed = nested
        elif all(isinstance(value, str) for value in parsed.values()):
            return {str(key): value for key, value in parsed.items()}
    if not isinstance(parsed, list):
        raise ValueError(f"model response is not a translation array: {content[:500]}")
    return {str(x["id"]): str(x["translation"]) for x in parsed}


def translate_values(base_url, model, records, cache_path, batch_size, reset_cache=False, retry_japanese=False):
    cache = {} if reset_cache else (json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {})
    if retry_japanese:
        cache = {key: value for key, value in cache.items() if not JP.search(value)}
    canonical_by_source = {}
    aliases = {}
    unique_records = []
    for record in records:
        key = record["source"]
        canonical = canonical_by_source.get(key)
        if canonical is None:
            canonical_by_source[key] = record["id"]
            aliases[record["id"]] = [record["id"]]
            unique_records.append(record)
        else:
            aliases[canonical].append(record["id"])
            if canonical in cache:
                cache[record["id"]] = cache[canonical]
    pending = [r for r in unique_records if r["id"] not in cache]
    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]
        request_items = []
        token_map = {}
        for r in batch:
            locked, tokens = lock_tokens(r["source"])
            item = {"id": r["id"], "source": locked}
            if r.get("draft"):
                draft, _ = lock_tokens(r["draft"])
                item["draft_korean"] = draft
            request_items.append(item)
            token_map[r["id"]] = tokens
        for attempt in range(3):
            try:
                result = local_chat(base_url, model, request_items)
                break
            except Exception as exc:
                if attempt == 2:
                    raise
                print(f"retry: {exc}", flush=True)
                time.sleep(2)
        for r in batch:
            rid = r["id"]
            if rid not in result and len(result) == len(batch):
                result = dict(zip((item["id"] for item in batch), result.values()))
            if rid not in result:
                raise ValueError(f"missing model result: {rid}; returned={list(result)[:20]}")
            translated = unlock_tokens(result[rid], token_map[rid])
            # Layout/font test strings are sometimes intentionally meaningless;
            # local models may echo them despite explicit instructions.
            translated = translated.translate(KANA_TEST_TABLE)
            if CTRL.findall(translated) != CTRL.findall(r["source"]):
                raise ValueError(f"control token mismatch: {rid}")
            cache[rid] = translated
            for alias in aliases[rid]:
                cache[alias] = translated
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"translated {min(start + len(batch), len(pending))}/{len(pending)} (cache {len(cache)})", flush=True)
    cache.update(REVIEWED_OVERRIDES)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    return cache


def collect_ui(original_root):
    records = []
    for path in sorted(original_root.rglob("*.xml")):
        if "systemMessage" in path.relative_to(original_root).parts:
            continue
        raw = path.read_text(encoding="utf-8", errors="strict")
        relative = path.relative_to(original_root).as_posix()
        occurrence = 0
        for match in ATTR.finditer(raw):
            value = html.unescape(match.group("value"))
            if not JP.search(value):
                continue
            records.append({"id": f"ui:{relative}:{occurrence}", "source": value, "file": relative})
            occurrence += 1
    return records


def read_xml_text_attrs(path, encoding):
    raw = path.read_text(encoding=encoding)
    return raw, [html.unescape(m.group("value")) for m in TEXT_ATTR.finditer(raw)]


def collect_sysmess(original, draft):
    _, sources = read_xml_text_attrs(original, "cp932")
    _, drafts = read_xml_text_attrs(draft, "utf-8")
    if len(sources) != len(drafts):
        raise ValueError(f"SysMess entry count mismatch: {len(sources)} != {len(drafts)}")
    return [{"id": f"sysmess:{i:04d}", "source": s, "draft": drafts[i]} for i, s in enumerate(sources)]


def xml_escape_attr(value, quote):
    escaped = html.escape(value, quote=True)
    return escaped.replace("&#x27;", "&apos;") if quote == "'" else escaped


def write_ui(original_root, output_root, cache):
    written = []
    for source in sorted(original_root.rglob("*.xml")):
        if "systemMessage" in source.relative_to(original_root).parts:
            continue
        raw = source.read_text(encoding="utf-8")
        relative = source.relative_to(original_root).as_posix()
        occurrence = 0
        def repl(match):
            nonlocal occurrence
            value = html.unescape(match.group("value"))
            if not JP.search(value):
                # Some source XML stores controls such as <CO> literally inside
                # attributes. Preserve their value while making the XML valid.
                return match.group("head") + match.group("q") + xml_escape_attr(value, match.group("q")) + match.group("q")
            rid = f"ui:{relative}:{occurrence}"
            occurrence += 1
            translated = cache[rid]
            return match.group("head") + match.group("q") + xml_escape_attr(translated, match.group("q")) + match.group("q")
        output = ATTR.sub(repl, raw)
        destination = output_root / source.relative_to(original_root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(output, encoding="utf-8", newline="")
        written.append(destination)
    return written


def write_sysmess(original, output, cache):
    raw = original.read_text(encoding="cp932")
    index = 0
    def repl(match):
        nonlocal index
        rid = f"sysmess:{index:04d}"
        index += 1
        translated = cache[rid]
        return match.group("head") + match.group("q") + xml_escape_attr(translated, match.group("q")) + match.group("q")
    result = TEXT_ATTR.sub(repl, raw)
    result = re.sub(r'encoding=["\']SHIFT-JIS["\']', 'encoding="UTF-8"', result, count=1, flags=re.I)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result, encoding="utf-8", newline="")


def verify(records, cache):
    errors = []
    for r in records:
        translated = cache[r["id"]]
        if CTRL.findall(translated) != CTRL.findall(r["source"]):
            errors.append(f"token:{r['id']}")
        if JP.search(translated):
            errors.append(f"japanese:{r['id']}:{translated}")
    if errors:
        raise SystemExit("verification failed\n" + "\n".join(errors[:100]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--original-sysmess", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", default="gemma-4-26b-a4b-it-qat")
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--reset-cache", action="store_true")
    parser.add_argument("--retry-japanese", action="store_true")
    args = parser.parse_args()
    original_ui = args.repo / "originalText" / "romfs" / "Saves"
    translated_root = args.repo / "translations" / "romfs" / "Saves"
    draft_sysmess = translated_root / "systemMessage" / "SysMess.xml"
    cache_path = args.repo / "build" / "saves_translation_cache.json"

    ui = collect_ui(original_ui)
    sysmess = collect_sysmess(args.original_sysmess, draft_sysmess)
    records = ui + sysmess
    baseline = {
        "original_ui_root": str(original_ui),
        "original_sysmess": str(args.original_sysmess),
        "original_sysmess_sha256": sha256(args.original_sysmess),
        "ui_files": len(list(original_ui.rglob("*.xml"))),
        "ui_units": len(ui),
        "sysmess_units": len(sysmess),
        "units": [{"id": r["id"], "source": r["source"], "tokens": CTRL.findall(r["source"])} for r in records],
    }
    baseline_path = args.repo / "originalText" / "translation_baseline.json"
    baseline_path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")

    cache = translate_values(args.base_url, args.model, records, cache_path, args.batch_size, args.reset_cache, args.retry_japanese)
    verify(records, cache)
    write_ui(original_ui, translated_root, cache)
    write_sysmess(args.original_sysmess, draft_sysmess, cache)
    print(json.dumps({"ui_units": len(ui), "sysmess_units": len(sysmess), "total": len(records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
