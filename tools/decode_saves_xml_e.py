#!/usr/bin/env python3
"""Decode/encode Ar nosurge's version-1 Gust .e files (Saves/*.xml.e).

Use --encode to go the other way: take a plain (possibly translated) XML file
and re-scramble + Glaze-"compress" (verbatim store, like gust_enc.c does for
modding) it back into a version-1 .e file the game will load. The encoder is
the exact mirror of the decoder below -- same seeds, same constants, same
stage order run in reverse -- and round-trips byte-for-byte on all 192 of the
game's Saves/*.xml.e files.

gust_tools (gust_enc) only implements .e encoding versions 2 and 3. This game
uses version 1, which is structurally the same four-stage scrambler + "Glaze"
compression documented in gust_enc.c / gust_enc.md, but with different global
PRNG constants that were recovered by disassembling the Switch `main` NSO's
resource loader (the function chain reachable from the "Saves/item/itemData.xml"
string reference: 0x86CF0 -> 0x88B40 -> 0x8A010 -> 0x3A9890 -> 0x3960/0x3730 ->
0x75F0 -> 0x5720).

Differences from gust_enc.c's documented v2/v3 algorithm:
  - RANDOM_INCREMENT is 0x2fa5, not 0x2f09.
  - The main scrambler constant is 0x3b9a728b, not 0x3b9a73c9 (upper 16 bits
    0x3b9a are shared; only the lower 16 bits differ).
  - Otherwise the pipeline matches the "version == 2" path exactly: trailing
    bit-scramble (slice 0x100) -> whole-payload fenced scramble -> footer/
    end-marker -> rotating scramble -> checksum validation -> leading
    bit-scramble (slice 0x80) -> Glaze decompression.

The per-game seeds (main/table/length/fence) are the ones already published
in gust_tools' gust_enc.json under id "ANP" (Ar nosurge Plus) -- despite that
entry's "version": 2 tag being wrong for this executable, the seed values
themselves check out exactly (confirmed via checksum validation, which is a
strong self-check: it would not pass by chance).
"""
import argparse
import struct
import sys
from pathlib import Path

MASK32 = 0xffffffff
RANDOM_CONSTANT = 0x3b9a728b
RANDOM_INCREMENT = 0x2fa5

SEEDS_MAIN = [0x630d, 0xc9df, 0x72cb]
SEEDS_TABLE = [0xabfb, 0xab89, 0x8c27]
SEEDS_LENGTH = [0x1d, 0x13, 0x0b]
FENCE = 0x989


class RNG:
    __slots__ = ("s0", "s1")

    def init(self, r0, r1):
        self.s0 = (RANDOM_CONSTANT + r0) & MASK32
        self.s1 = r1 & MASK32

    def u15(self):
        self.s1 = (self.s0 * self.s1 + RANDOM_INCREMENT) & MASK32
        return (self.s1 >> 16) & 0x7fff

    def u16(self):
        self.s1 = (self.s0 * self.s1 + RANDOM_INCREMENT) & MASK32
        return (self.s1 >> 16) & 0xffff


def _bit_scramble_core(rng, buf, offset, chunk_size, slice_size, descramble):
    pos = offset
    remaining = chunk_size
    while remaining > 0:
        table_size = min(slice_size * 8, remaining * 8)
        if table_size < 4:
            break
        base_table = list(range(table_size))
        scrambling_table = [0] * table_size
        for i in range(table_size):
            x = rng.u15() % (table_size - i)
            scrambling_table[i] = base_table[x]
            del base_table[x]
        idx_iter = range(0, table_size - 1, 2) if descramble else range(table_size - 2, -1, -2)
        for i in idx_iter:
            v0e, v1e = scrambling_table[i], scrambling_table[i + 1]
            p0, b0 = v0e >> 3, v0e & 7
            p1, b1 = v1e >> 3, v1e & 7
            v0 = (buf[pos + p0] >> b0) & 1
            v1 = (buf[pos + p1] >> b1) & 1
            buf[pos + p0] = (buf[pos + p0] & ~(1 << b0)) & 0xff | (v1 << b0)
            buf[pos + p1] = (buf[pos + p1] & ~(1 << b1)) & 0xff | (v0 << b1)
        pos += slice_size
        remaining -= slice_size


def bit_descramble(rng, buf, offset, chunk_size, slice_size):
    _bit_scramble_core(rng, buf, offset, chunk_size, slice_size, descramble=True)


