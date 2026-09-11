import json
import ssl
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class GitHubRelease:
    tag_name: str
    name: str
    body: str
    published_at: datetime
    zipball_url: str
    tarball_url: str
    html_url: str
    prerelease: bool
    bleeding_edge: bool = False
    assets: list = field(default_factory=list)

    @property
    def version(self) -> str:
        return self.tag_name.lstrip("vV")


class GitHubAPI:
    def __init__(self, repo: str, token: Optional[str] = None):
        self.repo = repo
        self.token = token
        self.base_url = f"https://api.github.com/repos/{repo}"

    def _request(self, endpoint: str) -> dict | list:
        url = f"{self.base_url}/{endpoint}"
        headers = {"User-Agent": "ZarinHub/1.0", "Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return json.loads(resp.read().decode())

    def get_repo_info(self) -> Optional[dict]:
        try:
            return self._request("")
        except (urllib.error.HTTPError, json.JSONDecodeError, OSError):
            return None

    def get_default_branch(self) -> str:
        info = self.get_repo_info()
        if info:
            return info.get("default_branch", "master")
        return "master"

    def get_latest_release(self) -> Optional[GitHubRelease]:
        try:
            data = self._request("releases/latest")
            return self._parse_release(data)
        except (urllib.error.HTTPError, json.JSONDecodeError, OSError):
            return None

    def get_all_releases(self, max_count: int = 20) -> list[GitHubRelease]:
        try:
            data = self._request(f"releases?per_page={max_count}")
            return [self._parse_release(r) for r in data]
        except (urllib.error.HTTPError, json.JSONDecodeError, OSError):
            return []

    def get_release_by_tag(self, tag: str) -> Optional[GitHubRelease]:
        try:
            data = self._request(f"releases/tags/{tag}")
            return self._parse_release(data)
        except (urllib.error.HTTPError, json.JSONDecodeError, OSError):
            return None

    def get_release_zip_url(self, tag: str) -> Optional[str]:
        try:
            data = self._request(f"releases/tags/{tag}")
            for asset in data.get("assets", []):
                name = asset.get("name", "")
                if name.endswith(".zip") and "source" not in name:
                    return asset["browser_download_url"]
            return data.get("zipball_url")
        except (urllib.error.HTTPError, json.JSONDecodeError, OSError):
            return None

    def get_branch_archive_url(self, branch: str = "") -> str:
        if not branch:
            branch = self.get_default_branch()
        return f"https://github.com/{self.repo}/archive/refs/heads/{branch}.zip"

    def get_branch_commit_sha(self, branch: str = "") -> Optional[str]:
        if not branch:
            branch = self.get_default_branch()
        try:
            data = self._request(f"branches/{branch}")
            return data["commit"]["sha"]
        except (urllib.error.HTTPError, json.JSONDecodeError, OSError, KeyError):
            return None

    def get_branch_commit_date(self, branch: str = "") -> Optional[str]:
        if not branch:
            branch = self.get_default_branch()
        try:
            data = self._request(f"branches/{branch}")
            return data["commit"]["commit"]["committer"]["date"]
        except (urllib.error.HTTPError, json.JSONDecodeError, OSError, KeyError):
            return None

    def _parse_release(self, data: dict) -> GitHubRelease:
        return GitHubRelease(
            tag_name=data["tag_name"],
            name=data.get("name", data["tag_name"]),
            body=data.get("body", ""),
            published_at=datetime.fromisoformat(data["published_at"].replace("Z", "+00:00")),
            zipball_url=data["zipball_url"],
            tarball_url=data["tarball_url"],
            html_url=data["html_url"],
            prerelease=data.get("prerelease", False),
            assets=data.get("assets", []),
        )
