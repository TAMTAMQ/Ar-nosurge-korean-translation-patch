#!/usr/bin/env python3
"""빌드한 romfs 트리를 PC(Steam)판 게임 폴더에 설치한다.

PC 판은 루즈 파일 오버라이드가 동작하지 않으므로 PAK 을 다시 만들어야 한다.
경로 대응은 실측으로 확인한 것이다. PAK 내부는 디렉터리도 파일명도 전부
소문자다.

    romfs/Event/event/AA01/x.ebm   ->  PACK01     event/event/aa01/x.ebm
    romfs/Event/balloonsel/*.bsb   ->  PACK01     event/balloonsel/*.bsb
    romfs/Saves/chara/Chara.xml.e  ->  PACK02     saves/chara/chara.xml.e
    romfs/Data/NX/Font/*.g1t       ->  PACK00_01  data/x64/font/mainfont_x64_0.g1t
    romfs/Data/NX/ui/*.g1t         ->  PACK00_01  data/x64/ui/*.g1t

PACK00_01 은 1.4GB 라 폰트와 텍스처 몇 개 때문에 통째로 재포장하는 것이 너무
비싸다. 이 파일들은 교체본과 원본의 바이트 수가 같으므로 인덱스를 건드리지 않고
제자리에서 덮어쓴다. PACK01 / PACK02 는 작아서 gust_pak 으로 재포장한다.

두 가지 모드가 있다.

  --extract-originals  PAK 에서 폰트/UI 텍스처와 Event 원본을 꺼내 온다.
                       공통 빌드 단계에 원본으로 넘기기 위한 준비다.
  --install            빌드한 romfs 를 게임 폴더에 설치한다.
"""
import argparse
import hashlib
import pathlib
import re
import shutil
import subprocess
import sys

PLATFORM_OFFSET = 0x14
PC_PLATFORM = 0x0A
G1T_MAGIC = b"GT1G"
BS = chr(92)
LIST_RE = re.compile(r"^([0-9a-f]+)\s+([0-9a-f]+)\s+(" + BS + BS + r"\S.*?)\s*$")

FONT_KEY = BS.join(["", "data", "x64", "font", "mainfont_x64_0.g1t"])
UI_NAMES = ("common", "mainmenu", "system", "window")


def ui_key(name):
    return BS.join(["", "data", "x64", "ui", name])


def sha(data):
    return hashlib.sha256(data).hexdigest()


def known_original_font_hashes():
    """폰트 패처가 등록해 둔 '손대지 않은 원본' 해시 목록을 그대로 쓴다.

    같은 사실을 두 곳에 적으면 한쪽만 갱신되어 어긋난다.
    """
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from build_final_korean_mod import VERIFIED_ORIGINAL_SHA256
    return set(VERIFIED_ORIGINAL_SHA256)


def pak_list(gust_pak, pak):
    """gust_pak -l 로 PAK 안의 (내부경로 -> (오프셋, 크기)) 를 얻는다."""
    result = subprocess.run([str(gust_pak), "-l", str(pak)],
                            capture_output=True, text=True, errors="replace")
    entries = {}
    for line in result.stdout.splitlines():
        match = LIST_RE.match(line)
        if not match:
            continue
        offset, size, name = match.groups()
        entries[name.rstrip("*").strip().lower()] = (int(offset, 16), int(size, 16))
    if not entries:
        sys.exit(f"오류: PAK 목록을 읽지 못했습니다: {pak}")
    return entries


def read_entry(pak, offset, size):
    with open(pak, "rb") as handle:
        handle.seek(offset)
        return handle.read(size)


def write_entry(pak, offset, payload, expect_magic=None):
    """PAK 안의 한 항목을 제자리에서 덮어쓴다.

    막고 싶은 사고는 '엉뚱한 오프셋에 쓰는 것'이다. 오프셋은 PAK 인덱스에서
    받고 크기도 대조하므로, 그 자리에 같은 종류의 파일이 있는지만 확인하면
    충분하다. 원본 해시와 같기를 요구하면 이미 설치된 게임에 다시 설치할 수
    없게 되는데, 번역을 고치면 폰트 아틀라스가 바뀌므로 재설치는 정상이다.
    """
    with open(pak, "r+b") as handle:
        handle.seek(offset)
        current = handle.read(len(payload))
        if len(current) != len(payload):
            sys.exit(f"오류: PAK 끝을 넘어섭니다. offset={offset:#x}")
        if expect_magic and current[:len(expect_magic)] != expect_magic:
            sys.exit(f"오류: {offset:#x} 에 기대한 형식이 아닙니다. 오프셋을 확인하세요.")
        if current == payload:
            return False
        handle.seek(offset)
        handle.write(payload)
    if read_entry(pak, offset, len(payload)) != payload:
        sys.exit("오류: 되읽기 검증 실패.")
    return True


