#!/usr/bin/env python3
"""Read and write `Event/balloonsel/balloonseldata.bsb` (dialogue choice data).

The file holds every選択肢 balloon the game shows during conversations. It is
neither EBM nor XML, so it was invisible to the rest of the pipeline; the
Japanese left in it gets drawn with the font cells the Korean patch reuses for
Hangul, which makes individual characters come out as unrelated Hangul
syllables.

Layout (little endian, no padding):

    u32                     group count
    per group:
        u32                 option count
        per option:
            u32             byte length including the trailing NUL
            bytes           UTF-8 text, NUL terminated

Every option ends with an ideographic space (U+3000) that the game relies on
for balloon padding, so the encoder keeps whatever the caller supplies and the
translator restores it explicitly.
"""
import struct

TRAILER = "　"


def parse(data):
    """Return a list of groups, each a list of option strings."""
    group_count = struct.unpack_from("<I", data, 0)[0]
    position = 4
    groups = []
    for _ in range(group_count):
        option_count = struct.unpack_from("<I", data, position)[0]
        position += 4
        options = []
        for _ in range(option_count):
            length = struct.unpack_from("<I", data, position)[0]
            position += 4
            raw = data[position:position + length]
            position += length
            if not raw.endswith(b"\0"):
                raise ValueError(f"option at {position} is not NUL terminated")
            options.append(raw[:-1].decode("utf-8"))
        groups.append(options)
    if position != len(data):
        raise ValueError(f"trailing bytes: consumed {position} of {len(data)}")
    return groups


def build(groups):
    out = bytearray(struct.pack("<I", len(groups)))
    for options in groups:
        out += struct.pack("<I", len(options))
        for option in options:
            payload = option.encode("utf-8") + b"\0"
            out += struct.pack("<I", len(payload)) + payload
    return bytes(out)
