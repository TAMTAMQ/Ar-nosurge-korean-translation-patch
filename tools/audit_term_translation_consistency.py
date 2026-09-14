#!/usr/bin/env python3
"""Audit inconsistent Korean renderings of repeated Japanese terms.

A canonical term lexicon is learned from short standalone main-string entries,
then every aligned Japanese/Korean runtime unit is checked.  If a source unit
contains a canonical Japanese term but the Korean unit does not contain the
canonical Korean rendering, the unit is reported for manual review.

The tool is intentionally conservative: it focuses on noun/name-like Japanese
strings (katakana/kanji/Latin identifiers), ignores control-code labels and
very short/common UI words, and normalizes harmless spacing/middle-dot/CR
variation before comparison.
"""
from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

from audit_glossary_substring_collisions import aligned_units
from rename_term import normalize_main_translation, rename as normalize_terms
from source_honorifics import normalize_source_terms

REPO = Path(__file__).resolve().parents[1]
CONTROL = re.compile(r"<[^>]+>")
JP_TERM = re.compile(r"^[\u30A0-\u30FF\u3400-\u9FFFＡ-Ｚａ-ｚ０-９A-Za-z0-9・ー]+$")
KATAKANA = re.compile(r"[\u30A0-\u30FF]")
KANJI = re.compile(r"[\u3400-\u9FFF]")
PUNCT = set("。、，．！？!?：:；;（）()「」『』【】［］[]〜～…―—・")
COMMON = {
    "決定", "取消", "戻る", "次へ", "前へ", "はい", "いいえ", "名前", "説明", "使用",
    "装備", "攻撃", "防御", "確認", "設定", "開始", "終了", "選択", "決定音", "ページ",
}

# 사용자가 지정한 나무위키 Ar nosurge/관련 문서에서 직접 확인한 표기.
# 짧은 main 문자열의 다수결보다 이 표기를 우선해, 잘못 번역된 다수 표기가
# 다시 '정답'으로 학습되는 일을 막는다.
AUTHORITATIVE_TERMS = {
    "アーシェス": "아셰스",
    "イオナサル": "이오나사르",
    "カソード": "캐소드",
    "ラシェーラ": "라셸라",
    "フェリオン": "펠리온",
    "タットリア": "타토리아",
    "クオンターヴ": "퀀타브",
    "シェルノトロン": "셰르노트론",
    "天統姫": "텐토우키",
    "天領沙羅": "텐료사라",
    "インターディメンド": "인터디멘드",
    "星詠台": "성영대",
    "アルノサージュ管": "아르노사쥬관",
    "レナルル": "레나루루",
    "ソレイル": "소레일",
    "ヒュムノス": "휴므노스",
    "ヒュムネス": "휴므네스",
    "ヒュムネスフィア": "휴므네스피어",
    "万寿沙羅": "만쥬사라",
    "イグジット": "이그지트",
    "コロン": "콜론",
    "ホルス": "호루스",
    "ヒュムノフォート": "휴므노포트",
    "ベゼリエルパージャ": "베제리엘 파자",
    "アルシェルノ": "아르 시엘노",
    "シャールロード": "샤르 로드",
    "菩提命王": "보리명왕",
    "ジェノメトリカ結晶": "제노메트리카 결정",
    "サイレントグリーン": "사일런트 그린",
    "ペルチェクーラー": "펠티어 쿨러",
    "インフィニティグラス": "인피니티 글라스",
    "一撃即倒パフェ": "일격필살 파르페",
    "リセッタストーン": "리세타 스톤",
    "エンタングル素子": "엔탱글 소자",
    "ＩＡＱＬ電離傘": "IAQL 전리 우산",
    "ブライダルランチ": "브라이덜 론치",
    "ヘリカリュージョン": "헬리컬루전",
    "ジェノミュー饅頭": "제노뮤 만쥬",
    "メジャールエヌエー": "메저 RNA",
    "ポックリスエット": "포쿠리 스웨트",
    "静止衛星軌道射出装置": "정지 위성 궤도 사출 장치",
    "天領沙羅中央駅前": "텐료사라 중앙역 앞",
    "ソラ": "소라",
    "紗或村": "샤르촌",
    "紗或城": "샤르성",
    "刻神楽": "토키카구라",
    "刻神楽": "토키카구라",
    "シェルン": "셰룬",
    "シェルンプロテクタ": "셰룬 프로텍터",
    "シェルノサージュ": "셰르노사쥬",
    "エアポート": "에어포트",
    "航行図": "항해도",
    "ジャクテンサイン": "자쿠텐 사인",
    "フレンド技": "프렌드 기술",
    "ジリリウム": "질리리움",
    "クルトヒンメル": "쿠르트힘멜",
    "シャラノイア": "샤라노이아",
    "契絆想界詩": "계반상계시",
    "アルシェールスフィア": "아르시엘스피어",
    "ハーモバースト": "하모 버스트",
    "マスターシャール": "마스터 샤르",
    "にゅろきー": "뉴로키",
    "にゃろきー": "냐로키",
    "白鷹": "시로타카",
}


