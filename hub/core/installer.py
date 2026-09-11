import os
import shutil
import subprocess
import sys
from pathlib import Path
from hub.utils.config import Config


if sys.platform == "win32":
    _NO_WINDOW = subprocess.CREATE_NO_WINDOW
else:
    _NO_WINDOW = 0


class Installer:
    def __init__(self):
        self.cfg = Config()
        self.install_path = Path(self.cfg.get("editor_install_path"))
        self.install_path.mkdir(parents=True, exist_ok=True)

    def install_python(self, output_callback=None):
        from hub.utils.platform import get_python_installer_url, download_file
        python_dir = Path(self.cfg.get("python_install_path"))
        python_dir.mkdir(parents=True, exist_ok=True)
        installer_path = python_dir / "python-installer.exe"
        url = get_python_installer_url()
        if output_callback:
            output_callback("Downloading Python installer...", False)
        download_file(url, installer_path)
        if output_callback:
            output_callback("Installing Python (this may take a few minutes)...", False)
        subprocess.run(
            [str(installer_path),
             "/quiet",
             "InstallAllUsers=0",
             f"TargetDir={python_dir}",
             "PrependPath=1",
             "Include_test=0",
             "Include_launcher=0",
             "Include_symbols=0"],
            check=True, creationflags=_NO_WINDOW
        )
        installer_path.unlink()
        if output_callback:
            output_callback(f"Python installed to {python_dir}", False)

    @staticmethod
    def _find_existing_msvc() -> bool:
        if shutil.which("cl"):
            return True
        # Try vswhere.exe (Microsoft's VS locator)
        for vsdir in [
            Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")),
            Path(os.environ.get("ProgramFiles", "C:/Program Files")),
        ]:
            vswhere = vsdir / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
            if vswhere.exists():
                try:
                    result = subprocess.run(
                        [str(vswhere), "-latest", "-products", "*",
                         "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                         "-property", "installationPath"],
                        capture_output=True, text=True, timeout=15, creationflags=_NO_WINDOW
                    )
                    if result.returncode == 0:
                        vspath = result.stdout.strip()
                        if vspath:
                            root = Path(vspath)
                            for msvc_dir in sorted((root / "VC" / "Tools" / "MSVC").glob("*"), reverse=True):
                                for arch in ["Hostx64/x64", "Hostx86/x64", "Hostx64/x86"]:
                                    cl_path = msvc_dir / "bin" / arch
                                    if (cl_path / "cl.exe").exists():
                                        os.environ["PATH"] = str(cl_path) + os.pathsep + os.environ.get("PATH", "")
                                        return True
                except (subprocess.TimeoutExpired, OSError):
                    pass
                break
        # Scan known installation paths
        candidates = []
        for pf in [Path(os.environ.get("ProgramFiles", "C:/Program Files")),
                   Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")),
                   Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "VisualStudio"]:
            if not pf.exists():
                continue
            for year in ["2022", "2019", "2017"]:
                for edition in ["BuildTools", "Community", "Professional", "Enterprise"]:
                    candidates.append(pf / "Microsoft Visual Studio" / year / edition)
        for root in candidates:
            if not root.exists():
                continue
            for msvc_dir in sorted((root / "VC" / "Tools" / "MSVC").glob("*"), reverse=True):
                for arch in ["Hostx64/x64", "Hostx86/x64", "Hostx64/x86"]:
                    cl_path = msvc_dir / "bin" / arch
                    if (cl_path / "cl.exe").exists():
                        os.environ["PATH"] = str(cl_path) + os.pathsep + os.environ.get("PATH", "")
                        return True
        return False

    @staticmethod
    def _ensure_msvc(output_callback=None):
        if Installer._find_existing_msvc():
            return
        if output_callback:
            output_callback("Downloading C++ Build Tools (required for packages like pybullet)...", False)
        dest = Path.home() / "ZarinHub" / "vs_BuildTools.exe"
        dest.parent.mkdir(parents=True, exist_ok=True)
        from hub.utils.platform import download_file
        download_file("https://aka.ms/vs/17/release/vs_BuildTools.exe", dest)
        if not dest.exists() or dest.stat().st_size < 1024:
            if output_callback:
                output_callback("Failed to download VS Build Tools installer.", True)
            return
        if output_callback:
            output_callback("Installing C++ Build Tools (this may take several minutes, may prompt for admin)...", False)
        result = subprocess.run(
            [str(dest), "--wait", "--norestart",
             "--add", "Microsoft.VisualStudio.Workload.VCTools",
             "--includeRecommended"],
        )
        dest.unlink(missing_ok=True)
        if result.returncode != 0:
            Installer._find_existing_msvc()
            if output_callback:
                if result.returncode == 5008:
                    output_callback("C++ Build Tools installation cancelled or failed (needs admin rights).", True)
                    output_callback("You can install manually from: https://aka.ms/vs/17/release/vs_BuildTools.exe", False)
                else:
                    output_callback(f"C++ Build Tools installer exited with code {result.returncode}.", True)
            return
        Installer._find_existing_msvc()
        if output_callback:
            output_callback("C++ Build Tools ready." if shutil.which("cl") else "C++ Build Tools installed. Retrying build...", False)

    @staticmethod
    def _run_and_stream(cmd: list, output_callback=None, cwd=None) -> tuple[int, str]:
        full_err = []
        import os as _os
        env = {**_os.environ, "PYTHONUNBUFFERED": "1"}
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, env=env, creationflags=_NO_WINDOW, cwd=cwd
        )
        def _read(stream, is_err):
            for line in iter(stream.readline, ""):
                if not line:
                    break
                stripped = line.rstrip("\r\n")
                if stripped:
                    if output_callback:
                        output_callback(stripped, is_err)
                if is_err:
                    full_err.append(stripped)
            stream.close()
        import threading
        t1 = threading.Thread(target=_read, args=(proc.stdout, False), daemon=True)
        t2 = threading.Thread(target=_read, args=(proc.stderr, True), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        proc.wait()
        return proc.returncode, "\n".join(full_err)

    def _pip_install(self, pip_exe: Path, package_spec: str, output_callback=None):
        for extra_flags in [[], ["--pre"], ["--pre", "--ignore-requires-python"]]:
            cmd = [str(pip_exe), "install"] + extra_flags + [package_spec]
            rc, err = self._run_and_stream(cmd, output_callback)
            if rc == 0:
                return True, ""
            if "No matching distribution" in err or "Could not find a version" in err:
                continue
            return False, err
        return False, err

    def install_editor_dependencies(self, version_dir: Path, output_callback=None, progress_callback=None):
        venv_dir = version_dir / ".venv"
        if sys.platform == "win32":
            venv_python = venv_dir / "Scripts" / "python.exe"
            venv_pip = venv_dir / "Scripts" / "pip.exe"
        else:
            venv_python = venv_dir / "bin" / "python"
            venv_pip = venv_dir / "bin" / "pip"
        if not venv_dir.exists():
            if output_callback:
                output_callback("Creating virtual environment...", False)
            from hub.utils.platform import find_python, get_python_executable
            python_install_path = Path(self.cfg.get("python_install_path"))
            try:
                real_python = get_python_executable(python_install_path)
            except RuntimeError:
                if output_callback:
                    output_callback("Python not found. Installing recommended version...", False)
                self.install_python(output_callback=output_callback)
                real_python = get_python_executable(python_install_path)
            if output_callback:
                output_callback(f"Using {real_python}...", False)
            subprocess.run(
                [str(real_python), "-m", "venv", str(venv_dir)],
                check=True, capture_output=True, creationflags=_NO_WINDOW
            )
            if output_callback:
                output_callback("Virtual environment created.", False)
        if not venv_pip.exists():
            raise RuntimeError(f"Virtual environment creation failed: pip not found at {venv_pip}")
        if progress_callback:
            progress_callback(0.50, "Checking build tools...")
        self._ensure_msvc(output_callback)
        if output_callback:
            output_callback("Upgrading pip...", False)
        self._run_and_stream(
            [str(venv_python), "-m", "pip", "install", "--upgrade", "pip"],
            output_callback
        )
        req_file = version_dir / "requirements.txt"
        if req_file.exists():
            if output_callback:
                output_callback("Reading requirements...", False)
            packages = [line.strip() for line in req_file.read_text().splitlines()
                        if line.strip() and not line.startswith("#") and not line.startswith("-")]
            failed = []
            count = len(packages)
            for i, pkg in enumerate(packages):
                if output_callback:
                    output_callback(f"── Installing {pkg} ──", False)
                if progress_callback:
                    progress_callback(0.50 + 0.40 * i / count, f"Installing {pkg} ({i + 1}/{count})...")
                ok, err = self._pip_install(venv_pip, pkg, output_callback)
                if ok:
                    if output_callback:
                        output_callback(f"✓ {pkg} installed", False)
                else:
                    failed.append((pkg, err))
                    if output_callback:
                        output_callback(f"✗ {pkg} FAILED: {err[:120]}", True)
            if failed:
                msg = "; ".join(f"{p}: {e[:80]}" for p, e in failed)
                raise RuntimeError(
                    f"Some dependencies failed to install:\n{msg}\n\n"
                    f"Try installing them manually in the editor's virtual environment."
                )
        if progress_callback:
            progress_callback(0.92, "All dependencies installed.")
        if output_callback:
            output_callback("All dependencies installed.", False)

        # Build Cython extensions after pip install so first launch is fast
        setup_py = version_dir / "setup.py"
        if setup_py.exists() and venv_python.exists():
            if output_callback:
                output_callback("Building native extensions...", False)
            if progress_callback:
                progress_callback(0.93, "Building native extensions...")
            rc, err = self._run_and_stream(
                [str(venv_python), "setup.py", "build_ext", "--inplace"],
                output_callback, cwd=str(version_dir)
            )
            if rc == 0:
                marker = version_dir / ".build_done"
                marker.write_text("ok")
                if output_callback:
                    output_callback("Native extensions built.", False)
            else:
                if output_callback:
                    output_callback(f"Extension build failed (rc={rc}). Will retry on editor launch.", True)

    def configure_registry(self, editor_path: str):
        import winreg
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.zpes") as key:
                winreg.SetValue(key, "", winreg.REG_SZ, "ZarinEngine.Scene")
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\ZarinEngine.Scene") as key:
                winreg.SetValue(key, "", winreg.REG_SZ, "ZarinEngine Scene File")
            python_exe = Path(editor_path) / ".venv" / "Scripts" / "python.exe"
            venv_python = str(python_exe) if python_exe.exists() else "python"
            shell_cmd = f'"{venv_python}" "{editor_path}\\main.py" "%1"'
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                  r"Software\Classes\ZarinEngine.Scene\shell\open\command") as key:
                winreg.SetValue(key, "", winreg.REG_SZ, shell_cmd)
        except PermissionError:
            pass

    def register_uninstall_info(self, version: str, install_dir: str):
        import winreg
        try:
            key_path = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\ZarinEngine {version}"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, f"ZarinEngine {version}")
                winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, version)
                winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, install_dir)
                winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "Zarrakun")
                winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ,
                                  f'"{install_dir}\\main.py" "--uninstall"')
                icon_path = Path(install_dir) / "zarin_icon.svg"
                winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(icon_path))
        except PermissionError:
            pass
