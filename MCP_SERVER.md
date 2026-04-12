# mono MCP Server

MCP (Model Context Protocol) server for the mono payment SDK.
Enables any MCP-compatible AI agent to make USDC payments.

## Quick Start

```bash
# Install
pip install "mcp[cli]" mono-m2m-sdk

# Run (stdio — for Claude Desktop, Cursor, etc.)
MONO_API_KEY=mono_live_... python mono_mcp_server.py

# Run (HTTP — for remote agents)
MONO_API_KEY=mono_live_... python mono_mcp_server.py --http --port 8080
```

## Claude Desktop Config

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mono": {
      "command": "python",
      "args": ["/path/to/mono_mcp_server.py"],
      "env": {
        "MONO_API_KEY": "mono_live_..."
      }
    }
  }
}
```

## Tools

| Tool | Description |
|---|---|
| `mono_balance` | Check USDC balance |
| `mono_transfer` | Send USDC (off-chain, fast) |
| `mono_settle` | On-chain USDC settlement |
| `mono_transactions` | Payment history |
| `mono_set_limits` | Spending controls |
| `mono_health` | Gateway status |

## Compatible Frameworks

Works with any MCP-compatible agent: Claude, OpenAI Agents SDK, AutoGen, Google ADK, CrewAI, LangChain, Smolagents, Vercel AI SDK, Cursor, Windsurf, and more.
