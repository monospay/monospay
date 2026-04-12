"""
Redirect: The MCP server has moved to mono_sdk/mcp_server.py

Install and run:
    pip install "mono-m2m-sdk[mcp]"
    mono-mcp

Or directly:
    python -m mono_sdk.mcp_server
"""
from mono_sdk.mcp_server import main

if __name__ == "__main__":
    main()
