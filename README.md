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
  - Search pages using CQL (Confluence Query Language)
  - Get specific pages by ID or title
  - Ask questions about page content

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
- `JIRA_URL`: Base URL of your Jira instance (e.g., `https://yourcompany.atlassian.net`)
- `JIRA_USERNAME`: Your Jira username/email
- `JIRA_API_TOKEN`: Your Jira API token or password
- `JIRA_PERSONAL_TOKEN`: Personal access token (alternative to username/API token)

#### Confluence Configuration
- `CONFLUENCE_URL`: Base URL of your Confluence instance (e.g., `https://yourcompany.atlassian.net/wiki`)
- `CONFLUENCE_USERNAME`: Your Confluence username/email
- `CONFLUENCE_API_TOKEN`: Your Confluence API token or password
- `CONFLUENCE_PERSONAL_TOKEN`: Personal access token (alternative to username/API token)

### Quick Setup

1. Create API tokens from your Atlassian account settings
2. Set environment variables in your shell:

```bash
export JIRA_URL="https://yourcompany.atlassian.net"
export JIRA_USERNAME="your-email@company.com"
export JIRA_API_TOKEN="your-jira-api-token"

export CONFLUENCE_URL="https://yourcompany.atlassian.net/wiki"
export CONFLUENCE_USERNAME="your-email@company.com"
export CONFLUENCE_API_TOKEN="your-confluence-api-token"
```

3. Or use the provided `run.sh` script with environment variables

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

## Usage

### Available Tools

#### Jira Tools
- **`create-jira-issue`**: Create a new Jira issue
- **`comment-jira-issue`**: Add a comment to an issue
- **`transition-jira-issue`**: Change an issue's status

#### Confluence Tools
- **`create-confluence-page`**: Create a new Confluence page
- **`update-confluence-page`**: Update an existing page (version auto-fetched if not provided)
- **`comment-confluence-page`**: Add a comment to a page
- **`get-confluence-page`**: Get a specific page with optional comments/history
- **`search-confluence`**: Search pages using CQL queries
- **`ask-confluence-page`**: Ask questions about page content

### Usage Examples

#### Getting a Confluence Page
```
You can retrieve a page using either its ID or title + space key:

By ID:
- page_id: "123456789"
- include_comments: true
- include_history: false

By title and space:
- title: "API Documentation"
- space_key: "DEV"
- include_comments: false
```

#### Searching Confluence Pages
```
Search using CQL (Confluence Query Language):

Simple text search:
- query: "API Documentation"
- max_results: 10

Search by title:
- query: "title ~ 'API Documentation'"
- max_results: 10

Search in specific space:
- query: "space.key = 'DEV'"
- space_key: "DEV"
- max_results: 5

Recent pages:
- query: "lastmodified >= now('-7d')"

Note: The system automatically adds "type = page" to queries that don't specify a content type.
```

#### Asking Questions About Pages
```
Ask specific questions about page content:

- page_id: "123456789"
- question: "What are the main features described?"
- context_type: "summary" | "details" | "specific"

Or using title + space:
- title: "User Guide"
- space_key: "DOCS"
- question: "How do I configure authentication?"
- context_type: "details"
```

#### Common CQL Query Examples
- Simple text search: `"API Documentation"` (searches in content and title)
- Search by title: `title ~ "API Documentation"`
- Search in space: `space.key = "DEV"`
- Recent pages: `lastmodified >= now("-7d")`
- By author: `creator = "john.doe"`
- Combined: `title ~ "API" AND space.key = "DEV" AND lastmodified >= now("-30d")`
- Text in content: `text ~ "authentication method"`

Note: All queries automatically include `type = page` unless explicitly specified otherwise.

### Available Prompts

#### AI-Powered Analysis
- **`summarize-jira-issue`**: Create a summary of a Jira issue
- **`create-jira-description`**: Generate a structured issue description
- **`summarize-confluence-page`**: Create a summary of a Confluence page
- **`create-confluence-content`**: Generate structured Confluence content
- **`answer-confluence-question`**: Answer questions about specific page content

### Context Types for Question Answering
- **`summary`**: Quick answers using first 1000-1500 characters
- **`details`**: Comprehensive answers using full page content
- **`specific`**: Full content with enhanced filtering (future feature)

For detailed Confluence tool documentation and advanced CQL examples, see [CONFLUENCE_TOOLS.md](CONFLUENCE_TOOLS.md).

## Practical Examples

### Workflow: Research and Documentation
1. **Search for relevant pages**: Use `search-confluence` to find pages related to your topic
2. **Get page details**: Use `get-confluence-page` to retrieve full content with comments
3. **Ask specific questions**: Use `ask-confluence-page` to extract specific information
4. **Create summaries**: Use `summarize-confluence-page` prompt for quick overviews

### Common Use Cases

#### Finding Documentation
```
"Search for all API documentation in the DEV space that was updated in the last month"
→ Use search-confluence with query: "type = page AND space.key = 'DEV' AND title ~ 'API' AND lastmodified >= now('-30d')"
```

#### Getting Page Information
```
"Get the User Guide page from DOCS space with all comments"
→ Use get-confluence-page with title: "User Guide", space_key: "DOCS", include_comments: true
```

#### Content Analysis
```
"What authentication methods are supported according to the API documentation?"
→ Use ask-confluence-page with the API doc page ID and your specific question
```

#### Knowledge Extraction
```
"Summarize the key points from the deployment guide"
→ Use summarize-confluence-page prompt with the deployment guide page ID
```

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

## Changelog

### Version 0.2.0 (2025-07-27)

**Major Improvements:**

- **Fixed EmbeddedResource validation errors** - All tools now use the correct MCP structure with `type: "resource"` and proper `TextResourceContents` format
- **Enhanced Confluence formatting** - Dramatically improved markdown to Confluence conversion:
  - Proper list handling (grouped `<ul>`/`<ol>` tags instead of individual ones)
  - Better code block formatting with language support
  - Improved inline formatting (bold, italic, code, links)
  - Smarter paragraph handling
  - More robust markdown detection patterns
- **Fixed HTTP 409 conflicts** - Made version parameter optional in `update-confluence-page` with automatic version fetching
- **Added missing Confluence tools** - Implemented `get-confluence-page` and `search-confluence-pages` with proper CQL support
- **Improved error handling** - Better error messages and validation throughout

**Technical Changes:**

- Rewrote `ConfluenceFormatter.markdown_to_confluence()` with line-by-line processing
- Added regex-based markdown detection with multiple pattern matching
- Enhanced `_process_inline_formatting()` helper for consistent formatting
- Improved version conflict resolution in page updates
- Added comprehensive logging for format detection and conversion

### Version 0.1.9 (2025-07-26)

- Initial PyPI release with basic Jira and Confluence functionality
- Fixed basic EmbeddedResource structure issues
- Added core tool implementations