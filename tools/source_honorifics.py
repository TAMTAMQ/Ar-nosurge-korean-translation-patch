from __future__ import annotations

import re

# おネイ is intentionally transliterated as 오네이 rather than localized as
# 누나/언니/누님.  Preserve ordinary suffixes on top of that spelling:
# おネイさん -> 오네이씨, おネイちゃん -> 오네이쨩.
PLAIN_SOURCE_FORMS = (
    ("ネイちゃん", "네이쨩"),
    ("ネイさん", "네이씨"),
    # Alternate-world spellings use the kanji 寧 for the same name.
    ("寧ちゃん", "네이쨩"),
    ("寧さん", "네이씨"),
)

BAD_PLAIN_FORMS = (
    "네이 언니", "네이 누나", "네이 누님",
    "네이언니", "네이누나", "네이누님",
    "네이 짱", "네이짱", "네이 쨩", "네이 양", "네이양",
    "네이 씨", "네이씨",
)


def source_targets(japanese: str) -> list[str]:
    # Remove every おネイ form first because ネイさん is a substring of
    # おネイさん.  They are normalized separately as 오네이 variants.
    remainder = japanese
    for form in ("おネイさん", "おネイちゃん", "おネイ"):
        remainder = remainder.replace(form, "")

    targets: list[str] = []
    for source, target in PLAIN_SOURCE_FORMS:
        count = remainder.count(source)
        if count:
            targets.extend([target] * count)
            remainder = remainder.replace(source, "")
    return targets


def _repair_particles(text: str, target: str) -> str:
    if target.endswith("씨"):
        pairs = (("이", "가"), ("은", "는"), ("을", "를"), ("과", "와"))
    elif target.endswith("쨩"):
        pairs = (("가", "이"), ("는", "은"), ("를", "을"), ("와", "과"))
    else:
        pairs = ()
    for old, new in pairs:
        text = text.replace(target + old, target + new)
    return text


