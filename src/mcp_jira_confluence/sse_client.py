#!/usr/bin/env python3
"""
SSE Client for MCP Jira Confluence
This client connects to the SSE server and passes authentication tokens.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Dict, Any, Optional

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class SSEMCPClient:
    """MCP client that connects to SSE server with authentication."""
    
    def __init__(self, server_url: str, jira_token: str = None, confluence_token: str = None):
        self.server_url = server_url.rstrip('/')
        self.jira_token = jira_token
        self.confluence_token = confluence_token
        self.session = None
        
    async def connect(self):
        """Connect to the SSE server."""
        headers = {}
        
        # Add authentication headers
        if self.jira_token and self.confluence_token:
            # Use Jira token as primary if both are the same
            if self.jira_token == self.confluence_token:
                headers["Authorization"] = f"Bearer {self.jira_token}"
            else:
                headers["X-Jira-Token"] = self.jira_token
                headers["X-Confluence-Token"] = self.confluence_token
        elif self.jira_token:
            headers["Authorization"] = f"Bearer {self.jira_token}"
        elif self.confluence_token:
            headers["Authorization"] = f"Bearer {self.confluence_token}"
        
        # Create HTTP client
        self.client = httpx.AsyncClient(headers=headers, timeout=30.0)
        
        # Initialize MCP session
        await self.initialize()
        
    async def initialize(self):
        """Initialize the MCP session."""
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "sse-mcp-client",
                    "version": "1.0.0"
                }
            }
        }
        
        response = await self.client.post(f"{self.server_url}/mcp", json=init_request)
        response.raise_for_status()
        result = response.json()
        
        if "error" in result:
            raise Exception(f"Initialization failed: {result['error']}")
            
        logger.info("Successfully initialized MCP session")
        return result["result"]
        
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the server."""
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        response = await self.client.post(f"{self.server_url}/mcp", json=request)
        response.raise_for_status()
        result = response.json()
        
        if "error" in result:
            raise Exception(f"Tool call failed: {result['error']}")
            
        return result["result"]
        
    async def list_tools(self) -> Dict[str, Any]:
        """List available tools."""
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/list",
            "params": {}
        }
        
        response = await self.client.post(f"{self.server_url}/mcp", json=request)
        response.raise_for_status()
        result = response.json()
        
        if "error" in result:
            raise Exception(f"List tools failed: {result['error']}")
            
        return result["result"]
        
    async def health_check(self) -> Dict[str, Any]:
        """Check server health."""
        response = await self.client.get(f"{self.server_url}/health")
        response.raise_for_status()
        return response.json()
        
    async def close(self):
        """Close the client."""
        if self.client:
            await self.client.aclose()


async def main():
    """Main function to demonstrate SSE client usage."""
    logging.basicConfig(level=logging.INFO)
    
    # Get configuration from environment
    server_url = os.getenv("SSE_SERVER_URL", "http://localhost:8000")
    jira_token = os.getenv("JIRA_PERSONAL_TOKEN")
    confluence_token = os.getenv("CONFLUENCE_PERSONAL_TOKEN")
    
    if not jira_token and not confluence_token:
        logger.error("No authentication tokens provided")
        logger.error("Set JIRA_PERSONAL_TOKEN and/or CONFLUENCE_PERSONAL_TOKEN environment variables")
        sys.exit(1)
    
    # Create and connect client
    client = SSEMCPClient(server_url, jira_token, confluence_token)
    
    try:
        await client.connect()
        logger.info(f"Connected to SSE server at {server_url}")
        
        # Test health check
        health = await client.health_check()
        logger.info(f"Server health: {health}")
        
        # List available tools
        tools = await client.list_tools()
        logger.info(f"Available tools: {len(tools.get('tools', []))}")
        for tool in tools.get('tools', [])[:3]:  # Show first 3 tools
            logger.info(f"  - {tool['name']}: {tool['description']}")
        
        # Example: Get assigned issues (if available)
        try:
            result = await client.call_tool("get-my-assigned-issues", {"max_results": 5})
            logger.info("Successfully called get-my-assigned-issues tool")
        except Exception as e:
            logger.warning(f"Could not call tool: {e}")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
