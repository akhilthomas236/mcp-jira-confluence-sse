import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, Response
from sse_starlette.sse import EventSourceResponse
import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions

from .jira import jira_client
from .confluence import confluence_client
from .server import server  # Import the existing MCP server instance

logger = logging.getLogger("mcp-jira-confluence-sse")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    logger.info("Starting SSE server...")
    
    try:
        await jira_client.get_session()
        logger.info("Jira client initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize Jira client: {e}")
        
    try:
        await confluence_client.get_session()
        logger.info("Confluence client initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize Confluence client: {e}")
    
    logger.info("SSE server startup complete")
    yield
    
    # Shutdown
    logger.info("Shutting down SSE server...")
    try:
        await jira_client.close()
        await confluence_client.close()
        logger.info("SSE server shut down successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# Create FastAPI app
app = FastAPI(
    title="MCP Jira Confluence SSE Server",
    description="Server-Sent Events transport for MCP Jira/Confluence integration",
    version="0.3.0",
    lifespan=lifespan
)

class SSETransport:
    """SSE transport implementation for MCP server."""
    
    def __init__(self):
        self.message_queue = asyncio.Queue()
        self.connected_clients = set()
    
    async def send_message(self, message: Dict[str, Any]):
        """Send a message to all connected clients."""
        message_str = json.dumps(message)
        for client_queue in self.connected_clients:
            try:
                await client_queue.put(message_str)
            except Exception as e:
                logger.error(f"Failed to send message to client: {e}")
    
    async def add_client(self) -> asyncio.Queue:
        """Add a new client and return its message queue."""
        client_queue = asyncio.Queue()
        self.connected_clients.add(client_queue)
        return client_queue
    
    def remove_client(self, client_queue: asyncio.Queue):
        """Remove a client."""
        self.connected_clients.discard(client_queue)

sse_transport = SSETransport()

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Test connections
        jira_status = "ok"
        try:
            await jira_client.get_session()
        except Exception as e:
            jira_status = f"error: {str(e)}"
            
        confluence_status = "ok"
        try:
            await confluence_client.get_session()
        except Exception as e:
            confluence_status = f"error: {str(e)}"
            
        return {
            "status": "ok",
            "timestamp": time.time(),
            "services": {
                "jira": jira_status,
                "confluence": confluence_status
            },
            "connected_clients": len(sse_transport.connected_clients)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """Root endpoint with server information."""
    return {
        "name": "MCP Jira Confluence SSE Server",
        "version": "0.3.0",
        "transport": "sse",
        "endpoints": {
            "health": "/health",
            "sse": "/sse",
            "metrics": "/metrics"
        }
    }

@app.post("/sse")
async def sse_endpoint(request: Request) -> StreamingResponse:
    """SSE endpoint for MCP communication."""
    
    # Extract authentication from headers
    auth_header = request.headers.get("authorization")
    jira_token = request.headers.get("x-jira-token")
    confluence_token = request.headers.get("x-confluence-token")
    
    # Override client configurations with tokens from request
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Remove "Bearer " prefix
        # Use the same token for both services if no specific tokens provided
        if not jira_token:
            jira_token = token
        if not confluence_token:
            confluence_token = token
    
    # Create temporary client configurations for this connection
    temp_jira_config = None
    temp_confluence_config = None
    
    if jira_token:
        from .config import JiraConfig
        temp_jira_config = JiraConfig(
            url=jira_client.config.url,
            personal_token=jira_token,
            ssl_verify=jira_client.config.ssl_verify
        )
    
    if confluence_token:
        from .config import ConfluenceConfig
        temp_confluence_config = ConfluenceConfig(
            url=confluence_client.config.url,
            personal_token=confluence_token,
            ssl_verify=confluence_client.config.ssl_verify
        )
    
    async def event_stream() -> AsyncGenerator[str, None]:
        client_queue = await sse_transport.add_client()
        logger.info(f"New SSE client connected. Total clients: {len(sse_transport.connected_clients)}")
        
        try:
            # Send initialization message
            init_message = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": server.get_capabilities().model_dump(),
                    "serverInfo": {
                        "name": "mcp-jira-confluence",
                        "version": "0.3.0"
                    }
                }
            }
            yield f"data: {json.dumps(init_message)}\n\n"
            
            # Process messages from the queue
            while True:
                try:
                    # Wait for messages with a timeout to allow for periodic heartbeats
                    message = await asyncio.wait_for(client_queue.get(), timeout=30.0)
                    yield f"data: {message}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat
                    heartbeat = {
                        "jsonrpc": "2.0",
                        "method": "notifications/heartbeat",
                        "params": {"timestamp": time.time()}
                    }
                    yield f"data: {json.dumps(heartbeat)}\n\n"
                except Exception as e:
                    logger.error(f"Error in event stream: {e}")
                    error_message = {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32603,
                            "message": "Internal error",
                            "data": str(e)
                        }
                    }
                    yield f"data: {json.dumps(error_message)}\n\n"
                    break
                    
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            error_message = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": "Stream error",
                    "data": str(e)
                }
            }
            yield f"data: {json.dumps(error_message)}\n\n"
        finally:
            sse_transport.remove_client(client_queue)
            logger.info(f"SSE client disconnected. Remaining clients: {len(sse_transport.connected_clients)}")
    
    return EventSourceResponse(event_stream())

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """HTTP endpoint for MCP requests."""
    try:
        request_data = await request.json()
        logger.debug(f"Received MCP request: {request_data}")
        
        # Extract authentication from headers
        auth_header = request.headers.get("authorization")
        jira_token = request.headers.get("x-jira-token")
        confluence_token = request.headers.get("x-confluence-token")
        
        # Override client configurations with tokens from request
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            # Use the same token for both services if no specific tokens provided
            if not jira_token:
                jira_token = token
            if not confluence_token:
                confluence_token = token
        
        # Process the MCP request with authentication context
        response = await process_mcp_request(request_data, jira_token, confluence_token)
        
        return response
    except Exception as e:
        logger.error(f"Error processing MCP request: {e}")
        return {
            "jsonrpc": "2.0",
            "id": request_data.get("id") if 'request_data' in locals() else None,
            "error": {
                "code": -32603,
                "message": "Internal error",
                "data": str(e)
            }
        }