def normalize_nei_honorifics(japanese: str, korean: str) -> str:
    text = korean

    # おネイ is always kept as 오네이.  Normalize the fixed compounds first,
    # then generic さん/ちゃん variants so old 누나/언니/누님 translations
    # cannot reappear during a rebuild.
    if "疾風のおネイさん" in japanese:
        for variant in (
            "질풍의 네이 언니", "질풍의 네이 누나", "질풍의 네이 누님",
            "질풍의 네이 씨", "질풍의 네이씨", "질풍의 누님",
            "질풍의 오네이", "시푸노 네이 언니",
        ):
            text = text.replace(variant, "질풍의 오네이씨")
    elif "疾風のおネイちゃん" in japanese:
        for variant in (
            "질풍의 네이쨩", "질풍의 네이 쨩", "질풍의 네이 누나",
            "질풍의 네이 언니", "질풍의 네이 누님", "질풍의 오네이",
        ):
            text = text.replace(variant, "질풍의 오네이쨩")
    elif "疾風のおネイ" in japanese:
        for variant in (
            "질풍의 네이 언니", "질풍의 네이 누나", "질풍의 네이 누님",
            "질풍의 네이 씨", "질풍의 네이씨", "질풍의 누님",
            "시푸노 네이 언니",
        ):
            text = text.replace(variant, "질풍의 오네이")
    if "座長のおネイさん" in japanese:
        for variant in ("좌장의 네이 언니", "좌장의 네이 누님", "좌장 누님", "좌장 오네이"):
            text = text.replace(variant, "좌장 오네이씨")
    elif "座長のおネイちゃん" in japanese:
        for variant in ("좌장의 네이 언니", "좌장의 네이 누님", "좌장 누님", "좌장 오네이"):
            text = text.replace(variant, "좌장 오네이쨩")
    elif "座長のおネイ" in japanese:
        for variant in ("좌장의 네이 언니", "좌장의 네이 누님", "좌장 누님"):
            text = text.replace(variant, "좌장 오네이")
        text = text.replace("인기 만점인 네이 언니랑", "인기 만점인 좌장 오네이랑")
    if "おネイの新メニュー" in japanese:
        for variant in ("네이 언니의 신메뉴", "네이 누님의 신메뉴", "누님의 신메뉴"):
            text = text.replace(variant, "오네이의 신메뉴")

    onei_san_count = japanese.count("おネイさん")
    missing_onei_san = max(0, onei_san_count - text.count("오네이씨"))
    for variant in (
        "네이씨", "네이 씨", "네이 누나", "네이 언니", "네이 누님",
        "누나", "언니", "누님", "오네이 씨",
    ):
        while missing_onei_san and variant in text:
            text = text.replace(variant, "오네이씨", 1)
            missing_onei_san -= 1

    onei_chan_count = japanese.count("おネイちゃん")
    missing_onei_chan = max(0, onei_chan_count - text.count("오네이쨩"))
    for variant in (
        "네이쨩", "네이 쨩", "네이짱", "네이 짱", "네이 누나",
        "네이 언니", "네이 누님", "누나", "언니", "누님",
    ):
        while missing_onei_chan and variant in text:
            text = text.replace(variant, "오네이쨩", 1)
            missing_onei_chan -= 1

    # Plain おネイ can also appear without さん/ちゃん or inside ad-hoc
    # compounds such as 涼風のおネイ / 黒こげのおネイ.  Count only the
    # occurrences not already consumed by the fixed/suffixed forms above and
    # repair exactly that many legacy localized forms.
    onei_remainder = japanese
    for form in ("疾風のおネイ", "座長のおネイ", "おネイの新メニュー",
                 "おネイさん", "おネイちゃん"):
        onei_remainder = onei_remainder.replace(form, "")
    missing_plain_onei = max(0, onei_remainder.count("おネイ") - text.count("오네이"))
    for variant in (
        "네이 누나", "네이 언니", "네이 누님", "네이누나", "네이언니", "네이누님",
        "누나", "언니", "누님",
    ):
        while missing_plain_onei and variant in text:
            text = text.replace(variant, "오네이", 1)
            missing_plain_onei -= 1

    targets = source_targets(japanese)
    if not targets or len(set(targets)) != 1:
        return text

    target = targets[0]
    for bad in BAD_PLAIN_FORMS:
        if bad != target:
            # Do not let the plain ネイ repair rewrite the ネイ substring
            # inside the deliberately distinct 오네이 spelling.
            text = re.sub(rf"(?<!오){re.escape(bad)}", target, text)

    # A few translations dropped the suffix while keeping the name.  Because
    # this function only runs when the Japanese record contains exactly one
    # unambiguous plain source form, restoring the suffix is safe.
    if len(targets) == 1 and target not in text and text.count("네이") == 1:
        text = text.replace("네이", target, 1)

    return _repair_particles(text, target)


# 白鷹 is the character name 시로타카.  Older machine translations rendered
# the kanji literally or misread it in many different ways.  A global
# 백호/백학 replacement is unsafe because those strings can be ordinary nouns,
# so normalize them only when the aligned Japanese record actually contains
# 白鷹.
SHIROTAKA_ALIASES = (
    "하쿠오우", "하쿠요우", "하쿠요", "하쿠타치",
    "백호", "백아", "백악", "백학", "백타",
    "시라타코", "시라와시", "시라토리", "시라카기", "살카",
)

# Source-driven proper-name honorific normalization.  This intentionally lists
# real character names only; generic forms such as ウェイトレスちゃん,
# ママさん, ニンゲンさん remain contextual Korean rather than being forced.
# Source-gated legacy Korean aliases that must be canonicalized before the
# exact base+honorific repair below.  Keep this narrow: ordinary words must not
# be globally rewritten just because they resemble a character name.
NAMED_HONORIFIC_ALIASES = {
    "レオルム": ("레올름", "레오룸", "레올룸"),
    "プリティベリー": ("프리티 베리",),
}

