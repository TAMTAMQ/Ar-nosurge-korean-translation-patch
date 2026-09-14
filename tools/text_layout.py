"""게임의 자동 줄바꿈과 겹치는 강제 <CR>을 정리한다.

화면별 표시 폭이 서로 다르므로 줄당 표시 문자 수를 인자로 받는다. 기본값은
기존 Saves 대화 계열의 20자이며, 이벤트 EBM은 24자, 필드 fm_talk는 22자를
각 빌드 단계에서 명시해서 쓴다. 최대 행 수는 공통으로 3줄이다.

<CR>을 지울 때는 그 자리를 공백으로 메운다. 일본어는 띄어쓰기가 없어 줄바꿈만
지우면 되지만 한국어는 그 자리가 단어 경계라서, 그냥 이으면
"아니냐고PLASMA에게"처럼 두 단어가 붙어버린다.

공백까지 넣으면 세 줄을 넘기는 대사가 일부 있다. 그런 대사는 넘치지 않을
만큼만 이음새의 공백을 뒤에서부터 뺀다. 단어가 붙는 자리를 최소로 줄이면서
잘림도 피하기 위해서다.
"""

import re


LINE_WRAP_CHARS = 20
EVENT_LINE_WRAP_CHARS = 24
FM_TALK_LINE_WRAP_CHARS = 22
MAX_LINES = 3
CONTROL_CODE_PATTERN = re.compile(r"<[A-Za-z][A-Za-z0-9_]*>")
COLOR_CODE_PATTERN = re.compile(r"<#[0-9A-Fa-f]+>")
FORBIDDEN_LINE_START = frozenset(".,!?、。，．！？:;)]}」』】〉》〕］｝”’")


def visible_units(text):
    """일반 문자는 한 칸, CR 이외의 표시 제어 코드도 한 칸으로 센다."""
    text = COLOR_CODE_PATTERN.sub("", text)
    return len(CONTROL_CODE_PATTERN.sub("X", text))


TOKEN_PATTERN = re.compile(r"<#[0-9A-Fa-f]+>|<[A-Za-z][A-Za-z0-9_]*>|.", re.DOTALL)


def tokenize(text):
    """표시 폭 기준으로 쪼갠다. 색 코드는 폭 0, 나머지 제어 코드는 폭 1."""
    for token in TOKEN_PATTERN.findall(text):
        if token.startswith("<#"):
            yield token, 0
        elif token.startswith("<") and token.endswith(">"):
            yield token, 0 if token == "<CR>" else 1
        else:
            yield token, 1


def drop_wrapped_leading_spaces(text, line_wrap_chars=LINE_WRAP_CHARS):
    """자동/강제 개행 뒤 첫 표시 문자 앞의 공백을 버린다."""
    output = []
    column = 0
    at_wrap = True
    for token, width in tokenize(text):
        if token == "<CR>":
            output.append(token)
            column = 0
            at_wrap = True
            continue
        if column >= line_wrap_chars:
            column = 0
            at_wrap = True
        if at_wrap:
            if token == " ":
                continue
            at_wrap = False
        output.append(token)
        column += width
    return "".join(output)


def wrap_words_at_spaces(text, line_wrap_chars=LINE_WRAP_CHARS):
    """자동 개행 직전의 공백을 소비하고 다음 단어를 새 줄 0열로 보낸다."""
    tokens = list(tokenize(text))
    output = []
    column = 0

    def next_word_width(start):
        width = 0
        for token, token_width in tokens[start:]:
            if token == "<CR>" or token == " ":
                break
            width += token_width
        return width

    for index, (token, width) in enumerate(tokens):
        if token == "<CR>":
            output.append(token)
            column = 0
            continue
        if column >= line_wrap_chars:
            column = 0
        if token == " ":
            if column == 0:
                continue
            word_width = next_word_width(index + 1)
            if word_width and column + width + word_width > line_wrap_chars:
                output.append("<CR>")
                column = 0
                continue
        output.append(token)
        column += width
    return "".join(output)


def wrap_words_with_explicit_breaks(text, line_wrap_chars=LINE_WRAP_CHARS):
    """단어 경계를 우선해 모든 자동 개행 지점을 명시적 ``<CR>``로 만든다.

    ``wrap_words_at_spaces``는 게임의 자동 개행을 전제로 줄 경계의 공백을
    제거한다. 이후 다른 위치에 강제 CR이 추가되면 그 공백이 더 이상 줄 경계가
    아니게 되어 단어가 붙을 수 있다. 고정 폭으로 완전히 재배치해야 하는 텍스트는
    이 함수를 사용해 공백은 CR로 *대체*하고, 문장 내부 공백은 그대로 보존한다.
    """
    tokens = list(tokenize(text))
    output = []
    column = 0

    def next_word_width(start):
        width = 0
        for token, token_width in tokens[start:]:
            if token == "<CR>" or token == " ":
                break
            width += token_width
        return width

    for index, (token, width) in enumerate(tokens):
        if token == "<CR>":
            output.append(token)
            column = 0
            continue
        if token == " ":
            if column == 0:
                continue
            word_width = next_word_width(index + 1)
            if word_width and column + 1 + word_width > line_wrap_chars:
                output.append("<CR>")
                column = 0
                continue
            output.append(token)
            column += 1
            continue
        if width and column + width > line_wrap_chars:
            output.append("<CR>")
            column = 0
        output.append(token)
        column += width
    return "".join(output)