def bit_scramble(rng, buf, offset, chunk_size, slice_size):
    _bit_scramble_core(rng, buf, offset, chunk_size, slice_size, descramble=False)


def fenced_descramble(rng, buf, offset, buf_size, fence):
    for i in range(0, buf_size, 2):
        x = rng.u15()
        w = (buf[offset + i] << 8) | buf[offset + i + 1]
        if x % (fence * 2) >= fence:
            w ^= x
        w = (w - x) & 0xffff
        buf[offset + i] = (w >> 8) & 0xff
        buf[offset + i + 1] = w & 0xff


def fenced_scramble(rng, buf, offset, buf_size, fence):
    for i in range(0, buf_size, 2):
        x = rng.u15()
        w = (buf[offset + i] << 8) | buf[offset + i + 1]
        w = (w + x) & 0xffff
        if x % (fence * 2) >= fence:
            w ^= x
        buf[offset + i] = (w >> 8) & 0xff
        buf[offset + i + 1] = w & 0xff


def rotating_descramble(rng, buf, offset, buf_size, seeds_table, seeds_length):
    seed_table = list(seeds_table)
    seed_index = 0
    seed_switch_fudge = 0
    processed = 0
    for i in range(buf_size):
        buf[offset + i] ^= rng.u16() & 0xff
        processed += 1
        if processed >= seeds_length[seed_index] + seed_switch_fudge:
            seed_table[seed_index] = rng.s1
            seed_index += 1
            if seed_index >= 3:
                seed_index = 0
                seed_switch_fudge += 1
            rng.s1 = seed_table[seed_index]
            processed = 0


def checksum_sub(buf, offset, size):
    total = 0
    for i in range(0, size & ~3, 4):
        total = (total - struct.unpack_from(">I", buf, offset + i)[0]) & MASK32
    return total


def checksum_xor(buf, offset, size):
    total = 0
    for i in range(0, size & ~3, 4):
        total ^= (~struct.unpack_from(">I", buf, offset + i)[0]) & MASK32
    return total


def descramble(raw):
    rng = RNG()
    version, working_size = struct.unpack_from(">II", raw, 0)
    if version != 1:
        raise ValueError("not a version-1 .e file (got version=%d)" % version)
    payload = bytearray(raw[0x10:])
    payload_size = len(payload)

    chunk_len = min(payload_size, 0x800)
    chunk_off = payload_size - chunk_len
    rng.init(0, SEEDS_MAIN[0])
    bit_descramble(rng, payload, chunk_off, chunk_len, 0x100)

    rng.init(0, SEEDS_MAIN[1])
    fenced_descramble(rng, payload, 0, payload_size, FENCE)

    payload_size -= 16
    footer = payload[payload_size:payload_size + 16]
    marker = struct.unpack_from(">I", footer, 0)[0]
    if marker not in (0, 0xff, 0xff000000):
        raise ValueError("unexpected footer marker: 0x%08x" % marker)
    checksum = list(struct.unpack_from(">III", footer, 4))

    p = payload_size
    while p > 0 and payload[p] != 0xff:
        p -= 1
    if payload[p] != 0xff:
        raise ValueError("end-of-payload marker (0xff) not found")
    payload_size = p
    payload[payload_size] = 0

    rng.init(checksum[2], SEEDS_TABLE[0])
    rotating_descramble(rng, payload, 0, payload_size, SEEDS_TABLE, SEEDS_LENGTH)

    c0 = (checksum[0] - checksum_sub(payload, 0, payload_size)) & MASK32
    c1 = (checksum[1] ^ checksum_xor(payload, 0, payload_size)) & MASK32
    if c0 != 0 or c1 != 0:
        raise ValueError("checksum mismatch (c0=0x%08x c1=0x%08x) -- wrong seeds?" % (c0, c1))

    rng.init(checksum[2], SEEDS_MAIN[2])
    bit_descramble(rng, payload, 0, min(payload_size, 0x800), 0x80)

    return bytes(payload[:payload_size])


def adler32(data):
    a, b = 1, 0
    for byte in data:
        a = (a + byte) % 65521
        b = (b + a) % 65521
    return (b << 16) | a


