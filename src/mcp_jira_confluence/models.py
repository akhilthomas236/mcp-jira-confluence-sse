"""Models for the MCP Jira and Confluence server."""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class JiraIssue:
    """Representation of a Jira issue."""
    key: str
    summary: str
    description: Optional[str] = None
    status: Optional[str] = None
    issue_type: Optional[str] = None
    assignee: Optional[str] = None
    reporter: Optional[str] = None
    priority: Optional[str] = None
    created: Optional[str] = None
    updated: Optional[str] = None


@dataclass
class JiraProject:
    """Representation of a Jira project."""
    key: str
    name: str
    id: str


@dataclass
class JiraComment:
    """Representation of a Jira comment."""
    id: str
    body: str
    author: str
    created: str


@dataclass
class JiraTransition:
    """Representation of a Jira transition."""
    id: str
    name: str
    to_status: str


@dataclass
class ConfluencePage:
    """Representation of a Confluence page."""
    id: str
    title: str
    content: str
    space_key: str
    version: int
    created: Optional[str] = None
    updated: Optional[str] = None


@dataclass
class ConfluenceComment:
    """Representation of a Confluence comment."""
    id: str
    content: str
    author: str
    created: str


@dataclass
class ConfluenceSpace:
    """Representation of a Confluence space."""
    key: str
    name: str
