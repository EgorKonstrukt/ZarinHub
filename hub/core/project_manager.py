import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from hub.utils.config import Config


class ProjectManager:
    def __init__(self):
        self.cfg = Config()
        self.projects_file = Path.home() / ".zarin" / "projects.json"
        self.projects_file.parent.mkdir(parents=True, exist_ok=True)
        self.default_projects_path = Path(self.cfg.get("projects_path"))

    def get_projects(self) -> list:
        saved = self._load_projects()
        scanned = self._scan_projects()
        merged = {}
        for p in scanned:
            merged[p["path"]] = p
        for p in saved:
            if p["path"] not in merged:
                path = Path(p["path"])
                if path.exists() and (path / "ProjectSettings.json").exists():
                    merged[p["path"]] = p
        result = list(merged.values())
        result.sort(key=lambda x: x.get("last_opened", ""), reverse=True)
        return result

    def _load_projects(self) -> list:
        try:
            if self.projects_file.exists():
                with open(self.projects_file, encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
        return []

    def _save_projects(self, projects: list):
        with open(self.projects_file, "w", encoding="utf-8") as f:
            json.dump(projects, f, indent=2, ensure_ascii=False)

    def _scan_projects(self) -> list:
        projects = []
        if not self.default_projects_path.exists():
            return projects
        for child in self.default_projects_path.iterdir():
            if child.is_dir():
                ps = child / "ProjectSettings.json"
                if ps.exists():
                    meta = self._read_project_meta(ps)
                    projects.append({
                        "name": child.name,
                        "path": str(child),
                        "version": meta.get("version", ""),
                        "last_opened": meta.get("last_opened", ""),
                        "created_at": meta.get("created_at",
                                               datetime.fromtimestamp(child.stat().st_ctime).isoformat()),
                        "description": meta.get("description", ""),
                    })
        return projects

    def _read_project_meta(self, settings_path: Path) -> dict:
        try:
            with open(settings_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def create_project(self, name: str, template: str = "default",
                       version: str = "", description: str = "") -> str:
        project_dir = self.default_projects_path / name
        if project_dir.exists():
            raise FileExistsError(f"Project '{name}' already exists")
        project_dir.mkdir(parents=True)
        settings = {
            "project": {"name": name, "version": version or "1.0.0", "default_scene": ""},
            "description": description,
            "template": template,
            "created_at": datetime.now().isoformat(),
            "last_opened": datetime.now().isoformat(),
            "input": {"horizontal": "a,d", "vertical": "w,s", "mouse_sensitivity": 1.0},
            "rendering": {"render_pipeline": "forward", "anti_aliasing": "none", "shadow_distance": 50.0},
        }
        with open(project_dir / "ProjectSettings.json", "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        (project_dir / "assets").mkdir(exist_ok=True)
        (project_dir / "scenes").mkdir(exist_ok=True)
        projects = self._load_projects()
        projects.append({
            "name": name,
            "path": str(project_dir),
            "version": version,
            "last_opened": settings["last_opened"],
            "created_at": settings["created_at"],
            "description": description,
        })
        self._save_projects(projects)
        return str(project_dir)

    def open_project(self, project_path: str) -> dict:
        projects = self._load_projects()
        for p in projects:
            if p["path"] == project_path:
                p["last_opened"] = datetime.now().isoformat()
                self._save_projects(projects)
                return p
        ps = Path(project_path) / "ProjectSettings.json"
        if ps.exists():
            meta = self._read_project_meta(ps)
            entry = {
                "name": Path(project_path).name,
                "path": project_path,
                "version": meta.get("version", ""),
                "last_opened": datetime.now().isoformat(),
                "created_at": meta.get("created_at", ""),
                "description": meta.get("description", ""),
            }
            projects.append(entry)
            self._save_projects(projects)
            return entry
        raise FileNotFoundError(f"Project not found at {project_path}")

    def remove_project(self, project_path: str, delete_files: bool = False):
        projects = self._load_projects()
        projects = [p for p in projects if p["path"] != project_path]
        self._save_projects(projects)
        if delete_files:
            path = Path(project_path)
            if path.exists():
                shutil.rmtree(path)

    def get_project_version(self, project_path: str) -> str:
        ps = Path(project_path) / "ProjectSettings.json"
        if ps.exists():
            meta = self._read_project_meta(ps)
            return meta.get("project", {}).get("version", "any")
        return "any"

    def set_project_version(self, project_path: str, version: str):
        ps = Path(project_path) / "ProjectSettings.json"
        if ps.exists():
            meta = self._read_project_meta(ps)
            if "project" not in meta:
                meta["project"] = {}
            meta["project"]["version"] = version
            with open(ps, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)
