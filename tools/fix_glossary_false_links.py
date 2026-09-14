#!/usr/bin/env python3
"""Fix confirmed glossary false-link collisions in Event EBM text.

The game highlights registered glossary titles by raw substring.  These fixes
remove Korean wording that accidentally contains a glossary title when the
Japanese source is unrelated, while preserving genuine glossary occurrences.

The script is dry-run by default.  Pass --apply to rewrite only the listed EBM
record payloads; 32-byte record headers and every unlisted record are preserved.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from text_layout import EVENT_LINE_WRAP_CHARS, MAX_LINES, rendered_line_count

REPO = Path(__file__).resolve().parents[1]
EVENT_ROOT = REPO / "translations" / "romfs" / "Event" / "event"
RECORD_HEADER = 32


@dataclass(frozen=True)
class Fix:
    path: str
    index: int
    old: str
    new: str


FIXES = [
    # 救済 => 구제: ordinary Korean uses must not trigger the glossary entry.
    Fix("C11_4/EVENT_MESSAGE_C11_4_060.ebm", 39,
        "구제 불능인 바보네……", "정말 답 없는 바보네……"),
    Fix("C21_2/EVENT_MESSAGE_C21_2_090.ebm", 75,
        "아니…… 난 정말 구제 불능이야.", "아니…… 난 정말 답이 없어."),
    Fix("IM31/EVENT_MESSAGE_IM31_020.ebm", 7,
        "맞아. 캐스도,<CR>정말 좋아하는 간식이 해충 구제용 먹이처럼<CR>팔리고 있다면 싫잖아？",
        "맞아. 캐스도,<CR>정말 좋아하는 간식이 해충 퇴치용 먹이처럼<CR>팔리고 있다면 싫잖아？"),
    Fix("SWC02/EVENT_MESSAGE_SWC02_020.ebm", 61,
        "언제나 그렇듯 정말 구제 불능인 녀석들이야！",
        "언제나 그렇듯 정말 질리지도 않는 녀석들이야！"),
    Fix("SWC06/EVENT_MESSAGE_SWC06_070.ebm", 58,
        "백신이라고？<CR>너는 정말 구제 불능의 바보구나.<CR>그런 게 정말로 있을 거라고 생각한 거야？",
        "백신이라고？<CR>너는 정말 답 없는 바보구나.<CR>그런 게 정말로 있을 거라고 생각한 거야？"),
    Fix("SWC06/EVENT_MESSAGE_SWC06_070.ebm", 65,
        "……너, 구제 불능의 악녀구나.", "……너, 정말 지독한 악녀구나."),
    Fix("XX03/EVENT_MESSAGE_XX03_070.ebm", 35,
        "그나저나, 그런 문제 하나 못 풀다니<CR>정말 구제할 방법이 없네.",
        "그나저나, 그런 문제 하나 못 풀다니<CR>정말 답이 없네."),

    # ラシェーラ => 라셸라: distinguish different names/words that were
    # incorrectly collapsed to the planet name and therefore linked to it.
    Fix("C31_8/EVENT_MESSAGE_C31_8_030.ebm", 40,
        "프림 양도, 함께 노래해 줘…… 이게, <CR>라셸라・리인카네이션이야！",
        "프림 양도, 함께 노래해 줘…… 이게, <CR>라셸・린커네이션이야！"),
    Fix("IM21/EVENT_MESSAGE_IM21_280.ebm", 1,
        "찬성！<CR>라셸라, 어떤 게임이야？", "찬성！<CR>라즈에라, 어떤 게임이야？"),
    Fix("IM22/EVENT_MESSAGE_IM22_280.ebm", 19,
        "그건 당연하지.<CR>왜냐하면 이건 라셸라니까.",
        "그건 당연하지.<CR>왜냐하면 이건 라즈에라니까."),
    Fix("IM22/EVENT_MESSAGE_IM22_280.ebm", 20,
        "라셸라는 말이야,<CR>라셸라를 행성 파괴의 위기에서 구하는 것을<CR>목적으로 한 게임이야.",
        "라즈에라는 말이야,<CR>라셸라를 행성 파괴의 위기에서 구하는 것을<CR>목적으로 한 게임이야."),
    Fix("IM31/EVENT_MESSAGE_IM31_340.ebm", 11,
        "……뭐, 라셸라스럽긴 하네.", "……뭐, 이온답긴 하네."),

    # 審判 => 심판: generic judgment/punishment is not the glossary ritual.
    Fix("C11_1/EVENT_MESSAGE_C11_1_280.ebm", 10,
        "그러니 그 힘에만 의지하는 자에게는,<CR>심판이 내려질 수도 있어.<CR>방심하지 말고, 항상 마음을 갈고닦도록 해.",
        "그러니 그 힘에만 의지하는 자에게는,<CR>벌이 내려질 수도 있어.<CR>방심하지 말고, 항상 마음을 갈고닦도록 해."),
    Fix("SWC04/EVENT_MESSAGE_SWC04_020.ebm", 39,
        "그럼 델타. 이따가 즉시,<CR>나의 성 『사오성』으로 출두하도록 하세요.<CR>당신의 죄를 심판하겠습니다.",
        "그럼 델타. 이따가 즉시,<CR>나의 성 『사오성』으로 출두하도록 하세요.<CR>당신의 죄를 판결하겠습니다."),
    Fix("SWI06/EVENT_MESSAGE_SWI06_120.ebm", 5,
        "이 문에 간섭하는 자는,<CR>누구든 심판하겠다.",
        "이 문에 간섭하는 자는,<CR>누구든 처단하겠다."),
    Fix("SWI06/EVENT_MESSAGE_SWI06_180.ebm", 27,
        "이 문에 간섭하는 자는,<CR>누구든 심판하겠다.",
        "이 문에 간섭하는 자는,<CR>누구든 처단하겠다."),

    # シェルノトロン => 셰르노트론: チェルノトロン is a different proper
    # name.  The global term normalizer would otherwise collapse 셸노트론 into
    # the glossary title and make this line link to the wrong glossary entry.
    Fix("IM12/EVENT_MESSAGE_IM12_090.ebm", 20,
        "네, 외관을 고려하면 셸노트론이라는<CR>이름이 딱 어울린다고 생각해요！",
        "네, 외관을 고려하면 체르노트론이라는<CR>이름이 딱 어울린다고 생각해요！"),

    # Other short glossary words colliding with unrelated ordinary Korean.
    Fix("C21_3/EVENT_MESSAGE_C21_3_010.ebm", 20,
        "하지만 『모태소칸』의 융화로 인해,<CR>플라스크의 바다 속 인간의 영혼이 부족해.<CR>그래서 동력이 불안정해진 거야.",
        "하지만 『모태소칸』의 융합으로 인해,<CR>플라스크의 바다 속 인간의 영혼이 부족해.<CR>그래서 동력이 불안정해진 거야."),
    Fix("MT14/EVENT_MESSAGE_MT14_070.ebm", 8,
        "（부정했다간 화를 낼 것 같으니,<CR>일단은 동조해 둘까.）",
        "（부정했다간 화를 낼 것 같으니,<CR>일단은 동의해 둘까.）"),
    Fix("IM12/EVENT_MESSAGE_IM12_460.ebm", 14,
        "영유아기에는 몇 시간마다 배변과 수유로<CR>아이가 울어대기에, 어머니는 제대로 잠도<CR>자지 못하는 나날을 보내게 된답니다？",
        "아주 어릴 때는 몇 시간마다 배변과 수유로<CR>아이가 울어대기에, 어머니는 제대로 잠도<CR>자지 못하는 나날을 보내게 된답니다？"),

    # 天領割符 => 천령증표 is the registered glossary title; plain 割符 => 증표.
    # Guard legacy generic mistranslations so the formal title does not
    # accidentally appear where the source uses only the common noun.
    Fix("C11_5/EVENT_MESSAGE_C11_5_070.ebm", 23,
        "저기, 와리후라는 거, 이거 말하는 거야…？",
        "저기, 증표라는 거, 이거 말하는 거야…？"),
    Fix("C11_5/EVENT_MESSAGE_C11_5_080.ebm", 0,
        "그나저나, 정말 언제<CR>와리후 같은 게 들어있었던 걸까.",
        "그나저나, 정말 언제<CR>증표 같은 게 들어있었던 걸까."),
    Fix("C12_2/EVENT_MESSAGE_C12_2_110.ebm", 2,
        "그럼, 와리후를 제출해 주세요.",
        "그럼, 증표를 제출해 주세요."),
    Fix("C12_2/EVENT_MESSAGE_C12_2_110.ebm", 3,
        "와리후？", "증표？"),
    Fix("C12_2/EVENT_MESSAGE_C12_2_110.ebm", 4,
        "…와리후입니다.", "…증표입니다."),
    Fix("C12_2/EVENT_MESSAGE_C12_2_110.ebm", 5,
        "저기, 와리후라는 게……？", "저기, 증표라는 게……？"),
    Fix("C12_2/EVENT_MESSAGE_C12_2_110.ebm", 6,
        "당신, 인간이군요.<CR>와리후가 없는 분은 승차하실 수 없습니다.",
        "당신, 인간이군요.<CR>증표가 없는 분은 승차하실 수 없습니다."),
    Fix("C12_2/EVENT_MESSAGE_C12_2_110.ebm", 8,
        "와리후가 뭘까……<CR>근처에 있는 샤르에게 물어볼까？",
        "증표가 뭘까……<CR>근처에 있는 샤르에게 물어볼까？"),
    Fix("C12_2/EVENT_MESSAGE_C12_2_120.ebm", 0,
        "와리후를 제출해 주세용ー", "증표를 제출해 주세용ー"),

    # 浄化 => 정화 is a registered glossary title.  Ordinary 清め／清める
    # should keep their literal ritual/cleansing meaning without accidentally
    # linking to that glossary entry.  禊ぎ→정화 is a separate, intentional
    # short UI translation and is handled as an audit exception instead.
    Fix("C12_3/EVENT_MESSAGE_C12_3_040.ebm", 78,
        "이 이상의 문답은 불필요합니다.<CR>다시 한번 저 탑에서, 스스로를 정화하세요.<CR>이오나사르.",
        "이 이상의 문답은 불필요합니다.<CR>다시 저 탑에서 스스로를 정결히 하세요.<CR>이오나사르."),
    Fix("MT13/EVENT_MESSAGE_MT13_050.ebm", 2,
        "나도 왠지 마음이 정화되는 느낌이랄까,<CR>뭐라고 해야 할까？",
        "나도 왠지 마음이 맑아지는 느낌이랄까,<CR>뭐라고 해야 할까？"),
    Fix("MT13/EVENT_MESSAGE_MT13_050.ebm", 11,
        "헤～ 그렇구나……<CR>그렇다는 건, 이 정화되는 느낌은<CR>성수의 효과라는 거네.",
        "헤～ 그렇구나……<CR>그렇다는 건, 이 맑아지는 느낌은<CR>성수의 효과라는 거네."),
    Fix("MT13/EVENT_MESSAGE_MT13_050.ebm", 15,
        "아, 아마 교체하는 거 아닐까？<CR>아무리 성수로 정화한다고 해도,<CR>에티켓 문제가 있잖아.",
        "아, 아마 교체하는 거 아닐까？<CR>아무리 성수로 몸을 씻는다고 해도,<CR>에티켓 문제가 있잖아."),
    Fix("MT25/EVENT_MESSAGE_MT25_120.ebm", 8,
        "물 쪽이 몸을 정화하며 수행하는 신성한 <CR>분위기를 낼 수 있어서일지도 모르겠네.",
        "물 쪽이 몸을 씻으며 수행하는 신성한<CR>분위기를 낼 수 있어서일지도 모르겠네."),
    Fix("SWI01/EVENT_MESSAGE_SWI01_020.ebm", 1,
        "……구원하소서… 정화하소서……",
        "……구원하소서… 정결케 하소서……"),
    Fix("SWI01/EVENT_MESSAGE_SWI01_020.ebm", 6,
        "……구원하소서… 정화하소서……",
        "……구원하소서… 정결케 하소서……"),
    Fix("SWI01/EVENT_MESSAGE_SWI01_050.ebm", 8,
        "흠. 뭐, 됐다.<CR>그럼, 그 바위를 신사 앞에 두거라.<CR>오오카미 님께 정화받아야 할 것이니라.",
        "흠. 뭐, 됐다.<CR>그럼, 그 바위를 신사 앞에 두거라.<CR>오오카미 님께 정결 의식을 받거라."),
    Fix("SWI01/EVENT_MESSAGE_SWI01_050.ebm", 12,
        "음.<CR>그럼, 정화 의식을 시작하자꾸나！",
        "음.<CR>그럼, 정결 의식을 시작하자꾸나！"),
    Fix("SWI01/EVENT_MESSAGE_SWI01_050.ebm", 19,
        "정화가 필요한 바위는 이것입니까？",
        "정결 의식이 필요한 바위는 이것입니까？"),
]


def parse_ebm(data: bytes) -> list[list[bytes | str]]:
    count = int.from_bytes(data[:4], "little")
    pos = 4
    records: list[list[bytes | str]] = []
    for _ in range(count):
        header = data[pos:pos + RECORD_HEADER]
        length = int.from_bytes(data[pos + RECORD_HEADER:pos + RECORD_HEADER + 4], "little")
        start = pos + RECORD_HEADER + 4
        end = start + length
        records.append([header, data[start:end - 1].decode("utf-8")])
        pos = end
    if pos != len(data):
        raise ValueError(f"EBM trailing/parse mismatch: parsed={pos} file={len(data)}")
    return records


def build_ebm(records: list[list[bytes | str]]) -> bytes:
    out = bytearray(len(records).to_bytes(4, "little"))
    for header, text in records:
        payload = str(text).encode("utf-8") + b"\0"
        out += bytes(header) + len(payload).to_bytes(4, "little") + payload
    return bytes(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the verified fixes")
    args = ap.parse_args()

    by_path: dict[str, list[Fix]] = {}
    for fix in FIXES:
        by_path.setdefault(fix.path, []).append(fix)

    verified = 0
    changed_files = 0
    for relative, fixes in sorted(by_path.items()):
        path = EVENT_ROOT / relative
        original_bytes = path.read_bytes()
        records = parse_ebm(original_bytes)
        dirty = False
        for fix in sorted(fixes, key=lambda x: x.index):
            if fix.index >= len(records):
                raise SystemExit(f"record out of range: {relative}:{fix.index}")
            current = str(records[fix.index][1])
            if current == fix.new:
                print(f"ALREADY {relative}:{fix.index}  {fix.new}")
                verified += 1
                continue
            if current != fix.old:
                raise SystemExit(
                    f"guard mismatch: {relative}:{fix.index}\n"
                    f"expected: {fix.old!r}\n"
                    f"actual:   {current!r}"
                )
            lines = rendered_line_count(fix.new, EVENT_LINE_WRAP_CHARS)
            if lines > MAX_LINES:
                raise SystemExit(
                    f"layout overflow: {relative}:{fix.index} -> {lines} lines"
                )
            print(f"FIX     {relative}:{fix.index}\n  {fix.old}\n  -> {fix.new}")
            records[fix.index][1] = fix.new
            verified += 1
            dirty = True
        if dirty:
            rebuilt = build_ebm(records)
            # Reparse before any write so record framing/UTF-8 are guaranteed.
            parse_ebm(rebuilt)
            if args.apply:
                path.write_bytes(rebuilt)
            changed_files += 1

    if verified != len(FIXES):
        raise SystemExit(f"verified {verified}/{len(FIXES)} fixes")
    mode = "APPLIED" if args.apply else "DRY-RUN"
    print(f"{mode}: {verified} records verified across {changed_files} files")


if __name__ == "__main__":
    main()
