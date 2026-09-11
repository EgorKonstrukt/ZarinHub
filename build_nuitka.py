"""
ZarinHub — Nuitka build + installer script.
"""
import subprocess, sys, os, shutil, argparse, textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "dist"

sys.path.insert(0, str(ROOT))
from hub.version import APP_NAME, APP_VERSION

import platform
_arch = platform.machine().lower()
if _arch in ("amd64", "x86_64"):
    ARCH = "x64"
elif _arch in ("arm64", "aarch64"):
    ARCH = "arm64"
else:
    ARCH = _arch
OS_TAG = {"win32": "win", "linux": "linux", "darwin": "macos"}.get(sys.platform, sys.platform)
PLATFORM_TAG = f"{OS_TAG}-{ARCH}"

parser = argparse.ArgumentParser(description="ZarinHub Nuitka build")
parser.add_argument("--onefile", action="store_true", help="Single EXE (default: onedir)")
parser.add_argument("--no-console", action="store_true", help="Hide console window")
parser.add_argument("--output-dir", default=str(DIST_DIR), help="Output directory")
parser.add_argument("--clean", action="store_true", help="Remove output dir before build")
parser.add_argument("--jobs", type=int, default=0, help="Parallel jobs (0 = auto)")
parser.add_argument("--installer", action="store_true", help="Build Inno Setup installer after compile")
parser.add_argument("--compiler", choices=("auto", "mingw", "msvc"), default="auto",
                    help="C compiler for Nuitka (default: auto = MinGW-w64, auto-downloaded; "
                         "no heavy MSVC install needed). Use 'msvc' to force Visual Studio.")
known, remaining = parser.parse_known_args()

OUTPUT_DIR = Path(known.output_dir)

# Ensure .ico exists
from tools.svg_to_ico import ensure_ico
ico_path = ensure_ico()

# --- Functions (must be defined before use) ---


def _installer(ico_path: str, dist_path: str):
    ISCC = shutil.which("ISCC.exe") or shutil.which("iscc")
    if not ISCC:
        candidates = [
            "C:/Program Files (x86)/Inno Setup 6/ISCC.exe",
            "C:/Program Files/Inno Setup 6/ISCC.exe",
            "C:/Program Files (x86)/Inno Setup 7/ISCC.exe",
            "C:/Program Files/Inno Setup 7/ISCC.exe",
        ]
        for c in candidates:
            if Path(c).exists():
                ISCC = c
                break
    if not ISCC:
        iss = _write_iss(ico_path, dist_path)
        print("\nInno Setup not found. Install from https://jrsoftware.org/isdl.php")
        print("Then re-run with --installer or compile the .iss manually.")
        print(f"Inno Setup script written to: {iss}")
        return
    iss = _write_iss(ico_path, dist_path)
    print(f"\nCompiling installer with {ISCC}...")
    r = subprocess.run([ISCC, iss], cwd=str(ROOT))
    if r.returncode == 0:
        installer = OUTPUT_DIR / f"{APP_NAME}_Setup_v{APP_VERSION}_{PLATFORM_TAG}.exe"
        if installer.exists():
            print(f"\nInstaller created: {installer} ({installer.stat().st_size / 1024 / 1024:.1f} MB)")
    else:
        print(f"\nInstaller compilation failed (exit code {r.returncode})")
        sys.exit(r.returncode)


def _write_iss(ico_path: str, source_path: str) -> str:
    iss = ROOT / "dist" / "installer.iss"
    iss.parent.mkdir(parents=True, exist_ok=True)
    is_onedir = Path(source_path).is_dir()

    if is_onedir:
        source_line = f'Source: "{source_path}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs'
    else:
        source_line = f'Source: "{source_path}"; DestDir: "{{app}}"; Flags: ignoreversion'

    ver = APP_VERSION.split(".")
    while len(ver) < 4:
        ver.append("0")
    ver_str = ".".join(ver)

    import uuid
    app_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"com.zarrakun.{APP_NAME.lower()}"))

    content = f"""\
[Setup]
AppName={APP_NAME}
AppVersion={APP_VERSION}
AppVerName={APP_NAME} {APP_VERSION}
AppPublisher=Zarrakun
AppId={app_id}
DefaultDirName={{autopf}}\\{APP_NAME}
DefaultGroupName={APP_NAME}
OutputDir={OUTPUT_DIR.as_posix()}
OutputBaseFilename={APP_NAME}_Setup_v{APP_VERSION}_{PLATFORM_TAG}
SetupIconFile={ico_path}
UninstallDisplayIcon={{app}}\\ZarinHub.exe
Compression=lzma2/max
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
DisableDirPage=auto
DisableProgramGroupPage=auto
UsePreviousAppDir=yes
UsePreviousGroup=yes
UpdateUninstallLogAppName=no

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"
Name: "startmenu"; Description: "Create a &Start Menu shortcut"; GroupDescription: "Additional icons:"

[Files]
{source_line}

[Icons]
Name: "{{autoprograms}}\\{APP_NAME}"; Filename: "{{app}}\\ZarinHub.exe"; WorkingDir: "{{app}}"; Tasks: startmenu
Name: "{{autodesktop}}\\{APP_NAME}"; Filename: "{{app}}\\ZarinHub.exe"; WorkingDir: "{{app}}"; Tasks: desktopicon

[Run]
Filename: "{{app}}\\ZarinHub.exe"; Description: "Launch {APP_NAME}"; Flags: postinstall nowait skipifsilent
"""
    iss.write_text(content, encoding="utf-8")
    return str(iss)