def normalize_wrapped_line_starts(text, line_wrap_chars=LINE_WRAP_CHARS):
    """기존 CR 구조는 보존하고 자동/강제 개행 뒤 선행 공백만 없앤다.

    대화창처럼 최대 행 수를 재배치하면 안 되는 일반 UI/설명 텍스트용이다.
    단어가 현재 줄에 들어가지 않으면 그 앞 공백을 CR로 소비하여 다음 단어가
    새 줄의 0열부터 시작하게 한다.
    """
    return drop_wrapped_leading_spaces(
        wrap_words_at_spaces(text, line_wrap_chars), line_wrap_chars
    )


def needs_space(left, right):
    return bool(left) and bool(right) and not left[-1].isspace() and not right[0].isspace()


def assemble(segments, spaced_joins):
    """조각을 잇는다. spaced_joins에 없는 이음새는 공백 없이 붙인다."""
    text = segments[0]
    for index in range(1, len(segments)):
        separator = " " if (index in spaced_joins and needs_space(text, segments[index])) else ""
        text += separator + segments[index]
    return text


def _wrapped_line_starts(text, line_wrap_chars=LINE_WRAP_CHARS):
    """게임의 자동 개행을 흉내 내 각 표시줄의 첫 토큰을 돌려준다."""
    starts = []
    for segment in text.split("<CR>"):
        column = 0
        at_line_start = True
        for token, width in tokenize(segment):
            if column >= line_wrap_chars:
                column = 0
                at_line_start = True
            if token == " " and at_line_start:
                continue
            if at_line_start and width:
                starts.append(token)
                at_line_start = False
            column += width
    return starts


def _needs_punctuation_reflow(text, line_wrap_chars=LINE_WRAP_CHARS):
    starts = _wrapped_line_starts(text, line_wrap_chars)
    return any(token in FORBIDDEN_LINE_START for token in starts[1:])


def _rebalance_three_lines(text, line_wrap_chars=LINE_WRAP_CHARS, max_lines=MAX_LINES):
    """CR을 다시 배치해 지정 폭 이내 최대 max_lines줄로 균형 있게 나눈다."""
    segments = text.split("<CR>")
    flat = assemble(segments, set(range(1, len(segments))))
    tokens = list(tokenize(flat))
    if not tokens:
        return text

    if sum(width for _, width in tokens) > line_wrap_chars * max_lines:
        return text

    from functools import lru_cache

    def skip_spaces(index):
        while index < len(tokens) and tokens[index][0] == " ":
            index += 1
        return index

    def first_visible(index):
        index = skip_spaces(index)
        while index < len(tokens) and tokens[index][1] == 0:
            index += 1
            index = skip_spaces(index)
        return tokens[index][0] if index < len(tokens) else ""

    @lru_cache(maxsize=None)
    def solve(start, lines_left):
        start = skip_spaces(start)
        if start >= len(tokens):
            return (0, ())
        if lines_left <= 0:
            return None

        width = 0
        best = None
        for end in range(start + 1, len(tokens) + 1):
            width += tokens[end - 1][1]
            if width > line_wrap_chars:
                break

            trimmed_end = end
            while trimmed_end > start and tokens[trimmed_end - 1][0] == " ":
                trimmed_end -= 1
            if trimmed_end == start:
                continue
            line_width = sum(w for _, w in tokens[start:trimmed_end])
            next_start = skip_spaces(end)
            if next_start < len(tokens) and first_visible(next_start) in FORBIDDEN_LINE_START:
                continue

            line = "".join(token for token, _ in tokens[start:trimmed_end])
            if next_start >= len(tokens):
                candidate = ((line_wrap_chars - line_width) ** 2, (line,))
            else:
                tail = solve(next_start, lines_left - 1)
                if tail is None:
                    continue
                broke_at_space = end < len(tokens) and tokens[end][0] == " "
                ended_with_punctuation = bool(line) and line[-1] in ",.!?…。！？"
                if ended_with_punctuation:
                    break_penalty = -25
                elif broke_at_space:
                    break_penalty = 0
                else:
                    break_penalty = 1000
                candidate = (
                    tail[0] + (line_wrap_chars - line_width) ** 2 + break_penalty,
                    (line,) + tail[1],
                )
            if best is None or candidate[0] < best[0]:
                best = candidate
        return best

    solved = solve(0, max_lines)
    if solved is None:
        return text
    return "<CR>".join(solved[1])


