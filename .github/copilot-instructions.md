# GitHub Copilot Instructions for MCP Jira & Confluence Server

This is a Model Context Protocol (MCP) server that integrates with Jira and Confluence, enabling AI assistants to interact with Atlassian tools.

## Project Structure

- `src/mcp_jira_confluence/`: Main package directory
  - `server.py`: Main MCP server implementation
  - `config.py`: Configuration management for Jira and Confluence
  - `jira.py`: Jira API client with various operations
  - `confluence.py`: Confluence API client with various operations
  - `formatter.py`: Converters between Markdown and Jira/Confluence markup
  - `models.py`: Data models for Jira and Confluence resources

## Environment Variables

The server requires the following environment variables:

### Jira Configuration
- `JIRA_URL`: Base URL of Jira instance
- `JIRA_USERNAME`: Jira username
- `JIRA_API_TOKEN`: Jira API token or password
- `JIRA_PERSONAL_TOKEN`: Personal access token (alternative to username/API token)

### Confluence Configuration
- `CONFLUENCE_URL`: Base URL of Confluence instance
- `CONFLUENCE_USERNAME`: Confluence username
- `CONFLUENCE_API_TOKEN`: Confluence API token or password
- `CONFLUENCE_PERSONAL_TOKEN`: Personal access token (alternative to username/API token)

## Development Notes

- Uses the Model Context Protocol (MCP) to expose Jira and Confluence operations
- Implements resource listing, resource reading, prompts generation, and tool execution
- Follows async patterns using `httpx` for API communication
- Handles markup conversion between Markdown and Jira/Confluence formats
