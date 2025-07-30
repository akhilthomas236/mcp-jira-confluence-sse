#!/usr/bin/env python3
"""
Start SSE Server Script for MCP Jira Confluence
Python version of the SSE server startup script
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from typing import List, Optional

# Colors for terminal output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def print_colored(message: str, color: str = Colors.NC) -> None:
    """Print a colored message to the terminal."""
    print(f"{color}{message}{Colors.NC}")

def print_info(message: str) -> None:
    """Print an info message."""
    print_colored(f"[INFO] {message}", Colors.BLUE)

def print_success(message: str) -> None:
    """Print a success message."""
    print_colored(f"[SUCCESS] {message}", Colors.GREEN)

def print_warning(message: str) -> None:
    """Print a warning message."""
    print_colored(f"[WARNING] {message}", Colors.YELLOW)

def print_error(message: str) -> None:
    """Print an error message."""
    print_colored(f"[ERROR] {message}", Colors.RED)

def load_env_file(env_path: Path = Path(".env")) -> None:
    """Load environment variables from a .env file."""
    if env_path.exists():
        print_info(f"Loading environment variables from {env_path}")
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    elif Path(".env.example").exists():
        print_warning(".env file not found, but .env.example exists")
        print_info("Consider copying .env.example to .env and filling in your credentials")

def check_env_vars() -> bool:
    """Check if required environment variables are set."""
    missing_vars = []
    
    # Check Jira configuration
    if not os.getenv("JIRA_URL"):
        missing_vars.append("JIRA_URL")
    
    if not os.getenv("JIRA_PERSONAL_TOKEN") and (not os.getenv("JIRA_USERNAME") or not os.getenv("JIRA_API_TOKEN")):
        missing_vars.append("JIRA_PERSONAL_TOKEN or (JIRA_USERNAME and JIRA_API_TOKEN)")
    
    # Check Confluence configuration
    if not os.getenv("CONFLUENCE_URL"):
        missing_vars.append("CONFLUENCE_URL")
    
    if not os.getenv("CONFLUENCE_PERSONAL_TOKEN") and (not os.getenv("CONFLUENCE_USERNAME") or not os.getenv("CONFLUENCE_API_TOKEN")):
        missing_vars.append("CONFLUENCE_PERSONAL_TOKEN or (CONFLUENCE_USERNAME and CONFLUENCE_API_TOKEN)")
    
    if missing_vars:
        print_error("Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print()
        print_info("Please set the environment variables or create a .env file")
        print_info("See .env.example for reference")
        return False
    
    return True

def check_package_installation() -> bool:
    """Check if the package is installed and install if needed."""
    try:
        import mcp_jira_confluence
        return True
    except ImportError:
        print_info("Installing package in development mode...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], 
                         check=True, capture_output=True, text=True)
            print_success("Package installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print_error(f"Failed to install package: {e}")
            return False

def start_server(host: str, port: int, log_level: str, reload: bool) -> None:
    """Start the SSE server using uvicorn."""
    uvicorn_args = [
        sys.executable, "-m", "uvicorn",
        "mcp_jira_confluence.sse_server:app",
        "--host", host,
        "--port", str(port),
        "--log-level", log_level
    ]
    
    if reload:
        uvicorn_args.append("--reload")
        print_info("Development mode enabled (auto-reload)")
    
    # Show configuration
    print()
    print_info("Server Configuration:")
    print(f"  Host: {host}")
    print(f"  Port: {port}")
    print(f"  Log Level: {log_level}")
    print(f"  Reload: {reload}")
    print(f"  Jira URL: {os.getenv('JIRA_URL')}")
    print(f"  Confluence URL: {os.getenv('CONFLUENCE_URL')}")
    print()
    
    print_info("Server will be available at:")
    print(f"  • Health Check: http://{host}:{port}/health")
    print(f"  • SSE Endpoint: http://{host}:{port}/sse")
    print(f"  • MCP Endpoint: http://{host}:{port}/mcp")
    print(f"  • Metrics: http://{host}:{port}/metrics")
    print()
    
    print_success("Starting server...")
    print()
    
    try:
        subprocess.run(uvicorn_args)
    except KeyboardInterrupt:
        print_info("Shutting down server...")
    except Exception as e:
        print_error(f"Failed to start server: {e}")
        sys.exit(1)

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Start the MCP Jira Confluence SSE Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  JIRA_URL                    Your Jira instance URL
  JIRA_USERNAME               Your Jira username/email  
  JIRA_API_TOKEN              Your Jira API token
  JIRA_PERSONAL_TOKEN         Alternative to username/token
  CONFLUENCE_URL              Your Confluence instance URL
  CONFLUENCE_USERNAME         Your Confluence username/email
  CONFLUENCE_API_TOKEN        Your Confluence API token
  CONFLUENCE_PERSONAL_TOKEN   Alternative to username/token

Examples:
  python start_sse.py                          # Start with default settings
  python start_sse.py --port 3000              # Start on port 3000
  python start_sse.py --dev                    # Start in development mode
  python start_sse.py --host 0.0.0.0 --port 8080  # Bind to all interfaces
        """
    )
    
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=int(os.getenv("PORT", 8000)),
        help="Port to run server on (default: 8000)"
    )
    
    parser.add_argument(
        "-H", "--host",
        default=os.getenv("HOST", "127.0.0.1"),
        help="Host to bind to (default: 127.0.0.1)"
    )
    
    parser.add_argument(
        "-l", "--log-level",
        choices=["debug", "info", "warning", "error"],
        default=os.getenv("LOG_LEVEL", "info"),
        help="Log level (default: info)"
    )
    
    parser.add_argument(
        "-r", "--reload",
        action="store_true",
        default=os.getenv("RELOAD", "false").lower() == "true",
        help="Enable auto-reload for development"
    )
    
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Development mode (enables reload and debug logging)"
    )
    
    args = parser.parse_args()
    
    # Handle development mode
    if args.dev:
        args.reload = True
        args.log_level = "debug"
    
    print_info("Starting MCP Jira Confluence SSE Server...")
    print()
    
    # Check if we're in the right directory
    if not Path("src/mcp_jira_confluence/sse_server.py").exists():
        print_error("SSE server file not found. Please run this script from the project root directory.")
        sys.exit(1)
    
    # Load environment variables
    load_env_file()
    
    # Check environment variables
    if not check_env_vars():
        sys.exit(1)
    
    print_success("Environment variables configured")
    
    # Check package installation
    if not check_package_installation():
        sys.exit(1)
    
    # Start the server
    start_server(args.host, args.port, args.log_level, args.reload)

if __name__ == "__main__":
    main()
