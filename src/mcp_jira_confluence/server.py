import asyncio
import logging
import json
import sys
from typing import Dict, List, Optional, Any, Union
from urllib.parse import quote, urlparse, parse_qs, unquote

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl, ValidationError
import mcp.server.stdio

from .jira import jira_client
from .confluence import confluence_client
from .formatter import JiraFormatter, ConfluenceFormatter
from .models import JiraIssue, ConfluencePage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mcp-jira-confluence")

server = Server("mcp-jira-confluence")

# Define URI schemes
JIRA_SCHEME = "jira"
CONFLUENCE_SCHEME = "confluence"

# Helper functions
def build_jira_uri(issue_key: str) -> str:
    """Build a Jira issue URI."""
    return f"{JIRA_SCHEME}://issue/{issue_key}"

def build_confluence_uri(page_id: str, space_key: Optional[str] = None) -> str:
    """Build a Confluence page URI."""
    if space_key:
        return f"{CONFLUENCE_SCHEME}://space/{space_key}/page/{page_id}"
    return f"{CONFLUENCE_SCHEME}://page/{page_id}"

def parse_jira_uri(uri: str) -> Dict[str, Any]:
    """Parse a Jira URI into components."""
    parsed = urlparse(uri)
    if parsed.scheme != JIRA_SCHEME:
        raise ValueError(f"Invalid Jira URI scheme: {parsed.scheme}")
    
    path_parts = parsed.path.strip("/").split("/")
    if len(path_parts) < 2:
        raise ValueError(f"Invalid Jira URI path: {parsed.path}")
    
    resource_type = path_parts[0]
    resource_id = path_parts[1]
    
    return {
        "type": resource_type,
        "id": resource_id
    }

def parse_confluence_uri(uri: str) -> Dict[str, Any]:
    """Parse a Confluence URI into components."""
    parsed = urlparse(uri)
    if parsed.scheme != CONFLUENCE_SCHEME:
        raise ValueError(f"Invalid Confluence URI scheme: {parsed.scheme}")
    
    path_parts = parsed.path.strip("/").split("/")
    
    if len(path_parts) >= 3 and path_parts[0] == "space":
        return {
            "type": path_parts[2],  # "page"
            "space_key": path_parts[1],
            "id": path_parts[3]
        }
    elif len(path_parts) >= 2:
        return {
            "type": path_parts[0],  # "page"
            "id": path_parts[1]
        }
    
    raise ValueError(f"Invalid Confluence URI path: {parsed.path}")

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """
    List available Jira and Confluence resources.
    Each resource is exposed with a custom URI scheme.
    """
    resources = []
    
    # Add Jira issues using JQL search
    try:
        jql = "updated >= -7d ORDER BY updated DESC"  # Recently updated issues
        issues_result = await jira_client.search_issues(jql, max_results=10)
        
        for issue in issues_result.get("issues", []):
            issue_key = issue["key"]
            summary = issue["fields"]["summary"]
            status = issue["fields"]["status"]["name"] if "status" in issue["fields"] else "Unknown"
            
            resources.append(
                types.Resource(
                    uri=AnyUrl(build_jira_uri(issue_key)),
                    name=f"Jira: {issue_key}: {summary}",
                    description=f"Status: {status}",
                    mimeType="text/markdown",
                )
            )
    except Exception as e:
        logger.error(f"Error fetching Jira issues: {e}")
    
    # Add Confluence pages using CQL search
    try:
        cql = "lastmodified >= now('-7d')"  # Recently modified pages
        pages_result = await confluence_client.search(cql, limit=10)
        
        for page in pages_result.get("results", []):
            page_id = page["id"]
            title = page["title"]
            space_key = page["space"]["key"] if "space" in page else None
            
            resource_uri = build_confluence_uri(page_id, space_key)
            resources.append(
                types.Resource(
                    uri=AnyUrl(resource_uri),
                    name=f"Confluence: {title}",
                    description=f"Space: {space_key}" if space_key else "",
                    mimeType="text/markdown",
                )
            )
    except Exception as e:
        logger.error(f"Error fetching Confluence pages: {e}")
    
    return resources