def scramble(payload, working_size):
    """Reverse of descramble(): payload is Glaze-compressed bytes; returns a
    full .e file (16-byte header + scrambled body). Mirrors gust_enc.c's
    scramble() for version==2, with the version-1 constants."""
    rng = RNG()
    payload_size = len(payload)
    main_payload_size = (payload_size + 1 + 0xf) & ~0xf
    buf = bytearray(main_payload_size + 32)  # +16 footer, +16 header (added at the end)
    buf[:payload_size] = payload

    adler_sum = adler32(payload)

    rng.init(adler_sum, SEEDS_MAIN[2])
    bit_scramble(rng, buf, 0, min(payload_size, 0x800), 0x80)

    checksum0 = checksum_sub(buf, 0, payload_size)
    checksum1 = checksum_xor(buf, 0, payload_size)
    checksum2 = adler_sum
    struct.pack_into(">III", buf, main_payload_size + 4, checksum0, checksum1, checksum2)

    rng.init(checksum2, SEEDS_TABLE[0])
    rotating_descramble(rng, buf, 0, payload_size, SEEDS_TABLE, SEEDS_LENGTH)  # XOR is its own inverse

    buf[payload_size] = 0xff

    main_payload_size += 16
    rng.init(0, SEEDS_MAIN[1])
    fenced_scramble(rng, buf, 0, main_payload_size, FENCE)

    rng.init(0, SEEDS_MAIN[0])
    chunk_len = min(main_payload_size, 0x800)
    chunk_off = main_payload_size - chunk_len
    bit_scramble(rng, buf, chunk_off, chunk_len, 0x100)

    header = struct.pack(">IIII", 1, working_size, 0, 0)
    return header + bytes(buf[:main_payload_size])


# --- Glaze decompression (format is version-independent; ported from gust_enc.c) ---

class _Bits:
    __slots__ = ("buf", "pos", "end", "buffer", "mask")

    def __init__(self, buf, offset, size):
        self.buf = buf
        self.pos = offset
        self.end = offset + size
        self.buffer = 0
        self.mask = 0

    def get(self, n):
        x = 0
        for _ in range(n):
            if self.mask == 0:
                if self.pos >= self.end:
                    return None
                self.buffer = self.buf[self.pos]
                self.pos += 1
                self.mask = 0x80
            x <<= 1
            if self.buffer & self.mask:
                x |= 1
            self.mask >>= 1
        return x


def _build_code_table(buf, offset, length):
    code_table_length = struct.unpack_from(">I", buf, offset)[0]
    bits = _Bits(buf, offset + 4, length - 4)
    code_table = bytearray(code_table_length)
    i = 0
    c = bits.get(1)
    while i < code_table_length:
        if c is None:
            break
        if c == 1:
            code_table[i] = 1
        else:
            code_len = 0
            while True:
                code_len += 1
                if code_len >= 8:
                    break
                c = bits.get(1)
                if c != 0:
                    break
            if c is None:
                break
            code_table[i] = ((c << code_len) | bits.get(code_len)) & 0xff if code_len < 8 else 0
        i += 1
        c = bits.get(1)
    return code_table


def unglaze(src):
    dec_length = struct.unpack_from(">I", src, 0)[0]
    pos = 4
    bitstream_length = struct.unpack_from(">I", src, pos)[0]
    pos += 4
    code_table = _build_code_table(src, pos, bitstream_length)
    pos += bitstream_length

    dict_len = struct.unpack_from(">I", src, pos)[0]
    pos += 4
    dict_start = pos
    pos += dict_len

    len_start = pos + 4

    dst = bytearray(dec_length)
    dpos = code_i = 0
    dict_i, len_i = dict_start, len_start

    while dpos < dec_length:
        op = code_table[code_i]
        code_i += 1
        if op == 0x01:
            dst[dpos] = src[dict_i]
            dpos += 1
            dict_i += 1
        elif op == 0x02:
            dd = code_table[code_i]; code_i += 1
            dst[dpos] = dst[dpos - dd]
            dpos += 1
        elif op == 0x03:
            dd = code_table[code_i]; code_i += 1
            ll = code_table[code_i]; code_i += 1
            dd += ll
            for _ in range(ll + 1):
                dst[dpos] = dst[dpos - dd]
                dpos += 1
        elif op == 0x04:
            ll = code_table[code_i]; code_i += 1
            dd = src[dict_i] + ll; dict_i += 1
            for _ in range(ll + 1):
                dst[dpos] = dst[dpos - dd]
                dpos += 1
        elif op == 0x05:
            dd = (code_table[code_i] << 8) | src[dict_i]; code_i += 1; dict_i += 1
            ll = code_table[code_i]; code_i += 1
            dd += ll
            for _ in range(ll + 1):
                dst[dpos] = dst[dpos - dd]
                dpos += 1
        elif op == 0x06:
            ll = code_table[code_i] + 8; code_i += 1
            dst[dpos:dpos + ll] = src[dict_i:dict_i + ll]
            dpos += ll
            dict_i += ll
        elif op == 0x07:
            ll = src[len_i] + 14; len_i += 1
            dst[dpos:dpos + ll] = src[dict_i:dict_i + ll]
            dpos += ll
            dict_i += ll
        else:
            raise ValueError("unknown Glaze bytecode 0x%02x at dpos=%d" % (op, dpos))
    return bytes(dst)


