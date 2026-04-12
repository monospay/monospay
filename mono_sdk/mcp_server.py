"""
mono MCP Server — Financial infrastructure for AI agents via Model Context Protocol.

This module ships as part of the mono-m2m-sdk package and can be run as:
    mono-mcp                                      # stdio (Claude Desktop, Cursor)
    mono-mcp --http --port 8080                   # Streamable HTTP (remote agents)

Or directly:
    python -m mono_sdk.mcp_server

Environment:
    MONO_API_KEY    Required. Your agent API key from monospay.com/dashboard
    MONO_API_BASE   Optional. Override gateway URL (default: https://api.monospay.com/v1)

Compatible with: Claude Desktop, Cursor, Windsurf, OpenAI Agents SDK, AutoGen,
Google ADK, CrewAI, LangChain, Smolagents, Vercel AI SDK, and any MCP client.
"""

from __future__ import annotations

import json
import os
import sys
import uuid as uuid_lib
import urllib.error
import urllib.request
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict

# ── Constants ─────────────────────────────────────────────────────────────────

MONO_API_BASE = os.environ.get("MONO_API_BASE", "https://api.monospay.com/v1")
MONO_API_KEY = os.environ.get("MONO_API_KEY", "")

# ── HTTP Client ───────────────────────────────────────────────────────────────

def _api_request(
    method: str,
    path: str,
    body: dict | None = None,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """HTTP call to the mono gateway. Returns parsed JSON or error dict."""
    if not MONO_API_KEY:
        return {
            "error": "MONO_API_KEY_NOT_SET",
            "detail": "Set MONO_API_KEY environment variable. Get your key at monospay.com/dashboard → Agents → Issue API key.",
        }

    url = f"{MONO_API_BASE}{path}"
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MONO_API_KEY}",
        "User-Agent": "mono-mcp-server/1.0",
    }
    if extra_headers:
        headers.update(extra_headers)

    payload = json.dumps(body).encode("utf-8") if body else None

    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "ERROR":
                return {"error": data.get("code", "API_ERROR"), "detail": data.get("message", "")}
            return data
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode("utf-8"))
        except Exception:
            err = {}
        return {
            "error": err.get("error", err.get("detail", f"HTTP {e.code}")),
            "status_code": e.code,
            "detail": err.get("detail", str(e)),
        }
    except urllib.error.URLError as e:
        return {"error": "CONNECTION_FAILED", "detail": f"Cannot reach {url}: {e.reason}"}
    except Exception as e:
        return {"error": "UNEXPECTED_ERROR", "detail": str(e)}


def _format_result(data: dict[str, Any]) -> str:
    """Format API response as JSON string. Surface errors clearly."""
    if "error" in data:
        return json.dumps({"error": data["error"], "detail": data.get("detail", "")}, indent=2)
    return json.dumps(data, indent=2)


# ── MCP Server ────────────────────────────────────────────────────────────────

mcp = FastMCP(
    "mono_mcp",
    instructions=(
        "mono is a payment infrastructure for AI agents. "
        "Use mono_balance to check funds, mono_transfer to send USDC, "
        "mono_transactions for history, and mono_set_limits for spending controls. "
        "All amounts are in USDC on Base L2. No gas fees."
    ),
)


# ── Pydantic Input Models ─────────────────────────────────────────────────────

class TransferInput(BaseModel):
    """Input for sending USDC to another agent."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    to: str = Field(
        ...,
        description='Recipient agent name or UUID (e.g., "Agent 01" or "749939a0-5526-...")',
        min_length=1,
        max_length=100,
    )
    amount: float = Field(
        ...,
        description="Amount in USDC to send (e.g., 1.50 for $1.50)",
        gt=0,
        le=10000,
    )
    memo: str = Field(
        default="",
        description="Optional reason for the transfer (max 256 chars)",
        max_length=256,
    )


class SettleInput(BaseModel):
    """Input for on-chain USDC settlement."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    to: str = Field(
        ...,
        description='Recipient agent name or UUID',
        min_length=1,
        max_length=100,
    )
    amount: float = Field(
        ...,
        description="Amount in USDC to settle on-chain",
        gt=0,
        le=10000,
    )


class TransactionsInput(BaseModel):
    """Input for fetching transaction history."""
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(
        default=10,
        description="Number of transactions to return (1-100)",
        ge=1,
        le=100,
    )
    offset: int = Field(
        default=0,
        description="Offset for pagination",
        ge=0,
    )


class SetLimitsInput(BaseModel):
    """Input for setting spending limits."""
    model_config = ConfigDict(extra="forbid")

    spending_limit: Optional[float] = Field(
        default=None,
        description="Max USDC per single transaction. Omit or null to keep unchanged.",
        ge=0,
    )
    daily_budget: Optional[float] = Field(
        default=None,
        description="Max USDC this agent can spend per day. Omit or null to keep unchanged.",
        ge=0,
    )


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="mono_health",
    annotations={
        "title": "Gateway Health Check",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def mono_health() -> str:
    """Check if the mono payment gateway is online and healthy.

    Returns gateway status, database connectivity, and API version.
    Does not require authentication.
    """
    try:
        url = f"{MONO_API_BASE}/health"
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "mono-mcp-server/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": "GATEWAY_UNREACHABLE", "detail": str(e)}, indent=2)