@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    """
    Read content from Jira or Confluence based on the URI.
    """
    uri_str = str(uri)
    
    try:
        if uri.scheme == JIRA_SCHEME:
            resource_info = parse_jira_uri(uri_str)
            
            if resource_info["type"] == "issue":
                issue_key = resource_info["id"]
                issue_data = await jira_client.get_issue(issue_key)
                
                # Format the issue data as markdown
                summary = issue_data["fields"]["summary"]
                description = issue_data["fields"].get("description", "")
                status = issue_data["fields"]["status"]["name"] if "status" in issue_data["fields"] else "Unknown"
                issue_type = issue_data["fields"]["issuetype"]["name"] if "issuetype" in issue_data["fields"] else "Unknown"
                
                # Build markdown representation
                content = f"# {issue_key}: {summary}\n\n"
                content += f"**Type:** {issue_type}  \n"
                content += f"**Status:** {status}  \n\n"
                
                if description:
                    content += "## Description\n\n"
                    # Convert from Jira markup to Markdown if needed
                    markdown_desc = JiraFormatter.jira_to_markdown(description) if description else ""
                    content += f"{markdown_desc}\n\n"
                
                # Add comments if available
                try:
                    comments_data = await jira_client.get_issue(issue_key, "comment")
                    if "comment" in comments_data and "comments" in comments_data["comment"]:
                        content += "## Comments\n\n"
                        for comment in comments_data["comment"]["comments"]:
                            author = comment.get("author", {}).get("displayName", "Unknown")
                            body = comment.get("body", "")
                            created = comment.get("created", "")
                            
                            content += f"**{author}** - {created}\n\n"
                            content += f"{JiraFormatter.jira_to_markdown(body)}\n\n"
                            content += "---\n\n"
                except Exception as e:
                    logger.error(f"Error fetching Jira comments: {e}")
                
                return content
            else:
                raise ValueError(f"Unsupported Jira resource type: {resource_info['type']}")
                
        elif uri.scheme == CONFLUENCE_SCHEME:
            resource_info = parse_confluence_uri(uri_str)
            
            if resource_info["type"] == "page":
                page_id = resource_info["id"]
                page_data = await confluence_client.get_page(page_id, expand="body.storage,version")
                
                # Format the page data as markdown
                title = page_data["title"]
                content = page_data["body"]["storage"]["value"]
                space_name = page_data.get("space", {}).get("name", "Unknown Space")
                
                # Convert from Confluence markup to Markdown
                markdown_content = ConfluenceFormatter.confluence_to_markdown(content)
                
                # Build markdown representation
                result = f"# {title}\n\n"
                result += f"**Space:** {space_name}  \n"
                result += f"**Version:** {page_data['version']['number']}  \n\n"
                result += markdown_content
                
                return result
            else:
                raise ValueError(f"Unsupported Confluence resource type: {resource_info['type']}")
        else:
            raise ValueError(f"Unsupported URI scheme: {uri.scheme}")
    except Exception as e:
        logger.error(f"Error reading resource {uri_str}: {e}")
        return f"Error: Could not read resource: {str(e)}"

@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    """
    List available prompts for Jira and Confluence.
    Each prompt can have optional arguments to customize its behavior.
    """
    return [
        types.Prompt(
            name="summarize-jira-issue",
            description="Creates a summary of a Jira issue",
            arguments=[
                types.PromptArgument(
                    name="issue_key",
                    description="The key of the Jira issue (e.g., PROJ-123)",
                    required=True,
                ),
                types.PromptArgument(
                    name="style",
                    description="Style of the summary (brief/detailed)",
                    required=False,
                )
            ],
        ),
        types.Prompt(
            name="create-jira-description",
            description="Creates a well-structured description for a Jira issue",
            arguments=[
                types.PromptArgument(
                    name="summary",
                    description="The summary/title of the issue",
                    required=True,
                ),
                types.PromptArgument(
                    name="issue_type",
                    description="The type of issue (e.g., Bug, Story, Task)",
                    required=True,
                )
            ],
        ),
        types.Prompt(
            name="summarize-confluence-page",
            description="Creates a summary of a Confluence page",
            arguments=[
                types.PromptArgument(
                    name="page_id",
                    description="The ID of the Confluence page",
                    required=True,
                ),
                types.PromptArgument(
                    name="style",
                    description="Style of the summary (brief/detailed)",
                    required=False,
                )
            ],
        ),
        types.Prompt(
            name="create-confluence-content",
            description="Creates well-structured content for a Confluence page",
            arguments=[
                types.PromptArgument(
                    name="title",
                    description="The title of the page",
                    required=True,
                ),
                types.PromptArgument(
                    name="topic",
                    description="The main topic of the page",
                    required=True,
                )
            ],
        ),
    ]