def glaze(src):
    """"Compress" src into the Glaze container without real LZ compression:
    store it verbatim in the dictionary and emit bytecode 0x07 ("copy N+14
    bytes from the dictionary") for each <=256-byte block, exactly as
    gust_enc.c's glaze() does for modding purposes."""
    src_size = len(src)
    if src_size < 14:
        raise ValueError("cannot Glaze-compress data smaller than 14 bytes")
    remainder = src_size % 256
    short_last_block = (remainder != 0) and (remainder <= 14)
    num_blocks = (src_size + 255) // 256
    if short_last_block:
        num_blocks -= 1
    bitstream_size = ((5 * num_blocks) + 7) // 8

    out = bytearray()
    out += struct.pack(">III", src_size, bitstream_size + 4, num_blocks)
    pattern = bytes([0x39, 0xce, 0x73, 0x9c, 0xe7])
    stream = bytearray((bitstream_size // 5 + 1) * 5)
    for i in range(0, len(stream), 5):
        stream[i:i + 5] = pattern
    stream = stream[:bitstream_size]
    bits_in_last_byte = (5 * num_blocks) % 8
    if bits_in_last_byte != 0 and bitstream_size > 0:
        stream[-1] &= (0xff << (8 - bits_in_last_byte)) & 0xff
    out += stream

    out += struct.pack(">I", src_size)
    out += src

    out += struct.pack(">I", num_blocks)
    if num_blocks > 1:
        out += bytes([256 - 14]) * (num_blocks - 1)
    if short_last_block:
        out += bytes([(256 - 14) + (src_size % 256)])
    else:
        out += bytes([((src_size % 256) - 14) & 0xff])
    return bytes(out)


def detect_text_encoding(raw_bytes):
    """Most Saves/*.xml.e files are genuinely CP932 (matching their declared
    <?xml ... encoding="SHIFT-JIS"?>), but some (all seen so far under
    field/) are UTF-8 despite a header that still (incorrectly) claims
    SHIFT_JIS -- the declaration cannot be trusted, so sniff the actual
    bytes instead: strict UTF-8 first, then CP932 (a superset of Shift-JIS
    that also covers the NEC/IBM extended rows some item/achievement names
    use, e.g. b'\\xfb\\x7e')."""
    try:
        raw_bytes.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "cp932"


def decode_file(path):
    raw = Path(path).read_bytes()
    glaze_data = descramble(raw)
    return unglaze(glaze_data)


def encode_file(xml_bytes):
    """Encode plain XML bytes back into a version-1 .e file."""
    compressed = glaze(xml_bytes)
    # gust_enc.c: working_size = max(uncompressed_size, compressed_size + bytecode_size field)
    num_blocks = struct.unpack_from(">I", compressed, 8)[0]
    working_size = max(len(xml_bytes), len(compressed) + num_blocks)
    return scramble(compressed, working_size)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("inputs", nargs="+", type=Path,
                        help=".xml.e files to decode, or plain .xml files to --encode")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="output directory (default: alongside each input)")
    parser.add_argument("--encode", action="store_true",
                        help="re-encode plain XML files back into version-1 .xml.e")
    args = parser.parse_args()

    for path in args.inputs:
        try:
            if args.encode:
                data = encode_file(path.read_bytes())
                out_name = path.name + ".e" if not path.name.endswith(".e") else path.name
            else:
                data = decode_file(path)
                out_name = path.name[:-2] if path.name.endswith(".e") else path.name + ".decoded"
        except Exception as exc:
            print("FAIL %s: %s" % (path, exc), file=sys.stderr)
            continue
        out_path = (args.out_dir / out_name) if args.out_dir else path.with_name(out_name)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
        print("OK   %s -> %s (%d bytes)" % (path, out_path, len(data)))


if __name__ == "__main__":
    main()
