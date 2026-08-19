"""RenderDoc에서 추출한 정점 버퍼로 문자별 폰트 UV를 해독한다."""
import argparse
import json
import struct

W, H, PITCH, ORIGIN_Y, COLS = 2048, 1024, 26, 2, 79

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vertex_buffer")
    parser.add_argument("probe_json")
    parser.add_argument("output_json")
    parser.add_argument("--known")
    args = parser.parse_args()
    data = open(args.vertex_buffer, "rb").read()
    probe = json.load(open(args.probe_json, encoding="utf-8"))
    chars = [ch for line in probe["lines"] for ch in line]
    if len(chars) * 6 * 32 != len(data):
        raise SystemExit("probe length and vertex-buffer size do not match")
    decoded = []
    for glyph, ch in enumerate(chars):
        uvs = [struct.unpack_from("<2f", data, (glyph * 6 + v) * 32 + 20)
               for v in range(5)]
        min_u, max_u = min(x[0] for x in uvs), max(x[0] for x in uvs)
        min_v, max_v = min(x[1] for x in uvs), max(x[1] for x in uvs)
        px, py = min_u * W, min_v * H
        col = int(round(px / PITCH))
        row = int(round((py - ORIGIN_Y) / PITCH))
        decoded.append({
            "position": glyph, "char": ch, "cell": row * COLS + col,
            "row": row, "col": col, "uvPixelX": px, "uvPixelY": py,
            "uvWidth": (max_u - min_u) * W,
            "uvHeight": (max_v - min_v) * H,
        })
    mapping, conflicts = {}, []
    for item in decoded:
        old = mapping.get(item["char"])
        if old is not None and old != item["cell"]:
            conflicts.append({"char": item["char"], "first": old,
                              "second": item["cell"]})
        mapping[item["char"]] = item["cell"]
    result = {"mapping": mapping, "decoded": decoded, "conflicts": conflicts}
    if args.known:
        known = json.load(open(args.known, encoding="utf-8"))
        result["knownChecks"] = {
            ch: {"expected": cell, "actual": mapping.get(ch),
                 "match": mapping.get(ch) == cell}
            for ch, cell in known.items()
        }
        result["allKnownMatch"] = all(
            x["match"] for x in result["knownChecks"].values())
    with open(args.output_json, "w", encoding="utf-8") as fp:
        json.dump(result, fp, ensure_ascii=False, indent=2)
    print(f"decoded {len(decoded)} draws into {len(mapping)} unique characters")
    print(f"conflicts: {len(conflicts)}")

if __name__ == "__main__":
    main()