@mcp.tool(
    name="mono_balance",
    annotations={
        "title": "Check Agent Balance",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def mono_balance() -> str:
    """Check the current USDC balance of this agent.

    Returns the agent name, unique ID, and balance in both USDC and micro-USDC.
    Uses the API key from the MONO_API_KEY environment variable.

    Returns:
        JSON with: agent_id, name, balance_usdc, balance_micro
    """
    result = _api_request("GET", "/balance")
    if "error" in result:
        return _format_result(result)
    return json.dumps({
        "agent_id": result.get("agent_id"),
        "name": result.get("name"),
        "balance_usdc": result.get("balance_usdc"),
        "balance_micro": result.get("balance_micro"),
    }, indent=2)


@mcp.tool(
    name="mono_transfer",
    annotations={
        "title": "Transfer USDC to Agent",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def mono_transfer(params: TransferInput) -> str:
    """Send USDC to another agent by name or UUID.

    Off-chain ledger transfer — instant, zero gas fees.
    Each call generates a unique idempotency key to prevent duplicates.

    Args:
        params: TransferInput with to (recipient), amount (USDC), memo (optional)

    Returns:
        JSON with: status, transaction_id, sender_balance, receiver, amount_usdc
    """
    result = _api_request(
        "POST", "/transfer",
        body={
            "receiver_id": params.to,
            "amount_micro": round(params.amount * 1_000_000),
            "memo": params.memo,
        },
        extra_headers={"Idempotency-Key": str(uuid_lib.uuid4())},
    )
    if "error" in result:
        return _format_result(result)
    return json.dumps({
        "status": result.get("status", "transferred"),
        "transaction_id": result.get("transaction_id", ""),
        "sender_balance": result.get("sender_balance"),
        "receiver": result.get("receiver_name"),
        "amount_usdc": params.amount,
        "memo": params.memo or None,
    }, indent=2)


@mcp.tool(
    name="mono_settle",
    annotations={
        "title": "Settle USDC On-Chain",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def mono_settle(params: SettleInput) -> str:
    """Execute an on-chain USDC settlement on Base L2.

    Unlike transfer(), this creates an actual blockchain transaction.
    Use transfer() for faster off-chain payments; settle() for finality.

    Args:
        params: SettleInput with to (recipient) and amount (USDC)

    Returns:
        JSON with: status, transaction_id, sender_balance, receiver, amount_usdc
    """
    result = _api_request(
        "POST", "/settle",
        body={
            "receiver_id": params.to,
            "amount_micro": round(params.amount * 1_000_000),
        },
        extra_headers={"Idempotency-Key": str(uuid_lib.uuid4())},
    )
    if "error" in result:
        return _format_result(result)
    return json.dumps({
        "status": result.get("status", "settled"),
        "transaction_id": result.get("transaction_id", ""),
        "sender_balance": result.get("sender_balance"),
        "receiver": result.get("receiver_name"),
        "amount_usdc": params.amount,
    }, indent=2)


@mcp.tool(
    name="mono_transactions",
    annotations={
        "title": "Transaction History",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def mono_transactions(params: TransactionsInput) -> str:
    """Fetch the transaction history for this agent.

    Returns recent transfers, settlements, fees, and top-ups
    with pagination support.

    Args:
        params: TransactionsInput with limit (1-100) and offset

    Returns:
        JSON array of transactions with: id, type, amount, created_at, status
    """
    result = _api_request("GET", f"/transactions?limit={params.limit}&offset={params.offset}")
    if "error" in result:
        return _format_result(result)
    return json.dumps(result.get("transactions", []), indent=2)


@mcp.tool(
    name="mono_set_limits",
    annotations={
        "title": "Set Spending Limits",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def mono_set_limits(params: SetLimitsInput) -> str:
    """Set per-transaction spending limit and/or daily budget.

    Limits are enforced server-side — the agent cannot bypass them.
    Use this to cap how much an autonomous agent can spend.

    Args:
        params: SetLimitsInput with spending_limit and/or daily_budget

    Returns:
        JSON confirmation with updated limit values
    """
    body: dict[str, Any] = {}
    if params.spending_limit is not None:
        body["spending_limit"] = params.spending_limit
    if params.daily_budget is not None:
        body["daily_budget"] = params.daily_budget
    if not body:
        return json.dumps({"error": "NO_LIMITS_PROVIDED", "detail": "Provide spending_limit and/or daily_budget."}, indent=2)

    result = _api_request("POST", "/limits", body=body)
    return _format_result(result)


# ── Resource ──────────────────────────────────────────────────────────────────

@mcp.resource("mono://docs/quickstart")
async def quickstart_docs() -> str:
    """Quickstart guide for the mono payment SDK."""
    return (
        "# mono Quickstart\n\n"
        "## Install\n"
        "curl -fsSL https://monospay.com/install.sh | bash\n\n"
        "## Python\n"
        "```python\n"
        "from mono_sdk import MonoClient\n"
        "client = MonoClient(api_key='mono_live_...')\n"
        "client.transfer(to='Agent 01', amount=1.00)\n"
        "```\n\n"
        "## MCP Tools: mono_balance, mono_transfer, mono_settle, mono_transactions, mono_set_limits, mono_health\n\n"
        "Dashboard: https://monospay.com/dashboard\n"
        "GitHub: https://github.com/Agash0818/mono-sdk\n"
    )


# ── Entry Point ───────────────────────────────────────────────────────────────

def main():
    """CLI entry point for mono-mcp command."""
    if not MONO_API_KEY:
        print("⚠  MONO_API_KEY not set.", file=sys.stderr)
        print("   export MONO_API_KEY=mono_live_...", file=sys.stderr)
        print("   Get your key: monospay.com/dashboard → Agents → Issue API key", file=sys.stderr)
        print(file=sys.stderr)

    if "--http" in sys.argv:
        port = 8080
        for i, arg in enumerate(sys.argv):
            if arg == "--port" and i + 1 < len(sys.argv):
                port = int(sys.argv[i + 1])
        print(f"mono MCP server · http://0.0.0.0:{port}", file=sys.stderr)
        mcp.run(transport="streamable_http", port=port)
    else:
        mcp.run()  # stdio


if __name__ == "__main__":
    main()
