import os
import shutil
import subprocess
import sys
from pathlib import Path


def get_python_installer_url():
    import platform
    arch = platform.machine()
    if "ARM" in arch or "aarch64" in arch:
        arch_tag = "arm64"
    else:
        arch_tag = "amd64"
    return f"https://www.python.org/ftp/python/3.13.2/python-3.13.2-{arch_tag}.exe"


def download_file(url: str, dest: Path, progress_callback=None):
    import urllib.request
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={
        "User-Agent": "ZarinHub/1.0",
    })
    with urllib.request.urlopen(req, context=ctx) as response:
        total = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 8192
        with open(dest, "wb") as f:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total:
                    progress_callback(downloaded / total)


def is_python_installed() -> bool:
    try:
        py = find_python()
        result = subprocess.run(
            [str(py), "--version"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, RuntimeError):
        return False


def find_python() -> Path:
    seen = set()
    candidates = []

    def _add(p):
        resolved = Path(p).resolve()
        if resolved not in seen:
            seen.add(resolved)
            candidates.append(resolved)

    _add(sys.executable)

    for name in ["python3", "python"]:
        found = shutil.which(name)
        if found:
            _add(found)

    for d in [
        os.environ.get("ProgramFiles", "C:/Program Files"),
        os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"),
        Path(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python"),
        Path(os.environ.get("APPDATA", ""), "..", "Local", "Programs", "Python").resolve(),
    ]:
        for ver in ["313", "312", "311", "310", "39", "38"]:
            p = Path(d) / f"Python{ver}" / "python.exe"
            if p.exists():
                _add(p)

    for p in candidates:
        try:
            r = subprocess.run([str(p), "--version"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and "Python" in (r.stdout or ""):
                return p
        except (OSError, subprocess.TimeoutExpired):
            continue

    raise RuntimeError(
        "Python interpreter not found.\n"
        "Install Python from https://python.org and try again."
    )


def get_python_executable(install_path: Path) -> Path:
    python_exe = install_path / "python.exe"
    if python_exe.exists():
        return python_exe
    alt = install_path / "Scripts" / "python.exe"
    if alt.exists():
        return alt
    return find_python()
