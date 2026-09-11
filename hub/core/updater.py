import json
import os
import shutil
import subprocess
import ssl
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

if sys.platform == "win32":
    _NO_WINDOW = subprocess.CREATE_NO_WINDOW
    _DETACHED = subprocess.DETACHED_PROCESS
else:
    _NO_WINDOW = 0
    _DETACHED = 0

from hub.version import APP_NAME, APP_VERSION
from hub.utils.config import Config
from hub.core.github_api import GitHubAPI


def _request_json(url: str) -> tuple[Optional[dict | list], str]:
    headers = {"User-Agent": f"{APP_NAME}/{APP_VERSION}", "Accept": "application/vnd.github+json"}
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            return json.loads(resp.read().decode()), ""
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return None, str(e)


def _get_hub_repo() -> str:
    cfg = Config()
    return cfg.get("hub_github_repo", "EgorKonstrukt/ZarinHub")


def _download_file(url: str, dest: Path):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
    with urllib.request.urlopen(req, context=ctx) as resp:
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)


def _hub_root() -> Path:
    return Path(__file__).parent.parent.parent.resolve()


def _is_compiled() -> bool:
    return getattr(sys, "frozen", False)


def check_latest_version() -> tuple[Optional[dict], str]:
    repo = _get_hub_repo()
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    data, err = _request_json(url)
    if data and isinstance(data, dict) and "tag_name" in data:
        tag = data.get("tag_name", "").lstrip("vV")
        return {
            "tag_name": data["tag_name"],
            "version": tag,
            "zipball_url": data.get("zipball_url", ""),
            "html_url": data.get("html_url", ""),
            "published_at": data.get("published_at", ""),
            "body": data.get("body", ""),
            "assets": data.get("assets", []),
        }, ""
    api = GitHubAPI(repo)
    try:
        branch = api.get_default_branch()
        sha = api.get_branch_commit_sha(branch)
        if branch:
            return {
                "tag_name": branch,
                "version": branch,
                "zipball_url": api.get_branch_archive_url(branch),
                "html_url": f"https://github.com/{repo}",
                "published_at": "",
                "body": f"Latest ({branch})",
                "assets": [],
                "commit_sha": sha[:12] if sha else "",
            }, ""
    except Exception:
        pass
    if err:
        return None, err
    return None, "No releases or branch info found"


def is_update_available(latest: dict) -> bool:
    current_parts = [int(x) for x in APP_VERSION.split(".")]
    v = latest["version"].lstrip("vV")
    try:
        latest_parts = [int(x) for x in v.split(".")]
    except ValueError:
        return False
    return latest_parts > current_parts


def _download_update(latest: dict, progress_callback=None) -> Path:
    repo = _get_hub_repo()
    tag = latest["tag_name"]
    root = _hub_root()
    temp_dir = root / "_update_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    if _is_compiled():
        asset_url = None
        for asset in latest.get("assets", []):
            name = asset.get("name", "")
            if name.endswith(".exe") and "Setup" in name:
                asset_url = asset.get("browser_download_url")
                break
        if not asset_url:
            asset_url = f"https://github.com/{repo}/releases/download/{tag}/ZarinHub_Setup_v{latest['version']}_win-x64.exe"
        if progress_callback:
            progress_callback(0, "Downloading installer...")
        download_path = temp_dir / f"zarinhub_{tag}.exe"
        _download_file(asset_url, download_path)
    else:
        zip_url = f"https://github.com/{repo}/archive/refs/tags/{tag}.zip"
        zip_path = temp_dir / f"zarinhub_update_{tag}.zip"
        if progress_callback:
            progress_callback(0, "Downloading update...")
        _download_file(zip_url, zip_path)
        if not zip_path.exists() or zip_path.stat().st_size < 100:
            zip_path.unlink(missing_ok=True)
            raise ValueError(f"Download failed: invalid or empty zip from {zip_url}")
        download_path = zip_path
    if progress_callback:
        progress_callback(50, "Download complete.")
    return download_path


_RUNNER_TEMPLATE = '''"""ZarinHub self-update runner."""
import os, sys, time, subprocess, shutil, zipfile
from pathlib import Path

ROOT = Path({hub_root!r})
DOWNLOAD = Path({download!r})
IS_COMPILED = {is_compiled!r}
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
LAUNCHER = ROOT / "main.py"

def find_python():
    if PYTHON.exists():
        return str(PYTHON)
    for name in ("python3.exe", "python.exe"):
        for p in os.environ.get("PATH", "").split(os.pathsep):
            exe = os.path.join(p, name)
            if os.path.isfile(exe):
                return exe
    return None

time.sleep(3)

if IS_COMPILED:
    subprocess.run(
        [str(DOWNLOAD), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
        creationflags=0x08000000,
    )
else:
    extract_dir = ROOT / "_update_extracted"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    with zipfile.ZipFile(str(DOWNLOAD), "r") as zf:
        zf.extractall(str(extract_dir))
    contents = list(extract_dir.iterdir())
    if len(contents) == 1 and contents[0].is_dir():
        src = contents[0]
        for item in src.iterdir():
            dest = ROOT / item.name
            if dest.exists():
                (shutil.rmtree if dest.is_dir() else os.unlink)(str(dest))
            shutil.move(str(item), str(dest))
    else:
        for item in contents:
            dest = ROOT / item.name
            if dest.exists():
                (shutil.rmtree if dest.is_dir() else os.unlink)(str(dest))
            shutil.move(str(item), str(dest))
    shutil.rmtree(extract_dir)
    DOWNLOAD.unlink(missing_ok=True)
    py = find_python()
    if py:
        req = ROOT / "requirements.txt"
        if req.exists():
            subprocess.run(
                [py, "-m", "pip", "install", "-r", str(req)],
                capture_output=True, creationflags=0x08000000,
            )

if LAUNCHER.exists():
    py = find_python()
    if py:
        subprocess.Popen([py, str(LAUNCHER)], cwd=str(ROOT))
    else:
        subprocess.Popen([str(LAUNCHER)], cwd=str(ROOT))
'''


def _write_runner(download_path: Path):
    runner_path = _hub_root() / "_update_runner.py"
    script = _RUNNER_TEMPLATE.format(
        hub_root=str(_hub_root()),
        download=str(download_path),
        is_compiled=_is_compiled(),
    )
    runner_path.write_text(script, encoding="utf-8")
    return runner_path


def apply_update(latest: dict, progress_callback=None):
    download_path = _download_update(latest, progress_callback)
    if progress_callback:
        progress_callback(80, "Preparing to restart...")
    runner_path = _write_runner(download_path)
    if progress_callback:
        progress_callback(90, "Restarting...")
    python_exe = sys.executable
    if not os.path.isfile(python_exe):
        venv_python = _hub_root() / ".venv" / "Scripts" / "python.exe"
        if venv_python.exists():
            python_exe = str(venv_python)
        else:
            for name in ("python3.exe", "python.exe"):
                for p in os.environ.get("PATH", "").split(os.pathsep):
                    exe = os.path.join(p, name)
                    if os.path.isfile(exe):
                        python_exe = exe
                        break
                if os.path.isfile(python_exe):
                    break
    subprocess.Popen(
        [python_exe, str(runner_path)],
        creationflags=_DETACHED,
        cwd=str(_hub_root()),
    )
