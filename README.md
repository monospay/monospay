# mono SDK

Financial infrastructure for autonomous AI agents.  
Your agent can think. Now it can pay.

---

## Install

```bash
curl -fsSL https://monospay.com/install.sh | bash
```

Or manually:

```bash
pip install mono-m2m-sdk
mono init
```

Works on macOS, Linux, Windows · Python 3.9+

---

## CLI — Quick Reference

```bash
# Setup (run once)
mono init

# Balance
mono balance

# Transfer USDC to another agent
mono transfer --to <agent_id> --amount 1.50

# On-chain settlement
mono settle --to <agent_id> --amount 1.50

# Fleet overview
mono status

# Node management
mono nodes create --name "Agent 01"
mono nodes kill   --id <node_id>

# Config & diagnostics
mono config show
mono health
```

---

## Python SDK

```python
import os
from mono_sdk import MonoClient

client = MonoClient(api_key=os.environ["MONO_API_KEY"])

# Check balance
balance = client.balance()
print(f"Budget: ${balance['available_usdc']}")  # → Budget: $50.00

# Deduct cost of an AI call
client.charge(0.003, "gpt-4o reasoning call")

# Pay another agent instantly
client.transfer(to="agent_02", amount=1.50)

# On-chain settlement
result = client.settle(to="agent_02", amount=1.50)
print(result.transaction_id)
```

No wallets. No gas. No KYC.

---

## How it works

```
Developer  →  funds agent via dashboard (USDC)
Agent      →  spends via charge() / transfer()
Dashboard  →  real-time balance as agent runs
```

Every `charge()` or `transfer()` is an off-chain ledger write — confirmed in 15ms,
settled on Base L2 periodically.

---

## LangChain

```bash
pip install "mono-m2m-sdk[langchain]"
```

```python
from mono_sdk.langchain_tools import MonoToolkit

toolkit = MonoToolkit(api_key=os.environ["MONO_API_KEY"])
tools   = toolkit.get_tools()   # LLM inference, RPC, price oracle
```

---

## OpenAI Function Calling

```python
from mono_sdk.openai_functions import get_mono_tools, handle_tool_call

tools    = get_mono_tools()          # drop-in OpenAI tool schemas
response = openai.chat.completions.create(model="gpt-4o", tools=tools, ...)
result   = handle_tool_call(tool_call.function.name,
                             tool_call.function.arguments, client)
```

---

## Error handling

```python
from mono_sdk.errors import InsufficientBalanceError, AuthenticationError

try:
    client.charge(999.00)
except InsufficientBalanceError:
    print("Out of budget — top up at monospay.com/dashboard")
except AuthenticationError:
    print("Invalid key — run: mono init")
```

---

## Environment variables

| Variable | Description |
|---|---|
| `MONO_API_KEY` | Agent API key (from monospay dashboard) |
| `MONO_GATEWAY_URL` | Override API endpoint (optional) |

---

## Links

- Dashboard · [monospay.com](https://monospay.com)
- Docs · [monospay.com/docs](https://monospay.com/docs)
- PyPI · [mono-m2m-sdk](https://pypi.org/project/mono-m2m-sdk/)
- Contract · [BaseScan 0xA9DC3105…](https://basescan.org/address/0xA9DC3105ec1A84E4Bc3c9702dFC772a6efA2CDBA)
- Built on [Base](https://base.org) · Settled in [USDC](https://www.circle.com/usdc)
