# MCP Server for Jira and Confluence

A Model Context Protocol (MCP) server that integrates with Atlassian's Jira and Confluence, enabling AI assistants to interact with these tools directly.

## Features

- **Jira Integration**
  - List recent issues
  - View issue details including comments
  - Create new issues
  - Add comments to issues
  - Transition issues between statuses

- **Confluence Integration**
  - List recent pages
  - View page content
  - Create new pages
  - Update existing pages
  - Add comments to pages

- **AI-Powered Prompts**
  - Summarize Jira issues
  - Create structured Jira issue descriptions
  - Summarize Confluence pages
  - Generate structured Confluence content

## Installation

1. Clone the repository
2. Install dependencies using `uv`:

```bash
pip install uv
uv pip install -e .
```

## Configuration

### Environment Variables

Set the following environment variables to configure the server:

#### Jira Configuration
- `JIRA_URL`: Base URL of your Jira instance
- `JIRA_USERNAME`: Your Jira username
- `JIRA_API_TOKEN`: Your Jira API token or password
- `JIRA_PERSONAL_TOKEN`: Personal access token (alternative to username/API token)

#### Confluence Configuration
- `CONFLUENCE_URL`: Base URL of your Confluence instance
- `CONFLUENCE_USERNAME`: Your Confluence username
- `CONFLUENCE_API_TOKEN`: Your Confluence API token or password
- `CONFLUENCE_PERSONAL_TOKEN`: Personal access token (alternative to username/API token)

## Usage

### Starting the Server

Run the server directly:

```bash
python -m mcp_jira_confluence.server
```

### VSCode MCP Extension

If using with the VSCode MCP extension, the server is automatically configured via `.vscode/mcp.json`.

### Claude Desktop

To use with Claude Desktop, add the following configuration:

On MacOS: `~/Library/Application\ Support/Claude/claude_desktop_config.json`
On Windows: `%APPDATA%/Claude/claude_desktop_config.json`

<details>
  <summary>Development/Unpublished Servers Configuration</summary>
  
```json
"mcpServers": {
  "mcp-jira-confluence": {
    "command": "uv",
    "args": [
      "--directory",
      "/Users/annmariyajoshy/vibecoding/mcp-jira-confluence",
      "run",
      "mcp-jira-confluence"
    ]
    }
  }
  ```
</details>

<details>
  <summary>Published Servers Configuration</summary>
  
```json
"mcpServers": {
  "mcp-jira-confluence": {
    "command": "uvx",
    "args": [
      "mcp-jira-confluence"
    ]
  }
}
```
</details>

## Resources

The server exposes the following types of resources:

- `jira://issue/{ISSUE_KEY}` - Jira issues
- `confluence://page/{PAGE_ID}` - Confluence pages
- `confluence://space/{SPACE_KEY}/page/{PAGE_ID}` - Confluence pages with space key

## Tools and Prompts

The server implements various tools and prompts for interacting with Jira and Confluence:

### Tools
- `create-jira-issue`: Create a new Jira issue
- `comment-jira-issue`: Add a comment to an issue
- `transition-jira-issue`: Change an issue's status
- `create-confluence-page`: Create a new Confluence page
- `update-confluence-page`: Update an existing page
- `comment-confluence-page`: Add a comment to a page

### Prompts
- `summarize-jira-issue`: Create a summary of a Jira issue
- `create-jira-description`: Generate a structured issue description
- `summarize-confluence-page`: Create a summary of a Confluence page
- `create-confluence-content`: Generate structured Confluence content

## Development

### Building and Publishing

To prepare the package for distribution:

1. Sync dependencies and update lockfile:
```bash
uv sync
```

2. Build package distributions:
```bash
uv build
```

This will create source and wheel distributions in the `dist/` directory.

3. Publish to PyPI:
```bash
uv publish
```

Note: You'll need to set PyPI credentials via environment variables or command flags:
- Token: `--token` or `UV_PUBLISH_TOKEN`
- Or username/password: `--username`/`UV_PUBLISH_USERNAME` and `--password`/`UV_PUBLISH_PASSWORD`

### Debugging

Since MCP servers run over stdio, debugging can be challenging. For the best debugging
experience, we strongly recommend using the [MCP Inspector](https://github.com/modelcontextprotocol/inspector).


You can launch the MCP Inspector via [`npm`](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) with this command:

```bash
npx @modelcontextprotocol/inspector uv --directory /Users/annmariyajoshy/vibecoding/mcp-jira-confluence run mcp-jira-confluence
```


Upon launching, the Inspector will display a URL that you can access in your browser to begin debugging.