def strip_wrap_boundary_breaks(text, line_wrap_chars=LINE_WRAP_CHARS, max_lines=MAX_LINES):
    """자동 줄바꿈 경계와 겹치는 강제 <CR>을 제거한다."""
    if "<CR>" not in text:
        return drop_wrapped_leading_spaces(text, line_wrap_chars)
    segments = text.split("<CR>")

    merged = [segments[0]]
    for index in range(1, len(segments)):
        if visible_units(segments[index - 1]) >= line_wrap_chars:
            separator = " " if needs_space(merged[-1], segments[index]) else ""
            merged[-1] += separator + segments[index]
        else:
            merged.append(segments[index])
    result = "<CR>".join(merged)
    if rendered_line_count(result, line_wrap_chars) <= max_lines:
        return drop_wrapped_leading_spaces(result, line_wrap_chars)

    budget = line_wrap_chars * max_lines
    joins = list(range(1, len(segments)))
    for glued in range(len(joins) + 1):
        spaced = set(joins[:len(joins) - glued])
        candidate = assemble(segments, spaced)
        if visible_units(candidate) <= budget:
            return drop_wrapped_leading_spaces(candidate, line_wrap_chars)
    return drop_wrapped_leading_spaces(result, line_wrap_chars)


def reflow_dialogue_layout(text, line_wrap_chars=LINE_WRAP_CHARS, max_lines=MAX_LINES):
    """지정한 폭×행 수에 맞춰 개행을 정리하고 새 줄의 선행 공백을 없앤다."""
    result = strip_wrap_boundary_breaks(text, line_wrap_chars, max_lines)
    # 이벤트 대사뿐 아니라 MESSAGE/UI/시스템 텍스트도 단어 경계 공백 때문에
    # 자동 줄바꿈된 다음 줄이 한 칸 들여써지는 문제가 생긴다. 폭을 아는 모든
    # 텍스트에서 그 공백을 개행으로 소비해 다음 단어를 0열부터 시작시킨다.
    result = wrap_words_at_spaces(result, line_wrap_chars)
    if (rendered_line_count(result, line_wrap_chars) <= max_lines and
            _needs_punctuation_reflow(result, line_wrap_chars)):
        balanced = _rebalance_three_lines(result, line_wrap_chars, max_lines)
        # 자동 줄바꿈으로 충분한데 강제 CR을 새로 늘리면 다음 실행에서 그 CR을
        # 다시 제거하는 왕복이 생길 수 있다. 같은 수 이하의 CR로 재배치될 때만
        # 채택하여 반복 빌드가 항상 같은 결과가 되게 한다.
        if balanced.count("<CR>") <= result.count("<CR>"):
            result = balanced
    return drop_wrapped_leading_spaces(result, line_wrap_chars)


def reflow_event_dialogue_layout(text):
    """이벤트 EBM의 기존 강제 개행을 풀어 24자×3줄 자동 줄바꿈에 맡긴다.

    이벤트 번역의 <CR>은 과거 20자 창에 맞춘 레이아웃용 개행이므로, 전체가
    72표시칸 이내면 모두 제거한다. 72칸을 넘는 특수 문자열은 기존 개행을 보존한
    채 일반 정리만 적용한다.
    """
    segments = text.split("<CR>")
    flattened = assemble(segments, set(range(1, len(segments))))
    if visible_units(flattened) <= EVENT_LINE_WRAP_CHARS * MAX_LINES:
        # 기존 레이아웃용 CR은 먼저 풀고, 실제 24자 자동 개행 직전의 단어 경계는
        # 공백 대신 CR로 바꿔 다음 단어가 들여쓰기 없이 0열부터 시작하게 한다.
        wrapped = wrap_words_at_spaces(flattened, EVENT_LINE_WRAP_CHARS)
        if rendered_line_count(wrapped, EVENT_LINE_WRAP_CHARS) <= MAX_LINES:
            return wrapped
        return drop_wrapped_leading_spaces(flattened, EVENT_LINE_WRAP_CHARS)
    return reflow_dialogue_layout(text, EVENT_LINE_WRAP_CHARS, MAX_LINES)


def rendered_line_count(text, line_wrap_chars=LINE_WRAP_CHARS):
    """지정한 자동 개행 폭과 남은 CR을 함께 반영한 예상 줄 수."""
    return sum(max(1, (visible_units(part) + line_wrap_chars - 1) // line_wrap_chars)
               for part in text.split("<CR>"))
