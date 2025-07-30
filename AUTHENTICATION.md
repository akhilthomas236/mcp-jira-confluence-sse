# SSE Server Authentication Implementation

This document describes how personal access tokens can be passed from MCP clients to the SSE server for authentication with Jira and Confluence.

## Overview

The SSE server now supports multiple authentication methods:

1. **Server-side environment variables** (traditional approach)
2. **Client-side HTTP headers** (new approach)
3. **Hybrid approach** (mix of both)

## Authentication Flow

### Client-side Authentication (Recommended)

```
MCP Client → HTTP Headers → SSE Server → Temporary Clients → Jira/Confluence APIs
```

**Benefits:**
- Multiple clients can use different credentials
- Centralized server with distributed authentication
- No need to restart server for credential changes
- Better security (tokens not stored on server)

### Server-side Authentication (Fallback)

```
Environment Variables → SSE Server → Global Clients → Jira/Confluence APIs
```

**Benefits:**
- Simple configuration
- Works without client modification
- Good for single-user scenarios

## HTTP Headers Supported

### 1. Authorization Bearer Token
```
Authorization: Bearer <personal-access-token>
```
- Uses the same token for both Jira and Confluence
- Standard HTTP authentication header
- Preferred for single-token scenarios

### 2. Service-specific Headers
```
X-Jira-Token: <jira-personal-access-token>
X-Confluence-Token: <confluence-personal-access-token>
```
- Allows different tokens for each service
- Useful when services have different access requirements
- More granular control

## Implementation Details

### SSE Server Changes

1. **Modified `/sse` endpoint** to extract authentication headers
2. **Modified `/mcp` endpoint** to extract authentication headers  
3. **Updated `process_mcp_request()`** to accept optional tokens
4. **Temporary client creation** using provided tokens
5. **Client substitution** during tool/resource operations

### Client Implementation

The SSE client (`sse_client.py`) demonstrates:
- Reading tokens from environment variables
- Setting appropriate HTTP headers
- Making authenticated requests

### Backward Compatibility

- Existing environment variable configuration still works
- No breaking changes to existing deployments
- Client headers override server environment variables

## Usage Examples

### 1. Claude Desktop Configuration

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

### 2. Direct HTTP Client

```python
import httpx

headers = {"Authorization": "Bearer your-personal-access-token"}

async with httpx.AsyncClient(headers=headers) as client:
    response = await client.post("http://localhost:8000/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    })
```

### 3. Service-specific Tokens

```python
headers = {
    "X-Jira-Token": "jira-token-here",
    "X-Confluence-Token": "confluence-token-here"
}
```

## Security Considerations

1. **HTTPS in Production**: Always use HTTPS to protect tokens in transit
2. **Token Rotation**: Support for token rotation without server restart
3. **Minimal Privileges**: Use tokens with minimal required permissions
4. **Token Storage**: Clients should securely store tokens (keychain, etc.)

## Testing

Use the provided test script to verify authentication:

```bash
# Start SSE server
./start_sse.sh

# In another terminal, test authentication
python test_auth.py
```

## Migration Path

For existing deployments:

1. **Keep current setup** working with environment variables
2. **Add client authentication** gradually
3. **Test thoroughly** with both methods
4. **Eventually migrate** to client-side authentication for better security

## Files Modified

- `src/mcp_jira_confluence/sse_server.py` - Main authentication logic
- `src/mcp_jira_confluence/sse_client.py` - Example client implementation
- `README-SSE.md` - Documentation updates
- `start_sse.sh` - Updated environment variable checking
- `config-sse-auth.json` - Example configuration
- `test_auth.py` - Authentication testing script

## Benefits of This Approach

1. **Scalability**: One server, multiple authenticated clients
2. **Security**: Tokens not stored on server
3. **Flexibility**: Different tokens per client/user
4. **Simplicity**: Standard HTTP authentication patterns
5. **Compatibility**: Works with existing MCP client implementations
