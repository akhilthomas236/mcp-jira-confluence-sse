# Confluence Tools Documentation

This document describes the available Confluence tools and how to use them for retrieving and querying page content.

## Available Tools

### 1. `get-confluence-page`
Retrieve a specific Confluence page with optional metadata.

**Parameters:**
- `page_id` (string): The ID of the Confluence page
- `title` (string): The title of the page (requires `space_key`)
- `space_key` (string): The space key (when using title)
- `include_comments` (boolean, default: false): Include page comments
- `include_history` (boolean, default: false): Include version history

**Example Usage:**
```json
{
  "page_id": "123456789",
  "include_comments": true,
  "include_history": false
}
```

### 2. `search-confluence`
Search for Confluence pages using CQL (Confluence Query Language).

**Parameters:**
- `query` (string, required): CQL query string
- `space_key` (string, optional): Limit search to specific space
- `max_results` (integer, default: 10): Maximum number of results

**Example Usage:**
```json
{
  "query": "API Documentation",
  "space_key": "DEV",
  "max_results": 5
}
```

**Advanced CQL Examples:**
```json
{
  "query": "title ~ \"API\" AND text ~ \"authentication\"",
  "max_results": 10
}
```

### 3. `ask-confluence-page`
Ask a question about specific Confluence page content.

**Parameters:**
- `page_id` (string): The ID of the Confluence page
- `title` (string): The title of the page (requires `space_key`)
- `space_key` (string): The space key (when using title)
- `question` (string, required): The question about the page content
- `context_type` (string, default: "summary"): Context depth (summary/details/specific)

**Example Usage:**
```json
{
  "page_id": "123456789",
  "question": "What are the main features described in this page?",
  "context_type": "details"
}
```

### 4. `update-confluence-page`
Update an existing Confluence page with new content.

**Parameters:**
- `page_id` (string, required): The ID of the Confluence page to update
- `title` (string, required): The new title for the page
- `content` (string, required): The new content in Confluence storage format
- `version` (number, optional): Current version number. If not provided, it will be automatically fetched to prevent conflicts.

**Example Usage:**
```json
{
  "page_id": "123456789",
  "title": "Updated API Documentation",
  "content": "<h1>New Content</h1><p>Updated information...</p>"
}
```

**Note:** The tool automatically handles version conflicts by fetching the current page version if not provided, preventing HTTP 409 Conflict errors.

## Available Prompts

### 1. `summarize-confluence-page`
Creates a summary of a Confluence page.

### 2. `create-confluence-content`
Creates well-structured content for a new Confluence page.

### 3. `answer-confluence-question`
Answer questions about Confluence page content using AI assistance.

## CQL Query Examples

Here are some useful CQL query examples for `search-confluence`:

1. **Simple text search**: `"API Documentation"` (searches content and titles)
2. **Search by title**: `title ~ "API Documentation"`
3. **Search in specific space**: `space.key = "DEV"`
4. **Recently modified pages**: `lastmodified >= now("-7d")`
5. **Pages by specific author**: `creator = "john.doe"`
6. **Text in page content**: `text ~ "authentication method"`
7. **Combine conditions**: `title ~ "API" AND space.key = "DEV" AND lastmodified >= now("-30d")`
8. **Case-insensitive search**: `title ~ "api" OR text ~ "api"`
9. **Multiple spaces**: `space.key IN ("DEV", "DOCS")`
10. **Exclude archived content**: `type = page AND status = "current"`

**Important Notes:**
- The system automatically adds `type = page` to queries that don't specify content type
- Use `~` for partial matches and `=` for exact matches
- Date functions like `now("-7d")` are relative to current time
- Quotes are required around values containing spaces

## Context Types for Question Answering

- **summary**: Uses first 1000-1500 characters for quick answers
- **details**: Uses full page content for comprehensive answers
- **specific**: Full content with note about specific filtering (future enhancement)

## Error Handling

All tools include proper error handling for:
- Missing required parameters
- Page not found scenarios
- API connection issues
- Invalid CQL queries

## Performance Notes

- Pages are fetched fresh from the API each time (no local caching)
- Large pages may take longer to process in "details" context mode
- Search results are limited by the `max_results` parameter
- Content is converted from Confluence markup to Markdown for better readability
