import json
from pathlib import Path


class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self):
        if self._loaded:
            return
        self._loaded = True
        self.config_dir = Path.home() / ".zarinhub"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.config_dir / "config.json"
        self._data = {}
        self.load()

    DEFAULTS = {
        "hub_path": str(Path.home() / "ZarinHub"),
        "editor_install_path": str(Path.home() / "ZarinHub" / "Editors"),
        "projects_path": str(Path.home() / "ZarinHub" / "Projects"),
        "python_install_path": str(Path.home() / "ZarinHub" / "Python"),
        "auto_install_python": True,
        "auto_update_editor": True,
        "theme": "dark",
        "language": "ru",
        "github_repo": "EgorKonstrukt/ZarinEngine",
        "source_type": "release",
        "enabled_platforms": ["windows"],
        "recent_projects_max": 10,
    }

    def load(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def save(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get(self, key, default=None):
        return self._data.get(key, self.DEFAULTS.get(key, default))

    def set(self, key, value):
        self._data[key] = value
        self.save()