def norm_jp(text: str) -> str:
    """Normalize layout-only differences without conflating hiragana/katakana."""
    text = CONTROL.sub("", text)
    return "".join(ch for ch in text if not ch.isspace() and ch != "・")


def is_katakana(ch: str) -> bool:
    return "ァ" <= ch <= "ヿ" or ch == "ー"


def pure_katakana_term(text: str) -> bool:
    return bool(text) and all(is_katakana(ch) for ch in text)


def valid_source_match(key: str, start: int, end: int, text: str) -> bool:
    """Reject matches that are only prefixes inside a different proper noun."""
    if pure_katakana_term(key) and (
        (start > 0 and is_katakana(text[start - 1])) or
        (end < len(text) and is_katakana(text[end]))
    ):
        return False
    # にゅろきー is a creature/name, while にゅろきーる is a distinct place/name.
    # The generic hiragana boundary rule cannot distinguish particles from the latter,
    # so keep this one source-verified compound exclusion explicit.
    if key == "にゅろきー" and text.startswith("にゅろきーる", start):
        return False
    return True


def norm_ko(text: str) -> str:
    text = CONTROL.sub("", text)
    return "".join(ch for ch in text if not ch.isspace() and ch not in "・·")


def clean_jp(text: str) -> str:
    return CONTROL.sub("", text).replace(" ", "").replace("　", "")


def candidate_term(text: str) -> bool:
    text = clean_jp(text)
    if not (2 <= len(text) <= 28):
        return False
    if text in COMMON or any(ch in PUNCT for ch in text):
        return False
    if not JP_TERM.fullmatch(text):
        return False
    # At least one katakana or kanji makes it noun/name-like enough to audit.
    if not (KATAKANA.search(text) or KANJI.search(text)):
        return False
    # Two-kanji generic words create too many context-sensitive false positives.
    if len(text) <= 2 and not KATAKANA.search(text):
        return False
    return True


def main_slot_exception_indices() -> set[int]:
    """Return main-string indices explicitly marked as fixed-slot abbreviations."""
    csv.field_size_limit(1 << 30)
    path = REPO / "translations" / "exefs" / "main_1.0.1.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return {
            int(row["index"])
            for row in csv.DictReader(f)
            if "slot_exception" in (row.get("notes") or "")
        }


