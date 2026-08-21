#!/usr/bin/env python3
"""Patch string bytes the compiler baked into .text as MOV/MOVK immediates.

Short std::string literals get constructed inline: the compiler copies the head
of the string from .rodata (`ldr` for 8 bytes, `ldp` for 16) and materialises
the remaining bytes as immediate constants in the instruction stream, e.g.

    mov  w8, #0x18              ; SSO length field = byte_length << 1
    adrp x9, #0x71d000
    add  x9, x9, #0x429         ; -> "人物図鑑" in .rodata
    ldr  x8, [x9]               ; first 8 bytes come from .rodata
    mov  w10, #0xe9b3           ; last 4 bytes are baked in here:
    movk w10, #0x9191, lsl #16  ;   0x9191E9B3 -> B3 E9 91 91

Patching only .rodata therefore replaces the head of such a string and leaves
the tail as the original Japanese. The mixed byte run usually decodes to a
character the game font does not contain, which renders as a "tofu" box. This
module finds those immediates and rewrites them so the tail matches the
translated payload, and fixes the inlined SSO length field when the translation
is shorter than the original (otherwise the leftover bytes render as tofu too).
"""
import struct

MOVZ, MOVK = 2, 3
IMM16_MASK = 0xFFFF << 5
NUL = bytes(1)

# How many leading bytes the compiler copies from .rodata before inlining the
# rest: `ldr xN, [ptr]` copies 8, `ldp xA, xB, [ptr]` copies 16. Anything past
# that boundary can be materialised as an immediate instead.
HEAD_CANDIDATES = (8, 16)
# Window around the ADRP+ADD in which the constructor's immediates appear.
WINDOW = range(-0x18, 0x48, 4)


def _sign_extend(value, bits):
    sign = 1 << (bits - 1)
    return (value & (sign - 1)) - (value & sign)


def _decode_mov(word):
    """Return (op, hw, imm16, rd) for a 32-bit MOVZ/MOVK, else None."""
    if (word >> 23) & 0x3F != 0b100101:
        return None
    op = (word >> 29) & 3
    if op not in (MOVZ, MOVK):
        return None
    return op, (word >> 21) & 3, (word >> 5) & 0xFFFF, word & 31


def _set_imm16(word, imm16):
    return (word & ~IMM16_MASK) | ((imm16 & 0xFFFF) << 5)


def find_adrp_add_refs(text_data, text_base, targets):
    """Map each target address to the addresses of ADRP+ADD pairs forming it."""
    refs = {target: [] for target in targets}
    for offset in range(0, len(text_data) - 8, 4):
        adrp = struct.unpack_from("<I", text_data, offset)[0]
        if adrp & 0x9F000000 != 0x90000000:
            continue
        rd = adrp & 31
        add = struct.unpack_from("<I", text_data, offset + 4)[0]
        if add & 0x7F000000 != 0x11000000 or ((add >> 5) & 31) != rd:
            continue
        imm21 = ((adrp >> 5) & 0x7FFFF) << 2 | ((adrp >> 29) & 3)
        instruction = text_base + offset
        page = (instruction & ~0xFFF) + (_sign_extend(imm21, 21) << 12)
        immediate = (add >> 10) & 0xFFF
        if (add >> 22) & 1:
            immediate <<= 12
        target = page + immediate
        if target in refs:
            refs[target].append(instruction)
    return refs


def collect_inline_patches(text_data, text_base, refs, original, payload, address):
    """Return {instruction_address: new_word} for one string's inlined bytes."""
    patches = {}
    old_length_field = len(original) << 1
    new_length_field = len(payload.rstrip(NUL)) << 1

    for reference in refs.get(address, []):
        base_offset = reference - text_base
        for delta in WINDOW:
            offset = base_offset + delta
            if offset < 0 or offset + 4 > len(text_data):
                continue
            word = struct.unpack_from("<I", text_data, offset)[0]
            decoded = _decode_mov(word)
            if decoded is None:
                continue
            op, hw, imm16, _ = decoded
            if not imm16:
                continue

            matched = False
            for head in HEAD_CANDIDATES:
                if len(original) <= head:
                    continue
                tail_len = len(original) - head
                old_value = struct.unpack(
                    "<I", original[head:head + 4].ljust(4, NUL))[0]
                new_value = struct.unpack(
                    "<I", payload[head:head + tail_len][:4].ljust(4, NUL))[0]
                if imm16 != (old_value >> (16 * hw)) & 0xFFFF:
                    continue
                replacement = (new_value >> (16 * hw)) & 0xFFFF
                if replacement != imm16:
                    patches[text_base + offset] = _set_imm16(word, replacement)
                matched = True
                break
            if matched:
                continue

            # Inlined SSO length byte, only meaningful when the length changed.
            if (op == MOVZ and hw == 0 and imm16 == old_length_field
                    and new_length_field != old_length_field):
                patches[text_base + offset] = _set_imm16(word, new_length_field)
    return patches


def build_text_patches(text_data, text_base, rodata_data, rodata_base, records):
    """records: iterable of (address, payload). Returns {address: new_word}."""
    addresses = {address for address, _ in records}
    refs = find_adrp_add_refs(text_data, text_base, addresses)
    patches = {}
    for address, payload in records:
        offset = address - rodata_base
        end = rodata_data.find(NUL, offset)
        if end < 0:
            continue
        original = bytes(rodata_data[offset:end])
        patches.update(collect_inline_patches(
            text_data, text_base, refs, original, payload, address))
    return patches
