#!/usr/bin/env python3
"""현재 빌드 결과로 배포 ZIP을 만든다.

설치 로직은 PC/Switch 모두 v0.2 Patch ZIP의 검증본을 기준으로 재사용한다.
단, 설치/제거 상태에 포함되는 버전 값(완료 문구, PC 백업 폴더명)은 현재
--version 값으로 주입한다. 동영상 ZIP은 영상 자체가 변경된 릴리스에서만
--include-movies로 만든다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import zipfile

TITLE_ID = "01003CF0128DE000"
INSTALLER_VERSION = "v0.2"
MOVIES = {"opening", "prologue", "seq02", "seq03", "seq04", "seq05", "tm_felion_D"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_bytes(z: zipfile.ZipFile, name: str, data: bytes) -> None:
    # 영상/PAK/G1T는 이미 압축된 데이터라 재압축 이득이 거의 없다.
    z.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)


def donor_root(z: zipfile.ZipFile) -> str:
    roots = {n.split("/", 1)[0] for n in z.namelist() if "/" in n}
    if len(roots) != 1:
        raise SystemExit("donor ZIP 최상위 폴더를 하나로 확정할 수 없습니다")
    return next(iter(roots))


def unique_entry(z: zipfile.ZipFile, suffix: str) -> bytes:
    hits = [n for n in z.namelist() if n.endswith(suffix)]
    if len(hits) != 1:
        raise SystemExit(f"ZIP 항목을 하나로 확정할 수 없습니다: {suffix}")
    return z.read(hits[0])


def replace_utf8_script_text(data: bytes, old: str, new: str, label: str) -> bytes:
    """v0.2 검증 스크립트에서 허용된 표시 문구 한 곳만 바꾼다."""
    bom = b"\xef\xbb\xbf" if data.startswith(b"\xef\xbb\xbf") else b""
    text = data[len(bom):].decode("utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{label}: 버전 표시 문구를 정확히 1개 찾지 못했습니다")
    return bom + text.replace(old, new, 1).encode("utf-8")


def pc_installer_for_version(data: bytes, version: str) -> bytes:
    data = replace_utf8_script_text(
        data,
        f"KoreanPatchBackup-{INSTALLER_VERSION}",
        f"KoreanPatchBackup-{version}",
        "PC installer backup version",
    )
    return replace_utf8_script_text(
        data,
        "Write-Host 'PC 한국어 패치 설치가 완료되었습니다.'",
        f"Write-Host 'PC 한국어 패치 {version} 설치가 완료되었습니다.'",
        "PC installer completion version",
    )


def pc_uninstaller_for_version(data: bytes, version: str) -> bytes:
    return replace_utf8_script_text(
        data,
        f"KoreanPatchBackup-{INSTALLER_VERSION}",
        f"KoreanPatchBackup-{version}",
        "PC uninstaller backup version",
    )


def switch_installer_for_version(data: bytes, version: str) -> bytes:
    return replace_utf8_script_text(
        data,
        '"${Target}용 패치 폴더를 만들었습니다.`n$output"',
        f'"${{Target}}용 한국어 패치 {version} 폴더를 만들었습니다.`n$output"',
        "Switch installer",
    )


def pc_readme(version: str) -> bytes:
    return ("\ufeff" + f"""Ar nosurge DX 한국어 패치 PC판 {version}\n\n1. PC-Patch ZIP을 원하는 폴더에 풉니다.\n2. 동영상 자막도 적용하려면 PC-Movies ZIP을 같은 폴더에 덮어 풉니다.\n3. install.bat를 실행하고 ArnosurgeDX.exe가 있는 게임 폴더를 선택합니다.\n\n제거할 때는 uninstall.bat를 실행하세요.\n""").encode("utf-8")


def switch_readme(version: str) -> bytes:
    return ("\ufeff" + f"""Ar nosurge DX 한국어 패치 Nintendo Switch판 {version}\n\n1. Switch-Patch ZIP을 풉니다.\n2. 동영상 자막도 적용하려면 Switch-Movies ZIP을 같은 위치에 덮어 풉니다.\n3. setup_switch.bat을 실행합니다.\n4. Atmosphere 또는 Ryujinx와 60FPS 패치 적용 여부를 선택합니다.\n""").encode("utf-8")


def movie_readme(label: str, version: str) -> bytes:
    return ("\ufeff" + f"Ar nosurge DX 한국어 패치 {label} 동영상 팩 {version}\n\n자막이 합성된 완성 동영상 7개입니다. 같은 버전의 Patch ZIP과 함께 사용하세요.\n").encode("utf-8")


def build_pc(repo: pathlib.Path, donor: pathlib.Path, version: str,
             expected_font: pathlib.Path,
             include_movies: bool = False,
             exe_override: pathlib.Path | None = None) -> list[pathlib.Path]:
    releases = repo / "releases"
    releases.mkdir(exist_ok=True)
    patch_out = releases / f"ArNosurgeDX-Korean-{version}-PC-Patch.zip"
    movies_out = releases / f"ArNosurgeDX-Korean-{version}-PC-Movies.zip"
    root = f"ArNosurgeDX-Korean-{version}-PC"
    game = repo / "Ar.Nosurge.DX_PC"
    pak00 = game / "Data" / "PACK00_01.PAK"

    with zipfile.ZipFile(donor) as zin:
        old_root = donor_root(zin)
        pack_manifest = json.loads(zin.read(f"{old_root}/payload/pack00_manifest.json").decode("utf-8"))
        files_manifest = json.loads(zin.read(f"{old_root}/payload/files_manifest.json").decode("utf-8"))

        # 현재 PACK00_01에서 릴리스 대상 엔트리를 정확한 오프셋/크기로 다시 읽는다.
        # 폰트는 별도로 권위본에서 재생성한 expected_font와 바이트 동일해야 한다.
        # 테스트 설치에서 PACK00만 갱신하지 않은 채 릴리스하면 문자열은 최신인데
        # `킵→튄`처럼 이전 글리프 배정이 섞일 수 있으므로 여기서 강제로 막는다.
        pak_blob = pak00.read_bytes()
        expected_font_blob = expected_font.read_bytes()
        pack_payloads: dict[str, bytes] = {}
        font_verified = 0
        for entry in pack_manifest["entries"]:
            off, size = entry["offset"], entry["size"]
            payload = pak_blob[off:off + size]
            if len(payload) != size:
                raise SystemExit(f"PACK00 readback 실패: {entry['name']}")
            if entry["name"].replace("/", "\\").lower().endswith("\\mainfont_x64_0.g1t"):
                if payload != expected_font_blob:
                    raise SystemExit(
                        "PC PACK00 폰트가 권위본 재생성 폰트와 다릅니다. "
                        "PACK00_01에 최신 폰트를 설치한 뒤 다시 릴리스하세요."
                    )
                font_verified += 1
            entry["sha256"] = sha(payload)
            pack_payloads[entry["payload"]] = payload
        if font_verified != 1:
            raise SystemExit(f"PC PACK00 폰트 검증 엔트리 수 불일치: {font_verified}")

        exe_source = exe_override or (game / "ArnosurgeDX.exe")
        if not exe_source.is_file():
            raise SystemExit(f"PC 실행 파일이 없습니다: {exe_source}")
        patch_files = {
            "ArnosurgeDX.exe": exe_source.read_bytes(),
            "Data\\PACK01.PAK": (game / "Data" / "PACK01.PAK").read_bytes(),
            "Data\\PACK02.PAK": (game / "Data" / "PACK02.PAK").read_bytes(),
        }
        files_manifest["files"] = [
            {"path": path, "size": len(data), "sha256": sha(data)}
            for path, data in patch_files.items()
        ]

        install_bat = unique_entry(zin, "/install.bat")
        uninstall_bat = unique_entry(zin, "/uninstall.bat")
        installer = pc_installer_for_version(unique_entry(zin, "/install_pc_patch.ps1"), version)
        uninstaller = pc_uninstaller_for_version(unique_entry(zin, "/uninstall_pc_patch.ps1"), version)

        with zipfile.ZipFile(patch_out, "w", allowZip64=True) as zout:
            write_bytes(zout, f"{root}/install.bat", install_bat)
            write_bytes(zout, f"{root}/uninstall.bat", uninstall_bat)
            write_bytes(zout, f"{root}/install_pc_patch.ps1", installer)
            write_bytes(zout, f"{root}/uninstall_pc_patch.ps1", uninstaller)
            write_bytes(zout, f"{root}/README.txt", pc_readme(version))
            for path, data in patch_files.items():
                write_bytes(zout, f"{root}/payload/files/{path.replace(chr(92), '/')}", data)
            write_bytes(zout, f"{root}/payload/files_manifest.json", json.dumps(files_manifest, ensure_ascii=False, indent=2).encode("utf-8"))
            write_bytes(zout, f"{root}/payload/pack00_manifest.json", json.dumps(pack_manifest, ensure_ascii=False, indent=2).encode("utf-8"))
            for name, data in pack_payloads.items():
                write_bytes(zout, f"{root}/payload/pack00/{name}", data)

        outputs = [patch_out]
        if include_movies:
            movie_files = {
                f"Data\\x64\\Movie\\{name}.wmv":
                    (game / "Data" / "x64" / "Movie" / f"{name}.wmv").read_bytes()
                for name in sorted(MOVIES)
            }
            movie_manifest = {
                "files": [
                    {"path": path, "size": len(data), "sha256": sha(data)}
                    for path, data in movie_files.items()
                ]
            }
            with zipfile.ZipFile(movies_out, "w", allowZip64=True) as zout:
                write_bytes(zout, f"{root}/install.bat", install_bat)
                write_bytes(zout, f"{root}/uninstall.bat", uninstall_bat)
                write_bytes(zout, f"{root}/install_pc_patch.ps1", installer)
                write_bytes(zout, f"{root}/uninstall_pc_patch.ps1", uninstaller)
                write_bytes(zout, f"{root}/README-MOVIES.txt", movie_readme("PC", version))
                write_bytes(
                    zout,
                    f"{root}/payload/files_manifest.json",
                    json.dumps(movie_manifest, ensure_ascii=False, indent=2).encode("utf-8"),
                )
                for path, data in movie_files.items():
                    write_bytes(zout, f"{root}/payload/files/{path.replace(chr(92), '/')}", data)
            outputs.append(movies_out)
    return outputs


def build_pc_staged_patch(repo: pathlib.Path, donor: pathlib.Path, version: str,
                          stage: pathlib.Path, font: pathlib.Path) -> pathlib.Path:
    """Build a PC patch ZIP from already-built payloads without touching the game."""
    releases = repo / "releases"
    releases.mkdir(exist_ok=True)
    patch_out = releases / f"ArNosurgeDX-Korean-{version}-PC-Patch.zip"
    root = f"ArNosurgeDX-Korean-{version}-PC"

    required = {
        "ArnosurgeDX.exe": stage / "ArnosurgeDX.exe",
        "Data\\PACK01.PAK": stage / "Data" / "PACK01.PAK",
        "Data\\PACK02.PAK": stage / "Data" / "PACK02.PAK",
    }
    missing = [str(path) for path in required.values() if not path.is_file()]
    if missing:
        raise SystemExit("staged PC payload가 없습니다: " + ", ".join(missing))
    if not font.is_file():
        raise SystemExit(f"staged PC font가 없습니다: {font}")

    with zipfile.ZipFile(donor) as zin:
        old_root = donor_root(zin)
        pack_manifest = json.loads(
            zin.read(f"{old_root}/payload/pack00_manifest.json").decode("utf-8")
        )
        pack_payloads: dict[str, bytes] = {}
        font_replaced = 0
        for entry in pack_manifest["entries"]:
            payload_name = entry["payload"]
            data = zin.read(f"{old_root}/payload/pack00/{payload_name}")
            if entry["name"].replace("/", "\\").lower().endswith("\\mainfont_x64_0.g1t"):
                data = font.read_bytes()
                font_replaced += 1
            if len(data) != entry["size"]:
                raise SystemExit(
                    f"PACK00 payload 크기 불일치: {entry['name']} {len(data)} != {entry['size']}"
                )
            entry["sha256"] = sha(data)
            pack_payloads[payload_name] = data
        if font_replaced != 1:
            raise SystemExit(f"PC 폰트 payload 교체 건수 불일치: {font_replaced}")

        patch_files = {name: path.read_bytes() for name, path in required.items()}
        files_manifest = {
            "files": [
                {"path": path, "size": len(data), "sha256": sha(data)}
                for path, data in patch_files.items()
            ]
        }
        install_bat = unique_entry(zin, "/install.bat")
        uninstall_bat = unique_entry(zin, "/uninstall.bat")
        installer = pc_installer_for_version(unique_entry(zin, "/install_pc_patch.ps1"), version)
        uninstaller = pc_uninstaller_for_version(unique_entry(zin, "/uninstall_pc_patch.ps1"), version)

        with zipfile.ZipFile(patch_out, "w", allowZip64=True) as zout:
            write_bytes(zout, f"{root}/install.bat", install_bat)
            write_bytes(zout, f"{root}/uninstall.bat", uninstall_bat)
            write_bytes(zout, f"{root}/install_pc_patch.ps1", installer)
            write_bytes(zout, f"{root}/uninstall_pc_patch.ps1", uninstaller)
            write_bytes(zout, f"{root}/README.txt", pc_readme(version))
            for path, data in patch_files.items():
                write_bytes(zout, f"{root}/payload/files/{path.replace(chr(92), '/')}", data)
            write_bytes(
                zout,
                f"{root}/payload/files_manifest.json",
                json.dumps(files_manifest, ensure_ascii=False, indent=2).encode("utf-8"),
            )
            write_bytes(
                zout,
                f"{root}/payload/pack00_manifest.json",
                json.dumps(pack_manifest, ensure_ascii=False, indent=2).encode("utf-8"),
            )
            for name, data in pack_payloads.items():
                write_bytes(zout, f"{root}/payload/pack00/{name}", data)

    # Final ZIP readback: every payload must match its manifest before handing it off.
    with zipfile.ZipFile(patch_out) as zcheck:
        for entry in files_manifest["files"]:
            data = zcheck.read(f"{root}/payload/files/{entry['path'].replace(chr(92), '/')}")
            if len(data) != entry["size"] or sha(data) != entry["sha256"]:
                raise SystemExit(f"PC test ZIP files readback 실패: {entry['path']}")
        for entry in pack_manifest["entries"]:
            data = zcheck.read(f"{root}/payload/pack00/{entry['payload']}")
            if len(data) != entry["size"] or sha(data) != entry["sha256"]:
                raise SystemExit(f"PC test ZIP PACK00 readback 실패: {entry['name']}")
    return patch_out


def build_switch(repo: pathlib.Path, installer_donor: pathlib.Path,
                 version: str, include_movies: bool = False) -> list[pathlib.Path]:
    releases = repo / "releases"
    patch_out = releases / f"ArNosurgeDX-Korean-{version}-Switch-Patch.zip"
    movies_out = releases / f"ArNosurgeDX-Korean-{version}-Switch-Movies.zip"
    root = f"ArNosurgeDX-Korean-{version}-Switch"
    atmosphere = repo / "atmosphere"
    content_root = atmosphere / "contents" / TITLE_ID / "romfs"

    with zipfile.ZipFile(installer_donor) as zinstaller, zipfile.ZipFile(patch_out, "w", allowZip64=True) as zout:
        for src in sorted(p for p in content_root.rglob("*") if p.is_file()):
            rel = src.relative_to(content_root).as_posix()
            write_bytes(zout, f"{root}/payload/romfs/{rel}", src.read_bytes())
        for patch_name in ("ArNosurgeKoreanUI", "ArNosurgeFpsUnlock"):
            src_root = atmosphere / "exefs_patches" / patch_name
            if src_root.is_dir():
                for src in sorted(p for p in src_root.rglob("*") if p.is_file()):
                    rel = src.relative_to(src_root).as_posix()
                    write_bytes(zout, f"{root}/payload/exefs/{patch_name}/{rel}", src.read_bytes())
        write_bytes(zout, f"{root}/setup_switch.bat", unique_entry(zinstaller, "/setup_switch.bat"))
        write_bytes(
            zout,
            f"{root}/build_switch_layout.ps1",
            switch_installer_for_version(unique_entry(zinstaller, "/build_switch_layout.ps1"), version),
        )
        write_bytes(zout, f"{root}/README.txt", switch_readme(version))

    outputs = [patch_out]
    if include_movies:
        with zipfile.ZipFile(installer_donor) as zinstaller, zipfile.ZipFile(movies_out, "w", allowZip64=True) as zout:
            for name in sorted(MOVIES):
                source = content_root / "Data" / "NX" / "Movie" / f"{name}.mp4"
                if not source.is_file():
                    raise SystemExit(f"Switch 동영상이 없습니다: {source}")
                write_bytes(zout, f"{root}/payload/romfs/Data/NX/Movie/{source.name}", source.read_bytes())
            write_bytes(zout, f"{root}/setup_switch.bat", unique_entry(zinstaller, "/setup_switch.bat"))
            write_bytes(
                zout,
                f"{root}/build_switch_layout.ps1",
                switch_installer_for_version(unique_entry(zinstaller, "/build_switch_layout.ps1"), version),
            )
            write_bytes(zout, f"{root}/README-MOVIES.txt", movie_readme("Switch", version))
        outputs.append(movies_out)
    return outputs


def main() -> None:
    repo = pathlib.Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version", default="v0.4")
    ap.add_argument(
        "--include-movies",
        action="store_true",
        help="영상 자체가 변경된 릴리스에서만 새 PC/Switch Movies ZIP을 생성",
    )
    ap.add_argument("--pc-stage", type=pathlib.Path,
                    help="게임을 수정하지 않고 이미 빌드한 PC EXE/PACK01/PACK02로 Patch ZIP 생성")
    ap.add_argument("--pc-exe", type=pathlib.Path,
                    help="실행 중인 게임 EXE가 잠겨 있을 때 릴리스에 넣을 별도 빌드 EXE")
    ap.add_argument("--pc-font", type=pathlib.Path,
                    help="권위본에서 정품 PC 원본으로 재생성한 mainfont_x64_0.g1t. PC 릴리스에 필수")
    args = ap.parse_args()
    releases = repo / "releases"
    pc_donor = releases / f"ArNosurgeDX-Korean-{INSTALLER_VERSION}-PC-Patch.zip"
    if not pc_donor.is_file():
        raise SystemExit(f"기존 PC 릴리스 ZIP이 없습니다: {pc_donor}")
    if not args.pc_font or not args.pc_font.is_file():
        raise SystemExit("PC 릴리스에는 freshly rebuilt --pc-font 지정이 필수입니다")
    if args.pc_stage:
        output = build_pc_staged_patch(
            repo, pc_donor, args.version, args.pc_stage, args.pc_font
        )
        print(f"{output.name}: {output.stat().st_size:,} bytes sha256={sha(output.read_bytes())}")
        return

    sw_installer_donor = releases / f"ArNosurgeDX-Korean-{INSTALLER_VERSION}-Switch-Patch.zip"
    if not sw_installer_donor.is_file():
        raise SystemExit(f"기존 Switch Patch ZIP이 없습니다: {sw_installer_donor}")
    outputs = [
        *build_pc(repo, pc_donor, args.version, args.pc_font, args.include_movies, args.pc_exe),
        *build_switch(repo, sw_installer_donor, args.version, args.include_movies),
    ]
    for p in outputs:
        print(f"{p.name}: {p.stat().st_size:,} bytes sha256={sha(p.read_bytes())}")


if __name__ == "__main__":
    main()
