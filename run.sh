#!/bin/zsh

# Set environment variables for Jira
export JIRA_URL="https://vibecoding.atlassian.net"
export JIRA_USERNAME="akhilthomas236@gmail.com"
export JIRA_API_TOKEN="${JIRA_TOKEN:-your-jira-token}"  # Set JIRA_TOKEN in your environment

# Set environment variables for Confluence
export CONFLUENCE_URL="https://vibecoding.atlassian.net/wiki"
export CONFLUENCE_USERNAME="akhilthomas236@gmail.com"
export CONFLUENCE_API_TOKEN="${CONFLUENCE_TOKEN:-your-confluence-token}"  # Set CONFLUENCE_TOKEN in your environment

# Make sure we're in the correct virtual environment (if using one)
# Uncomment and modify if using a specific virtual environment:
# source .venv/bin/activate

# Install the package in development mode if needed
uv pip install -e . 2>/dev/null || pip install -e .

# Run the MCP server
python -m mcp_jira_confluence.server
