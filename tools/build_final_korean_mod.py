"""Build the Ar nosurge DX Korean dialogue/font LayeredFS mod.

Hangul is not present in the game's character-to-atlas lookup table.  Replace
rare Japanese dialogue characters in the EBM text with three-byte UTF-8 CJK
stand-ins, and draw the corresponding Hangul glyph in each stand-in's atlas
cell.  Only BC3 alpha blocks touched by selected cells are rewritten; all
other compressed font data remains byte-identical to the original.
"""
from collections import Counter, defaultdict
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from text_layout import strip_wrap_boundary_breaks


ROOT = Path(__file__).resolve().parents[1]
DIST = None
ORIGINAL_FONT = None
MAPPING_JSON = ROOT / "data" / "char_to_cell_renderdoc.json"
PROBE_JSON = ROOT / "data" / "probe_chars_full.json"
PROTECTED_JSON = ROOT / "data" / "protected_ui_chars.json"
STABLE_MAPPING_JSON = ROOT / "data" / "final_mod_report.json"
OUT = ROOT / "build" / "mod"
REPORT = ROOT / "build" / "final_mod_report.json"
FONT_PATH = ROOT / "fonts" / "Pretendard-Bold.otf"

W, H = 2048, 1024
PITCH, ORIGIN_Y, CELL_W, CELL_H = 26, 2, 23, 26
COLS, ROWS = 79, 39
G1T_HEADER = 56
INSET_L, INSET_R, INSET_T, INSET_B = 2, 2, 2, 2
RECORD_HEADER = 32


def rebuild_ebm_with_layout(data, path):
    """EBM 메타데이터를 보존하며 각 UTF-8 레코드의 CR 경계를 정리한다."""
    if len(data) < 4:
        raise RuntimeError(f"EBM too short: {path}")
    count = int.from_bytes(data[:4], "little")
    pos = 4
    output = bytearray(data[:4])
    removed = 0
    for index in range(count):
        if pos + RECORD_HEADER + 4 > len(data):
            raise RuntimeError(f"EBM header truncated: {path}:{index}")
        header = data[pos:pos + RECORD_HEADER]
        length = int.from_bytes(data[pos + RECORD_HEADER:pos + RECORD_HEADER + 4], "little")
        start = pos + RECORD_HEADER + 4
        end = start + length
        payload = data[start:end]
        if end > len(data) or not payload.endswith(b"\x00"):
            raise RuntimeError(f"EBM text framing error: {path}:{index}")
        text = payload[:-1].decode("utf-8")
        laid_out = strip_wrap_boundary_breaks(text)
        removed += text.count("<CR>") - laid_out.count("<CR>")
        encoded = laid_out.encode("utf-8") + b"\x00"
        output += header
        output += len(encoded).to_bytes(4, "little")
        output += encoded
        pos = end
    if pos != len(data):
        raise RuntimeError(f"EBM trailing bytes: {path}:{len(data) - pos}")
    return bytes(output), removed


