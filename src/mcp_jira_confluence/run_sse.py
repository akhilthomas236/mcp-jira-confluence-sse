import argparse
import logging
import os
import sys
from typing import Optional

import uvicorn

logger = logging.getLogger("mcp-jira-confluence-sse")

def main():
    """Entry point for SSE server."""
    parser = argparse.ArgumentParser(description="MCP Jira Confluence SSE Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    parser.add_argument("--log-level", default="info", 
                       choices=["debug", "info", "warning", "error"],
                       help="Log level (default: info)")
    parser.add_argument("--reload", action="store_true", 
                       help="Enable auto-reload for development")
    parser.add_argument("--workers", type=int, default=1,
                       help="Number of worker processes (default: 1)")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = getattr(logging, args.log_level.upper())
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Validate environment variables
    required_env_vars = [
        "JIRA_URL", "JIRA_EMAIL", "JIRA_API_TOKEN",
        "CONFLUENCE_URL", "CONFLUENCE_EMAIL", "CONFLUENCE_API_TOKEN"
    ]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set all required environment variables before starting the server.")
        return 1
    
    logger.info(f"Starting SSE server on {args.host}:{args.port}")
    logger.info(f"Log level: {args.log_level}")
    logger.info(f"Reload mode: {args.reload}")
    logger.info(f"Workers: {args.workers}")
    
    try:
        uvicorn.run(
            "mcp_jira_confluence.sse_server:app",
            host=args.host,
            port=args.port,
            log_level=args.log_level,
            reload=args.reload,
            workers=args.workers if not args.reload else 1,  # Reload doesn't work with multiple workers
            access_log=True,
            loop="asyncio"
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        return 0
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