# --- Build ---

if known.clean and OUTPUT_DIR.exists():
    shutil.rmtree(OUTPUT_DIR)

# --- C compiler: compact auto-downloaded MinGW-w64 by default (no MSVC) ---
sys.path.insert(0, str(ROOT))
try:
    from tools.mingw import ensure_mingw, nuitka_flags, resolve_compiler, activate
    _COMPILER = resolve_compiler(known.compiler if known.compiler != "auto" else None)
    print(f"C compiler: {_COMPILER} (MinGW-w64 is compact, MSVC would need several GB)")
    _COMPILER_FLAGS = nuitka_flags(known.compiler if known.compiler != "auto" else None)
    _BUILD_ENV = dict(os.environ)
    if sys.platform == "win32" and _COMPILER == "mingw":
        try:
            _BUILD_ENV = activate(ensure_mingw())
        except Exception as e:
            print(f"WARNING: MinGW-w64 auto-download failed: {e}")
            print("Falling back to Nuitka's own toolchain download.")
            _BUILD_ENV = dict(os.environ)
except ImportError:
    _COMPILER_FLAGS = ["--assume-yes-for-downloads"]
    _BUILD_ENV = dict(os.environ)
print(f"Nuitka compiler flags: {_COMPILER_FLAGS}")

# --- Nuitka build ---
cmd = [
    sys.executable, "-m", "nuitka",
    "--standalone",
    *_COMPILER_FLAGS,
    "--enable-plugin=pyqt6",
    "--output-dir=" + str(OUTPUT_DIR),
    "--output-filename=ZarinHub",
    "--windows-icon-from-ico=" + ico_path,
    "--include-package=hub",
    "--include-package-data=qtawesome",
    "--include-data-file=zarin_logo.svg=zarin_logo.svg",
    "--include-data-file=zarin_icon.svg=zarin_icon.svg",
    "--include-data-file=zarin_icon.ico=zarin_icon.ico",
    "--warn-unusual-code",
    "--remove-output",
]
if known.onefile:
    cmd.append("--onefile")
if known.no_console:
    cmd.append("--windows-console-mode=disable")
if known.jobs:
    cmd.append(f"--jobs={known.jobs}")

cmd.append(str(ROOT / "main.py"))

MODE = "onefile" if known.onefile else "onedir"
print(f"Building ZarinHub ({MODE}) with Nuitka ({sys.executable})")
print(f"Output: {OUTPUT_DIR}")
print()

result = subprocess.run(cmd, cwd=str(ROOT), env=_BUILD_ENV)

if result.returncode != 0:
    print(f"\nBuild failed (exit code {result.returncode})")
    sys.exit(result.returncode)

# --- Report & rename dist dir ---
if known.onefile:
    exe = OUTPUT_DIR / "ZarinHub.exe"
    size = exe.stat().st_size / 1024 / 1024 if exe.exists() else 0
    print(f"\nBuild successful! {exe} ({size:.1f} MB)")
    dist_path = str(exe)
else:
    src_dir = OUTPUT_DIR / "main.dist"
    dst_dir = OUTPUT_DIR / "ZarinHub.dist"
    if src_dir.exists():
        if dst_dir.exists():
            shutil.rmtree(dst_dir)
        src_dir.rename(dst_dir)
    if dst_dir.exists():
        total = sum(f.stat().st_size for f in dst_dir.rglob("*") if f.is_file()) / 1024 / 1024
        print(f"\nBuild successful! {dst_dir} ({total:.1f} MB)")
    dist_path = str(dst_dir)

# --- Installer ---
if known.installer:
    _installer(ico_path, dist_path)