def decode_bc4(payload):
    """Decode the alpha half of every BC3 block into an 8-bit image."""
    alpha = np.zeros((H, W), dtype=np.uint8)
    blocks_x = W // 4
    for by in range(H // 4):
        for bx in range(blocks_x):
            off = (by * blocks_x + bx) * 16
            a0, a1 = payload[off], payload[off + 1]
            if a0 > a1:
                table = [a0, a1] + [((7 - i) * a0 + i * a1) // 7
                                    for i in range(1, 7)]
            else:
                table = [a0, a1] + [((5 - i) * a0 + i * a1) // 5
                                    for i in range(1, 5)] + [0, 255]
            bits = int.from_bytes(payload[off + 2:off + 8], "little")
            for i in range(16):
                alpha[by * 4 + i // 4, bx * 4 + i % 4] = table[(bits >> (3 * i)) & 7]
    return alpha


def encode_bc4_alpha(block):
    """Encode one 4x4 alpha block with BC4's eight interpolation levels."""
    palette = np.array([255, 0, 218, 182, 145, 109, 72, 36], dtype=np.int16)
    bits = 0
    for i, value in enumerate(block.reshape(-1)):
        index = int(np.abs(palette - int(value)).argmin())
        bits |= index << (3 * i)
    return bytes((255, 0)) + bits.to_bytes(6, "little")


def render_glyph(ch, width, height):
    scale = 4
    image = Image.new("L", (width * scale, height * scale), 0)
    font = ImageFont.truetype(str(FONT_PATH), int(min(width, height) * scale * 1.06))
    ImageDraw.Draw(image).text((width * scale / 2, height * scale / 2), ch,
                               font=font, fill=255, anchor="mm")
    return np.asarray(image.resize((width, height), Image.Resampling.LANCZOS))


def choose_maps(hangul, protected, stable_mapping):
    capture = json.loads(MAPPING_JSON.read_text(encoding="utf-8"))
    captured = capture["mapping"]
    metrics = {}
    for item in capture["decoded"]:
        metrics.setdefault(item["char"], item)
    probe = json.loads(PROBE_JSON.read_text(encoding="utf-8"))
    frequency = probe["frequency"]

    by_cell = defaultdict(list)
    for ch, cell in captured.items():
        by_cell[cell].append(ch)

    # A shared cell is ambiguous: changing it would alter more than one
    # Japanese code point.  Exclude every such cell completely.
    unique_chars = {
        chars[0]: cell for cell, chars in by_cell.items()
        if (len(chars) == 1 and metrics[chars[0]]["uvWidth"] >= 24 and
            metrics[chars[0]]["uvHeight"] >= 24)
    }
    candidates = sorted((ch for ch in unique_chars if ch not in protected),
                        key=lambda ch: (frequency.get(ch, 10**9), ord(ch)))
    hangul_to_standin = {
        ch: stable_mapping[ch] for ch in hangul if ch in stable_mapping
    }
    reserved = set(stable_mapping.values())
    available = [ch for ch in candidates if ch not in reserved]
    new_hangul = [ch for ch in hangul if ch not in hangul_to_standin]
    if len(available) < len(new_hangul):
        raise RuntimeError(f"safe new cells {len(available)} < new Hangul {len(new_hangul)}")
    hangul_to_standin.update(zip(new_hangul, available))
    invalid = {ko: ja for ko, ja in hangul_to_standin.items() if ja not in unique_chars}
    if invalid:
        raise RuntimeError(f"stable mapping contains unavailable cells: {invalid}")
    hangul_to_cell = {h: unique_chars[s] for h, s in hangul_to_standin.items()}
    hangul_to_rect = {h: metrics[s] for h, s in hangul_to_standin.items()}
    return hangul_to_standin, hangul_to_cell, hangul_to_rect, by_cell


# SHA-256 of the untouched MainFont_nx_0.g1t dumped from update 1.0.1. Building
# on top of an already patched font leaves stale Hangul from the older mapping
# in cells the current mapping expects to still hold Japanese, which shows up
# in game as scrambled syllables in menus, numbers and button prompts.
VERIFIED_ORIGINAL_SHA256 = "732f2aeb3860c76832dc18ae80de5a775addef561df41e2984d7ca2c64e810b4"
ALREADY_PATCHED_TOLERANCE = 30.0


def verify_original_font(hangul_to_rect, allow_unverified=False):
    """Refuse to build on a font that already carries Hangul glyphs."""
    data = ORIGINAL_FONT.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest == VERIFIED_ORIGINAL_SHA256:
        return
    message = (f"원본 폰트 해시가 확인된 값과 다릅니다.\n"
               f"      지정한 파일: {ORIGINAL_FONT}\n"
               f"      해시:   {digest}\n"
               f"      기대값: {VERIFIED_ORIGINAL_SHA256}\n"
               f"      게임에서 직접 추출한 원본이 아니라 이미 패치된 폰트일 수 있습니다.\n"
               f"      이미 패치된 폰트 위에 다시 빌드하면 예전 배정이 남아 메뉴·숫자·\n"
               f"      버튼 표시가 엉뚱한 한글로 깨집니다. 다른 게임 버전이라 해시가\n"
               f"      다른 것이 확실하면 --allow-unverified-font 를 붙이세요.")
    if not allow_unverified:
        raise SystemExit(f"오류: {message}")
    print(f"경고: {message}")
    if len(data) != G1T_HEADER + W * H:
        return
    alpha = decode_bc4(bytearray(data[G1T_HEADER:]))
    scores = []
    for ch in sorted(hangul_to_rect)[::max(1, len(hangul_to_rect) // 48)][:48]:
        rect = hangul_to_rect[ch]
        x = int(round(rect["uvPixelX"])) + INSET_L
        y = int(round(rect["uvPixelY"])) + INSET_T
        w = int(round(rect["uvWidth"])) - INSET_L - INSET_R
        h = int(round(rect["uvHeight"])) - INSET_T - INSET_B
        if w <= 0 or h <= 0:
            continue
        want = render_glyph(ch, w, h).astype(int)
        got = alpha[y:y + h, x:x + w].astype(int)
        if got.shape == want.shape:
            scores.append(float(np.abs(want - got).mean()))
    if scores and float(np.median(scores)) < ALREADY_PATCHED_TOLERANCE:
        raise RuntimeError(
            f"{ORIGINAL_FONT}는 이미 한글로 패치된 폰트입니다. 이 위에 다시 빌드하면 "
            "예전 배정이 남아 글자가 깨집니다. 게임에서 추출한 원본을 지정하세요."
        )


def patch_font(hangul_to_rect, destination):
    source = ORIGINAL_FONT.read_bytes()
    if len(source) != G1T_HEADER + W * H:
        raise RuntimeError(f"unexpected font size: {len(source)}")
    payload = bytearray(source[G1T_HEADER:])
    alpha = decode_bc4(payload)
    touched = set()

    for ch, rect in hangul_to_rect.items():
        # The cell number identifies the lookup-table entry, but the actual
        # sampled rectangle is character-specific and may be shifted by up to
        # half a cell.  Draw into the captured rectangle itself.
        x0 = int(round(rect["uvPixelX"]))
        y0 = int(round(rect["uvPixelY"]))
        rect_w = int(round(rect["uvWidth"]))
        rect_h = int(round(rect["uvHeight"]))
        x1, y1 = min(x0 + rect_w, W), min(y0 + rect_h, H)
        if x0 < 0 or y0 < 0 or x1 <= x0 or y1 <= y0:
            raise RuntimeError(f"UV rectangle out of range: {ch} -> {rect}")
        alpha[y0:y1, x0:x1] = 0
        bx, by = x0 + INSET_L, y0 + INSET_T
        bw = min(rect_w - INSET_L - INSET_R, W - bx)
        bh = min(rect_h - INSET_T - INSET_B, H - by)
        alpha[by:by + bh, bx:bx + bw] = render_glyph(ch, bw, bh)
        for block_y in range(y0 // 4, (y1 + 3) // 4):
            for block_x in range(x0 // 4, (x1 + 3) // 4):
                touched.add((block_x, block_y))

    blocks_x = W // 4
    for block_x, block_y in touched:
        block = alpha[block_y * 4:block_y * 4 + 4,
                      block_x * 4:block_x * 4 + 4]
        off = (block_y * blocks_x + block_x) * 16
        payload[off:off + 8] = encode_bc4_alpha(block)

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source[:G1T_HEADER] + payload)
    return len(touched)


def main():
    global DIST, ORIGINAL_FONT, MAPPING_JSON, PROBE_JSON, PROTECTED_JSON, STABLE_MAPPING_JSON, OUT, REPORT, FONT_PATH
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translated-mod", required=True, type=Path,
                        help="번역된 romfs/Event/event가 들어 있는 모드 루트")
    parser.add_argument("--original-font", required=True, type=Path,
                        help="본인 게임에서 추출한 원본 MainFont_nx_0.g1t")
    parser.add_argument("--mapping", type=Path, default=MAPPING_JSON)
    parser.add_argument("--probe", type=Path, default=PROBE_JSON)
    parser.add_argument("--protected", type=Path, default=PROTECTED_JSON,
                        help="한글 대체 문자로 사용하지 않을 UI 문자 JSON")
    parser.add_argument("--stable-mapping", type=Path, default=STABLE_MAPPING_JSON,
                        help="기존 검증된 한글→대체 문자 배정을 고정할 보고서")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--font", type=Path, default=FONT_PATH)
    parser.add_argument("--allow-unverified-font", action="store_true",
                        help="원본 폰트 해시가 확인된 값과 달라도 진행한다. 이미 패치된 "
                             "폰트를 다시 입력하면 글자가 깨지므로 주의할 것.")
    parser.add_argument("--extra-text-dir", type=Path,
                        help="폰트 매핑에 포함할 추가 UTF-8 텍스트/XML 폴더")
    args = parser.parse_args()
    DIST, ORIGINAL_FONT = args.translated_mod, args.original_font
    MAPPING_JSON, PROBE_JSON, PROTECTED_JSON = args.mapping, args.probe, args.protected
    STABLE_MAPPING_JSON = args.stable_mapping
    OUT, REPORT, FONT_PATH = args.output, args.report, args.font
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    ebm_files = sorted(DIST.rglob("*.ebm"))
    if not ebm_files:
        raise RuntimeError(f"no translated EBM files under {DIST}")
    corpus = "".join(p.read_bytes().decode("utf-8", "ignore") for p in ebm_files)
    if args.extra_text_dir:
        if not args.extra_text_dir.is_dir():
            raise RuntimeError(f"extra text directory not found: {args.extra_text_dir}")
        extra_files = sorted(p for p in args.extra_text_dir.rglob("*") if p.is_file())
        corpus += "".join(p.read_text(encoding="utf-8", errors="ignore") for p in extra_files)
    counts = Counter(ch for ch in corpus if "\uac00" <= ch <= "\ud7a3")
    # Stable, human-readable ordering; frequency does not affect correctness.
    hangul = sorted(counts)
    protected = set()
    if PROTECTED_JSON and PROTECTED_JSON.exists():
        protected = set(json.loads(PROTECTED_JSON.read_text(encoding="utf-8"))["characters"])
    stable_mapping = {}
    if STABLE_MAPPING_JSON and STABLE_MAPPING_JSON.exists():
        stable_mapping = json.loads(STABLE_MAPPING_JSON.read_text(encoding="utf-8"))["hangul_to_standin"]
    # 이미 배포된 글리프는 현재 corpus에서 잠시 사라져도 아틀라스에 계속
    # 유지한다. 일부 시스템 UI는 같은 대체문자를 별도 경로로 참조하므로
    # 기존 셀 하나라도 원래 일본어 글리프로 되돌리면 문자가 깨질 수 있다.
    font_hangul = sorted(set(hangul) | set(stable_mapping))
    hangul_to_standin, hangul_to_cell, hangul_to_rect, by_cell = choose_maps(
        font_hangul, protected, stable_mapping
    )
    verify_original_font(hangul_to_rect, args.allow_unverified_font)

    if OUT.exists():
        shutil.rmtree(OUT)
    event_out = OUT / "romfs" / "Event" / "event"
    replaced_total = 0
    removed_wrap_breaks = 0
    for src in ebm_files:
        rel = src.relative_to(DIST / "romfs" / "Event" / "event")
        data, removed = rebuild_ebm_with_layout(src.read_bytes(), src)
        removed_wrap_breaks += removed
        for ko, ja in hangul_to_standin.items():
            old, new = ko.encode("utf-8"), ja.encode("utf-8")
            n = data.count(old)
            if n:
                data = data.replace(old, new)
                replaced_total += n
        dst = event_out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)

    font_out = OUT / "romfs" / "Data" / "NX" / "Font" / "MainFont_nx_0.g1t"
    touched_blocks = patch_font(hangul_to_rect, font_out)

    remaining_hangul = 0
    for p in event_out.rglob("*.ebm"):
        text = p.read_bytes().decode("utf-8", "ignore")
        remaining_hangul += sum("\uac00" <= ch <= "\ud7a3" for ch in text)
    report = {
        "source_ebm_files": len(ebm_files),
        "unique_hangul": len(hangul),
        "font_hangul": len(font_hangul),
        "hangul_occurrences_replaced": replaced_total,
        "remaining_hangul": remaining_hangul,
        "captured_characters": sum(len(v) for v in by_cell.values()),
        "unique_candidate_cells": sum(len(v) == 1 for v in by_cell.values()),
        "shared_cells_excluded": sum(len(v) > 1 for v in by_cell.values()),
        "protected_characters_excluded": len(protected),
        "stable_mapping_assignments": sum(ch in stable_mapping for ch in font_hangul),
        "new_mapping_assignments": sum(ch not in stable_mapping for ch in font_hangul),
        "wide_unique_candidate_cells": len({x["cell"] for x in hangul_to_rect.values()}),
        "font_alpha_blocks_rewritten": touched_blocks,
        "wrap_boundary_cr_removed": removed_wrap_breaks,
        "hangul_to_standin": hangul_to_standin,
        "hangul_to_cell": hangul_to_cell,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if not isinstance(v, dict)},
                     ensure_ascii=False, indent=2))
    print(f"output: {OUT}")
    print(f"report: {REPORT}")


if __name__ == "__main__":
    main()
