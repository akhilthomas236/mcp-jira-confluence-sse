"""Confluence operations for the MCP server."""

import logging
import httpx
import json
from typing import Dict, List, Optional, Any
from urllib.parse import quote

from .config import ConfluenceConfig, get_confluence_config

logger = logging.getLogger(__name__)


class ConfluenceClient:
    """Client for interacting with Confluence API."""

    def __init__(self, config: Optional[ConfluenceConfig] = None):
        """Initialize the Confluence client with configuration."""
        self.config = config or get_confluence_config()
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
        """Make a GET request to the Confluence API."""
        session = await self.get_session()
        url = f"{self.config.url}/rest/api/{path}"
        response = await session.get(url, params=params)
        response.raise_for_status()
        return response.json()
        
    async def post(self, path: str, data: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a POST request to the Confluence API."""
        session = await self.get_session()
        url = f"{self.config.url}/rest/api/{path}"
        response = await session.post(url, json=data, params=params)
        response.raise_for_status()
        return response.json()
        
    async def put(self, path: str, data: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a PUT request to the Confluence API."""
        session = await self.get_session()
        url = f"{self.config.url}/rest/api/{path}"
        response = await session.put(url, json=data, params=params)
        response.raise_for_status()
        return response.json()
        
    async def delete(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a DELETE request to the Confluence API."""
        session = await self.get_session()
        url = f"{self.config.url}/rest/api/{path}"
        response = await session.delete(url, params=params)
        response.raise_for_status()
        if response.status_code == 204:  # No content
            return {}
        return response.json()

    async def search(self, cql: str, start: int = 0, limit: int = 50) -> Dict[str, Any]:
        """Search Confluence content using CQL."""
        return await self.get("content/search", params={
            "cql": cql,
            "start": start,
            "limit": limit,
        })

    async def get_page(self, page_id: str, expand: Optional[str] = None) -> Dict[str, Any]:
        """Get a Confluence page by its ID."""
        params = {}
        if expand:
            params["expand"] = expand
        return await self.get(f"content/{page_id}", params=params)
    
    async def get_page_by_title(self, space_key: str, title: str) -> Optional[Dict[str, Any]]:
        """Get a page by its title in a specific space."""
        params = {
            "title": title,
            "spaceKey": space_key,
            "expand": "body.storage",
            "limit": 1
        }
        result = await self.get("content", params=params)
        
        if result.get("results") and len(result["results"]) > 0:
            return result["results"][0]
        return None
    
    async def create_page(self, space_key: str, title: str, content: str, parent_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new Confluence page."""
        data = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": content,
                    "representation": "storage"
                }
            }
        }
        
        if parent_id:
            data["ancestors"] = [{"id": parent_id}]
            
        return await self.post("content", data)
    
    async def update_page(self, page_id: str, title: str, content: str, version: int) -> Dict[str, Any]:
        """Update an existing Confluence page."""
        data = {
            "type": "page",
            "title": title,
            "body": {
                "storage": {
                    "value": content,
                    "representation": "storage"
                }
            },
            "version": {
                "number": version + 1
            }
        }
        
        return await self.put(f"content/{page_id}", data)
    
    async def add_comment(self, page_id: str, comment: str) -> Dict[str, Any]:
        """Add a comment to a Confluence page."""
        data = {
            "type": "comment",
            "container": {"id": page_id, "type": "page"},
            "body": {
                "storage": {
                    "value": comment,
                    "representation": "storage"
                }
            }
        }
        
        return await self.post("content", data)
    
    async def get_comments(self, page_id: str, start: int = 0, limit: int = 25) -> Dict[str, Any]:
        """Get comments for a Confluence page."""
        params = {
            "start": start,
            "limit": limit,
            "expand": "body.storage"
        }
        return await self.get(f"content/{page_id}/child/comment", params=params)


# Instantiate a global client
confluence_client = ConfluenceClient()