NAMED_HONORIFIC_BASES = {
    "サーリ": "살리",
    "キャス": "캐스",
    "キャスティ": "캐스티",
    "フェリエ": "펠리에",
    "リン": "린",
    "プリム": "프림",
    "イオン": "이온",
    "プリティベリー": "프리티베리",
    "ウンドゥ": "운두",
    "シュレリア": "슈레리아",
    "ネロ": "네로",
    "レナルル": "레나루루",
    "メルティピコ": "멜티피코",
    "ピコ": "피코",
    "ヒャッハー": "햐하",
    "デルタ": "델타",
    "カノン": "카논",
    "レオルム": "레오름",
    "プランク": "플랭크",
    "イオナサル": "이오나사르",
    "アーシェス": "아셰스",
    "タットリア": "타토리아",
    "コーザル": "코잘",
    "白鷹": "시로타카",
    "天統姫": "텐토우키",
}

SOURCE_HONORIFIC_SUFFIX = {
    "ちゃん": "쨩",
    "さん": "씨",
    "君": "군",
    "くん": "군",
    "様": "님",
    "さま": "님",
}

WRONG_KOREAN_HONORIFICS = (
    " 양", "양", " 언니", "언니", " 누나", "누나", " 누님", "누님",
    " 짱", "짱", " 쨩", "쨩", " 씨", "씨", " 군", "군", " 님", "님",
)


def _replace_vowel_name(text: str, before: str, after: str) -> str:
    """Replace a name and repair particles when 받침 status changes."""
    # Only the legacy literal readings 백악/백학 end in a 받침 while
    # 시로타카 does not.  Handle the longest copula/particle forms first so
    # `백악이라는` is not accidentally treated as subject particle `이`.
    if before in ("백악", "백학"):
        particle_pairs = (
            ("이었다", "였다"), ("이라는", "라는"), ("이라고", "라고"),
            ("이라", "라"), ("이야", "야"), ("이나", "나"),
            ("이랑", "랑"), ("으로", "로"),
            ("은", "는"), ("을", "를"), ("과", "와"), ("이", "가"),
        )
        for old_particle, new_particle in particle_pairs:
            text = text.replace(before + old_particle, after + new_particle)
    return text.replace(before, after)


def _has_batchim(char: str) -> bool:
    return "가" <= char <= "힣" and (ord(char) - 0xAC00) % 28 != 0


def _repair_named_particles(text: str, target: str) -> str:
    """Repair particles after an attached Korean honorific."""
    if not target or not ("가" <= target[-1] <= "힣"):
        return text
    if _has_batchim(target[-1]):
        pairs = (
            ("라면", "이라면"), ("라고", "이라고"), ("라는", "이라는"),
            ("라니", "이라니"), ("란", "이란"), ("랑", "이랑"), ("로", "으로"),
            ("는", "은"), ("가", "이"), ("를", "을"), ("와", "과"),
        )
    else:
        pairs = (
            ("이라면", "라면"), ("이라고", "라고"), ("이라는", "라는"),
            ("이라니", "라니"), ("이란", "란"), ("이랑", "랑"), ("으로", "로"),
            ("은", "는"), ("이", "가"), ("을", "를"), ("과", "와"),
        )
    for before, after in pairs:
        text = text.replace(target + before, target + after)
    return text


def _source_name_count(japanese: str, name: str) -> int:
    if all("ァ" <= ch <= "ヺ" or ch == "ー" for ch in name):
        return len(re.findall(rf"(?<![ァ-ヺー]){re.escape(name)}(?![ァ-ヺー])", japanese))
    return japanese.count(name)


