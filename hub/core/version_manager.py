import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from hub.utils.config import Config
from hub.utils.platform import download_file
from hub.core.github_api import GitHubAPI, GitHubRelease
from hub.core.installer import Installer


class VersionManager:
    def __init__(self):
        self.cfg = Config()
        self.versions_file = self.cfg.config_dir / "installed_versions.json"
        self.installer = Installer()

    @property
    def install_path(self) -> Path:
        p = Path(self.cfg.get("editor_install_path"))
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_installed_versions(self) -> dict:
        if self.versions_file.exists():
            with open(self.versions_file, encoding="utf-8") as f:
                return json.load(f)
        return self._scan_installed_versions()

    def _scan_installed_versions(self) -> dict:
        versions = {}
        for d in self.install_path.iterdir():
            self._check_version_dir(d, versions)
        self._save_versions(versions)
        return versions

    def _check_version_dir(self, d: Path, versions: dict):
        if not d.is_dir():
            return
        has_entry = (d / "main.py").exists() or (d / "main.exe").exists()
        if not has_entry:
            return
        ver_file = d / "version.txt"
        version = ver_file.read_text().strip() if ver_file.exists() else d.name
        compiled_exe = None
        for exe in ["main.exe", "ZarinPlayer.exe"]:
            p = d / exe
            if p.exists():
                compiled_exe = str(p)
                break
        meta = {}
        meta_file = d / "version_meta.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        versions[version] = {
            "path": str(d),
            "version": version,
            "installed_at": meta.get("installed_at", datetime.fromtimestamp(d.stat().st_ctime).isoformat()),
            "commit_date": meta.get("commit_date", ""),
            "commit_sha": meta.get("commit_sha", ""),
            "compiled_exe": compiled_exe,
            "has_venv": (d / ".venv" / "Scripts" / "python.exe").exists(),
        }

    def add_existing_version(self, path: str) -> str:
        d = Path(path)
        if not (d / "main.py").exists():
            raise ValueError(f"Not a valid ZarinEngine directory: no main.py in {path}")
        ver_file = d / "version.txt"
        tag = ver_file.read_text().strip() if ver_file.exists() else d.name
        versions = self.get_installed_versions()
        if tag in versions:
            raise ValueError(f"Version {tag} already registered")
        self._check_version_dir(d, versions)
        self._save_versions(versions)
        return tag

    def _save_versions(self, versions: dict):
        with open(self.versions_file, "w", encoding="utf-8") as f:
            json.dump(versions, f, indent=2, ensure_ascii=False)

    def _make_pseudo_release(self, api: GitHubAPI) -> list:
        repo = self.cfg.get("github_repo")
        branch = api.get_default_branch()
        pseudo = GitHubRelease(
            tag_name=branch,
            name=f"Latest ({branch})",
            body="Latest development version from repository.",
            published_at=datetime.now(),
            zipball_url=api.get_branch_archive_url(branch),
            tarball_url="",
            html_url=f"https://github.com/{repo}",
            prerelease=False,
            bleeding_edge=True,
        )
        return [pseudo]

    def get_available_versions(self) -> list:
        repo = self.cfg.get("github_repo")
        api = GitHubAPI(repo)
        source_type = self.cfg.get("source_type")
        if source_type == "branch":
            return self._make_pseudo_release(api)
        releases = api.get_all_releases(20)
        if releases:
            return releases
        return self._make_pseudo_release(api)

    def get_latest_version(self) -> Optional[str]:
        repo = self.cfg.get("github_repo")
        api = GitHubAPI(repo)
        if self.cfg.get("source_type") == "branch":
            return api.get_default_branch()
        release = api.get_latest_release()
        if release:
            return release.tag_name
        return api.get_default_branch()

    def download_and_install(self, tag: str, progress_callback=None, output_callback=None):
        repo = self.cfg.get("github_repo")
        api = GitHubAPI(repo)
        target_dir = self.install_path / tag
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True)
        if output_callback:
            output_callback(f"Starting installation of {tag}...", False)
        if progress_callback:
            progress_callback(0.0, f"Getting info for {tag}...")
        release = api.get_release_by_tag(tag)
        if release:
            zip_url = api.get_release_zip_url(tag)
            if not zip_url:
                zip_url = release.zipball_url
        else:
            zip_url = api.get_branch_archive_url(tag)
            if output_callback:
                output_callback(f"No release tag — using {tag} branch archive.", False)
            if progress_callback:
                progress_callback(0.01, f"Using {tag} branch...")
        if not zip_url:
            raise ValueError(f"Download URL for {tag} not found")
        zip_path = target_dir / "source.zip"
        if output_callback:
            output_callback(f"Downloading {tag}...", False)
        if progress_callback:
            progress_callback(0.05, f"Downloading {tag}...")
        download_file(
            zip_url, zip_path,
            lambda p: progress_callback(0.05 + p * 0.45, f"Downloading {tag}...")
        )
        if output_callback:
            output_callback("Download complete. Extracting...", False)
        if progress_callback:
            progress_callback(0.5, f"Extracting {tag}...")
        extract_dir = target_dir / "_extracted"
        extract_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(str(extract_dir))
        zip_path.unlink()
        contents = list(extract_dir.iterdir())
        if len(contents) == 1 and contents[0].is_dir():
            nested = contents[0]
            for item in nested.iterdir():
                dest = target_dir / item.name
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                shutil.move(str(item), str(dest))
            shutil.rmtree(str(extract_dir))
        else:
            for item in contents:
                dest = target_dir / item.name
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                shutil.move(str(item), str(dest))
            shutil.rmtree(str(extract_dir))
        if output_callback:
            output_callback("Extraction complete. Setting up virtual environment...", False)
        if progress_callback:
            progress_callback(0.6, "Setting up virtual environment...")
        self.installer.install_editor_dependencies(
            target_dir,
            output_callback=output_callback,
            progress_callback=progress_callback,
        )
        if output_callback:
            output_callback("Configuring system registry...", False)
        if progress_callback:
            progress_callback(0.95, "Configuring system...")
        self.installer.configure_registry(str(target_dir))
        self.installer.register_uninstall_info(tag, str(target_dir))
        (target_dir / "version.txt").write_text(tag, encoding="utf-8")
        meta = {"installed_at": datetime.now().isoformat(), "tag": tag}
        if not release:
            meta["bleeding_edge"] = True
            commit_date = api.get_branch_commit_date(tag)
            commit_sha = api.get_branch_commit_sha(tag)
            if commit_date:
                meta["commit_date"] = commit_date
            if commit_sha:
                meta["commit_sha"] = commit_sha[:12]
            if output_callback and commit_date:
                from datetime import datetime as dt
                try:
                    d = dt.fromisoformat(commit_date.replace("Z", "+00:00"))
                    output_callback(f"  Commit date: {d.strftime('%d.%m.%Y %H:%M')}", False)
                except Exception:
                    pass
        (target_dir / "version_meta.json").write_text(json.dumps(meta), encoding="utf-8")
        self._scan_installed_versions()
        if progress_callback:
            progress_callback(1.0, f"{tag} installed successfully")

    def remove_version(self, tag: str):
        versions = self.get_installed_versions()
        if tag in versions:
            path = Path(versions[tag]["path"])
            if path.exists():
                shutil.rmtree(path)
            del versions[tag]
            self._save_versions(versions)

    def launch_editor(self, version: str, scene_path: Optional[str] = None):
        versions = self.get_installed_versions()
        if version not in versions:
            raise ValueError(f"Version {version} not installed")
        info = versions[version]
        editor_dir = Path(info["path"])
        compiled_exe = info.get("compiled_exe")
        if compiled_exe:
            cmd = [compiled_exe]
            if scene_path:
                cmd.append(scene_path)
            subprocess.Popen(cmd, cwd=str(editor_dir))
            return
        python_exe = editor_dir / ".venv" / "Scripts" / "python.exe"
        if not python_exe.exists():
            python_exe = Path(sys.executable)
        cmd = [str(python_exe), "main.py"]
        if scene_path:
            cmd.append(scene_path)
        subprocess.Popen(cmd, cwd=str(editor_dir))

    def launch_player(self, version: str, scene_path: Optional[str] = None):
        versions = self.get_installed_versions()
        if version not in versions:
            raise ValueError(f"Version {version} not installed")
        info = versions[version]
        editor_dir = Path(info["path"])
        player_exe = editor_dir / "ZarinPlayer.exe"
        if player_exe.exists():
            cmd = [str(player_exe)]
            if scene_path:
                cmd.append(scene_path)
            subprocess.Popen(cmd, cwd=str(editor_dir))
            return
        python_exe = editor_dir / ".venv" / "Scripts" / "python.exe"
        if not python_exe.exists():
            python_exe = Path(sys.executable)
        cmd = [str(python_exe), "player.py"]
        if scene_path:
            cmd.append(scene_path)
        subprocess.Popen(cmd, cwd=str(editor_dir))
