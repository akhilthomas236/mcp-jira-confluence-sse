import asyncio
import logging
import json
import re
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
        types.Prompt(
            name="answer-confluence-question",
            description="Answer a question about a specific Confluence page using its content",
            arguments=[
                types.PromptArgument(
                    name="page_id",
                    description="The ID of the Confluence page",
                    required=False,
                ),
                types.PromptArgument(
                    name="title",
                    description="The title of the Confluence page",
                    required=False,
                ),
                types.PromptArgument(
                    name="space_key",
                    description="The key of the Confluence space",
                    required=False,
                ),
                types.PromptArgument(
                    name="question",
                    description="The question to answer about the page content",
                    required=True,
                ),
                types.PromptArgument(
                    name="context_depth",
                    description="How much context to include (brief/detailed)",
                    required=False,
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
        
    elif name == "answer-confluence-question":
        question = arguments.get("question")
        page_id = arguments.get("page_id")
        title = arguments.get("title")
        space_key = arguments.get("space_key")
        context_depth = arguments.get("context_depth", "brief")
        
        if not question:
            raise ValueError("Missing required argument: question")
            
        if not page_id and (not title or not space_key):
            raise ValueError("Missing required arguments: either page_id or both title and space_key")
        
        try:
            # Fetch the page content
            page_data = None
            if page_id:
                page_data = await confluence_client.get_page(page_id, expand="body.storage,version,space")
            else:
                # Search by title and space key
                cql = f'title = "{title}" AND space.key = "{space_key}"'
                search_result = await confluence_client.search(cql, limit=1)
                if search_result.get("results"):
                    page_id = search_result["results"][0]["id"]
                    page_data = await confluence_client.get_page(page_id, expand="body.storage,version,space")
                else:
                    raise ValueError("Page not found")
            
            page_title = page_data["title"]
            content = page_data["body"]["storage"]["value"]
            space_name = page_data.get("space", {}).get("name", "Unknown Space")
            
            # Convert to markdown for better readability
            markdown_content = ConfluenceFormatter.confluence_to_markdown(content)
            
            # Determine context based on depth
            if context_depth == "detailed":
                context_text = markdown_content
                context_instruction = "Use the full page content to provide a comprehensive answer."
            else:
                # Use first 1500 characters for brief context
                context_text = markdown_content[:1500] + "..." if len(markdown_content) > 1500 else markdown_content
                context_instruction = "Use the provided content excerpt to answer the question. Be concise but informative."
            
            return types.GetPromptResult(
                description=f"Answer question about Confluence page '{page_title}'",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=f"Please answer the following question based on the Confluence page content:\n\n"
                                f"**Question:** {question}\n\n"
                                f"**Page:** {page_title}\n"
                                f"**Space:** {space_name}\n\n"
                                f"**Instructions:** {context_instruction}\n\n"
                                f"**Page Content:**\n{context_text}\n\n"
                                f"Provide a clear, accurate answer based on the content above. If the content doesn't contain enough information to answer the question, say so."
                        ),
                    )
                ],
            )
        except Exception as e:
            logger.error(f"Error creating Confluence question prompt: {e}")
            raise ValueError(f"Could not fetch Confluence page data: {str(e)}")
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
            description="Update an existing Confluence page. If version is not provided, the current version will be automatically fetched to prevent conflicts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string"},
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "version": {"type": "number", "description": "Version number of the page. If not provided, current version will be automatically fetched."},
                },
                "required": ["page_id", "title", "content"],
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
        types.Tool(
            name="get-confluence-page",
            description="Get a Confluence page by ID or title. Use this tool to retrieve a specific page's content, optionally including comments and version history.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "The ID of the Confluence page"},
                    "title": {"type": "string", "description": "The title of the Confluence page"},
                    "space_key": {"type": "string", "description": "The key of the Confluence space"},
                    "include_comments": {"type": "boolean", "default": False},
                    "include_history": {"type": "boolean", "default": False}
                },
                "anyOf": [
                    {"required": ["page_id"]},
                    {"required": ["title", "space_key"]}
                ]
            }
        ),
        types.Tool(
            name="search-confluence",
            description="Search Confluence pages using CQL (Confluence Query Language). Use this to find pages matching specific criteria.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "CQL query string"
                    },
                    "space_key": {
                        "type": "string",
                        "description": "Limit search to a specific space"
                    },
                    "max_results": {
                        "type": "integer",
                        "default": 10,
                        "description": "Maximum number of results to return"
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="ask-confluence-page",
            description="Ask a question about a specific Confluence page content",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "The ID of the Confluence page"},
                    "title": {"type": "string", "description": "The title of the Confluence page"},
                    "space_key": {"type": "string", "description": "The key of the Confluence space"},
                    "question": {"type": "string", "description": "The question to ask about the page content"},
                    "context_type": {
                        "type": "string", 
                        "enum": ["summary", "details", "specific"],
                        "default": "summary",
                        "description": "Type of context needed to answer the question"
                    }
                },
                "anyOf": [
                    {"required": ["page_id", "question"]},
                    {"required": ["title", "space_key", "question"]}
                ]
            }
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
                types.EmbeddedResource(
                    type="resource",
                    resource=types.TextResourceContents(
                        uri=AnyUrl(build_jira_uri(issue_key)),
                        text=f"Created Jira issue: {issue_key}",
                        mimeType="text/markdown"
                    )
                )
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
                types.EmbeddedResource(
                    type="resource",
                    resource=types.TextResourceContents(
                        uri=AnyUrl(build_jira_uri(issue_key)),
                        text=f"Added comment to Jira issue: {issue_key}",
                        mimeType="text/markdown"
                    )
                )
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
                types.EmbeddedResource(
                    type="resource",
                    resource=types.TextResourceContents(
                        uri=AnyUrl(build_jira_uri(issue_key)),
                        text=f"Transitioned Jira issue {issue_key} to status: {new_status}",
                        mimeType="text/markdown"
                    )
                )
            ]
        
        # Confluence operations
        elif name == "create-confluence-page":
            space_key = arguments.get("space_key")
            title = arguments.get("title")
            content = arguments.get("content")
            parent_id = arguments.get("parent_id")
            
            if not space_key or not title or not content:
                raise ValueError("Missing required arguments: space_key, title, and content")
            
            # Convert content from markdown to Confluence storage format if needed
            # Improved markdown detection
            markdown_patterns = [
                r'^#{1,6}\s+',           # Headers
                r'\*\*(.*?)\*\*',        # Bold
                r'\*(.*?)\*',            # Italic/emphasis  
                r'`([^`]+)`',            # Inline code
                r'```',                  # Code blocks
                r'^[\s]*[-*]\s+',        # Unordered lists
                r'^[\s]*\d+\.\s+',       # Ordered lists
                r'\[.*?\]\(.*?\)',       # Links
                r'!\[.*?\]\(.*?\)',      # Images
            ]
            
            is_markdown = any(re.search(pattern, content, re.MULTILINE) for pattern in markdown_patterns)
            
            if is_markdown:
                try:
                    formatted_content = ConfluenceFormatter.markdown_to_confluence(content)
                    logger.info("Successfully converted markdown content to Confluence storage format")
                except Exception as e:
                    logger.warning(f"Failed to convert markdown, using as plain HTML: {e}")
                    # Fallback: wrap in simple paragraph tags with line breaks
                    lines = content.split('\n')
                    formatted_lines = [f"<p>{line}</p>" if line.strip() else "" for line in lines]
                    formatted_content = '\n'.join(formatted_lines)
            else:
                # Check if it's already HTML/XML format
                if content.strip().startswith('<') and content.strip().endswith('>'):
                    formatted_content = content
                    logger.info("Using content as-is (appears to be HTML/storage format)")
                else:
                    # Plain text - wrap in paragraph tags
                    formatted_content = f"<p>{content}</p>"
                    logger.info("Plain text detected - wrapped in paragraph tags")
                
            result = await confluence_client.create_page(
                space_key=space_key,
                title=title,
                content=formatted_content,
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
                types.EmbeddedResource(
                    type="resource",
                    resource=types.TextResourceContents(
                        uri=AnyUrl(build_confluence_uri(page_id, space_key)),
                        text=f"Created Confluence page: {title}",
                        mimeType="text/markdown"
                    )
                )
            ]
            
        elif name == "update-confluence-page":
            page_id = arguments.get("page_id")
            title = arguments.get("title")
            content = arguments.get("content")
            version = arguments.get("version")
            
            if not page_id or not title or not content:
                raise ValueError("Missing required arguments: page_id, title, and content")
            
            # If version is not provided, fetch the current version to prevent conflicts
            if version is None:
                try:
                    page_data = await confluence_client.get_page(page_id, expand="version")
                    version = page_data["version"]["number"]
                    logger.info(f"Auto-fetched current version {version} for page {page_id}")
                except Exception as e:
                    raise ValueError(f"Could not fetch current page version: {str(e)}")
            
            # Convert content from markdown to Confluence storage format if needed
            # Improved markdown detection
            markdown_patterns = [
                r'^#{1,6}\s+',           # Headers
                r'\*\*(.*?)\*\*',        # Bold
                r'\*(.*?)\*',            # Italic/emphasis  
                r'`([^`]+)`',            # Inline code
                r'```',                  # Code blocks
                r'^[\s]*[-*]\s+',        # Unordered lists
                r'^[\s]*\d+\.\s+',       # Ordered lists
                r'\[.*?\]\(.*?\)',       # Links
                r'!\[.*?\]\(.*?\)',      # Images
            ]
            
            is_markdown = any(re.search(pattern, content, re.MULTILINE) for pattern in markdown_patterns)
            
            if is_markdown:
                try:
                    formatted_content = ConfluenceFormatter.markdown_to_confluence(content)
                    logger.info("Successfully converted markdown content to Confluence storage format")
                except Exception as e:
                    logger.warning(f"Failed to convert markdown, using as plain HTML: {e}")
                    # Fallback: wrap in simple paragraph tags with line breaks
                    lines = content.split('\n')
                    formatted_lines = [f"<p>{line}</p>" if line.strip() else "" for line in lines]
                    formatted_content = '\n'.join(formatted_lines)
            else:
                # Check if it's already HTML/XML format
                if content.strip().startswith('<') and content.strip().endswith('>'):
                    formatted_content = content
                    logger.info("Using content as-is (appears to be HTML/storage format)")
                else:
                    # Plain text - wrap in paragraph tags
                    formatted_content = f"<p>{content}</p>"
                    logger.info("Plain text detected - wrapped in paragraph tags")
                
            result = await confluence_client.update_page(
                page_id=page_id,
                title=title,
                content=formatted_content,
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
                types.EmbeddedResource(
                    type="resource",
                    resource=types.TextResourceContents(
                        uri=AnyUrl(build_confluence_uri(page_id, space_key)),
                        text=f"Updated Confluence page: {title} to version {version + 1}",
                        mimeType="text/markdown"
                    )
                )
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
                types.EmbeddedResource(
                    type="resource",
                    resource=types.TextResourceContents(
                        uri=AnyUrl(build_confluence_uri(page_id, space_key)),
                        text=f"Comment added to page: {page_data.get('title', 'Unknown Title')}",
                        mimeType="text/markdown"
                    )
                )
            ]
        elif name == "get-confluence-page":
            page_id = arguments.get("page_id")
            title = arguments.get("title")
            space_key = arguments.get("space_key")
            include_comments = arguments.get("include_comments", False)
            include_history = arguments.get("include_history", False)
            
            if not page_id and (not title or not space_key):
                raise ValueError("Missing required arguments: either page_id or both title and space_key")
                
            # Fetch the page data
            page_data = None
            if page_id:
                page_data = await confluence_client.get_page(page_id, expand="body.storage,version,space")
            else:
                # Search by title and space key
                cql = f'title = "{title}" AND space.key = "{space_key}"'
                search_result = await confluence_client.search(cql, limit=1)
                if search_result.get("results"):
                    page_id = search_result["results"][0]["id"]
                    page_data = await confluence_client.get_page(page_id, expand="body.storage,version,space")
                else:
                    raise ValueError("Page not found")
            
            # Format the response
            title = page_data["title"]
            content = page_data["body"]["storage"]["value"]
            space_name = page_data.get("space", {}).get("name", "Unknown Space")
            version = page_data["version"]["number"] if "version" in page_data else "Unknown"
            
            response = f"**Title:** {title}\n"
            response += f"**Space:** {space_name}\n"
            response += f"**Version:** {version}\n\n"
            response += f"{ConfluenceFormatter.confluence_to_markdown(content)}"
            
            if include_comments:
                # Add comments section
                try:
                    comments_data = await confluence_client.get_page_comments(page_id)
                    if comments_data.get("results"):
                        response += "\n\n**Comments:**\n"
                        for comment in comments_data["results"]:
                            author = comment.get("by", {}).get("displayName", "Unknown")
                            body = comment.get("body", {}).get("storage", {}).get("value", "")
                            created = comment.get("when", "")
                            
                            response += f"- **{author}** on {created}: {ConfluenceFormatter.confluence_to_markdown(body)}\n"
                except Exception as e:
                    logger.warning(f"Could not fetch comments: {e}")
            
            if include_history:
                # Add history section
                try:
                    history_data = await confluence_client.get_page_history(page_id)
                    if history_data.get("results"):
                        response += "\n\n**History:**\n"
                        for version_info in history_data["results"]:
                            version_number = version_info.get("number", "Unknown")
                            author = version_info.get("by", {}).get("displayName", "Unknown")
                            date = version_info.get("when", "Unknown")
                            
                            response += f"- Version {version_number} by {author} on {date}\n"
                except Exception as e:
                    logger.warning(f"Could not fetch history: {e}")
            
            return [
                types.TextContent(
                    type="text",
                    text=response,
                )
            ]
        elif name == "search-confluence":
            query = arguments.get("query")
            space_key = arguments.get("space_key")
            max_results = arguments.get("max_results", 10)
            
            if not query:
                raise ValueError("Missing required argument: query")
                
            # Build CQL query with proper content type specification
            cql = query
            
            # If the query doesn't explicitly specify type, add "type = page"
            if "type" not in cql.lower():
                if cql.strip():
                    cql = f"type = page AND ({cql})"
                else:
                    cql = "type = page"
            
            # Add space constraint if provided
            if space_key:
                cql += f' AND space.key = "{space_key}"'
            
            # Execute search
            result = await confluence_client.search(cql, limit=max_results)
            
            if not result.get("results"):
                return [
                    types.TextContent(
                        type="text",
                        text="No Confluence pages found matching the query.",
                    )
                ]
            
            # Format the response as a list of pages
            response = "Confluence Pages Found:\n\n"
            for page in result["results"]:
                page_title = page["title"]
                page_id = page["id"]
                space_name = page.get("space", {}).get("name", "Unknown Space")
                last_modified = page.get("lastModified", {}).get("when", "Unknown")
                
                response += f"- **{page_title}** (ID: {page_id})\n"
                response += f"  Space: {space_name} | Last Modified: {last_modified}\n\n"
            
            return [
                types.TextContent(
                    type="text",
                    text=response,
                )
            ]
        elif name == "ask-confluence-page":
            page_id = arguments.get("page_id")
            title = arguments.get("title")
            space_key = arguments.get("space_key")
            question = arguments.get("question")
            context_type = arguments.get("context_type", "summary")
            
            if not question:
                raise ValueError("Missing required argument: question")
                
            if not page_id and (not title or not space_key):
                raise ValueError("Missing required arguments: either page_id or both title and space_key")
                
            # Fetch the page content
            page_data = None
            if page_id:
                page_data = await confluence_client.get_page(page_id, expand="body.storage,version,space")
            else:
                # Search by title and space key
                cql = f'title = "{title}" AND space.key = "{space_key}"'
                search_result = await confluence_client.search(cql, limit=1)
                if search_result.get("results"):
                    page_id = search_result["results"][0]["id"]
                    page_data = await confluence_client.get_page(page_id, expand="body.storage,version,space")
                else:
                    raise ValueError("Page not found")
            
            page_title = page_data["title"]
            content = page_data["body"]["storage"]["value"]
            space_name = page_data.get("space", {}).get("name", "Unknown Space")
            
            # Convert content to markdown for better readability
            markdown_content = ConfluenceFormatter.confluence_to_markdown(content)
            
            # Extract context based on the context type
            if context_type == "summary":
                # Use first 1000 characters for summary context
                context = markdown_content[:1000] + "..." if len(markdown_content) > 1000 else markdown_content
            elif context_type == "details":
                context = markdown_content
            else:
                # For specific context, use full content but note it's not specifically filtered
                context = markdown_content
            
            # Create a response that answers the question based on the page content
            response = f"**Question:** {question}\n\n"
            response += f"**Page:** {page_title}\n"
            response += f"**Space:** {space_name}\n\n"
            response += f"**Answer based on page content:**\n\n"
            response += f"Here is the relevant content from the Confluence page to help answer your question:\n\n"
            response += f"**Context ({context_type}):**\n{context}\n\n"
            
            if context_type == "details":
                response += f"**Full Content:**\n{markdown_content}"
            else:
                response += f"Please note: This is a {context_type} view. For complete details, use context_type='details'."
            
            return [
                types.TextContent(
                    type="text",
                    text=response,
                )
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