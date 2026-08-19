"""Build the Ar nosurge DX Korean dialogue/font LayeredFS mod.

Hangul is not present in the game's character-to-atlas lookup table.  Replace
rare Japanese dialogue characters in the EBM text with three-byte UTF-8 CJK
stand-ins, and draw the corresponding Hangul glyph in each stand-in's atlas
cell.  Only BC3 alpha blocks touched by selected cells are rewritten; all
other compressed font data remains byte-identical to the original.
"""
from collections import Counter, defaultdict
import argparse
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DIST = None
ORIGINAL_FONT = None
MAPPING_JSON = ROOT / "data" / "char_to_cell_renderdoc.json"
PROBE_JSON = ROOT / "data" / "probe_chars_full.json"
OUT = ROOT / "build" / "mod"
REPORT = ROOT / "build" / "final_mod_report.json"
FONT_PATH = ROOT / "fonts" / "Pretendard-Bold.otf"

W, H = 2048, 1024
PITCH, ORIGIN_Y, CELL_W, CELL_H = 26, 2, 23, 26
COLS, ROWS = 79, 39
G1T_HEADER = 56
INSET_L, INSET_R, INSET_T, INSET_B = 2, 2, 2, 2


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


def choose_maps(hangul):
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
    candidates = sorted(unique_chars,
                        key=lambda ch: (frequency.get(ch, 10**9), ord(ch)))
    if len(candidates) < len(hangul):
        raise RuntimeError(f"safe cells {len(candidates)} < Hangul {len(hangul)}")

    standins = candidates[:len(hangul)]
    hangul_to_standin = dict(zip(hangul, standins))
    hangul_to_cell = {h: unique_chars[s] for h, s in hangul_to_standin.items()}
    hangul_to_rect = {h: metrics[s] for h, s in hangul_to_standin.items()}
    return hangul_to_standin, hangul_to_cell, hangul_to_rect, by_cell


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
    global DIST, ORIGINAL_FONT, MAPPING_JSON, PROBE_JSON, OUT, REPORT, FONT_PATH
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translated-mod", required=True, type=Path,
                        help="번역된 romfs/Event/event가 들어 있는 모드 루트")
    parser.add_argument("--original-font", required=True, type=Path,
                        help="본인 게임에서 추출한 원본 MainFont_nx_0.g1t")
    parser.add_argument("--mapping", type=Path, default=MAPPING_JSON)
    parser.add_argument("--probe", type=Path, default=PROBE_JSON)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--font", type=Path, default=FONT_PATH)
    parser.add_argument("--extra-text-dir", type=Path,
                        help="폰트 매핑에 포함할 추가 UTF-8 텍스트/XML 폴더")
    args = parser.parse_args()
    DIST, ORIGINAL_FONT = args.translated_mod, args.original_font
    MAPPING_JSON, PROBE_JSON = args.mapping, args.probe
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
    hangul_to_standin, hangul_to_cell, hangul_to_rect, by_cell = choose_maps(hangul)

    if OUT.exists():
        shutil.rmtree(OUT)
    event_out = OUT / "romfs" / "Event" / "event"
    replaced_total = 0
    for src in ebm_files:
        rel = src.relative_to(DIST / "romfs" / "Event" / "event")
        data = src.read_bytes()
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
        "hangul_occurrences_replaced": replaced_total,
        "remaining_hangul": remaining_hangul,
        "captured_characters": sum(len(v) for v in by_cell.values()),
        "unique_candidate_cells": sum(len(v) == 1 for v in by_cell.values()),
        "shared_cells_excluded": sum(len(v) > 1 for v in by_cell.values()),
        "wide_unique_candidate_cells": len({x["cell"] for x in hangul_to_rect.values()}),
        "font_alpha_blocks_rewritten": touched_blocks,
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
