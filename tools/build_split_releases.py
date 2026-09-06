#!/usr/bin/env python3
"""PC/Atmosphere/Ryujinx 패치와 완성 동영상을 각각 별도 ZIP으로 만든다."""
from __future__ import annotations

import pathlib
import tempfile
import textwrap
import time
import zipfile


MOVIES = {"opening", "prologue", "seq02", "seq03", "seq04", "seq05", "tm_felion_D"}


def replace_with_retry(source: pathlib.Path, destination: pathlib.Path) -> None:
    for attempt in range(10):
        try:
            source.replace(destination)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.5)


def zip_root(archive: zipfile.ZipFile) -> str:
    roots = {name.split("/", 1)[0] for name in archive.namelist() if "/" in name}
    if len(roots) != 1:
        raise SystemExit("ZIP 최상위 폴더를 하나로 확정할 수 없습니다.")
    return roots.pop()


def movie_name(path: str, suffix: str) -> str | None:
    normalized = path.replace("\\", "/")
    if not normalized.lower().endswith(suffix):
        return None
    return pathlib.PurePosixPath(normalized).stem


def write_bytes(zout: zipfile.ZipFile, name: str, payload: bytes) -> None:
    zout.writestr(name, payload, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def read_pc_script(zin: zipfile.ZipFile, suffix: str) -> str:
    candidates = [name for name in zin.namelist() if name.endswith(suffix)]
    if len(candidates) != 1:
        raise SystemExit(f"PC 스크립트를 하나로 확정할 수 없습니다: {suffix}")
    return zin.read(candidates[0]).decode("utf-8-sig").replace("\r\n", "\n")


def add_pc_folder_picker(text: str) -> str:
    if "function Select-GameFolder" in text:
        return text
    start = text.find("if (-not $GameDir) {")
    marker = "$GameDir = [IO.Path]::GetFullPath($GameDir)"
    end = text.find(marker, start)
    if start < 0 or end < 0:
        raise SystemExit("PC 스크립트의 게임 폴더 입력 부분을 찾지 못했습니다.")
    block = """function Select-GameFolder {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = 'Ar nosurge DX 게임 폴더(ArnosurgeDX.exe가 있는 폴더)를 선택하세요.'
    $dialog.ShowNewFolderButton = $false
    if (Test-Path -LiteralPath $PSScriptRoot) { $dialog.SelectedPath = $PSScriptRoot }
    try {
        $result = $dialog.ShowDialog()
        if ($result -ne [System.Windows.Forms.DialogResult]::OK) { throw '폴더 선택을 취소했습니다.' }
        return $dialog.SelectedPath
    } finally {
        $dialog.Dispose()
    }
}

if (-not $GameDir) { $GameDir = Select-GameFolder }
"""
    return text[:start] + block + text[end:]


def pc_installer(zin: zipfile.ZipFile) -> bytes:
    text = add_pc_folder_picker(read_pc_script(zin, "/install_pc_patch.ps1"))
    old = "    $target = Join-Path $GameDir $relative\n    $keep = Join-Path $backup $relative"
    new = (
        "    $target = Join-Path $GameDir $relative\n"
        "    if (-not (Test-Path -LiteralPath $source)) { return }\n"
        "    $keep = Join-Path $backup $relative"
    )
    if old not in text:
        raise SystemExit("PC 설치 스크립트의 파일 복사 함수를 찾지 못했습니다.")
    text = text.replace(old, new, 1)
    start = text.find("$pak = Join-Path $GameDir 'Data\\PACK00_01.PAK'")
    end_marker = "\nWrite-Host 'PC 한국어 패치 설치가 완료되었습니다.'"
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        raise SystemExit("PC 설치 스크립트의 PACK00 블록을 찾지 못했습니다.")
    block = text[start:end].replace(
        "(Join-Path $payload 'pack00_manifest.json')", "$pack00ManifestPath"
    )
    guarded = (
        "$pack00ManifestPath = Join-Path $payload 'pack00_manifest.json'\n"
        "if (Test-Path -LiteralPath $pack00ManifestPath) {\n"
        + textwrap.indent(block, "    ") + "\n}\n"
    )
    return ("\ufeff" + text[:start] + guarded + text[end:]).encode("utf-8")


def pc_uninstaller(zin: zipfile.ZipFile) -> bytes:
    text = add_pc_folder_picker(read_pc_script(zin, "/uninstall_pc_patch.ps1"))
    start = text.find("$pak = Join-Path $GameDir 'Data\\PACK00_01.PAK'")
    end_marker = "\nWrite-Host 'PC 한국어 패치를 백업 상태로 복원했습니다.'"
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        raise SystemExit("PC 제거 스크립트의 PACK00 블록을 찾지 못했습니다.")
    block = text[start:end].replace(
        "(Join-Path $PSScriptRoot 'payload\\pack00_manifest.json')", "$pack00ManifestPath"
    )
    guarded = (
        "$pack00ManifestPath = Join-Path $PSScriptRoot 'payload\\pack00_manifest.json'\n"
        "if (Test-Path -LiteralPath $pack00ManifestPath) {\n"
        + textwrap.indent(block, "    ") + "\n}\n"
    )
    return ("\ufeff" + text[:start] + guarded + text[end:]).encode("utf-8")


def read_unique_entry(zin: zipfile.ZipFile, suffix: str) -> bytes:
    candidates = [name for name in zin.namelist() if name.endswith(suffix)]
    if len(candidates) != 1:
        raise SystemExit(f"ZIP 항목을 하나로 확정할 수 없습니다: {suffix}")
    return zin.read(candidates[0])


def pc_readme() -> bytes:
    return ("\ufeff" + """Ar nosurge DX 한국어 패치 PC판

1. PC-Patch ZIP을 원하는 폴더에 풉니다.
2. 동영상 자막도 적용하려면 PC-Movies ZIP을 같은 폴더에 덮어 풉니다.
3. install.bat를 실행하고 선택 창에서 ArnosurgeDX.exe가 있는 게임 폴더를 고릅니다.

제거할 때는 uninstall.bat를 실행하고 같은 게임 폴더를 선택하세요.
""").encode("utf-8")


def movie_readme(label: str) -> bytes:
    return ("\ufeff" + f"""Ar nosurge DX 한국어 패치 {label} 동영상 팩

이 ZIP은 자막이 합성된 완성 동영상 7개만 포함합니다.
같은 {label} Patch ZIP과 동일한 위치에 덮어 푼 뒤 안내에 따라 적용하세요.
""").encode("utf-8")


def build_pc(source: pathlib.Path, patch_out: pathlib.Path, movies_out: pathlib.Path) -> None:
    root = "ArNosurgeDX-Korean-v0.2-PC"
    with zipfile.ZipFile(source) as zin, \
         zipfile.ZipFile(patch_out, "w", allowZip64=True) as patch, \
         zipfile.ZipFile(movies_out, "w", allowZip64=True) as movies:
        old_root = zip_root(zin)
        for info in zin.infolist():
            if info.is_dir():
                continue
            normalized = info.filename.replace("\\", "/")
            relative = normalized[len(old_root) + 1:]
            name = movie_name(relative, ".wmv")
            if relative in {"install_pc_patch.ps1", "uninstall_pc_patch.ps1", "README.txt"}:
                continue
            if name in MOVIES and relative.startswith("payload/files/Data/x64/Movie/"):
                write_bytes(movies, f"{root}/{relative}", zin.read(info.filename))
            else:
                write_bytes(patch, f"{root}/{relative}", zin.read(info.filename))
        write_bytes(patch, f"{root}/install_pc_patch.ps1", pc_installer(zin))
        write_bytes(patch, f"{root}/uninstall_pc_patch.ps1", pc_uninstaller(zin))
        write_bytes(patch, f"{root}/README.txt", pc_readme())
        write_bytes(movies, f"{root}/install.bat", read_unique_entry(zin, "/install.bat"))
        write_bytes(movies, f"{root}/uninstall.bat", read_unique_entry(zin, "/uninstall.bat"))
        write_bytes(movies, f"{root}/install_pc_patch.ps1", pc_installer(zin))
        write_bytes(movies, f"{root}/uninstall_pc_patch.ps1", pc_uninstaller(zin))
        write_bytes(movies, f"{root}/payload/files_manifest.json",
                    read_unique_entry(zin, "/payload/files_manifest.json"))
        write_bytes(movies, f"{root}/README-MOVIES.txt", movie_readme("PC"))


def map_switch_payload(relative: str) -> str | None:
    content = "atmosphere/contents/01003CF0128DE000/romfs/"
    ui = "atmosphere/exefs_patches/ArNosurgeKoreanUI/"
    fps = "atmosphere/exefs_patches/ArNosurgeFpsUnlock/"
    if relative.startswith(content):
        return f"payload/romfs/{relative[len(content):]}"
    if relative.startswith(ui):
        return f"payload/exefs/ArNosurgeKoreanUI/{relative[len(ui):]}"
    if relative.startswith(fps):
        return f"payload/exefs/ArNosurgeFpsUnlock/{relative[len(fps):]}"
    return None


def switch_readme() -> bytes:
    text = """Ar nosurge DX 한국어 패치 Nintendo Switch판

1. Switch-Patch ZIP을 풉니다.
2. 동영상 자막도 적용하려면 Switch-Movies ZIP을 같은 위치에 덮어 풉니다.
3. setup_switch.bat을 실행합니다.
4. 한글 선택 창에서 Atmosphere 또는 Ryujinx와 60FPS 패치 적용 여부를 고릅니다.
5. 생성된 output 폴더 안의 atmosphere 또는 mods 폴더를 해당 환경에 복사합니다.

korean_final은 한국어 패치이며 fps_unlock은 선택형 60FPS 패치입니다.
"""
    return ("\ufeff" + text).encode("utf-8")


def build_switch(source: pathlib.Path, patch_out: pathlib.Path, movies_out: pathlib.Path,
                 templates: pathlib.Path) -> None:
    root = "ArNosurgeDX-Korean-v0.2-Switch"
    with zipfile.ZipFile(source) as zin, \
         zipfile.ZipFile(patch_out, "w", allowZip64=True) as patch, \
         zipfile.ZipFile(movies_out, "w", allowZip64=True) as movies:
        old_root = zip_root(zin)
        for info in zin.infolist():
            if info.is_dir():
                continue
            normalized = info.filename.replace("\\", "/")
            relative = normalized[len(old_root) + 1:]
            if relative == "README.txt":
                continue
            mapped = map_switch_payload(relative)
            if mapped is None:
                continue
            name = movie_name(mapped, ".mp4")
            output = movies if name in MOVIES and "/Movie/" in mapped else patch
            write_bytes(output, f"{root}/{mapped}", zin.read(info.filename))
        write_bytes(patch, f"{root}/README.txt", switch_readme())
        write_bytes(patch, f"{root}/setup_switch.bat",
                    (templates / "setup_switch.bat").read_bytes())
        script = (templates / "build_switch_layout.ps1").read_text(encoding="utf-8")
        write_bytes(patch, f"{root}/build_switch_layout.ps1", ("\ufeff" + script).encode("utf-8"))
        write_bytes(movies, f"{root}/README-MOVIES.txt", movie_readme("Switch"))
        write_bytes(movies, f"{root}/setup_switch.bat",
                    (templates / "setup_switch.bat").read_bytes())
        write_bytes(movies, f"{root}/build_switch_layout.ps1", ("\ufeff" + script).encode("utf-8"))


def main() -> None:
    repo = pathlib.Path(__file__).resolve().parents[1]
    releases = repo / "releases"
    templates = repo / "tools" / "release_templates"
    sources = repo / "build" / "release_sources"
    full_pc = sources / "ArNosurgeDX-Korean-v0.2-PC.zip"
    full_switch = sources / "ArNosurgeDX-Korean-v0.2-Switch.zip"
    if not full_pc.is_file() or not full_switch.is_file():
        raise SystemExit("원본 PC/Switch 전체 ZIP이 build/release_sources 폴더에 필요합니다.")

    outputs = {
        "pc_patch": releases / "ArNosurgeDX-Korean-v0.2-PC-Patch.zip",
        "pc_movies": releases / "ArNosurgeDX-Korean-v0.2-PC-Movies.zip",
        "switch_patch": releases / "ArNosurgeDX-Korean-v0.2-Switch-Patch.zip",
        "switch_movies": releases / "ArNosurgeDX-Korean-v0.2-Switch-Movies.zip",
    }
    with tempfile.TemporaryDirectory(prefix=".arnosurge-split-", dir=releases) as temp_name:
        temp = pathlib.Path(temp_name)
        staged = {key: temp / path.name for key, path in outputs.items()}
        build_pc(full_pc, staged["pc_patch"], staged["pc_movies"])
        build_switch(full_switch, staged["switch_patch"], staged["switch_movies"], templates)
        for key, destination in outputs.items():
            replace_with_retry(staged[key], destination)

    for path in outputs.values():
        print(f"{path.name}: {path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