async def process_mcp_request(request_data: Dict[str, Any], jira_token: str = None, confluence_token: str = None) -> Dict[str, Any]:
    """Process an MCP request and return the response."""
    try:
        method = request_data.get("method")
        params = request_data.get("params", {})
        request_id = request_data.get("id")
        
        # Create temporary clients if tokens are provided
        temp_jira_client = None
        temp_confluence_client = None
        
        if jira_token:
            from .jira import JiraClient
            from .config import JiraConfig
            temp_jira_config = JiraConfig(
                url=jira_client.config.url,
                personal_token=jira_token,
                ssl_verify=jira_client.config.ssl_verify
            )
            temp_jira_client = JiraClient(temp_jira_config)
        
        if confluence_token:
            from .confluence import ConfluenceClient
            from .config import ConfluenceConfig
            temp_confluence_config = ConfluenceConfig(
                url=confluence_client.config.url,
                personal_token=confluence_token,
                ssl_verify=confluence_client.config.ssl_verify
            )
            temp_confluence_client = ConfluenceClient(temp_confluence_config)
        
        # Use temporary clients or fall back to default
        active_jira_client = temp_jira_client or jira_client
        active_confluence_client = temp_confluence_client or confluence_client
        
        if method == "initialize":
            # Import NotificationOptions here to avoid import issues
            from mcp.server import NotificationOptions
            
            capabilities = server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            )
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": capabilities.model_dump(),
                    "serverInfo": {
                        "name": "mcp-jira-confluence",
                        "version": "0.3.0"
                    }
                }
            }
        
        elif method == "tools/list":
            # Call the original list_tools handler directly
            from . import server as server_module
            try:
                tool_list = await server_module.handle_list_tools()
                tools = []
                for tool in tool_list:
                    tools.append({
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema
                    })
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"tools": tools}
                }
            except Exception as e:
                logger.error(f"Error getting tools: {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": f"Failed to get tools: {str(e)}"
                    }
                }
        
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            # Call the original tool handler with custom clients
            from . import server as server_module
            try:
                # Temporarily replace the global clients if tokens were provided
                original_jira = server_module.jira_client
                original_confluence = server_module.confluence_client
                
                if temp_jira_client:
                    server_module.jira_client = temp_jira_client
                if temp_confluence_client:
                    server_module.confluence_client = temp_confluence_client
                
                try:
                    result = await server_module.handle_call_tool(tool_name, arguments)
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": result
                        }
                    }
                finally:
                    # Restore original clients
                    server_module.jira_client = original_jira
                    server_module.confluence_client = original_confluence
                    
            except Exception as e:
                logger.error(f"Error calling tool {tool_name}: {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": f"Tool execution failed: {str(e)}"
                    }
                }
        
        elif method == "resources/list":
            # Call the original list_resources handler with custom clients
            from . import server as server_module
            try:
                # Temporarily replace the global clients if tokens were provided
                original_jira = server_module.jira_client
                original_confluence = server_module.confluence_client
                
                if temp_jira_client:
                    server_module.jira_client = temp_jira_client
                if temp_confluence_client:
                    server_module.confluence_client = temp_confluence_client
                
                try:
                    resource_list = await server_module.handle_list_resources()
                    resources = []
                    for resource in resource_list:
                        resources.append({
                            "uri": str(resource.uri),
                            "name": resource.name,
                            "description": resource.description,
                            "mimeType": resource.mimeType
                        })
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {"resources": resources}
                    }
                finally:
                    # Restore original clients
                    server_module.jira_client = original_jira
                    server_module.confluence_client = original_confluence
                    
            except Exception as e:
                logger.error(f"Error getting resources: {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": f"Failed to get resources: {str(e)}"
                    }
                }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
            
    except Exception as e:
        logger.error(f"Error processing MCP request: {e}")
        return {
            "jsonrpc": "2.0",
            "id": request_data.get("id"),
            "error": {
                "code": -32603,
                "message": "Internal error",
                "data": str(e)
            }
        }

# Metrics endpoint (optional, for monitoring)
try:
    from prometheus_client import Counter, Histogram, generate_latest
    
    request_count = Counter('mcp_requests_total', 'Total MCP requests', ['method', 'status'])
    request_duration = Histogram('mcp_request_duration_seconds', 'Request duration')
    
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        
        request_count.labels(method=request.method, status=response.status_code).inc()
        request_duration.observe(duration)
        
        return response
    
    @app.get("/metrics")
    async def metrics():
        return Response(generate_latest(), media_type="text/plain")
        
except ImportError:
    logger.info("Prometheus client not available, metrics endpoint disabled")
    
    @app.get("/metrics")
    async def metrics():
        return {"error": "Metrics not available - prometheus_client not installed"}
