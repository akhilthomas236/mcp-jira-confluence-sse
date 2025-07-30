# MCP Jira Confluence SSE Server

A Server-Sent Events (SSE) transport implementation for the MCP Jira and Confluence server, enabling real-time communication with AI assistants through HTTP-based transport.

## Features

- **HTTP/SSE Transport**: Web-based communication using Server-Sent Events
- **Real-time Updates**: Server-initiated notifications and streaming responses
- **Better Error Handling**: HTTP status codes and structured error responses
- **Scalability**: Load balancing and horizontal scaling support
- **Monitoring**: Health checks and optional Prometheus metrics
- **Docker Support**: Containerized deployment ready

## Quick Start

### Using Docker (Recommended)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/akhilthomas236/jira-confluence-mcp.git
   cd jira-confluence-mcp
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your Jira/Confluence credentials
   ```

3. **Start the server**:
   ```bash
   docker-compose up -d
   ```

4. **Verify the server is running**:
   ```bash
   curl http://localhost:8000/health
   ```

### Manual Installation

1. **Install dependencies**:
   ```bash
   uv sync
   ```

2. **Set environment variables**:
   ```bash
   export JIRA_URL="https://your-instance.atlassian.net"
   export JIRA_EMAIL="your-email@example.com"
   export JIRA_API_TOKEN="your-api-token"
   export CONFLUENCE_URL="https://your-instance.atlassian.net/wiki"
   export CONFLUENCE_EMAIL="your-email@example.com"
   export CONFLUENCE_API_TOKEN="your-api-token"
   ```

3. **Start the SSE server**:
   ```bash
   mcp-jira-confluence-sse
   ```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `JIRA_URL` | Your Jira instance URL | Yes |
| `JIRA_EMAIL` | Your Jira email | Yes |
| `JIRA_API_TOKEN` | Your Jira API token | Yes |
| `CONFLUENCE_URL` | Your Confluence instance URL | Yes |
| `CONFLUENCE_EMAIL` | Your Confluence email | Yes |
| `CONFLUENCE_API_TOKEN` | Your Confluence API token | Yes |
| `SSE_HOST` | Host to bind to (default: 0.0.0.0) | No |
| `SSE_PORT` | Port to bind to (default: 8000) | No |
| `SSE_LOG_LEVEL` | Log level (default: info) | No |

### Client Configuration

#### Claude for Desktop

Add this to your Claude configuration file (`~/Library/Application Support/Claude/claude_desktop_config.json`):

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

#### Generic MCP Client

```json
{
  "transport": "sse",
  "url": "http://localhost:8000/sse",
  "timeout": 30000,
  "headers": {
    "User-Agent": "MCP-Client/1.0"
  }
}
```

## API Endpoints

### Health Check
```bash
GET /health
```
Returns server health status and service connectivity.

### SSE Transport
```bash
POST /sse
```
Server-Sent Events endpoint for MCP communication.

### MCP HTTP
```bash
POST /mcp
```
HTTP endpoint for direct MCP requests.

### Metrics (Optional)
```bash
GET /metrics
```
Prometheus metrics endpoint (if `prometheus-client` is installed).

## Authentication

The SSE server supports multiple authentication methods for connecting to Jira and Confluence:

### Method 1: Environment Variables (Server-side)
Set environment variables on the server:
```bash
export JIRA_PERSONAL_TOKEN="your-jira-token"
export CONFLUENCE_PERSONAL_TOKEN="your-confluence-token"
```

### Method 2: HTTP Headers (Client-side) - **Recommended**
Pass tokens from the MCP client via HTTP headers:

#### Using Authorization Header (same token for both services)
```bash
Authorization: Bearer your-personal-access-token
```

#### Using Service-specific Headers
```bash
X-Jira-Token: your-jira-token
X-Confluence-Token: your-confluence-token
```

### Method 3: Hybrid Approach
- Set base URLs in server environment variables
- Pass tokens from client via headers
- Tokens in headers override server environment variables

This allows multiple clients to use different credentials with the same server instance.

## Client Implementation

### HTTP Client Example
```python
import httpx

# Create client with authentication headers
headers = {
    "Authorization": "Bearer your-personal-access-token",
    # OR use service-specific headers:
    # "X-Jira-Token": "your-jira-token",
    # "X-Confluence-Token": "your-confluence-token"
}

async with httpx.AsyncClient(headers=headers) as client:
    # Initialize MCP session
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "my-client", "version": "1.0.0"}
        }
    }
    
    response = await client.post("http://localhost:8000/mcp", json=init_request)
    result = response.json()
```

### MCP Client Configuration
For Claude Desktop (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "mcp-jira-confluence-sse": {
      "command": "python",
      "args": ["-m", "mcp_jira_confluence.sse_client"],
      "env": {
        "SSE_SERVER_URL": "http://localhost:8000",
        "JIRA_PERSONAL_TOKEN": "your-jira-token",
        "CONFLUENCE_PERSONAL_TOKEN": "your-confluence-token"
      }
    }
  }
}
```

### Using the Example SSE Client
```bash
# Set authentication tokens
export JIRA_PERSONAL_TOKEN="your-jira-token"
export CONFLUENCE_PERSONAL_TOKEN="your-confluence-token"
export SSE_SERVER_URL="http://localhost:8000"

# Run the example client
python -m mcp_jira_confluence.sse_client
```

## Development

### Running in Development Mode

```bash
mcp-jira-confluence-sse --reload --log-level debug
```

### Running Tests

```bash
# Install test dependencies
uv sync --extra test

# Run tests
pytest tests/
```

### Building Docker Image

```bash
docker build -t mcp-jira-confluence-sse:latest .
```

## Deployment

### Docker Compose (Production)

```yaml
version: '3.8'
services:
  mcp-jira-confluence-sse:
    image: mcp-jira-confluence-sse:latest
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
    restart: unless-stopped
```

### Kubernetes Deployment

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

## Monitoring

### Health Checks

The server provides a health endpoint that checks:
- Server status
- Jira connectivity
- Confluence connectivity
- Connected SSE clients count

### Metrics

Install the metrics extra to enable Prometheus metrics:

```bash
uv sync --extra metrics
```

Metrics include:
- Request count by method and status
- Request duration histogram
- Active SSE connections

## Migration from STDIO

If you're migrating from the STDIO version:

1. **Keep both versions running** during transition
2. **Update client configuration** to use SSE transport
3. **Test thoroughly** before decommissioning STDIO version
4. **Monitor performance** and error rates

See `SSE_MIGRATION_GUIDE.md` for detailed migration instructions.

## Troubleshooting

### Common Issues

1. **Connection refused**: Check if the server is running and port is accessible
2. **Authentication errors**: Verify your Jira/Confluence credentials
3. **SSE connection drops**: Check network stability and firewall settings
4. **High memory usage**: Monitor for connection leaks and adjust worker count

### Logs

Check server logs for detailed error information:

```bash
# Docker logs
docker-compose logs -f mcp-jira-confluence-sse

# Direct logs
mcp-jira-confluence-sse --log-level debug
```

### Debug Mode

Enable debug logging for detailed request/response information:

```bash
mcp-jira-confluence-sse --log-level debug
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

## License

MIT License - see LICENSE file for details.
