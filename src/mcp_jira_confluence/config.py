"""Configuration handling for the MCP Jira and Confluence server."""

import os
from typing import Dict, Optional, Any
from pydantic import BaseModel, Field


class JiraConfig(BaseModel):
    """Jira configuration."""
    url: str = Field(
        default_factory=lambda: os.environ.get("JIRA_URL", ""),
        description="Jira instance URL"
    )
    username: Optional[str] = Field(
        default_factory=lambda: os.environ.get("JIRA_USERNAME", ""),
        description="Jira username for basic authentication"
    )
    api_token: Optional[str] = Field(
        default_factory=lambda: os.environ.get("JIRA_API_TOKEN", ""),
        description="API token for Jira Cloud"
    )
    personal_token: Optional[str] = Field(
        default_factory=lambda: os.environ.get("JIRA_PERSONAL_TOKEN", ""),
        description="Personal Access Token for Jira Server/DC"
    )
    ssl_verify: bool = Field(
        default_factory=lambda: os.environ.get("JIRA_SSL_VERIFY", "true").lower() != "false",
        description="Verify SSL certificates"
    )
    cloud_id: Optional[str] = Field(
        default_factory=lambda: os.environ.get("JIRA_CLOUD_ID", ""),
        description="Jira Cloud ID"
    )


class ConfluenceConfig(BaseModel):
    """Confluence configuration."""
    url: str = Field(
        default_factory=lambda: os.environ.get("CONFLUENCE_URL", ""),
        description="Confluence instance URL"
    )
    username: Optional[str] = Field(
        default_factory=lambda: os.environ.get("CONFLUENCE_USERNAME", ""),
        description="Confluence username for basic authentication"
    )
    api_token: Optional[str] = Field(
        default_factory=lambda: os.environ.get("CONFLUENCE_API_TOKEN", ""),
        description="API token for Confluence Cloud"
    )
    personal_token: Optional[str] = Field(
        default_factory=lambda: os.environ.get("CONFLUENCE_PERSONAL_TOKEN", ""),
        description="Personal Access Token for Confluence Server/DC"
    )
    ssl_verify: bool = Field(
        default_factory=lambda: os.environ.get("CONFLUENCE_SSL_VERIFY", "true").lower() != "false",
        description="Verify SSL certificates"
    )
    cloud_id: Optional[str] = Field(
        default_factory=lambda: os.environ.get("CONFLUENCE_CLOUD_ID", ""),
        description="Confluence Cloud ID"
    )


def get_jira_config() -> JiraConfig:
    """Get Jira configuration from environment variables."""
    return JiraConfig()


def get_confluence_config() -> ConfluenceConfig:
    """Get Confluence configuration from environment variables."""
    return ConfluenceConfig()
