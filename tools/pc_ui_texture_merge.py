#!/usr/bin/env python3
"""스위치 기반 한국어 UI G1T의 '실제로 수정한 블록'만 PC 원본 G1T에 이식한다.

한국어 UI 이미지는 Switch 원본에서 편집되었기 때문에 G1T 전체를 PC판에 넣으면
버튼/패드 아이콘 같은 플랫폼 전용 픽셀도 Switch판 것으로 바뀐다. 이 모듈은
`originalImage/<name>.<index>.png`와 `translateImage/<name>.<index>.png`를 비교해
보이는 픽셀이 바뀐 BC3 4x4 블록만 찾고, 그 블록만 한국어 Switch G1T에서 PC
원본 G1T로 복사한다. 따라서 한국어 이미지 수정은 유지하면서 PC 전용 아이콘과
그 밖의 미수정 픽셀은 PC 원본 그대로 남는다.

현재 직접 편집한 UI 페이지는 모두 20바이트 텍스처 헤더 + BC3(16바이트/4x4)
최상위 레벨 하나로 구성되어 있다. 구조가 달라지면 추측해서 쓰지 않고 중단한다.
"""

from __future__ import annotations

import argparse
import re
import struct
from pathlib import Path

from PIL import Image, ImageChops


MAGIC = b"GT1G"
PC_PLATFORM = 0x0A
TEXTURE_HEADER_SIZE = 20
BC3_BLOCK_SIZE = 16
FONT_HEADER_SIZE = 56
FONT_WIDTH = 2048
FONT_HEIGHT = 1024
PAGE_RE = re.compile(r"^(?P<stem>.+)\.(?P<index>\d{2})\.png$", re.IGNORECASE)


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _layout(data: bytes, label: str) -> tuple[int, int, list[int]]:
    if data[:4] != MAGIC:
        raise ValueError(f"{label}: G1T 매직이 아닙니다")
    table = _u32(data, 0x0C)
    count = _u32(data, 0x10)
    if table < 0x18 or table + count * 4 > len(data):
        raise ValueError(f"{label}: 잘못된 G1T 오프셋 테이블")
    offsets = [_u32(data, table + i * 4) for i in range(count)]
    starts = [table + value for value in offsets]
    if starts != sorted(starts) or any(s < table + count * 4 or s >= len(data) for s in starts):
        raise ValueError(f"{label}: 잘못된 텍스처 오프셋")
    return table, count, starts


def merge_g1t_entries(
    pc_original: Path,
    translated: Path,
    copy_entries: list[int] | tuple[int, ...],
) -> tuple[bytes, dict]:
    """PC 원본 G1T의 컨테이너/플랫폼 구조를 유지하고 지정 텍스처만 이식한다.

    PC와 Switch가 같은 G1T 슬롯/크기를 공유하더라도 일부 텍스처는 플랫폼 전용일
    수 있다. 예를 들어 타이틀의 0번 텍스처에는 PC에만 있는 EXIT 이미지가 있다.
    이 경우 Switch 번역 G1T 전체를 복사하지 않고, 한국어가 필요한 공통 텍스처
    엔트리만 PC 원본에 복사한다.
    """
    pc = pc_original.read_bytes()
    kr = translated.read_bytes()
    if len(pc) != len(kr):
        raise ValueError(
            f"{pc_original.name}: PC 원본/번역 G1T 크기가 다릅니다 ({len(pc)} / {len(kr)})"
        )

    pc_table, pc_count, pc_starts = _layout(pc, f"PC {pc_original.name}")
    kr_table, kr_count, kr_starts = _layout(kr, f"번역 {translated.name}")
    if (pc_table, pc_count, pc_starts) != (kr_table, kr_count, kr_starts):
        raise ValueError(f"{pc_original.name}: PC와 번역 G1T 텍스처 구조가 다릅니다")

    wanted = list(dict.fromkeys(int(index) for index in copy_entries))
    if any(index < 0 or index >= pc_count for index in wanted):
        raise ValueError(
            f"{pc_original.name}: 이식 엔트리 범위가 잘못되었습니다: {wanted} / count={pc_count}"
        )

    out = bytearray(pc)
    copied = []
    for index in wanted:
        start = pc_starts[index]
        end = pc_starts[index + 1] if index + 1 < pc_count else len(pc)
        before = pc[start:end]
        after = kr[start:end]
        out[start:end] = after
        copied.append({
            "index": index,
            "bytes": end - start,
            "changed": before != after,
        })

    # 전역 G1T 헤더는 PC 원본 것을 그대로 유지해야 한다.
    if _u32(bytes(out), 0x14) != PC_PLATFORM:
        raise ValueError(
            f"{pc_original.name}: 합성 결과 플랫폼 값이 PC(0x{PC_PLATFORM:02x})가 아닙니다"
        )
    return bytes(out), {
        "copied_entries": copied,
        "preserved_entries": [i for i in range(pc_count) if i not in wanted],
    }


