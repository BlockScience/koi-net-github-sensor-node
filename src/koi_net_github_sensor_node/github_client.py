import httpx
import logging
from typing import Dict, Any, Optional
from .models import GithubRepoObject

log = logging.getLogger(__name__)

class GithubClient:
    def __init__(self, api_token: Optional[str] = None):
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "koi-net-github-sensor"
        }
        if api_token:
            self.headers["Authorization"] = f"Bearer {api_token}"
        
        self.client = httpx.Client(headers=self.headers, timeout=30.0)
        self.base_url = "https://api.github.com"

    def get_repo_metadata(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """Fetch repository metadata."""
        url = f"{self.base_url}/repos/{owner}/{repo}"
        try:
            resp = self.client.get(url)
            if resp.status_code == 404:
                log.warning(f"Repo not found: {owner}/{repo}")
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.error(f"Error fetching repo metadata for {owner}/{repo}: {e}")
            return None

    def get_readme(self, owner: str, repo: str, default_branch: str = "main") -> str:
        """Fetch README content (raw markdown)."""
        # Try explicit raw accept header for content
        headers = self.headers.copy()
        headers["Accept"] = "application/vnd.github.raw+json"
        
        url = f"{self.base_url}/repos/{owner}/{repo}/readme"
        try:
            resp = self.client.get(url, headers=headers)
            if resp.status_code == 404:
                return ""
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            log.error(f"Error fetching README for {owner}/{repo}: {e}")
            return ""

    def fetch_repo_object(self, owner: str, repo: str) -> Optional[GithubRepoObject]:
        """Fetch and assemble the full GithubRepoObject."""
        meta = self.get_repo_metadata(owner, repo)
        if not meta:
            return None
        
        default_branch = meta.get("default_branch", "main")
        readme = self.get_readme(owner, repo, default_branch)
        
        # Parse updated_at
        updated_at = meta.get("updated_at")
        
        license_name = None
        if meta.get("license"):
            license_name = meta["license"].get("name")

        return GithubRepoObject(
            owner=owner,
            repo=repo,
            description=meta.get("description"),
            stars=meta.get("stargazers_count", 0),
            forks=meta.get("forks_count", 0),
            updated_at=updated_at,
            readme_content=readme,
            license=license_name,
            default_branch=default_branch
        )
