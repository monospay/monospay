#!/bin/bash
# ─────────────────────────────────────────────────────────────────────
# monospay Demo Recording — 30 Second Developer Journey
#
# Shows: pip install → first run (onboarding) → config → ready
#
# Record with asciinema:
#   asciinema rec demo.cast -c "bash demo_record.sh"
#   agg demo.cast demo.gif --theme dracula --font-size 16
# ─────────────────────────────────────────────────────────────────────

set -e

GREEN="\033[32m"
DIM="\033[90m"
CYAN="\033[36m"
BOLD="\033[1m"
RESET="\033[0m"

slow() { sleep 0.4; }
pause() { sleep 1.5; }

clear

# ── Step 1: Install ───────────────────────────────────────────────────

echo -e "${DIM}# Step 1: Install${RESET}"
echo -e "$ pip install \"monospay[mcp]\""
slow
echo "Collecting monospay[mcp]"
sleep 0.2
echo "  Downloading monospay-0.6.0-py3-none-any.whl (24 kB)"
sleep 0.3
echo -e "${GREEN}Successfully installed monospay-0.6.0${RESET}"
echo ""
pause

# ── Step 2: First run (no keys) ──────────────────────────────────────

echo -e "${DIM}# Step 2: First run — see what's needed${RESET}"
echo "$ mono-mcp"
slow
echo ""
echo "  monospay · payment infrastructure for AI agents"
echo "  ─────────────────────────────────────────────────"
echo ""
echo "  Almost there! Two steps to connect your agent:"
echo ""
echo "  1. Get your keys at monospay.com/dashboard"
echo "     → Agents → select agent → Issue API key"
echo ""
echo "  2. Set them in your environment:"
echo "     export MONO_API_KEY=mono_live_..."
echo "     export MONO_PRIVATE_KEY=0x..."
echo ""
pause
pause

# ── Step 3: Set keys + restart ───────────────────────────────────────

echo -e "${DIM}# Step 3: Set keys and go${RESET}"
echo '$ export MONO_API_KEY=mono_live_abc123'
slow
echo '$ export MONO_PRIVATE_KEY=0xdef456...'
slow
echo "$ mono-mcp"
slow
echo ""
echo -e "  ${GREEN}✓ monospay ready — your agent can pay.${RESET}"
echo "    API key: ✓  Private key: ✓"
echo "    Tools: mono_balance, mono_transfer, mono_transactions"
echo ""
pause

# ── Step 4: Outcome ──────────────────────────────────────────────────

echo ""
echo -e "${BOLD}  ──────────────────────────────────────${RESET}"
echo -e "${BOLD}  monospay.com — Your agent can pay.${RESET}"
echo -e "${BOLD}  ──────────────────────────────────────${RESET}"
echo ""
echo -e "  ${DIM}pip install monospay              # Python SDK${RESET}"
echo -e "  ${DIM}pip install \"monospay[mcp]\"      # MCP Server${RESET}"
echo -e "  ${DIM}pip install \"monospay[langchain]\" # LangChain${RESET}"
echo ""

sleep 3
