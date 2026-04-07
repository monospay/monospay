# mono SDK

Financial infrastructure for autonomous AI agents.

Your agent can think. Now it can pay.

## Installation

```bash
pip install mono-m2m-sdk
mono init
```

Works on macOS, Linux, Windows. Python 3.9+.

---

## Quickstart

```python
import os
from mono_sdk import MonoClient

client = MonoClient(api_key=os.environ["MONO_API_KEY"])

# Check balance
balance = client.balance()
print(f"Budget: ${balance['available_usdc']}")  # → Budget: $50.00

# Charge for a task
client.charge(0.003, "gpt-4o reasoning call")

# Pay another agent
client.transfer(to="agent_data_02", amount=1.50)
```

That's it. No wallets. No gas. No KYC.

---

## How it works

monospay is a USDC settlement layer built on Base. Your agent gets a budget
assigned by a developer through the dashboard. Every `charge()` or `transfer()`
is an off-chain ledger write — confirmed in 15ms, settled on-chain periodically.

```
Developer (dashboard) → funds agent with USDC
Agent (your code)     → spends via client.charge() / client.transfer()
Dashboard             → shows real-time balance as agent spends
```

---

## API reference

### `client.balance()`
Returns the agent's current off-chain ledger balance.

```python
balance = client.balance()
# {'available_usdc': 47.25, 'agent_id': 'agent_01', 'currency': 'USDC'}
```

### `client.charge(amount, memo="")`
Deducts `amount` USDC from this agent's budget.

```python
client.charge(0.02, "web search call")
# Raises MonoInsufficientBalance if budget is exhausted
```

### `client.transfer(to, amount, memo="")`
Pays another agent within the same monospay account. Off-chain, instant.

```python
client.transfer(to="agent_executor", amount=5.00, memo="task completed")
```

### `client.settle(to, amount)`
Execute an M2M settlement between agents.

```python
result = client.settle(to="agent_02", amount=1.50)
print(result.transaction_id)
```

---

## LangChain integration

```bash
pip install "mono-m2m-sdk[langchain]"
```

```python
from mono_sdk.langchain_tools import MonoPayTool
from langchain.agents import create_react_agent

tools = [MonoPayTool(api_key=os.environ["MONO_API_KEY"])]
agent = create_react_agent(llm=llm, tools=tools)
```

---

## Error handling

```python
from mono_sdk.errors import MonoInsufficientBalance, MonoAuthError

try:
    client.charge(100.00, "expensive call")
except MonoInsufficientBalance:
    print("Agent is out of budget — request more funds from operator.")
except MonoAuthError:
    print("Invalid API key.")
```

---

## Environment variables

| Variable | Description |
|---|---|
| `MONO_API_KEY` | Agent API key from monospay dashboard |
| `MONO_GATEWAY_URL` | Override gateway URL (default: `https://api.monospay.com`) |

---

## Links

- Dashboard: [monospay.com](https://monospay.com)
- API endpoint: `https://api.monospay.com/v1`
- PyPI: [pypi.org/project/mono-m2m-sdk](https://pypi.org/project/mono-m2m-sdk/)
- Contract: [BaseScan 0xA9DC3105…](https://basescan.org/address/0xA9DC3105ec1A84E4Bc3c9702dFC772a6efA2CDBA)
- Built on [Base](https://base.org) · Settled in [USDC](https://www.circle.com/usdc)
