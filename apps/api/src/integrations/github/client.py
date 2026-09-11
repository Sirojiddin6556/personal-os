"""GitHub REST API client."""

import base64
from typing import Any, Dict, List, Optional
import httpx


class GitHubClient:
    """Async client for interacting with GitHub REST API."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Personal-OS-App",
        }

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.BASE_URL}{path}" if path.startswith("/") else f"{self.BASE_URL}/{path}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=json_data,
            )
            if resp.status_code >= 400:
                error_detail = "GitHub API request failed"
                try:
                    data = resp.json()
                    error_detail = data.get("message", error_detail)
                except Exception:
                    error_detail = resp.text or error_detail
                raise ValueError(f"GitHub error ({resp.status_code}): {error_detail}")
            
            if resp.status_code == 204:
                return None
            return resp.json()

    async def get_current_user(self) -> Dict[str, Any]:
        """Fetch authenticated user profile."""
        return await self._request("GET", "/user")

    async def list_user_repos(self, page: int = 1, per_page: int = 50) -> List[Dict[str, Any]]:
        """List repositories accessible to the authenticated user."""
        return await self._request(
            "GET",
            "/user/repos",
            params={"sort": "updated", "direction": "desc", "per_page": per_page, "page": page, "type": "all"},
        )

    async def get_repo(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository metadata."""
        return await self._request("GET", f"/repos/{owner}/{repo}")

    async def list_commits(
        self, owner: str, repo: str, branch: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List recent commits on a repository branch."""
        params: Dict[str, Any] = {"per_page": min(limit, 50)}
        if branch:
            params["sha"] = branch
        return await self._request("GET", f"/repos/{owner}/{repo}/commits", params=params)

    async def get_contents(
        self, owner: str, repo: str, path: str = "", ref: Optional[str] = None
    ) -> Any:
        """Get contents of a file or directory in repository."""
        params = {}
        if ref:
            params["ref"] = ref
        clean_path = path.lstrip("/")
        endpoint = f"/repos/{owner}/{repo}/contents/{clean_path}" if clean_path else f"/repos/{owner}/{repo}/contents"
        return await self._request("GET", endpoint, params=params if params else None)

    async def create_or_update_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        commit_message: str,
        branch: str = "main",
        sha: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Commit changes to a file on GitHub."""
        clean_path = path.lstrip("/")
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("ascii")
        payload: Dict[str, Any] = {
            "message": commit_message,
            "content": encoded_content,
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        return await self._request("PUT", f"/repos/{owner}/{repo}/contents/{clean_path}", json_data=payload)

    async def list_issues(
        self, owner: str, repo: str, state: str = "open", limit: int = 30
    ) -> List[Dict[str, Any]]:
        """List repository issues."""
        return await self._request(
            "GET",
            f"/repos/{owner}/{repo}/issues",
            params={"state": state, "per_page": limit, "sort": "updated"},
        )

    async def create_issue(
        self, owner: str, repo: str, title: str, body: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new issue on GitHub."""
        payload: Dict[str, Any] = {"title": title}
        if body:
            payload["body"] = body
        return await self._request("POST", f"/repos/{owner}/{repo}/issues", json_data=payload)