def _normalize_named_honorifics(japanese: str, korean: str) -> str:
    text = korean
    for source_name, base in NAMED_HONORIFIC_BASES.items():
        source_name_count = _source_name_count(japanese, source_name)
        if not source_name_count:
            continue
        for alias in NAMED_HONORIFIC_ALIASES.get(source_name, ()):
            text = text.replace(alias, base)
        found = []
        for source_suffix, ko_suffix in SOURCE_HONORIFIC_SUFFIX.items():
            n = japanese.count(source_name + source_suffix)
            if n:
                found.append((source_suffix, ko_suffix, n))
        if not found:
            continue

        # Mixed source honorifics for one name are context-sensitive.  Without
        # per-occurrence alignment we cannot know which Korean occurrence maps
        # to which source suffix, so leave that name untouched in this record.
        target_suffixes = {ko_suffix for _, ko_suffix, _ in found}
        if len(target_suffixes) != 1:
            continue

        for _, ko_suffix, _ in found:
            target = base + ko_suffix
            for wrong in WRONG_KOREAN_HONORIFICS:
                candidate = base + wrong
                if candidate != target:
                    text = text.replace(candidate, target)
            # Vocative `살리야！` / `캐스야？` is a dropped source ちゃん, not
            # the copula.  Remove that Korean-only vocative ending before the
            # generic bare-name restoration below.
            if ko_suffix in {"쨩", "씨", "군", "님"}:
                text = re.sub(
                    rf"{re.escape(base)}[야아](?=\s*(?:[!！?？.,。…]|<CR>|$))",
                    target,
                    text,
                )
            text = _repair_named_particles(text, target)

        ko_suffix = next(iter(target_suffixes))
        expected_count = sum(n for _, suffix, n in found if suffix == ko_suffix)
        target = base + ko_suffix
        # Restore a completely dropped suffix only when every occurrence of the
        # Japanese name in this record carries that same honorific and the
        # Korean base count aligns exactly.  This avoids corrupting キャスティ
        # with the shorter キャス mapping or adding suffixes to plain-name uses.
        if (
            source_name_count == expected_count
            and text.count(target) < expected_count
            and text.count(base) == expected_count
        ):
            text = text.replace(base, target)
            text = _repair_named_particles(text, target)

    return text


def _normalize_nyuroki_names(japanese: str, korean: str) -> str:
    """Keep にゅろきー (뉴로키) and the knockoff にゃろきー (냐로키) distinct."""
    source_names = [
        match.group(0)
        for match in re.finditer(r"にゅろきー|にゃろきー", japanese)
    ]
    if not source_names or "にゃろきー" not in source_names:
        return korean

    target_matches = list(re.finditer(r"뉴로키|냐로키(?:이)?", korean))
    if len(target_matches) == len(source_names):
        parts: list[str] = []
        last = 0
        for source_name, match in zip(source_names, target_matches):
            parts.append(korean[last:match.start()])
            parts.append("냐로키" if source_name == "にゃろきー" else "뉴로키")
            last = match.end()
        parts.append(korean[last:])
        return "".join(parts)

    # If this record contains only the knockoff name, a count mismatch can only
    # come from dropped/repeated Korean wording.  It is still safe to repair the
    # known old merged spelling without touching ordinary にゅろきー records.
    if all(source_name == "にゃろきー" for source_name in source_names):
        return korean.replace("냐로키이", "냐로키").replace("뉴로키", "냐로키")

    return korean


