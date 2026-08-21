"""게임의 20자 자동 줄바꿈과 겹치는 강제 <CR>을 정리한다.

게임은 대사창을 20자에서 스스로 접는다(공백과 문장부호도 1자로 센다). 그래서
20자를 이미 채운 조각 뒤의 <CR>은 중복이며, 그대로 두면 3줄짜리 창에 4줄이
밀려 뒷부분이 잘린다.

<CR>을 지울 때는 그 자리를 공백으로 메운다. 일본어는 띄어쓰기가 없어 줄바꿈만
지우면 되지만 한국어는 그 자리가 단어 경계라서, 그냥 이으면
"아니냐고PLASMA에게"처럼 두 단어가 붙어버린다.

공백까지 넣으면 세 줄을 넘기는 대사가 일부 있다. 그런 대사는 넘치지 않을
만큼만 이음새의 공백을 뒤에서부터 뺀다. 단어가 붙는 자리를 최소로 줄이면서
잘림도 피하기 위해서다.
"""

import re


LINE_WRAP_CHARS = 20
MAX_LINES = 3
CONTROL_CODE_PATTERN = re.compile(r"<[A-Za-z][A-Za-z0-9_]*>")
COLOR_CODE_PATTERN = re.compile(r"<#[0-9A-Fa-f]+>")


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


def drop_wrapped_leading_spaces(text):
    """자동 개행 자리에 걸린 공백을 버린다.

    게임은 20자를 채우면 그 자리에서 줄을 바꾼다. 그 경계에 공백이 오면 다음
    줄 맨 앞에 공백 하나가 튀어나와 " 일로 시험받고 있는 거야."처럼 보인다.
    줄이 이미 나뉘어 있으니 그 공백은 필요 없다.
    """
    output = []
    column = 0
    at_wrap = False
    for token, width in tokenize(text):
        if token == "<CR>":
            output.append(token)
            column = 0
            at_wrap = False
            continue
        if column >= LINE_WRAP_CHARS:
            column = 0
            at_wrap = True
        if at_wrap:
            # 경계에 공백이 여러 개 몰려 있어도 전부 버린다.
            if token == " ":
                continue
            at_wrap = False
        output.append(token)
        column += width
    return "".join(output)


def needs_space(left, right):
    return bool(left) and bool(right) and not left[-1].isspace() and not right[0].isspace()


def assemble(segments, spaced_joins):
    """조각을 잇는다. spaced_joins에 없는 이음새는 공백 없이 붙인다."""
    text = segments[0]
    for index in range(1, len(segments)):
        separator = " " if (index in spaced_joins and needs_space(text, segments[index])) else ""
        text += separator + segments[index]
    return text


def strip_wrap_boundary_breaks(text):
    """20자 이상인 조각 바로 뒤의 <CR>을 제거해 자동 줄바꿈에 맡긴다."""
    if "<CR>" not in text:
        return drop_wrapped_leading_spaces(text)
    segments = text.split("<CR>")

    # 1단계: 이미 20자를 채운 조각 뒤의 <CR>만 없앤다.
    merged = [segments[0]]
    merged_joins = []
    for index in range(1, len(segments)):
        if visible_units(segments[index - 1]) >= LINE_WRAP_CHARS:
            separator = " " if needs_space(merged[-1], segments[index]) else ""
            merged[-1] += separator + segments[index]
            merged_joins.append(index)
        else:
            merged.append(segments[index])
    result = "<CR>".join(merged)
    if rendered_line_count(result) <= MAX_LINES:
        return drop_wrapped_leading_spaces(result)

    # 2단계: 그래도 창을 넘기면 남은 <CR>까지 푼다. 공백을 넣은 상태로 먼저
    # 시도하고, 넘칠 때만 뒤쪽 이음새부터 공백을 하나씩 뺀다.
    budget = LINE_WRAP_CHARS * MAX_LINES
    joins = list(range(1, len(segments)))
    for glued in range(len(joins) + 1):
        spaced = set(joins[:len(joins) - glued])
        candidate = assemble(segments, spaced)
        if visible_units(candidate) <= budget:
            return drop_wrapped_leading_spaces(candidate)
    return drop_wrapped_leading_spaces(result)


def rendered_line_count(text):
    """20자 자동 개행과 남은 CR을 함께 반영한 예상 줄 수."""
    return sum(max(1, (visible_units(part) + LINE_WRAP_CHARS - 1) // LINE_WRAP_CHARS)
               for part in text.split("<CR>"))
