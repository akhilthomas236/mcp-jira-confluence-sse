#!/bin/bash

# Simple test to check if the script is working
echo "Testing SSE server start script..."

# Check if we can find uvicorn
if command -v uvicorn &> /dev/null; then
    echo "✓ uvicorn is available"
else
    echo "✗ uvicorn not found - installing..."
    pip install uvicorn
fi

# Check if the SSE server file exists
if [[ -f "src/mcp_jira_confluence/sse_server.py" ]]; then
    echo "✓ SSE server file found"
else
    echo "✗ SSE server file not found"
    exit 1
fi

echo "All checks passed! You can start the server with:"
echo "./start_sse.sh --help"
echo "or"
echo "python start_sse.py --help"
