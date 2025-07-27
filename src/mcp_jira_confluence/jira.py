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
    
    async def get_current_user(self) -> Dict[str, Any]:
        """Get information about the current user."""
        return await self.get("myself")
    
    async def get_my_assigned_issues(self, max_results: int = 50, include_done: bool = False) -> Dict[str, Any]:
        """Get issues assigned to the current user, ordered by priority and date."""
        # Build JQL query for assigned issues
        jql_parts = ["assignee = currentUser()"]
        
        if not include_done:
            jql_parts.append('status not in ("Done", "Closed", "Resolved")')
        
        # Order by priority (highest first), then by created date (newest first)
        jql = " AND ".join(jql_parts) + " ORDER BY priority DESC, created DESC"
        
        fields = "summary,description,status,assignee,reporter,labels,priority,created,updated,issuetype,duedate"
        return await self.get("search", params={
            "jql": jql,
            "startAt": 0,
            "maxResults": max_results,
            "fields": fields
        })
    
    async def summarize_issue(self, issue_key: str) -> Dict[str, Any]:
        """Get detailed information about an issue for summarization including comments and links."""
        # Get issue with expanded fields including comments
        issue_data = await self.get(f"issue/{issue_key}", params={
            "fields": "summary,description,status,assignee,reporter,labels,priority,created,updated,issuetype,duedate,comment",
            "expand": "changelog"
        })
        
        # Get remote links (including Confluence links)
        try:
            remote_links = await self.get(f"issue/{issue_key}/remotelink")
        except:
            remote_links = []
        
        # Combine issue data with remote links for easier processing
        issue_data["remoteLinks"] = remote_links
        
        return issue_data
        
    async def extract_confluence_links(self, issue_key: str) -> List[Dict[str, Any]]:
        """Extract Confluence links from an issue's description, comments, and remote links."""
        confluence_links = []
        
        try:
            # Get issue data with comments and remote links
            issue_data = await self.summarize_issue(issue_key)
            
            # Check remote links first (most reliable)
            if "remoteLinks" in issue_data:
                for link in issue_data["remoteLinks"]:
                    if link.get("object", {}).get("url", "").find("confluence") != -1:
                        confluence_links.append({
                            "type": "remote_link",
                            "title": link.get("object", {}).get("title", ""),
                            "url": link.get("object", {}).get("url", ""),
                            "summary": link.get("object", {}).get("summary", "")
                        })
            
            # Check description for Confluence URLs
            description = issue_data.get("fields", {}).get("description", "") or ""
            confluence_urls = self._extract_confluence_urls_from_text(description)
            for url in confluence_urls:
                confluence_links.append({
                    "type": "description_link",
                    "title": "Confluence Page",
                    "url": url,
                    "summary": "Found in issue description"
                })
            
            # Check comments for Confluence URLs
            comments = issue_data.get("fields", {}).get("comment", {}).get("comments", [])
            for comment in comments:
                comment_body = comment.get("body", "") or ""
                confluence_urls = self._extract_confluence_urls_from_text(comment_body)
                for url in confluence_urls:
                    confluence_links.append({
                        "type": "comment_link",
                        "title": "Confluence Page",
                        "url": url,
                        "summary": f"Found in comment by {comment.get('author', {}).get('displayName', 'Unknown')}"
                    })
            
        except Exception as e:
            logger.warning(f"Error extracting Confluence links from {issue_key}: {e}")
        
        return confluence_links
    
    def _extract_confluence_urls_from_text(self, text: str) -> List[str]:
        """Extract Confluence URLs from text using regex."""
        import re
        
        if not text:
            return []
        
        # Common Confluence URL patterns
        patterns = [
            r'https?://[^/\s]+/confluence/[^\s\)]+',  # Standard Confluence URLs
            r'https?://[^/\s]+/wiki/[^\s\)]+',        # Wiki-style URLs
            r'https?://[^/\s]+/display/[^\s\)]+',     # Display URLs
            r'https?://[^\.]+\.atlassian\.net/wiki/[^\s\)]+',  # Atlassian cloud
        ]
        
        urls = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            urls.extend(matches)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        return unique_urls
    
    def _extract_git_urls_from_text(self, text: str) -> List[str]:
        """Extract Git repository URLs from text using regex."""
        import re
        
        if not text:
            return []
        
        # Common Git repository URL patterns
        patterns = [
            r'https?://github\.com/[^/\s]+/[^/\s]+(?:\.git)?(?:/[^\s\)]*)?',  # GitHub
            r'https?://gitlab\.com/[^/\s]+/[^/\s]+(?:\.git)?(?:/[^\s\)]*)?',  # GitLab.com
            r'https?://bitbucket\.org/[^/\s]+/[^/\s]+(?:\.git)?(?:/[^\s\)]*)?',  # Bitbucket
            r'https?://[^/\s]+/gitlab/[^/\s]+/[^/\s]+(?:\.git)?(?:/[^\s\)]*)?',  # Self-hosted GitLab
            r'https?://[^/\s]+/bitbucket/[^/\s]+/[^/\s]+(?:\.git)?(?:/[^\s\)]*)?',  # Self-hosted Bitbucket
            r'git@[^:\s]+:[^/\s]+/[^/\s]+(?:\.git)?',  # SSH URLs
            r'https?://[^/\s]+\.visualstudio\.com/[^/\s]+/_git/[^/\s]+',  # Azure DevOps
            r'https?://dev\.azure\.com/[^/\s]+/[^/\s]+/_git/[^/\s]+',  # Azure DevOps new format
            r'https?://[^/\s]+/git/[^/\s]+/[^/\s]+(?:\.git)?(?:/[^\s\)]*)?',  # Generic Git hosting
        ]
        
        urls = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            urls.extend(matches)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        return unique_urls
    
    async def extract_confluence_and_git_links(self, issue_key: str, include_git_urls: bool = True) -> List[Dict[str, Any]]:
        """Extract both Confluence and Git links from an issue's description, comments, and remote links."""
        all_links = []
        
        try:
            # Get issue data with comments and remote links
            issue_data = await self.summarize_issue(issue_key)
            
            # Check remote links first (most reliable)
            if "remoteLinks" in issue_data:
                for link in issue_data["remoteLinks"]:
                    url = link.get("object", {}).get("url", "")
                    title = link.get("object", {}).get("title", "")
                    summary = link.get("object", {}).get("summary", "")
                    
                    # Check if it's a Confluence link
                    if url.find("confluence") != -1 or url.find("wiki") != -1:
                        all_links.append({
                            "type": "remote_link",
                            "category": "confluence",
                            "title": title or "Confluence Page",
                            "url": url,
                            "summary": summary
                        })
                    # Check if it's a Git repository link
                    elif include_git_urls and any(pattern in url.lower() for pattern in ['github', 'gitlab', 'bitbucket', 'git', '_git']):
                        all_links.append({
                            "type": "remote_link", 
                            "category": "git",
                            "title": title or "Git Repository",
                            "url": url,
                            "summary": summary
                        })
            
            # Check description for Confluence and Git URLs
            description = issue_data.get("fields", {}).get("description", "") or ""
            
            confluence_urls = self._extract_confluence_urls_from_text(description)
            for url in confluence_urls:
                all_links.append({
                    "type": "description_link",
                    "category": "confluence",
                    "title": "Confluence Page",
                    "url": url,
                    "summary": "Found in issue description"
                })
            
            if include_git_urls:
                git_urls = self._extract_git_urls_from_text(description)
                for url in git_urls:
                    all_links.append({
                        "type": "description_link",
                        "category": "git", 
                        "title": "Git Repository",
                        "url": url,
                        "summary": "Found in issue description"
                    })
            
            # Check comments for Confluence and Git URLs
            comments = issue_data.get("fields", {}).get("comment", {}).get("comments", [])
            for comment in comments:
                comment_body = comment.get("body", "") or ""
                author = comment.get('author', {}).get('displayName', 'Unknown')
                
                confluence_urls = self._extract_confluence_urls_from_text(comment_body)
                for url in confluence_urls:
                    all_links.append({
                        "type": "comment_link",
                        "category": "confluence",
                        "title": "Confluence Page",
                        "url": url,
                        "summary": f"Found in comment by {author}"
                    })
                
                if include_git_urls:
                    git_urls = self._extract_git_urls_from_text(comment_body)
                    for url in git_urls:
                        all_links.append({
                            "type": "comment_link",
                            "category": "git",
                            "title": "Git Repository", 
                            "url": url,
                            "summary": f"Found in comment by {author}"
                        })
            
        except Exception as e:
            logger.warning(f"Error extracting links from {issue_key}: {e}")
        
        return all_links

# Instantiate a global client
jira_client = JiraClient()
