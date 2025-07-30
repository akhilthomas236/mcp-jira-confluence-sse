# MCP Server Migration Guide: STDIO to Server-Sent Events (SSE)

## Overview

This document provides a comprehensive guide for migrating the MCP Jira and Confluence server from STDIO transport to Server-Sent Events (SSE) transport. SSE provides several advantages over STDIO including better error handling, web-based integration capabilities, and support for real-time updates.

## Table of Contents

1. [Current Architecture](#current-architecture)
2. [Target Architecture](#target-architecture)
3. [Benefits of SSE Transport](#benefits-of-sse-transport)
4. [Migration Steps](#migration-steps)
5. [Code Changes Required](#code-changes-required)
6. [Configuration Changes](#configuration-changes)
7. [Testing Strategy](#testing-strategy)
8. [Deployment Considerations](#deployment-considerations)
9. [Rollback Plan](#rollback-plan)

## Current Architecture

### STDIO Transport Implementation

The current implementation uses STDIO transport with the following characteristics:

- **Transport**: `mcp.server.stdio.stdio_server()`
- **Communication**: Standard input/output streams
- **Entry Point**: `mcp-jira-confluence` script
- **Dependencies**: `mcp>=1.9.4`, `httpx>=0.24.0`, `pydantic>=2.0.0`

### Current Server Initialization

```python
async def run_server():
    # Initialize clients
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="mcp-jira-confluence",
                server_version="0.2.3",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )
```

## Target Architecture

### SSE Transport Implementation

The target implementation will use SSE transport with the following characteristics:

- **Transport**: HTTP-based Server-Sent Events
- **Communication**: HTTP requests and SSE responses
- **Entry Point**: Web server with SSE endpoints
- **Additional Dependencies**: `fastapi`, `uvicorn`, `sse-starlette`

### Target Server Architecture

```
┌─────────────────┐    HTTP/SSE    ┌─────────────────┐
│   MCP Client    │ ──────────────→ │   SSE Server    │
│   (Claude etc.) │ ←────────────── │   (FastAPI)     │
└─────────────────┘                └─────────────────┘
                                           │
                                           ▼
                                   ┌─────────────────┐
                                   │  MCP Core Logic │
                                   │  (Jira/Conf.)   │
                                   └─────────────────┘
```

## Benefits of SSE Transport

### 1. Web Integration
- Direct HTTP-based communication
- Better integration with web applications
- Support for CORS and web security policies

### 2. Real-time Capabilities
- Server-initiated updates
- Live notifications for Jira/Confluence changes
- Streaming responses for large datasets

### 3. Better Error Handling
- HTTP status codes for error reporting
- Structured error responses
- Connection health monitoring

### 4. Scalability
- Load balancing support
- Horizontal scaling capabilities
- Better resource management

### 5. Debugging and Monitoring
- HTTP access logs
- Request/response inspection
- Performance metrics collection

## Migration Steps

### Phase 1: Preparation

#### 1.1 Update Dependencies

Add SSE-related dependencies to `pyproject.toml`:

```toml
dependencies = [
    "mcp>=1.9.4",
    "httpx>=0.24.0",
    "pydantic>=2.0.0",
    "fastapi>=0.104.0",
    "uvicorn>=0.24.0",
    "sse-starlette>=1.8.0",
    "python-multipart>=0.0.6",
]
```

#### 1.2 Create SSE Server Module

Create `src/mcp_jira_confluence/sse_server.py`:

```python
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions

from .jira import jira_client
from .confluence import confluence_client
# Import all existing handlers

logger = logging.getLogger("mcp-jira-confluence-sse")

# Initialize MCP server (reuse existing server instance)
server = Server("mcp-jira-confluence")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
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
    
    yield
    
    # Shutdown
    await jira_client.close()
    await confluence_client.close()
    logger.info("SSE server shut down")

# Create FastAPI app
app = FastAPI(
    title="MCP Jira Confluence SSE Server",
    description="Server-Sent Events transport for MCP Jira/Confluence integration",
    version="0.3.0",
    lifespan=lifespan
)
```

### Phase 2: Core SSE Implementation

#### 2.1 SSE Endpoint Implementation

```python
@app.post("/sse")
async def sse_endpoint(request: Request) -> StreamingResponse:
    """SSE endpoint for MCP communication."""
    
    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            # Handle MCP initialization
            init_options = InitializationOptions(
                server_name="mcp-jira-confluence",
                server_version="0.3.0",
                capabilities=server.get_capabilities(),
            )
            
            # Process MCP messages
            async for message in server.run_sse():
                yield f"data: {message}\n\n"
                
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            yield f"data: {{'error': '{str(e)}'}}\n\n"
    
    return EventSourceResponse(event_stream())
```

#### 2.2 Health Check Endpoint

```python
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Test connections
        jira_status = "ok"
        try:
            await jira_client.get_session()
        except Exception:
            jira_status = "error"
            
        confluence_status = "ok"
        try:
            await confluence_client.get_session()
        except Exception:
            confluence_status = "error"
            
        return {
            "status": "ok",
            "services": {
                "jira": jira_status,
                "confluence": confluence_status
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Phase 3: Server Configuration

#### 3.1 Create SSE Server Runner

Create `src/mcp_jira_confluence/run_sse.py`:

```python
import argparse
import logging
import os
from typing import Optional

import uvicorn

from .sse_server import app

logger = logging.getLogger("mcp-jira-confluence-sse")

def main():
    """Entry point for SSE server."""
    parser = argparse.ArgumentParser(description="MCP Jira Confluence SSE Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--log-level", default="info", help="Log level")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    logger.info(f"Starting SSE server on {args.host}:{args.port}")
    
    uvicorn.run(
        "mcp_jira_confluence.sse_server:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=args.reload,
    )

if __name__ == "__main__":
    main()
```

#### 3.2 Update Project Configuration

Update `pyproject.toml` to include the new SSE entry point:

```toml
[project.scripts]
mcp-jira-confluence = "mcp_jira_confluence.server:main"
mcp-jira-confluence-sse = "mcp_jira_confluence.run_sse:main"
```

### Phase 4: MCP Core Adaptation

#### 4.1 Modify Server Class

Update the MCP server to support SSE transport:

```python
# In server.py, add SSE-specific methods

class SSEMCPServer(Server):
    """MCP Server with SSE transport support."""
    
    async def run_sse(self):
        """Run server with SSE transport."""
        # Implementation for SSE message handling
        pass
    
    async def handle_sse_request(self, request_data: dict):
        """Handle individual SSE requests."""
        # Process MCP requests and return responses
        pass
```

### Phase 5: Configuration and Environment

#### 5.1 Environment Variables

Add SSE-specific environment variables:

```bash
# .env file
JIRA_URL=https://your-jira-instance.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-jira-api-token

CONFLUENCE_URL=https://your-confluence-instance.atlassian.net
CONFLUENCE_EMAIL=your-email@example.com  
CONFLUENCE_API_TOKEN=your-confluence-api-token

# SSE Server Configuration
SSE_HOST=0.0.0.0
SSE_PORT=8000
SSE_LOG_LEVEL=info
```

#### 5.2 Docker Configuration

Create `Dockerfile` for containerized deployment:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync

COPY src/ ./src/

EXPOSE 8000

CMD ["mcp-jira-confluence-sse", "--host", "0.0.0.0", "--port", "8000"]
```

## Configuration Changes

### Client Configuration

#### STDIO Configuration (Current)
```json
{
  "mcpServers": {
    "jira-confluence": {
      "command": "mcp-jira-confluence",
      "env": {
        "JIRA_URL": "https://your-instance.atlassian.net",
        "JIRA_EMAIL": "your-email@example.com",
        "JIRA_API_TOKEN": "your-token"
      }
    }
  }
}
```

#### SSE Configuration (Target)
```json
{
  "mcpServers": {
    "jira-confluence-sse": {
      "transport": "sse",
      "url": "http://localhost:8000/sse",
      "timeout": 30000
    }
  }
}
```

## Testing Strategy

### 1. Unit Tests

Create comprehensive tests for SSE functionality:

```python
# tests/test_sse_server.py
import pytest
from fastapi.testclient import TestClient
from mcp_jira_confluence.sse_server import app

@pytest.fixture
def client():
    return TestClient(app)

def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()

def test_sse_endpoint(client):
    response = client.post("/sse")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream"
```

### 2. Integration Tests

Test SSE communication with MCP clients:

```python
# tests/test_sse_integration.py
import asyncio
import pytest
from mcp.client import create_client

@pytest.mark.asyncio
async def test_sse_client_communication():
    async with create_client("http://localhost:8000/sse") as client:
        # Test basic MCP operations
        tools = await client.list_tools()
        assert len(tools) > 0
```

### 3. Performance Tests

Benchmark SSE vs STDIO performance:

```python
# tests/test_performance.py
import time
import asyncio
from mcp.client import create_client

async def benchmark_sse_requests():
    start_time = time.time()
    async with create_client("http://localhost:8000/sse") as client:
        for _ in range(100):
            await client.list_tools()
    end_time = time.time()
    return end_time - start_time
```

## Deployment Considerations

### 1. Production Deployment

#### Docker Compose
```yaml
version: '3.8'
services:
  mcp-jira-confluence-sse:
    build: .
    ports:
      - "8000:8000"
    environment:
      - JIRA_URL=${JIRA_URL}
      - JIRA_EMAIL=${JIRA_EMAIL}
      - JIRA_API_TOKEN=${JIRA_API_TOKEN}
      - CONFLUENCE_URL=${CONFLUENCE_URL}
      - CONFLUENCE_EMAIL=${CONFLUENCE_EMAIL}
      - CONFLUENCE_API_TOKEN=${CONFLUENCE_API_TOKEN}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

#### Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-jira-confluence-sse
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mcp-jira-confluence-sse
  template:
    metadata:
      labels:
        app: mcp-jira-confluence-sse
    spec:
      containers:
      - name: mcp-server
        image: mcp-jira-confluence-sse:latest
        ports:
        - containerPort: 8000
        env:
        - name: JIRA_URL
          valueFrom:
            secretKeyRef:
              name: jira-config
              key: url
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
```

### 2. Load Balancing

Configure load balancing for high availability:

```nginx
upstream mcp_sse_backend {
    server mcp-sse-1:8000;
    server mcp-sse-2:8000;
    server mcp-sse-3:8000;
}

server {
    listen 80;
    location /sse {
        proxy_pass http://mcp_sse_backend;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
        proxy_buffering off;
        proxy_cache off;
    }
}
```

### 3. Monitoring and Observability

#### Metrics Collection
```python
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
```

## Rollback Plan

### 1. Immediate Rollback

If issues arise during migration:

1. **Stop SSE server**:
   ```bash
   docker-compose down
   # or
   kubectl delete deployment mcp-jira-confluence-sse
   ```

2. **Revert client configuration** to STDIO:
   ```json
   {
     "mcpServers": {
       "jira-confluence": {
         "command": "mcp-jira-confluence",
         "env": {...}
       }
     }
   }
   ```

3. **Restart STDIO server**:
   ```bash
   mcp-jira-confluence
   ```

### 2. Version Rollback

Maintain both versions during transition:

```toml
# pyproject.toml
[project.scripts]
mcp-jira-confluence = "mcp_jira_confluence.server:main"           # STDIO (v0.2.x)
mcp-jira-confluence-sse = "mcp_jira_confluence.run_sse:main"      # SSE (v0.3.x)
```

### 3. Data Migration Rollback

If data format changes are required:

```python
# Migration script
async def rollback_data_format():
    """Rollback any data format changes if needed."""
    # Implementation depends on specific changes made
    pass
```

## Timeline and Milestones

### Week 1: Preparation
- [ ] Update dependencies
- [ ] Create SSE server skeleton
- [ ] Set up development environment

### Week 2: Core Implementation
- [ ] Implement SSE endpoints
- [ ] Adapt MCP server for SSE
- [ ] Create configuration files

### Week 3: Testing
- [ ] Unit tests for SSE functionality
- [ ] Integration tests with MCP clients
- [ ] Performance benchmarking

### Week 4: Deployment Preparation
- [ ] Docker configuration
- [ ] Kubernetes manifests
- [ ] Monitoring setup

### Week 5: Migration Execution
- [ ] Deploy SSE server to staging
- [ ] Migrate test clients
- [ ] Production deployment
- [ ] Monitor and optimize

## Success Criteria

1. **Functional Parity**: All existing STDIO functionality works with SSE
2. **Performance**: SSE performance is within 10% of STDIO performance
3. **Reliability**: 99.9% uptime during migration period
4. **Compatibility**: Existing clients can migrate with configuration changes only
5. **Monitoring**: Full observability of SSE server operations

## Risk Mitigation

### High-Risk Items

1. **Client Compatibility**: Some MCP clients may not support SSE
   - *Mitigation*: Maintain STDIO version in parallel

2. **Performance Degradation**: SSE overhead may impact performance
   - *Mitigation*: Thorough benchmarking and optimization

3. **Network Dependencies**: SSE requires stable HTTP connections
   - *Mitigation*: Implement robust reconnection logic

### Medium-Risk Items

1. **Configuration Complexity**: SSE requires more complex setup
   - *Mitigation*: Comprehensive documentation and examples

2. **Debugging Difficulty**: HTTP-based debugging vs simple stdio
   - *Mitigation*: Enhanced logging and monitoring tools

## Conclusion

Migrating from STDIO to SSE transport will provide significant benefits in terms of scalability, monitoring, and integration capabilities. The migration should be executed in phases with careful testing and monitoring at each step. The parallel maintenance of both transport methods during the transition period will ensure a smooth migration experience for all users.

This migration represents a significant architectural improvement that will enable future enhancements and better production deployments of the MCP Jira and Confluence server.