@server.get_prompt()
async def handle_get_prompt(
    name: str, arguments: dict[str, str] | None
) -> types.GetPromptResult:
    """
    Generate prompts for Jira and Confluence operations.
    """
    if arguments is None:
        arguments = {}
        
    if name == "summarize-jira-issue":
        issue_key = arguments.get("issue_key")
        if not issue_key:
            raise ValueError("Missing required argument: issue_key")
            
        style = arguments.get("style", "brief")
        style_prompt = " Provide extensive details." if style == "detailed" else " Be concise."
        
        try:
            issue_data = await jira_client.get_issue(issue_key)
            
            summary = issue_data["fields"]["summary"]
            description = issue_data["fields"].get("description", "")
            status = issue_data["fields"]["status"]["name"] if "status" in issue_data["fields"] else "Unknown"
            issue_type = issue_data["fields"]["issuetype"]["name"] if "issuetype" in issue_data["fields"] else "Unknown"
            
            # Get comments if available
            comments = ""
            try:
                comments_data = await jira_client.get_issue(issue_key, "comment")
                if "comment" in comments_data and "comments" in comments_data["comment"]:
                    for comment in comments_data["comment"]["comments"]:
                        author = comment.get("author", {}).get("displayName", "Unknown")
                        body = comment.get("body", "")
                        created = comment.get("created", "")
                        
                        comments += f"Comment by {author} on {created}:\n{body}\n\n"
            except Exception as e:
                logger.error(f"Error fetching Jira comments for prompt: {e}")
                
            return types.GetPromptResult(
                description=f"Summarize Jira issue {issue_key}",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=f"Please summarize the following Jira issue.{style_prompt}\n\n"
                                f"Issue Key: {issue_key}\n"
                                f"Summary: {summary}\n"
                                f"Type: {issue_type}\n"
                                f"Status: {status}\n"
                                f"Description:\n{description}\n\n"
                                f"Comments:\n{comments}"
                        ),
                    )
                ],
            )
        except Exception as e:
            logger.error(f"Error creating Jira issue summary prompt: {e}")
            raise ValueError(f"Could not fetch Jira issue data: {str(e)}")
            
    elif name == "create-jira-description":
        summary = arguments.get("summary")
        issue_type = arguments.get("issue_type")
        
        if not summary or not issue_type:
            raise ValueError("Missing required arguments: summary and issue_type")
            
        structure_template = ""
        if issue_type.lower() == "bug":
            structure_template = "For a bug description, include these sections: Steps to Reproduce, Expected Result, Actual Result, Environment, and Impact."
        elif issue_type.lower() in ["story", "feature"]:
            structure_template = "For a user story, use this format: As a [type of user], I want [goal] so that [benefit]. Include Acceptance Criteria and any relevant details."
        else:
            structure_template = "Create a well-structured description with clear sections and details."
            
        return types.GetPromptResult(
            description=f"Create {issue_type} description for '{summary}'",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"Please create a well-structured description for a Jira {issue_type} with the summary: '{summary}'\n\n"
                            f"{structure_template}\n\n"
                            f"Use Jira markup formatting for the description."
                    ),
                )
            ],
        )
            
    elif name == "summarize-confluence-page":
        page_id = arguments.get("page_id")
        if not page_id:
            raise ValueError("Missing required argument: page_id")
            
        style = arguments.get("style", "brief")
        style_prompt = " Provide extensive details." if style == "detailed" else " Be concise."
        
        try:
            page_data = await confluence_client.get_page(page_id, expand="body.storage,version")
            
            title = page_data["title"]
            content = page_data["body"]["storage"]["value"]
            space_name = page_data.get("space", {}).get("name", "Unknown Space")
            
            return types.GetPromptResult(
                description=f"Summarize Confluence page '{title}'",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=f"Please summarize the following Confluence page.{style_prompt}\n\n"
                                f"Title: {title}\n"
                                f"Space: {space_name}\n\n"
                                f"Content:\n{content}"
                        ),
                    )
                ],
            )
        except Exception as e:
            logger.error(f"Error creating Confluence page summary prompt: {e}")
            raise ValueError(f"Could not fetch Confluence page data: {str(e)}")
            
    elif name == "create-confluence-content":
        title = arguments.get("title")
        topic = arguments.get("topic")
        
        if not title or not topic:
            raise ValueError("Missing required arguments: title and topic")
            
        return types.GetPromptResult(
            description=f"Create content for Confluence page '{title}'",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"Please create well-structured content for a Confluence page with the title: '{title}' about the topic: '{topic}'\n\n"
                            f"Include appropriate headings, bullet points, and formatting. The content should be comprehensive but clear. "
                            f"Use Confluence markup for formatting the content."
                    ),
                )
            ],
        )
    else:
        raise ValueError(f"Unknown prompt: {name}")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available tools for Jira and Confluence operations.
    Each tool specifies its arguments using JSON Schema validation.
    """
    return [
        types.Tool(
            name="create-jira-issue",
            description="Create a new Jira issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_key": {"type": "string"},
                    "summary": {"type": "string"},
                    "issue_type": {"type": "string"},
                    "description": {"type": "string"},
                    "assignee": {"type": "string"},
                },
                "required": ["project_key", "summary", "issue_type"],
            },
        ),
        types.Tool(
            name="comment-jira-issue",
            description="Add a comment to a Jira issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {"type": "string"},
                    "comment": {"type": "string"},
                },
                "required": ["issue_key", "comment"],
            },
        ),
        types.Tool(
            name="transition-jira-issue",
            description="Transition a Jira issue to a new status",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {"type": "string"},
                    "transition_id": {"type": "string"},
                },
                "required": ["issue_key", "transition_id"],
            },
        ),
        types.Tool(
            name="create-confluence-page",
            description="Create a new Confluence page",
            inputSchema={
                "type": "object",
                "properties": {
                    "space_key": {"type": "string"},
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "parent_id": {"type": "string"},
                },
                "required": ["space_key", "title", "content"],
            },
        ),
        types.Tool(
            name="update-confluence-page",
            description="Update an existing Confluence page",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string"},
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "version": {"type": "number"},
                },
                "required": ["page_id", "title", "content", "version"],
            },
        ),
        types.Tool(
            name="comment-confluence-page",
            description="Add a comment to a Confluence page",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string"},
                    "comment": {"type": "string"},
                },
                "required": ["page_id", "comment"],
            },
        ),
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle tool execution requests for Jira and Confluence operations.
    """
    if not arguments:
        raise ValueError("Missing arguments")
        
    try:
        # Jira operations
        if name == "create-jira-issue":
            project_key = arguments.get("project_key")
            summary = arguments.get("summary")
            issue_type = arguments.get("issue_type")
            description = arguments.get("description")
            assignee = arguments.get("assignee")
            
            if not project_key or not summary or not issue_type:
                raise ValueError("Missing required arguments: project_key, summary, and issue_type")
                
            result = await jira_client.create_issue(
                project_key=project_key,
                summary=summary,
                issue_type=issue_type,
                description=description,
                assignee=assignee
            )
            
            issue_key = result.get("key")
            if not issue_key:
                raise ValueError("Failed to create Jira issue, no issue key returned")
                
            return [
                types.TextContent(
                    type="text",
                    text=f"Created Jira issue {issue_key}",
                ),
                types.EmbeddedResource(uri=AnyUrl(build_jira_uri(issue_key)))
            ]
            
        elif name == "comment-jira-issue":
            issue_key = arguments.get("issue_key")
            comment = arguments.get("comment")
            
            if not issue_key or not comment:
                raise ValueError("Missing required arguments: issue_key and comment")
                
            result = await jira_client.add_comment(
                issue_key=issue_key,
                comment=comment
            )
            
            return [
                types.TextContent(
                    type="text",
                    text=f"Added comment to Jira issue {issue_key}",
                ),
                types.EmbeddedResource(uri=AnyUrl(build_jira_uri(issue_key)))
            ]
            
        elif name == "transition-jira-issue":
            issue_key = arguments.get("issue_key")
            transition_id = arguments.get("transition_id")
            
            if not issue_key or not transition_id:
                raise ValueError("Missing required arguments: issue_key and transition_id")
                
            await jira_client.transition_issue(
                issue_key=issue_key,
                transition_id=transition_id
            )
            
            # Get the issue to see the new status
            issue = await jira_client.get_issue(issue_key)
            new_status = issue["fields"]["status"]["name"] if "status" in issue["fields"] else "Unknown"
            
            return [
                types.TextContent(
                    type="text",
                    text=f"Transitioned Jira issue {issue_key} to status: {new_status}",
                ),
                types.EmbeddedResource(uri=AnyUrl(build_jira_uri(issue_key)))
            ]
        
        # Confluence operations
        elif name == "create-confluence-page":
            space_key = arguments.get("space_key")
            title = arguments.get("title")
            content = arguments.get("content")
            parent_id = arguments.get("parent_id")
            
            if not space_key or not title or not content:
                raise ValueError("Missing required arguments: space_key, title, and content")
                
            result = await confluence_client.create_page(
                space_key=space_key,
                title=title,
                content=content,
                parent_id=parent_id
            )
            
            page_id = result.get("id")
            if not page_id:
                raise ValueError("Failed to create Confluence page, no page id returned")
                
            return [
                types.TextContent(
                    type="text",
                    text=f"Created Confluence page: {title}",
                ),
                types.EmbeddedResource(uri=AnyUrl(build_confluence_uri(page_id, space_key)))
            ]
            
        elif name == "update-confluence-page":
            page_id = arguments.get("page_id")
            title = arguments.get("title")
            content = arguments.get("content")
            version = arguments.get("version")
            
            if not page_id or not title or not content or version is None:
                raise ValueError("Missing required arguments: page_id, title, content, and version")
                
            result = await confluence_client.update_page(
                page_id=page_id,
                title=title,
                content=content,
                version=version
            )
            
            # Get the space key for the URI
            page_data = await confluence_client.get_page(page_id)
            space_key = page_data.get("space", {}).get("key") if "space" in page_data else None
            
            return [
                types.TextContent(
                    type="text",
                    text=f"Updated Confluence page: {title} to version {version + 1}",
                ),
                types.EmbeddedResource(uri=AnyUrl(build_confluence_uri(page_id, space_key)))
            ]
            
        elif name == "comment-confluence-page":
            page_id = arguments.get("page_id")
            comment = arguments.get("comment")
            
            if not page_id or not comment:
                raise ValueError("Missing required arguments: page_id and comment")
                
            result = await confluence_client.add_comment(
                page_id=page_id,
                comment=comment
            )
            
            # Get the space key for the URI
            page_data = await confluence_client.get_page(page_id)
            space_key = page_data.get("space", {}).get("key") if "space" in page_data else None
            
            return [
                types.TextContent(
                    type="text",
                    text=f"Added comment to Confluence page",
                ),
                types.EmbeddedResource(uri=AnyUrl(build_confluence_uri(page_id, space_key)))
            ]
        else:
            raise ValueError(f"Unknown tool: {name}")
            
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return [
            types.TextContent(
                type="text",
                text=f"Error executing {name}: {str(e)}",
            )
        ]

async def run_server():
    # Initialize clients
    try:
        # Test Jira connection
        await jira_client.get_session()
        logger.info("Jira client initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize Jira client: {e}")
        
    try:
        # Test Confluence connection
        await confluence_client.get_session()
        logger.info("Confluence client initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize Confluence client: {e}")
    
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        try:
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="mcp-jira-confluence",
                    server_version="0.1.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            # Close client connections
            await jira_client.close()
            await confluence_client.close()
            logger.info("MCP server shut down")

def main():
    """Entry point for the application script."""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())