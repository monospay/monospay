"""
mono CLI — The control plane for the mono M2M settlement network.

Usage:
    mono init                              Zero-config setup wizard
    mono balance                           Show main balance + all agent balances
    mono transfer --to <id> --amount <n>   Move USDC to another agent instantly
    mono settle   --to <id> --amount <n>   On-chain settlement between agents
    mono status                            Fleet overview
    mono nodes list|create|kill            Manage agent nodes
    mono health                            System health check
    mono config show|set|clear             Local config management
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from mono_sdk.client import MonoClient
from mono_sdk.errors import (
    AuthenticationError,
    InsufficientBalanceError,
    MonoError,
    NetworkError,
    NodeLockedError,
    RateLimitError,
    RecipientNotFoundError,
    SpendingLimitExceededError,
    SystemHaltedError,
)

# ── ANSI helpers ──────────────────────────────────────────────────────────────

R = "\033[0m"
BOLD = "\033[1m"
DIM  = "\033[2m"
RED  = "\033[31m"
GRN  = "\033[32m"
YLW  = "\033[33m"
BLU  = "\033[34m"
CYN  = "\033[36m"

def ok(msg: str)   -> None: print(f"  {GRN}✓{R}  {msg}")
def err(msg: str)  -> None: print(f"  {RED}✗{R}  {msg}", file=sys.stderr)
def warn(msg: str) -> None: print(f"  {YLW}!{R}  {msg}")
def dim(msg: str)  -> None: print(f"  {DIM}{msg}{R}")

def rule(width: int = 56) -> None:
    print(f"  {DIM}{'─' * width}{R}")


# ── Table printer ─────────────────────────────────────────────────────────────

def table(rows: list[tuple], headers: tuple | None = None) -> None:
    """Render a left-aligned terminal table with optional headers."""
    if not rows:
        return
    all_rows = [headers] + list(rows) if headers else list(rows)
    widths   = [max(len(str(cell)) for cell in col) for col in zip(*all_rows)]

    def fmt_row(r: tuple, bold: bool = False) -> str:
        cells = "  ".join(str(c).ljust(w) for c, w in zip(r, widths))
        return f"  {BOLD}{cells}{R}" if bold else f"  {cells}"

    print()
    if headers:
        print(fmt_row(headers, bold=True))
        rule(sum(widths) + 2 * (len(widths) - 1))
    for row in rows:
        print(fmt_row(row))
    print()


# ── Config ────────────────────────────────────────────────────────────────────

MONO_DIR    = Path.home() / ".mono"
CONFIG_FILE = MONO_DIR / "config.json"
DEFAULT_API = "https://mono-production-b257.up.railway.app/v1"

DEFAULTS: dict = {
    "base_rpc_url":   "https://mainnet.base.org",
    "paymaster_url":  "https://api.monospay.com/paymaster",
    "gateway_url":    DEFAULT_API,
    "chain":          "base",
    "chain_id":       8453,
    "usdc_address":   "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "eurc_address":   "0x60a3E35Cc302bFA44Cb288Bc5a4F316Fdb1adb42",
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_config(cfg: dict) -> None:
    MONO_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    CONFIG_FILE.chmod(0o600)


def get_setting(key: str) -> str | None:
    if val := os.environ.get(f"MONO_{key.upper()}"):
        return val
    if val := load_config().get(key):
        return str(val)
    return str(DEFAULTS[key]) if key in DEFAULTS else None


def get_api_key() -> str | None:
    return os.environ.get("MONO_API_KEY") or load_config().get("api_key")


def get_client() -> MonoClient:
    key = get_api_key()
    if not key:
        err("No API key found.")
        dim("Run:  mono init")
        print()
        sys.exit(1)
    return MonoClient(api_key=key, base_url=get_setting("gateway_url") or DEFAULT_API)


# ── Error handler — human-readable, no stack traces ───────────────────────────

def handle_mono_error(e: MonoError) -> None:
    """Map SDK errors to friendly red terminal messages."""
    messages: dict[type, str] = {
        InsufficientBalanceError:  "Insufficient balance — add funds to your agent first.",
        AuthenticationError:       "Invalid API key — run `mono init` to reconfigure.",
        NodeLockedError:           "Agent node is locked and cannot send funds.",
        RecipientNotFoundError:    "Recipient agent not found — check the ID and try again.",
        SpendingLimitExceededError:"Amount exceeds your spending limit for this agent.",
        SystemHaltedError:         "System is temporarily paused — try again in a moment.",
        RateLimitError:            "Too many requests — slow down and retry.",
        NetworkError:              "Connection failed — check your network and try again.",
    }
    friendly = messages.get(type(e), None)
    print(file=sys.stderr)
    if friendly:
        err(friendly)
        if e.detail:
            dim(e.detail)
    else:
        err(e.message)
    print(file=sys.stderr)
    sys.exit(1)


# ── mono balance ──────────────────────────────────────────────────────────────

def cmd_balance(args: argparse.Namespace) -> None:
    client = get_client()

    # Main balance (caller's node)
    bal = client.balance()
    avail = float(bal.get("available_usdc", 0))
    agent_id = bal.get("agent_id", "—")

    print()
    print(f"  {BOLD}Balance{R}  {DIM}agent: {agent_id}{R}")
    rule()
    print(f"  {'Available':<20} {GRN}{avail:>12.4f} USDC{R}")

    # All nodes under this account
    nodes = client.list_nodes()
    if nodes:
        rule()
        print(f"  {BOLD}{'Agent':<22} {'Balance':>12}  {'Status':<10} {'Limit':>10}{R}")
        rule()
        for n in nodes:
            status_color = GRN if n.status == "active" else RED
            limit_str = f"{n.spending_limit:>9.2f}" if n.spending_limit else "      —   "
            print(
                f"  {n.name:<22} {n.balance:>12.4f}  "
                f"{status_color}{n.status:<10}{R} {limit_str}"
            )
        total = sum(n.balance for n in nodes)
        rule()
        print(f"  {'Total (all agents)':<22} {total:>12.4f}")

    print()


# ── mono transfer ─────────────────────────────────────────────────────────────

def cmd_transfer(args: argparse.Namespace) -> None:
    client = get_client()

    print()
    dim(f"Transferring {args.amount:.4f} USDC → {args.to} …")

    result = client.transfer(to=args.to, amount=args.amount)

    print()
    ok(f"Transfer complete")
    rule()
    print(f"  {'Transaction':<18} {result.transaction_id}")
    print(f"  {'Amount':<18} {result.amount:.4f} USDC")
    print(f"  {'Your balance':<18} {GRN}{result.sender_balance:.4f} USDC{R}")
    print(f"  {'Recipient balance':<18} {result.recipient_balance:.4f} USDC")
    print()


# ── mono settle ───────────────────────────────────────────────────────────────

def cmd_settle(args: argparse.Namespace) -> None:
    client = get_client()

    print()
    dim(f"Settling {args.amount:.4f} USDC → {args.to} …")

    result = client.settle(to=args.to, amount=args.amount)

    print()
    ok("Settlement complete")
    rule()
    print(f"  {'Transaction':<18} {result.transaction_id}")
    print(f"  {'Amount':<18} {result.amount:.4f} USDC")
    print(f"  {'Your balance':<18} {GRN}{result.sender_balance:.4f} USDC{R}")
    print(f"  {'Recipient balance':<18} {result.recipient_balance:.4f} USDC")
    print(f"  {'Status':<18} {result.status}")
    print()


# ── mono status ───────────────────────────────────────────────────────────────

def cmd_status(args: argparse.Namespace) -> None:
    client = get_client()
    nodes  = client.list_nodes()
    total  = sum(n.balance for n in nodes)
    active = sum(1 for n in nodes if n.status == "active")

    print()
    print(f"  {BOLD}Fleet{R}  {len(nodes)} agents · {active} active · {total:.4f} USDC total")
    rule()

    if not nodes:
        dim("No agents yet. Run: mono nodes create --name \"Agent 01\"")
        print()
        return

    print(f"  {BOLD}{'Name':<22} {'Balance':>12}  {'Status':<10} {'Cap':>10}{R}")
    rule()
    for n in nodes:
        dot   = f"{GRN}●{R}" if n.status == "active" else f"{RED}○{R}"
        cap   = f"{n.spending_limit:>9.2f}" if n.spending_limit else "      —   "
        print(f"  {dot} {n.name:<20} {n.balance:>12.4f}  {n.status:<10} {cap}")
    print()


# ── mono health ───────────────────────────────────────────────────────────────

def cmd_health(args: argparse.Namespace) -> None:
    gateway = get_setting("gateway_url") or DEFAULT_API
    try:
        req = urllib.request.Request(f"{gateway.rstrip('/')}/health")
        with urllib.request.urlopen(req, timeout=10) as resp:
            h = json.loads(resp.read())
    except Exception:
        hs = get_client().health()
        h  = {
            "status":          hs.status,
            "ledger_sum":      hs.ledger_sum,
            "nodes":           {"active": hs.nodes_active, "total": hs.nodes_total},
            "circuit_breaker": {"active": hs.circuit_breaker_active},
        }

    st   = h.get("status", "UNKNOWN")
    icon = f"{GRN}●{R}" if st in ("HEALTHY", "OK") else f"{YLW}●{R}" if st == "WARNING" else f"{RED}●{R}"
    cb   = h.get("circuit_breaker", {})
    nd   = h.get("nodes", {})

    print()
    print(f"  {icon}  {BOLD}{st}{R}")
    rule()
    print(f"  {'Ledger':<18} {float(h.get('ledger_sum', 0)):.2f} USDC")
    print(f"  {'Nodes':<18} {nd.get('active', '?')}/{nd.get('total', '?')} active")
    print(f"  {'Circuit breaker':<18} {'ACTIVE' if cb.get('active') else 'OFF'}")
    print(f"  {'API':<18} {DIM}{gateway}{R}")
    print()


# ── mono nodes ────────────────────────────────────────────────────────────────

def cmd_nodes_create(args: argparse.Namespace) -> None:
    client = get_client()
    node   = client.create_node(name=args.name, spending_limit=args.limit)

    print()
    ok(f"Node created: {BOLD}{node.name}{R}")
    rule()
    print(f"  {'ID':<14} {node.id}")
    print(f"  {'Status':<14} {node.status}")
    if node.spending_limit:
        print(f"  {'Spending cap':<14} {node.spending_limit:.2f} USDC")
    if node.api_key:
        print()
        warn(f"API key — shown ONCE, copy now:")
        print(f"\n  {BOLD}{node.api_key}{R}\n")
    else:
        print()


def cmd_nodes_kill(args: argparse.Namespace) -> None:
    client = get_client()
    client.kill_node(args.id)
    print()
    ok(f"Node {args.id} killed.")
    print()


# ── mono config ───────────────────────────────────────────────────────────────

def cmd_config_show(args: argparse.Namespace) -> None:
    cfg = load_config()
    if not cfg:
        print()
        warn("No config found. Run: mono init")
        print()
        return
    print()
    print(f"  {BOLD}Config{R}  {DIM}{CONFIG_FILE}{R}")
    rule()
    for k, v in cfg.items():
        if k == "api_key":
            v = f"{str(v)[:15]}…{str(v)[-4:]}" if v else "(not set)"
        print(f"  {k:<22} {v}")
    print()


def cmd_config_set(args: argparse.Namespace) -> None:
    cfg = load_config()
    cfg[args.key] = args.value
    save_config(cfg)
    print()
    ok(f"{args.key} = {args.value}")
    print()


def cmd_config_clear(args: argparse.Namespace) -> None:
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
    print()
    ok(f"Config cleared: {CONFIG_FILE}")
    print()


# ── mono init ─────────────────────────────────────────────────────────────────

def detect_profile() -> Path:
    shell = os.environ.get("SHELL", "")
    home  = Path.home()
    if "zsh"  in shell: return home / ".zshrc"
    if "bash" in shell: return home / ".bash_profile"
    return home / ".profile"


def write_export(key: str, value: str) -> None:
    profile = detect_profile()
    line    = f'export {key}="{value}"'
    try:
        text = profile.read_text() if profile.exists() else ""
        if f"export {key}=" not in text:
            with profile.open("a") as f:
                f.write(f"\n# mono SDK\n{line}\n")
    except PermissionError:
        pass


def test_connection(key: str, url: str) -> bool:
    try:
        req = urllib.request.Request(
            f"{url.rstrip('/')}/health",
            headers={"Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read()).get("status") in ("HEALTHY", "OK", "ok")
    except urllib.error.HTTPError as e:
        return e.code in (401, 403)  # reachable, just wrong key
    except Exception:
        return False


def cmd_init(args: argparse.Namespace) -> None:
    print()
    print(f"  {BOLD}mono init{R}  Setting up your environment")
    print()

    cfg         = load_config()
    existing    = get_api_key()

    if existing and not args.force:
        masked = f"{existing[:15]}…{existing[-4:]}"
        ok(f"API key already configured: {DIM}{masked}{R}")
        api_key = existing
    else:
        print(f"  Get your key at: {BOLD}https://monospay.com/dashboard{R}")
        print()
        try:
            api_key = input("  MONO_API_KEY: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n  Cancelled.\n")
            sys.exit(0)

        if not api_key:
            warn("Skipped — set MONO_API_KEY later.")
            api_key = ""
        elif not api_key.startswith("mono_live_"):
            warn("Key should start with 'mono_live_'")

    gateway_url = DEFAULT_API
    cfg.update({
        "gateway_url":    gateway_url,
        "base_rpc_url":   DEFAULTS["base_rpc_url"],
        "paymaster_url":  DEFAULTS["paymaster_url"],
        "chain":          "base",
        "chain_id":       8453,
        "usdc_address":   DEFAULTS["usdc_address"],
        "eurc_address":   DEFAULTS["eurc_address"],
    })
    if api_key:
        cfg["api_key"] = api_key

    save_config(cfg)

    print()
    ok(f"Network:   Base Mainnet (chain 8453)")
    ok(f"Paymaster: {DEFAULTS['paymaster_url']}")
    ok(f"Config:    {CONFIG_FILE}")

    if api_key:
        write_export("MONO_API_KEY", api_key)
        ok(f"MONO_API_KEY → {detect_profile()}")

    print()
    if api_key:
        print("  Testing connection…", end="", flush=True)
        connected = test_connection(api_key, gateway_url)
        if connected:
            print(f"\r  {GRN}✓{R}  Connected to monospay.com          ")
        else:
            print(f"\r  {YLW}!{R}  Could not connect — check key/network")

    print()
    print(f"  {BOLD}{GRN}All set.{R}\n")
    print(f"  {DIM}Next: source {detect_profile()} && mono balance{R}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mono",
        description=f"mono CLI — {DIM}monospay.com{R}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  mono init                              # First-time setup\n"
            "  mono balance                           # Show all balances\n"
            "  mono transfer --to agent_02 --amount 1.50\n"
            "  mono settle   --to agent_02 --amount 1.50\n"
            "  mono status                            # Fleet overview\n"
            "  mono nodes create --name \"Agent 01\"\n"
            "  mono config show\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", metavar="command")

    # init
    p_init = sub.add_parser("init", help="Zero-config setup wizard")
    p_init.add_argument("--force", action="store_true", help="Re-run even if already configured")

    # balance
    sub.add_parser("balance", help="Show main balance + all agent balances")

    # transfer
    p_transfer = sub.add_parser("transfer", help="Move USDC to another agent instantly")
    p_transfer.add_argument("--to",     required=True,             help="Recipient agent ID or name")
    p_transfer.add_argument("--amount", required=True, type=float, help="Amount in USDC")

    # settle
    p_settle = sub.add_parser("settle", help="Execute an on-chain settlement")
    p_settle.add_argument("--to",     required=True,             help="Recipient agent ID or name")
    p_settle.add_argument("--amount", required=True, type=float, help="Amount in USDC")

    # status
    sub.add_parser("status", help="Show agent fleet overview")

    # health
    sub.add_parser("health", help="System health check (no auth required)")

    # nodes
    p_nodes   = sub.add_parser("nodes", help="Manage agent nodes")
    nodes_sub = p_nodes.add_subparsers(dest="nodes_cmd", metavar="subcommand")
    nodes_sub.add_parser("list", help="List all nodes")
    p_create = nodes_sub.add_parser("create", help="Create a new agent node")
    p_create.add_argument("--name",  required=True, help="Node name")
    p_create.add_argument("--limit", type=float, default=None, help="Spending cap in USDC")
    p_kill = nodes_sub.add_parser("kill", help="Kill (lock) a node permanently")
    p_kill.add_argument("--id", required=True, help="Node ID")

    # config
    p_cfg   = sub.add_parser("config", help="Manage local configuration")
    cfg_sub = p_cfg.add_subparsers(dest="cfg_cmd", metavar="subcommand")
    cfg_sub.add_parser("show",  help="Show current config")
    p_cset  = cfg_sub.add_parser("set", help="Set a config value")
    p_cset.add_argument("key"); p_cset.add_argument("value")
    cfg_sub.add_parser("clear", help="Delete config file")

    args = parser.parse_args()

    try:
        cmd = args.command

        if cmd == "init":
            cmd_init(args)
        elif cmd == "balance":
            cmd_balance(args)
        elif cmd == "transfer":
            cmd_transfer(args)
        elif cmd == "settle":
            cmd_settle(args)
        elif cmd == "status":
            cmd_status(args)
        elif cmd == "health":
            cmd_health(args)
        elif cmd == "nodes":
            nc = getattr(args, "nodes_cmd", None)
            if   nc == "list":   cmd_status(args)
            elif nc == "create": cmd_nodes_create(args)
            elif nc == "kill":   cmd_nodes_kill(args)
            else:                p_nodes.print_help()
        elif cmd == "config":
            cc = getattr(args, "cfg_cmd", None)
            if   cc == "show":  cmd_config_show(args)
            elif cc == "set":   cmd_config_set(args)
            elif cc == "clear": cmd_config_clear(args)
            else:               p_cfg.print_help()
        else:
            parser.print_help()
            print(f"\n  {DIM}First time? Run: mono init{R}\n")

    except (
        InsufficientBalanceError,
        AuthenticationError,
        NodeLockedError,
        RecipientNotFoundError,
        SpendingLimitExceededError,
        SystemHaltedError,
        RateLimitError,
        NetworkError,
        MonoError,
    ) as e:
        handle_mono_error(e)
    except KeyboardInterrupt:
        print("\n  Aborted.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