def canonical_terms() -> dict[str, tuple[str, int]]:
    csv.field_size_limit(1 << 30)
    path = REPO / "translations" / "exefs" / "main_1.0.1.csv"
    variants: dict[str, Counter[str]] = defaultdict(Counter)
    display: dict[tuple[str, str], str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            jp = row["original"].strip()
            ko = row["translation"].strip()
            if not ko or not candidate_term(jp):
                continue
            key = norm_jp(clean_jp(jp))
            nko = norm_ko(ko)
            if not nko:
                continue
            variants[key][nko] += 1
            display[(key, nko)] = ko
    out: dict[str, tuple[str, int]] = {}
    for key, counts in variants.items():
        canonical, count = counts.most_common(1)[0]
        out[key] = (display[(key, canonical)], count)
    for jp, ko in AUTHORITATIVE_TERMS.items():
        out[norm_jp(jp)] = (ko, 1)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-source-hits", type=int, default=2)
    ap.add_argument("--contexts", type=int, default=6)
    ap.add_argument("--max-findings", type=int, default=0,
                    help="print only the first N ranked findings (0 = all)")
    ap.add_argument("--term", help="Japanese or Korean term filter")
    ap.add_argument("--simulate-normalization", action="store_true",
                    help="audit the text after build-time rename_term normalization")
    ap.add_argument("--authoritative-only", action="store_true",
                    help="audit only the source-verified AUTHORITATIVE_TERMS entries")
    ap.add_argument("--simulate-review-fixes", action="store_true",
                    help="audit Event EBM text after record-guarded semantic review fixes")
    ap.add_argument("--presence-only", action="store_true",
                    help="require each source term to appear at least once, ignoring natural repeated-name omission")
    args = ap.parse_args()

    review_fixes = {}
    if args.simulate_review_fixes:
        from event_translation_review_fixes import FIXES
        review_fixes = {
            f"ebm:romfs/Event/event/{fix.path}:{fix.index}": fix.new
            for fix in FIXES
        }

    terms = canonical_terms()
    if args.authoritative_only:
        terms = {norm_jp(jp): (ko, 1) for jp, ko in AUTHORITATIVE_TERMS.items()}
    if args.term:
        terms = {jp: info for jp, info in terms.items()
                 if args.term in jp or args.term in info[0]}

    # Build a small trie so the 160k aligned units are scanned once instead of
    # doing (#terms × #units) substring searches.
    END = ""
    trie: dict = {}
    for jp_key in terms:
        node = trie
        for ch in jp_key:
            node = node.setdefault(ch, {})
        node[END] = jp_key

    source_hits: Counter[str] = Counter()
    missing: dict[str, list[tuple[str, str, str, int]]] = defaultdict(list)
    slot_exceptions = main_slot_exception_indices()
    slot_exception_skips = 0
    unit_count = 0
    for uid, jp, ko in aligned_units():
        unit_count += 1
        njp = norm_jp(clean_jp(jp))
        matched: Counter[str] = Counter()
        for start, ch in enumerate(njp):
            node = trie.get(ch)
            if node is None:
                continue
            if END in node:
                key = node[END]
                end = start + len(key)
                if valid_source_match(key, start, end, njp):
                    matched[key] += 1
            pos = start + 1
            while pos < len(njp):
                node = node.get(njp[pos])
                if node is None:
                    break
                if END in node:
                    key = node[END]
                    end = pos + 1
                    if valid_source_match(key, start, end, njp):
                        matched[key] += 1
                pos += 1
        if not matched:
            continue
        compared_ko = review_fixes.get(uid, ko)
        if args.simulate_normalization:
            if uid.startswith("main:"):
                compared_ko = normalize_main_translation(
                    uid.split(":", 1)[1], compared_ko, jp
                )
            else:
                compared_ko = normalize_terms(compared_ko)
                compared_ko = normalize_source_terms(jp, compared_ko)
        normalized_ko = norm_ko(compared_ko)
        for jp_key, count in matched.items():
            source_hits[jp_key] += count
            ko_term = terms[jp_key][0]
            have = normalized_ko.count(norm_ko(ko_term))
            missing_count = (1 if have == 0 else 0) if args.presence_only else max(0, count - have)
            if missing_count and uid.startswith("main:"):
                try:
                    main_index = int(uid.split(":", 1)[1])
                except ValueError:
                    main_index = -1
                if main_index in slot_exceptions:
                    slot_exception_skips += missing_count
                    continue
            if missing_count:
                missing[jp_key].append((uid, jp, ko, missing_count))

    findings = []
    for jp_key, rows in missing.items():
        hits = source_hits[jp_key]
        if hits < args.min_source_hits:
            continue
        ko_term, seed_count = terms[jp_key]
        findings.append((sum(x[3] for x in rows), hits, jp_key, ko_term, seed_count, rows))

    findings.sort(key=lambda x: (-x[0], -x[1], x[2]))
    print(f"canonical terms: {len(terms)} / aligned units: {unit_count}")
    print(f"slot-exception misses ignored: {slot_exception_skips}")
    print(f"candidate inconsistent terms: {len(findings)}")
    shown = findings[:args.max_findings] if args.max_findings else findings
    for miss, hits, jp, ko, seeds, rows in shown:
        print(f"\n[{miss:4d}/{hits:4d}] {jp} => {ko}  (standalone seeds={seeds}, units={len(rows)})")
        for uid, src, dst, extra in rows[:args.contexts]:
            print(f"  {uid} (-{extra})")
            print(f"    JP: {src[:220]}")
            print(f"    KO: {dst[:220]}")


if __name__ == "__main__":
    main()
