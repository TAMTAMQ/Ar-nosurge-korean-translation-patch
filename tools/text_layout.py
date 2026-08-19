"""게임의 20자 자동 줄바꿈과 겹치는 강제 <CR>을 정리한다."""

import re


LINE_WRAP_CHARS = 20
CONTROL_CODE_PATTERN = re.compile(r"<[A-Za-z][A-Za-z0-9_]*>")
COLOR_CODE_PATTERN = re.compile(r"<#[0-9A-Fa-f]+>")


def visible_units(text):
    """일반 문자는 한 칸, CR 이외의 표시 제어 코드도 한 칸으로 센다."""
    text = COLOR_CODE_PATTERN.sub("", text)
    return len(CONTROL_CODE_PATTERN.sub("X", text))


def strip_wrap_boundary_breaks(text):
    """20자 이상인 조각 바로 뒤의 <CR>을 제거해 자동 줄바꿈에 맡긴다."""
    if "<CR>" not in text:
        return text
    segments = text.split("<CR>")
    output = [segments[0]]
    for index in range(1, len(segments)):
        if visible_units(segments[index - 1]) >= LINE_WRAP_CHARS:
            output[-1] += segments[index]
        else:
            output.append(segments[index])
    result = "<CR>".join(output)
    if rendered_line_count(result) > 3 and visible_units(result.replace("<CR>", "")) <= 60:
        return result.replace("<CR>", "")
    return result


def rendered_line_count(text):
    """20자 자동 개행과 남은 CR을 함께 반영한 예상 줄 수."""
    return sum(max(1, (visible_units(part) + LINE_WRAP_CHARS - 1) // LINE_WRAP_CHARS)
               for part in text.split("<CR>"))