def _changed_visible_blocks(original_png: Path, translated_png: Path) -> tuple[set[int], int, int]:
    with Image.open(original_png) as src_im, Image.open(translated_png) as dst_im:
        src = src_im.convert("RGBA")
        dst = dst_im.convert("RGBA")
    if src.size != dst.size:
        raise ValueError(
            f"{translated_png.name}: PNG 크기가 원본과 다릅니다 {dst.size} != {src.size}"
        )

    # 완전 투명 픽셀의 RGB 차이는 화면에 보이지 않고, G1T 재인코딩 과정에서 대량으로
    # 생길 수 있다. 알파가 어느 한쪽에서라도 보이는 픽셀의 실제 RGBA 변경만 취급한다.
    channels = ImageChops.difference(src, dst).split()
    diff_any = channels[0]
    for channel in channels[1:]:
        diff_any = ImageChops.lighter(diff_any, channel)
    visible = ImageChops.lighter(src.getchannel("A"), dst.getchannel("A"))
    changed = ImageChops.multiply(diff_any, visible)

    width, height = src.size
    blocks_w = (width + 3) // 4
    blocks = set()
    for pixel_index, value in enumerate(changed.tobytes()):
        if not value:
            continue
        x = pixel_index % width
        y = pixel_index // width
        blocks.add((y // 4) * blocks_w + (x // 4))
    return blocks, width, height


def _page_pairs(stem: str, original_images: Path, translated_images: Path) -> list[tuple[int, Path, Path]]:
    pairs = []
    for translated in sorted(translated_images.glob(f"{stem}.*.png")):
        match = PAGE_RE.match(translated.name)
        if not match or match.group("stem").lower() != stem.lower():
            continue
        index = int(match.group("index"))
        original = original_images / translated.name
        if not original.is_file():
            raise ValueError(f"편집 원본 PNG가 없습니다: {original}")
        pairs.append((index, original, translated))
    return pairs


def _decode_bc3_alpha_block(block: bytes) -> tuple[int, ...]:
    if len(block) != BC3_BLOCK_SIZE:
        raise ValueError("BC3 블록 크기가 올바르지 않습니다")
    a0, a1 = block[0], block[1]
    if a0 > a1:
        table = [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
    else:
        table = [a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255]
    bits = int.from_bytes(block[2:8], "little")
    return tuple(table[(bits >> (3 * i)) & 7] for i in range(16))


def _component_summary(blocks: set[int], blocks_w: int, limit: int = 24) -> list[dict]:
    remaining = set(blocks)
    components = []
    while remaining:
        seed = remaining.pop()
        stack = [seed]
        comp = {seed}
        while stack:
            block = stack.pop()
            x, y = block % blocks_w, block // blocks_w
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if nx < 0 or nx >= blocks_w or ny < 0:
                    continue
                neighbor = ny * blocks_w + nx
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    comp.add(neighbor)
                    stack.append(neighbor)
        components.append(comp)
    components.sort(key=len, reverse=True)
    return [
        {"blocks": len(comp), "bbox": _block_bbox(comp, blocks_w)}
        for comp in components[:limit]
    ]


def _block_bbox(blocks: set[int], blocks_w: int) -> list[int] | None:
    if not blocks:
        return None
    xs = [block % blocks_w for block in blocks]
    ys = [block // blocks_w for block in blocks]
    return [min(xs) * 4, min(ys) * 4, (max(xs) + 1) * 4 - 1, (max(ys) + 1) * 4 - 1]


def merge_font_g1t(
    pc_original: Path,
    switch_original: Path,
    switch_translated: Path,
) -> tuple[bytes, dict]:
    """PC 폰트의 플랫폼 전용 인라인 아이콘을 보존하고 한글 수정 블록만 이식한다."""
    pc = pc_original.read_bytes()
    sw = switch_original.read_bytes()
    kr = switch_translated.read_bytes()
    if not (len(pc) == len(sw) == len(kr)):
        raise ValueError(
            f"폰트 G1T 크기가 다릅니다 ({len(pc)} / {len(sw)} / {len(kr)})"
        )
    if pc[:4] != MAGIC or sw[:4] != MAGIC or kr[:4] != MAGIC:
        raise ValueError("폰트 G1T 매직이 올바르지 않습니다")
    expected = FONT_HEADER_SIZE + FONT_WIDTH * FONT_HEIGHT
    if len(pc) != expected:
        raise ValueError(f"예상하지 못한 폰트 G1T 크기입니다: {len(pc)} != {expected}")

    # PC/Switch 헤더 차이는 플랫폼 바이트(0x14)만 허용한다. 한국어 폰트는 Switch
    # 원본 헤더와 같아야 한다. 이 조건이 깨지면 다른 판본을 섞은 것이므로 중단한다.
    pc_header = bytearray(pc[:FONT_HEADER_SIZE])
    sw_header = bytearray(sw[:FONT_HEADER_SIZE])
    kr_header = bytearray(kr[:FONT_HEADER_SIZE])
    pc_header[0x14] = sw_header[0x14]
    if pc_header != sw_header:
        raise ValueError("PC/Switch 폰트 헤더가 플랫폼 바이트 외에도 다릅니다")
    kr_header[0x14] = sw_header[0x14]
    if sw_header != kr_header:
        raise ValueError("Switch 원본/한국어 폰트 헤더가 플랫폼 바이트 외에도 다릅니다")

    blocks_w = FONT_WIDTH // 4
    total_blocks = (FONT_WIDTH // 4) * (FONT_HEIGHT // 4)
    platform_blocks = set()
    translated_blocks = set()
    platform_scores = {}
    for block in range(total_blocks):
        off = FONT_HEADER_SIZE + block * BC3_BLOCK_SIZE
        pc_block = pc[off:off + BC3_BLOCK_SIZE]
        sw_block = sw[off:off + BC3_BLOCK_SIZE]
        kr_block = kr[off:off + BC3_BLOCK_SIZE]
        # PC/Switch 원본은 같은 그림을 서로 다른 BC3 값으로 재인코딩한 블록이 많다.
        # raw 바이트가 아니라 실제 알파 픽셀이 달라지는 블록만 플랫폼 전용 아이콘으로 본다.
        pc_alpha = _decode_bc3_alpha_block(pc_block)
        sw_alpha = _decode_bc3_alpha_block(sw_block)
        kr_alpha = _decode_bc3_alpha_block(kr_block)
        if pc_alpha != sw_alpha:
            platform_blocks.add(block)
            diffs = [abs(a - b) for a, b in zip(pc_alpha, sw_alpha)]
            platform_scores[block] = (max(diffs), sum(diffs), sum(d > 0 for d in diffs))
        if sw_alpha != kr_alpha:
            translated_blocks.add(block)

    conflicts = platform_blocks & translated_blocks
    if conflicts:
        coords = [(b % blocks_w * 4, b // blocks_w * 4) for b in sorted(conflicts)[:12]]
        thresholds = (1, 2, 4, 8, 16, 32, 64, 128)
        all_hist = {t: sum(score[0] >= t for score in platform_scores.values()) for t in thresholds}
        conflict_hist = {
            t: sum(platform_scores[b][0] >= t for b in conflicts) for t in thresholds
        }
        raise ValueError(
            "한글 폰트 수정 블록과 PC/Switch 원본의 시각 차이 블록이 "
            f"{len(conflicts)}개 겹칩니다. 자동 합성을 중단합니다. 예: {coords}. "
            f"최대 알파차 임계별 전체={all_hist}, 겹침={conflict_hist}, "
            f"연결영역={_component_summary(platform_blocks, blocks_w)}"
        )

    out = bytearray(pc)
    for block in translated_blocks:
        off = FONT_HEADER_SIZE + block * BC3_BLOCK_SIZE
        # 한글 폰트 패처도 알파 절반(앞 8바이트)만 수정한다. PC 원본의 색상 절반은
        # 그대로 보존해 플랫폼별 재인코딩 차이까지 불필요하게 덮어쓰지 않는다.
        out[off:off + 8] = kr[off:off + 8]

    report = {
        "translated_blocks": len(translated_blocks),
        "platform_blocks_preserved": len(platform_blocks),
        "conflicts": 0,
        "translated_bbox": _block_bbox(translated_blocks, blocks_w),
        "platform_bbox": _block_bbox(platform_blocks, blocks_w),
    }
    return bytes(out), report


def merge_ui_g1t(
    pc_original: Path,
    switch_original: Path,
    switch_translated: Path,
    original_images: Path,
    translated_images: Path,
) -> tuple[bytes, list[dict]]:
    """PC 원본에 한국어로 수정한 BC3 블록만 이식한 G1T 바이트를 반환한다."""
    pc = pc_original.read_bytes()
    sw = switch_original.read_bytes()
    kr = switch_translated.read_bytes()

    if not (len(pc) == len(sw) == len(kr)):
        raise ValueError(
            f"{pc_original.name}: PC/Switch/번역 G1T 크기가 다릅니다 "
            f"({len(pc)} / {len(sw)} / {len(kr)})"
        )

    pc_table, pc_count, pc_starts = _layout(pc, f"PC {pc_original.name}")
    sw_table, sw_count, sw_starts = _layout(sw, f"Switch {switch_original.name}")
    kr_table, kr_count, kr_starts = _layout(kr, f"번역 {switch_translated.name}")
    if (pc_table, pc_count, pc_starts) != (sw_table, sw_count, sw_starts):
        raise ValueError(f"{pc_original.name}: PC와 Switch G1T 텍스처 구조가 다릅니다")
    if (sw_table, sw_count, sw_starts) != (kr_table, kr_count, kr_starts):
        raise ValueError(f"{pc_original.name}: Switch 원본과 번역 G1T 텍스처 구조가 다릅니다")

    stem = pc_original.stem
    pairs = _page_pairs(stem, original_images, translated_images)
    if not pairs:
        raise ValueError(f"{pc_original.name}: 번역 PNG 페이지를 찾지 못했습니다")

    out = bytearray(pc)
    report = []
    for index, original_png, translated_png in pairs:
        if index >= pc_count:
            raise ValueError(f"{translated_png.name}: G1T 텍스처 인덱스 범위 밖입니다 ({index} >= {pc_count})")

        start = pc_starts[index]
        end = pc_starts[index + 1] if index + 1 < pc_count else len(pc)
        entry_size = end - start
        changed_blocks, width, height = _changed_visible_blocks(original_png, translated_png)
        blocks_w = (width + 3) // 4
        blocks_h = (height + 3) // 4
        expected = TEXTURE_HEADER_SIZE + blocks_w * blocks_h * BC3_BLOCK_SIZE
        if entry_size != expected:
            raise ValueError(
                f"{translated_png.name}: 현재 안전 이식 대상인 단일 레벨 BC3 구조가 아닙니다 "
                f"(entry={entry_size}, expected={expected})"
            )

        # 텍스처 자체의 형식/크기 헤더는 편집 전후에 같아야 한다. PC 헤더는 보존한다.
        if sw[start:start + TEXTURE_HEADER_SIZE] != kr[start:start + TEXTURE_HEADER_SIZE]:
            raise ValueError(f"{translated_png.name}: 번역 과정에서 G1T 텍스처 헤더가 바뀌었습니다")

        platform_blocks = set()
        data_start = start + TEXTURE_HEADER_SIZE
        total_blocks = blocks_w * blocks_h
        for block in range(total_blocks):
            off = data_start + block * BC3_BLOCK_SIZE
            if pc[off:off + BC3_BLOCK_SIZE] != sw[off:off + BC3_BLOCK_SIZE]:
                platform_blocks.add(block)

        conflicts = changed_blocks & platform_blocks
        if conflicts:
            sample = sorted(conflicts)[:12]
            coords = [(block % blocks_w * 4, block // blocks_w * 4) for block in sample]
            raise ValueError(
                f"{translated_png.name}: 한국어 수정 블록과 PC/Switch 전용 픽셀 블록이 "
                f"{len(conflicts)}개 겹칩니다. 자동 이식을 중단합니다. 예: {coords}"
            )

        # PNG에서 보이는 픽셀이 실제로 바뀐 블록은 G1T 압축 블록도 달라야 한다.
        unchanged_encoded = []
        for block in sorted(changed_blocks):
            off = data_start + block * BC3_BLOCK_SIZE
            if sw[off:off + BC3_BLOCK_SIZE] == kr[off:off + BC3_BLOCK_SIZE]:
                unchanged_encoded.append(block)
                continue
            out[off:off + BC3_BLOCK_SIZE] = kr[off:off + BC3_BLOCK_SIZE]
        if unchanged_encoded:
            raise ValueError(
                f"{translated_png.name}: PNG는 바뀌었지만 G1T 블록이 그대로인 곳이 "
                f"{len(unchanged_encoded)}개 있습니다. 원본/번역 파일 조합을 확인하세요."
            )

        report.append({
            "page": translated_png.name,
            "size": [width, height],
            "translated_blocks": len(changed_blocks),
            "pc_switch_blocks_preserved": len(platform_blocks),
            "conflicts": 0,
        })

    if _u32(bytes(out), 0x14) != PC_PLATFORM:
        raise ValueError(
            f"{pc_original.name}: 합성 결과 플랫폼 값이 PC(0x{PC_PLATFORM:02x})가 아닙니다"
        )
    return bytes(out), report


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pc-original", required=True, type=Path)
    ap.add_argument("--switch-original", required=True, type=Path)
    ap.add_argument("--translated", required=True, type=Path)
    ap.add_argument("--original-images", type=Path, default=repo / "originalImage")
    ap.add_argument("--translated-images", type=Path, default=repo / "translateImage")
    ap.add_argument("--output", type=Path, help="지정하면 합성 G1T를 기록한다. 생략하면 검증만 한다")
    args = ap.parse_args()

    payload, report = merge_ui_g1t(
        args.pc_original,
        args.switch_original,
        args.translated,
        args.original_images,
        args.translated_images,
    )
    for item in report:
        print(
            f"{item['page']}: 한국어 블록 {item['translated_blocks']} / "
            f"PC 전용 보존 블록 {item['pc_switch_blocks_preserved']} / 충돌 0"
        )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(payload)
        print(f"기록: {args.output} ({len(payload):,}바이트)")
    else:
        print(f"검증 완료: {args.pc_original.name} ({len(payload):,}바이트, 파일 미기록)")


if __name__ == "__main__":
    main()