def backup(path, work):
    """원본을 한 번만 보관한다. 이미 있으면 그것이 진짜 원본이다.

    이미 패치된 파일을 원본으로 착각해 보관하면 되돌릴 길이 사라지고, 그 위에
    다시 빌드하면 이전 배정이 남아 글자가 깨진다. 그래서 한 번 만든 백업은
    절대 덮어쓰지 않는다.
    """
    keep = work / f"{path.stem}.ORIGINAL{path.suffix}"
    if not keep.exists():
        keep.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, keep)
        print(f"  원본 보관: {keep}")
    return keep


def extract_pak(gust_pak, pak, into):
    into.mkdir(parents=True, exist_ok=True)
    staged = into / pak.name.replace(".ORIGINAL", "")
    shutil.copyfile(pak, staged)
    result = subprocess.run([str(gust_pak), staged.name], cwd=into,
                            capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        sys.exit(f"오류: PAK 추출 실패: {pak}")
    return staged.with_suffix(".json")


def repack_pak(gust_pak, manifest):
    result = subprocess.run([str(gust_pak), manifest.name], cwd=manifest.parent,
                            capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        sys.exit(f"오류: PAK 재포장 실패: {manifest}")
    built = manifest.with_suffix(".pak")
    if not built.is_file():
        sys.exit(f"오류: 재포장 결과가 없습니다: {built}")
    return built


def extract_originals(args):
    """PACK00_01 에서 폰트와 UI 텍스처의 원본을 꺼내 둔다.

    PACK00_01 은 1.4GB 라 통째로 백업하지 않는다. 대신 우리가 건드리는 파일만
    꺼내 두고, 그것이 되돌릴 때의 복원본이 된다.

    이미 설치된 게임에서 이 단계를 다시 돌리면 패치본을 원본으로 캡처하게
    되므로, 한 번 만든 원본은 덮어쓰지 않는다. 폰트는 등록된 해시와 대조해
    확실히 막는다.
    """
    game, work = args.game_dir, args.work
    out = work / "originals"
    (out / "ui").mkdir(parents=True, exist_ok=True)

    pak = game / "Data" / "PACK00_01.PAK"
    entries = pak_list(args.gust_pak, pak)

    if FONT_KEY not in entries:
        sys.exit(f"오류: PACK00_01 에 폰트가 없습니다: {FONT_KEY}")
    offset, size = entries[FONT_KEY]
    blob = read_entry(pak, offset, size)
    if blob[:4] != G1T_MAGIC:
        sys.exit("오류: 폰트 자리에서 G1T 매직이 나오지 않습니다.")

    font_out = out / "mainfont_x64_0.g1t"
    if font_out.exists():
        print(f"  폰트: 이미 있음, 유지 ({sha(font_out.read_bytes())[:16]})")
    elif sha(blob) not in known_original_font_hashes():
        sys.exit("오류: PACK00_01 의 폰트가 등록된 원본 해시와 다릅니다.\n"
                 f"      실제 {sha(blob)}\n"
                 "      이미 패치된 게임에서 원본을 꺼내려 한 것으로 보입니다.\n"
                 "      정품 원본에서 다시 시작하거나, 보관해 둔 원본을\n"
                 f"      {font_out} 에 두고 다시 실행하세요.")
    else:
        font_out.write_bytes(blob)
        print(f"  폰트: {len(blob)} 바이트  sha {sha(blob)[:16]}")

    for name in UI_NAMES:
        key = ui_key(f"{name}.g1t")
        if key not in entries:
            print(f"  건너뜀: {key} 없음")
            continue
        target = out / "ui" / f"{name}.g1t"
        if target.exists():
            print(f"  UI {name}.g1t: 이미 있음, 유지")
            continue
        offset, size = entries[key]
        target.write_bytes(read_entry(pak, offset, size))
        print(f"  UI {name}.g1t: {size} 바이트")

    # Event 원본(.ebd / .bsb)은 PACK01 을 풀어야 얻는다.
    into = work / "extract" / "PACK01"
    if not (into / "event").is_dir():
        extract_pak(args.gust_pak, backup(game / "Data" / "PACK01.PAK", work), into)
    print(f"  Event 원본: {into / 'event'}")


def find_ci(root, relative):
    """대소문자를 가리지 않고 찾는다. 스위치 romfs 는 대문자가 섞여 있다."""
    want = relative.lower().replace("\\", "/")
    for path in root.rglob("*"):
        if path.is_file() and path.relative_to(root).as_posix().lower() == want:
            return path
    return None


def apply_switch_g1t(args, pak, entries):
    """스위치판 텍스처로 PC판 g1t 를 교체한다.

    교체본이 PAK 슬롯보다 작으면 남는 자리를 0 으로 채워 제자리에 넣는다.
    G1T 헤더 0x08 에 자기 전체 크기가 들어 있어 로더가 그 값을 쓰면 뒤쪽
    패딩은 읽지 않는다. 슬롯보다 크면 제자리 교체가 불가능하므로 중단한다.
    """
    manifest = args.g1t_manifest
    if not manifest.is_file():
        return 0
    if not args.switch_romfs:
        print("  건너뜀: --switch-romfs 를 지정하지 않았습니다 "
              f"({manifest.name} 의 교체가 적용되지 않습니다)")
        return 0
    if not args.switch_romfs.is_dir():
        sys.exit(f"오류: 스위치 romfs 폴더가 없습니다: {args.switch_romfs}")

    import json
    rules = json.loads(manifest.read_text(encoding="utf-8"))["replacements"]
    applied = 0
    for rule in rules:
        key = BS + rule["pak"].replace("/", BS)
        if key not in entries:
            sys.exit(f"오류: PAK 에 그 경로가 없습니다: {rule['pak']}")
        offset, size = entries[key]
        source = find_ci(args.switch_romfs, rule["switch"])
        if source is None:
            sys.exit(f"오류: 스위치 원본을 찾지 못했습니다: {rule['switch']}")
        payload = bytearray(source.read_bytes())
        if payload[:4] != G1T_MAGIC:
            sys.exit(f"오류: G1T 매직이 아닙니다: {source}")
        payload[PLATFORM_OFFSET] = PC_PLATFORM
        if len(payload) > size:
            sys.exit(f"오류: {rule['pak']} 교체본이 슬롯보다 큽니다 "
                     f"({len(payload)} > {size}). PACK00_01 재포장이 필요합니다.")
        padded = bytes(payload) + b"\0" * (size - len(payload))
        changed = write_entry(pak, offset, padded, G1T_MAGIC)
        applied += 1
        print(f"  {rule['pak']}: {'교체' if changed else '이미 동일'}"
              f" ({len(payload)} + 패딩 {size - len(payload)})")
    return applied


def overlay(source_root, target_root, label):
    """romfs 하위 트리를 추출된 PAK 트리에 소문자 경로로 덮어쓴다."""
    if not source_root.is_dir():
        print(f"  {label}: 넣을 것이 없습니다 ({source_root})")
        return
    written = same = 0
    missing = []
    for source in sorted(p for p in source_root.rglob("*") if p.is_file()):
        relative = source.relative_to(source_root)
        target = target_root.joinpath(*[part.lower() for part in relative.parts])
        if not target.exists():
            missing.append(relative.as_posix())
            continue
        if target.read_bytes() == source.read_bytes():
            same += 1
            continue
        shutil.copyfile(source, target)
        written += 1
    print(f"  {label}: 덮어씀 {written} / 동일 {same} / 대상없음 {len(missing)}")
    for name in missing[:10]:
        print(f"    대상없음: {name}")
    if missing:
        sys.exit(f"오류: {label} 에 PAK 안에 없는 파일이 있습니다. 경로 대응을 확인하세요.")


def install(args):
    game, work, romfs = args.game_dir, args.work, args.romfs

    print("\n[1/4] PACK00_01 제자리 교체 (폰트 / UI 텍스처)")
    pak = game / "Data" / "PACK00_01.PAK"
    # PACK00_01 은 1.4GB 라 통째로 백업하지 않는다. --extract-originals 로 꺼내 둔
    # 파일이 원본 기준이자 복원본이다.
    originals = work / "originals"
    if not (originals / "mainfont_x64_0.g1t").is_file():
        sys.exit(f"오류: 원본이 없습니다: {originals}\n"
                 "      먼저 --extract-originals 를 실행하세요.")
    entries = pak_list(args.gust_pak, pak)

    font = romfs / "Data" / "NX" / "Font" / "MainFont_nx_0.g1t"
    if font.is_file():
        offset, size = entries[FONT_KEY]
        payload = font.read_bytes()
        if len(payload) != size:
            sys.exit(f"오류: 폰트 크기가 다릅니다 {len(payload)} != {size}. 재포장이 필요합니다.")
        changed = write_entry(pak, offset, payload, G1T_MAGIC)
        print(f"  폰트: {'교체' if changed else '이미 동일'}")

    ui_dir = romfs / "Data" / "NX" / "ui"
    for source in sorted(ui_dir.glob("*.g1t")) if ui_dir.is_dir() else []:
        key = ui_key(source.name.lower())
        if key not in entries:
            print(f"  건너뜀: {key} 없음")
            continue
        offset, size = entries[key]
        payload = bytearray(source.read_bytes())
        if payload[:4] != G1T_MAGIC:
            sys.exit(f"오류: G1T 매직이 아닙니다: {source}")
        # 번역 텍스처는 스위치 원본 위에서 만든 것이라 플랫폼 바이트가 0x10 이다.
        payload[PLATFORM_OFFSET] = PC_PLATFORM
        if len(payload) != size:
            sys.exit(f"오류: {source.name} 크기가 다릅니다 {len(payload)} != {size}.")
        changed = write_entry(pak, offset, bytes(payload), G1T_MAGIC)
        print(f"  UI {source.name}: {'교체' if changed else '이미 동일'}")

    apply_switch_g1t(args, pak, entries)

    print("\n[2/4] PACK01 재포장 (대사 / 선택지 / 이벤트 스크립트)")
    # 작업 트리는 매번 원본에서 새로 푼다. 한 번 풀어 두고 재사용하면 앞선
    # 설치에서 덮어쓴 번역본이 남아, 다음에 그 트리를 원본으로 삼는 단계가
    # 번역본 위에 다시 빌드하게 된다. 실제로 그렇게 오염된 적이 있다.
    staging = work / "staging" / "PACK01"
    if staging.exists():
        shutil.rmtree(staging)
    manifest = extract_pak(args.gust_pak, backup(game / "Data" / "PACK01.PAK", work), staging)
    overlay(romfs / "Event", manifest.parent / "event", "Event")
    shutil.copyfile(repack_pak(args.gust_pak, manifest), game / "Data" / "PACK01.PAK")
    print(f"  설치: {game / 'Data' / 'PACK01.PAK'}")

    print("\n[3/4] PACK02 재포장 (Saves)")
    staging = work / "staging" / "PACK02"
    if staging.exists():
        shutil.rmtree(staging)
    manifest = extract_pak(args.gust_pak, backup(game / "Data" / "PACK02.PAK", work), staging)
    overlay(romfs / "Saves", manifest.parent / "saves", "Saves")
    shutil.copyfile(repack_pak(args.gust_pak, manifest), game / "Data" / "PACK02.PAK")
    print(f"  설치: {game / 'Data' / 'PACK02.PAK'}")

    print("\n[4/4] 실행 파일 패치 (문자열 / 코드페이지)")
    exe = game / "ArnosurgeDX.exe"
    original_exe = backup(exe, work)
    here = pathlib.Path(__file__).resolve().parent
    staged = work / "ArnosurgeDX.strings.exe"
    subprocess.run([sys.executable, str(here / "build_pc_main_text_patch.py"),
                    "--exe", str(original_exe),
                    "--translations", str(args.translations),
                    "--mapping", str(args.mapping),
                    "--output", str(staged)], check=True)
    subprocess.run([sys.executable, str(here / "pc_force_codepage.py"),
                    "--exe", str(staged),
                    "--output", str(exe),
                    "--locale", args.codepage], check=True)
    print(f"  설치: {exe}")


def main():
    repo = pathlib.Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game-dir", required=True, type=pathlib.Path)
    ap.add_argument("--work", type=pathlib.Path, default=repo / "build" / "pc")
    ap.add_argument("--gust-pak", type=pathlib.Path,
                    default=pathlib.Path("D:/trans/gust_tools/gust_pak.exe"))
    ap.add_argument("--romfs", type=pathlib.Path,
                    help="설치할 romfs 트리 (--install 에 필요)")
    ap.add_argument("--translations", type=pathlib.Path,
                    default=repo / "translations" / "exefs" / "main_1.0.1.csv")
    ap.add_argument("--mapping", type=pathlib.Path,
                    default=repo / "build" / "final_mod_report.json")
    ap.add_argument("--codepage", default="ja-JP",
                    help="매니페스트 activeCodePage. 기본 ja-JP (CP932).")
    ap.add_argument("--switch-romfs", type=pathlib.Path,
                    help="언팩된 스위치 romfs. 스위치 텍스처로 교체하는 단계에 쓴다.")
    ap.add_argument("--g1t-manifest", type=pathlib.Path,
                    default=repo / "translations" / "pc" / "g1t_from_switch.json",
                    help="스위치 텍스처로 교체할 g1t 목록.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--extract-originals", action="store_true")
    mode.add_argument("--install", action="store_true")
    args = ap.parse_args()

    if not args.game_dir.is_dir():
        sys.exit(f"오류: 게임 폴더가 없습니다: {args.game_dir}")
    if not args.gust_pak.is_file():
        sys.exit(f"오류: gust_pak.exe 가 없습니다: {args.gust_pak}")
    args.work.mkdir(parents=True, exist_ok=True)

    if args.extract_originals:
        print("PC 원본 추출")
        extract_originals(args)
    else:
        if not args.romfs or not args.romfs.is_dir():
            sys.exit("오류: --romfs 로 빌드한 romfs 트리를 지정하세요.")
        install(args)
    print("\n완료")


if __name__ == "__main__":
    main()
