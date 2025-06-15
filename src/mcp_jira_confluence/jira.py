"""Jira operations for the MCP server."""

import logging
import httpx
import json
from typing import Dict, List, Optional, Any
from urllib.parse import quote

from .config import JiraConfig, get_jira_config

logger = logging.getLogger(__name__)


class JiraClient:
    """Client for interacting with Jira API."""

    def __init__(self, config: Optional[JiraConfig] = None):
        """Initialize the Jira client with configuration."""
        self.config = config or get_jira_config()
        self._session = None
        self._headers = {}
        
        # Configure authorization headers
        if self.config.personal_token:
            self._headers["Authorization"] = f"Bearer {self.config.personal_token}"
        elif self.config.username and self.config.api_token:
            from base64 import b64encode
            auth_str = f"{self.config.username}:{self.config.api_token}"
            auth_bytes = auth_str.encode('ascii')
            auth_base64 = b64encode(auth_bytes).decode('ascii')
            self._headers["Authorization"] = f"Basic {auth_base64}"
            
        # Common headers
        self._headers["Accept"] = "application/json"
        self._headers["Content-Type"] = "application/json"

    async def get_session(self) -> httpx.AsyncClient:
        """Get or create an HTTP session."""
        if self._session is None or self._session.is_closed:
            self._session = httpx.AsyncClient(
                verify=self.config.ssl_verify,
                headers=self._headers,
                follow_redirects=True,
                timeout=30.0
            )
        return self._session
        
    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.is_closed:
            await self._session.aclose()
            self._session = None
    
    async def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a GET request to the Jira API."""
        session = await self.get_session()
        url = f"{self.config.url}/rest/api/2/{path}"
        response = await session.get(url, params=params)
        response.raise_for_status()
        return response.json()
        
    async def post(self, path: str, data: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a POST request to the Jira API."""
        session = await self.get_session()
        url = f"{self.config.url}/rest/api/2/{path}"
        response = await session.post(url, json=data, params=params)
        response.raise_for_status()
        return response.json()
        
    async def put(self, path: str, data: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a PUT request to the Jira API."""
        session = await self.get_session()
        url = f"{self.config.url}/rest/api/2/{path}"
        response = await session.put(url, json=data, params=params)
        response.raise_for_status()
        if response.status_code == 204:  # No content
            return {}
        return response.json()

    async def get_issue(self, issue_key: str) -> Dict[str, Any]:
        """Get an issue by its key."""
        fields = "summary,description,status,assignee,reporter,labels,priority,created,updated,issuetype"
        return await self.get(f"issue/{issue_key}", params={"fields": fields})
    
    async def search_issues(self, jql: str, start: int = 0, max_results: int = 50) -> Dict[str, Any]:
        """Search for issues using JQL."""
        fields = "summary,description,status,assignee,reporter,labels,priority,created,updated,issuetype"
        return await self.get("search", params={
            "jql": jql,
            "startAt": start,
            "maxResults": max_results,
            "fields": fields
        })
    
    async def create_issue(self, project_key: str, summary: str, issue_type: str, 
                          description: Optional[str] = None, 
                          assignee: Optional[str] = None) -> Dict[str, Any]:
        """Create a new issue."""
        data = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "issuetype": {"name": issue_type},
            }
        }
        
        if description:
            data["fields"]["description"] = description
            
        if assignee:
            data["fields"]["assignee"] = {"name": assignee}
            
        return await self.post("issue", data)
    
    async def update_issue(self, issue_key: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        """Update an issue."""
        data = {"fields": fields}
        return await self.put(f"issue/{issue_key}", data)
    
    async def add_comment(self, issue_key: str, comment: str) -> Dict[str, Any]:
        """Add a comment to an issue."""
        data = {"body": comment}
        return await self.post(f"issue/{issue_key}/comment", data)
    
    async def get_transitions(self, issue_key: str) -> Dict[str, Any]:
        """Get available transitions for an issue."""
        return await self.get(f"issue/{issue_key}/transitions")
    
    async def transition_issue(self, issue_key: str, transition_id: str) -> Dict[str, Any]:
        """Transition an issue to a new status."""
        data = {
            "transition": {"id": transition_id}
        }
        return await self.post(f"issue/{issue_key}/transitions", data)
        
    async def get_project_versions(self, project_key: str) -> List[Dict[str, Any]]:
        """Get all versions for a project."""
        return await self.get(f"project/{project_key}/versions")


# Instantiate a global client
jira_client = JiraClient()