def normalize_source_terms(japanese: str, korean: str) -> str:
    """Normalize terms whose safe Korean form depends on the Japanese source."""
    text = _normalize_nyuroki_names(japanese, korean)

    # シャール達 / シャールたち is an ordinary plural, not a separate party
    # or entourage.  Keep this source-gated so a genuine Korean `일행` elsewhere
    # is never flattened.  シャールの全滅 is a different construction: the
    # legacy `샤르 일행의 전멸` must become simply `샤르의 전멸`.
    if "シャール達" in japanese or "シャールたち" in japanese:
        text = text.replace("샤르 일행", "샤르들")
    if "シャールの全滅" in japanese:
        text = text.replace("샤르 일행", "샤르")
        text = text.replace("샤르들의 전멸", "샤르의 전멸")

    # 七支 is the established setting term 칠지 (the seven 皇帝契絆支).
    # Legacy machine translations guessed several Japanese readings or even
    # paraphrased it as a generic group.  Gate these aliases on the source term
    # so ordinary Korean uses of the same syllables are never affected.
    if "七支" in japanese:
        for alias in (
            "나나나시", "나나쿠사", "나나시", "나나나", "나나차",
            "시치", "시시", "일곱 지파",
        ):
            text = text.replace(alias, "칠지")
        if "七支の想い" in japanese:
            text = text.replace("일곱 가지 염원", "칠지의 마음")

    # 割符 is the setting's ordinary "증표".  Older translations guessed from
    # the immediate train context and rendered it as 승차권/와리후/부적.  Gate
    # these repairs on the Japanese source so genuine tickets or charms remain
    # untouched.  天領割符 is the separate registered title 천령증표 and is
    # already handled by the canonical rename table.
    if "割符" in japanese and "天領割符" not in japanese:
        for alias in ("승차권", "와리후", "부적", "할부"):
            text = text.replace(alias, "증표")
        text = _repair_named_particles(text, "증표")

    # ヒトガタ is a glossary/world-setting term, not the ordinary noun 人形.
    # Old translations sometimes flattened it to `인형` or explanatory
    # `인간 형태`.  Gate every repair on the aligned Japanese source so normal
    # 人形 records remain untouched, and repair particles for the vowel-ending
    # canonical spelling 히토가타.
    if "ヒトガタ" in japanese:
        for before, after in (
            ("인간 형태인", "히토가타인"),
            ("인형이었", "히토가타였"),
            ("인형이야", "히토가타야"),
            ("인형이니까", "히토가타니까"),
            ("인형이기", "히토가타이기"),
            ("인형이라", "히토가타라"),
            ("인형인", "히토가타인"),
            ("인형의", "히토가타의"),
            ("인형으로", "히토가타로"),
            ("인형은", "히토가타는"),
            ("인형을", "히토가타를"),
            ("인형과", "히토가타와"),
            ("인형이 될", "히토가타가 될"),
            ("인형이 된", "히토가타가 된"),
            ("인형이 되", "히토가타가 되"),
        ):
            text = text.replace(before, after)

    # にゅろーん星 is the fictional planet name behind にゅろきー.  Old
    # translations split into several phonetic guesses (뉘로른/뉴로른/뉴로온)
    # and sometimes rendered 星 as 성.  Only normalize when the Japanese source
    # explicitly contains this name; 星人 is naturally rendered as 뉴론인.
    if "にゅろーん星" in japanese:
        for before, after in (
            ("뉘로른 행성인", "뉴론인"),
            ("뉘로른 행성", "뉴론 행성"),
            ("뉴로른 행성", "뉴론 행성"),
            ("뉴로론 행성", "뉴론 행성"),
            ("뉴로온 성", "뉴론 행성"),
            ("뉴론 성", "뉴론 행성"),
        ):
            text = text.replace(before, after)

    # 禊 / 禊ぎ is the series-specific ritual "미소기", not the glossary term
    # 浄化(정화).  Leaving old `정화` translations here makes the game's raw
    # substring glossary matcher link ordinary Misogi UI/dialogue to the
    # unrelated 浄化 glossary entry.  Keep this source-gated so genuine 浄化
    # text remains `정화`.
    if "禊" in japanese and "浄化" not in japanese:
        for before, after in (
            ("정화의 장소", "미소기 장소"),
            ("정화의 장", "미소기장"),
            ("정화 의식", "미소기"),
            ("정화처", "미소기장"),
            ("정화", "미소기"),
        ):
            text = text.replace(before, after)

    if "白鷹" in japanese:
        for alias in SHIROTAKA_ALIASES:
            text = _replace_vowel_name(text, alias, "시로타카")

        # Two records also had a wrong case/semantic role around the old name.
        # Keep these source-gated so ordinary `...에서` / `...에` text is never
        # rewritten elsewhere.
        if "サーリが白鷹から逃げた" in japanese:
            text = text.replace("시로타카에서 도망", "시로타카에게서 도망")
        if "白鷹に<CR>謳ってもらえたら" in japanese:
            text = text.replace("시로타카에<CR>노래해 준다면", "시로타카가<CR>노래해 준다면")

    return _normalize_named_honorifics(japanese, text)
