#!/usr/bin/env python3
"""PC판 exe 의 매니페스트에 activeCodePage 를 넣어 ANSI 코드페이지를 고정한다.

이 게임은 문자열 일부를 CP_ACP(시스템 ANSI 코드페이지)로 변환한다. 일본어
Windows 에서는 그 값이 932 라 문제가 없지만, 한글 Windows 에서는 949 다.
한글 패치가 대체문자로 쓰는 벽자 한자는 CP932 에는 있어도 CP949 에는 없어서
변환 과정에서 '?' 로 떨어지거나 엉뚱한 글리프가 되어 글자가 깨진다. 번역
이전의 일본어 원문에서도 같은 이유로 깨진다.

Windows 11 은 애플리케이션 매니페스트의 activeCodePage 로 프로세스 단위 ANSI
코드페이지를 정할 수 있다. 시스템 로케일을 바꾸거나 Locale Emulator 같은 외부
도구를 쓰지 않아도 이 exe 만 CP932 로 돌게 된다.

매니페스트는 .rsrc 안에 있고 뒤에 정렬 패딩이 남아 있어 섹션을 옮기지 않고
늘릴 수 있다. 리소스 데이터 엔트리의 크기와 .rsrc 의 VirtualSize 를 함께
고친다.
"""
import argparse
import pathlib
import struct
import sys

RT_MANIFEST = 24
BLOCK = (
    "\r\n  <application xmlns=\"urn:schemas-microsoft-com:asm.v3\">\r\n"
    "    <windowsSettings>\r\n"
    "      <activeCodePage "
    "xmlns=\"http://schemas.microsoft.com/SMI/2019/WindowsSettings\">"
    "{locale}</activeCodePage>\r\n"
    "    </windowsSettings>\r\n"
    "  </application>"
)


def parse(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    optsz = struct.unpack_from("<H", data, pe + 20)[0]
    secs = []
    off = pe + 24 + optsz
    for _ in range(nsec):
        name = data[off:off + 8].rstrip(b"\0").decode(errors="replace")
        vsize, vaddr, rsize, roff = struct.unpack_from("<IIII", data, off + 8)
        secs.append({"name": name, "vaddr": vaddr, "vsize": vsize,
                     "roff": roff, "rsize": rsize, "hdr": off})
        off += 40
    rsrc_rva = struct.unpack_from("<I", data, pe + 24 + 112 + 16)[0]
    return pe, secs, rsrc_rva


def find_manifest(data, secs, rsrc_rva):
    rsrc = next(s for s in secs if s["name"] == ".rsrc")

    def r2o(rva):
        return rsrc["roff"] + (rva - rsrc["vaddr"])

    root = r2o(rsrc_rva)

    def walk(off, path):
        n_named, n_id = struct.unpack_from("<HH", data, off + 12)
        found = []
        for i in range(n_named + n_id):
            nameid, offset = struct.unpack_from("<II", data, off + 16 + i * 8)
            if offset & 0x80000000:
                found += walk(root + (offset & 0x7FFFFFFF), path + [nameid])
            else:
                entry = root + offset
                rva, size, _cp, _r = struct.unpack_from("<IIII", data, entry)
                found.append((path + [nameid], entry, rva, size))
        return found

    for path, entry, rva, size in walk(root, []):
        if path and (path[0] & 0xFFFF) == RT_MANIFEST:
            return rsrc, entry, rva, size, r2o(rva)
    sys.exit("오류: RT_MANIFEST 리소스를 찾지 못했습니다.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe", required=True, type=pathlib.Path)
    ap.add_argument("--output", required=True, type=pathlib.Path)
    ap.add_argument("--locale", default="ja-JP",
                    help="activeCodePage 값. 기본 ja-JP (CP932).")
    args = ap.parse_args()

    data = bytearray(args.exe.read_bytes())
    pe, secs, rsrc_rva = parse(data)
    rsrc, entry, rva, size, off = find_manifest(data, secs, rsrc_rva)

    manifest = bytes(data[off:off + size])
    print(f"매니페스트 리소스: 오프셋 {off:#x} RVA {rva:#x} 크기 {size}")
    if b"activeCodePage" in manifest:
        sys.exit("이미 activeCodePage 가 들어 있습니다. 중복 적용을 막습니다.")
    tail = b"</assembly>"
    at = manifest.rfind(tail)
    if at < 0:
        sys.exit("오류: </assembly> 를 찾지 못했습니다.")

    block = BLOCK.format(locale=args.locale).encode()
    new = manifest[:at] + block + manifest[at:]

    limit = (rsrc["roff"] + rsrc["rsize"]) - off
    print(f"새 크기 {len(new)} / 사용 가능 {limit}")
    if len(new) > limit:
        sys.exit(f"오류: 공간 부족. {len(new)} > {limit}")

    data[off:off + len(new)] = new
    struct.pack_into("<I", data, entry + 4, len(new))          # 리소스 크기
    need = (off + len(new)) - rsrc["roff"]
    if need > rsrc["vsize"]:
        nxt = min((s["vaddr"] for s in secs if s["vaddr"] > rsrc["vaddr"]),
                  default=None)
        if nxt is not None and rsrc["vaddr"] + need > nxt:
            sys.exit("오류: VirtualSize 를 늘리면 다음 섹션과 겹칩니다.")
        struct.pack_into("<I", data, rsrc["hdr"] + 8, need)
        print(f".rsrc VirtualSize {rsrc['vsize']:#x} -> {need:#x}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(bytes(data))
    print(f"기록: {args.output} ({len(data)} 바이트, 크기 변화 "
          f"{len(data) - len(args.exe.read_bytes())})")
    print(f"activeCodePage = {args.locale}")


if __name__ == "__main__":
    main()
