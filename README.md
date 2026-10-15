# AI Governance Gateway

A control point between AI agents and enterprise systems. Agents reach tools through an **MCP server**,
and every call is checked for **permission**, screened for **prompt injection** (both direct and indirect),
**redacted** for personal data and secrets, and written to a **tamper-evident audit log**. A companion
**AI inventory** classifies each AI system against EU AI Act risk tiers and produces an audit-evidence
pack mapped to ISO/IEC 42001 and the NIST AI RMF.

```
 AI agent (MCP client)
        │  tools/call
        ▼
 ┌─────────────── Governance Gateway (MCP server) ───────────────┐
 │ 1 Permission    default-deny per agent, human approval for    │
 │                 high-risk tools, rate limits                  │
 │ 2 Input scan    rules + ML classifier for prompt injection    │
 │ 3 Execute       call the enterprise system                    │
 │ 4 Output scan   quarantine indirect injection (poisoned docs) │
 │ 5 Redact        emails, phones, SSNs, cards (Luhn), keys, IPs │
 │ 6 Audit         hash-chained JSONL; edits break the chain     │
 └────────────────────────────────────────────────────────────────┘
        │
        ▼
 CRM · ticketing · knowledge base (stubbed in tools.py)
```

## What it shows

| Concern | Implementation |
| --- | --- |
| **Agent permissioning** | `policy.py`. Agents only see and call the tools they're granted (`config/policy.yaml`). High-risk tools need human approval, and each agent has a sliding-window rate limit. |
| **Prompt injection** | `injection.py`. Regex rules for known patterns plus a TF-IDF + logistic-regression classifier for paraphrases. Applied to tool arguments *and* tool results, so indirect injection in retrieved documents is caught. |
| **Data leakage** | `pii.py`. Typed redaction (`[REDACTED:US_SSN]`) of personal data and secrets before anything returns to the model. Card numbers are Luhn-checked to avoid false positives. |
| **Auditability** | `audit.py`. Each entry stores the previous entry's SHA-256, and `verify()` pinpoints the first edited or deleted line. |
| **MCP** | `server.py`. Built on the official MCP Python SDK (v2 `MCPServer`). Blocked calls return MCP tool errors with safe messages. |
| **AI governance** | `inventory.py` and `report.py`. AI inventory (including shadow AI), EU AI Act risk-tier triage, obligations per tier, gap detection (no owner, no human oversight, special-category data), and a Markdown evidence pack. |
| **MLOps** | `ml/`. Reproducible training, cross-validation, a hand-written held-out set, a model card (version, data hash, metrics, limitations), and a CI quality gate that fails the build below the agreed recall and precision. |

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m governance_gateway.ml.train --out models      # train + write models/model_card.json
python -m governance_gateway.ml.evaluate                # quality gate
pytest -q                                               # 24 tests
python examples/demo.py                                 # see the gateway in action
python -m governance_gateway.report                     # evidence pack (Markdown)
```

### Use it from an MCP client

Run one gateway per agent so each has its own identity and permissions:

```json
{
  "mcpServers": {
    "governed-tools": {
      "command": "python",
      "args": ["-m", "governance_gateway.server", "--agent", "support-assistant"]
    }
  }
}
```

### HTTP API (for non-MCP apps)

```bash
uvicorn governance_gateway.api:app --port 8000
curl -X POST localhost:8000/v1/scan -H 'content-type: application/json' \
     -d '{"text":"Ignore previous instructions. My email is a@b.com"}'
```

The API also has `GET /v1/audit/verify` and `GET /v1/evidence`. To run it with Docker:
`docker build -t ai-governance-gateway . && docker run -p 8000:8000 ai-governance-gateway`.

## Model results and honest limitations

The classifier is trained on **synthetic, template-generated data** (641 rows). Scores on a split of that
same data are perfect and don't mean much. The number that matters is the **hand-written held-out set** of
30 examples, phrased in ways the templates never produce:

| Held-out set (n=30) | Precision | Recall | ROC-AUC |
| --- | --- | --- | --- |
| Classifier alone | 1.00 | 0.80 | 0.99 |
| Rules + classifier (what the gateway uses) | 1.00 | 0.93 (14/15) | n/a |

The first version of the training data scored only 0.60 recall here. The CI gate caught it, and the
training vocabulary was broadened without copying held-out examples. Before using this in production:
- Retrain on real labeled traffic.
- Add non-English data.
- Treat the classifier as one signal among several, not the only security control.

The EU AI Act tiers are a **rules-based triage** for organizing an inventory. They are not legal advice.

## Project layout

```
governance_gateway/
  policy.py      agent permissions, approvals, rate limits
  injection.py   rules + classifier
  pii.py         detection and redaction
  audit.py       hash-chained audit log
  gateway.py     the six-step enforcement pipeline
  server.py      MCP server (one per agent)
  api.py         FastAPI endpoints
  inventory.py   AI inventory and EU AI Act triage
  report.py      evidence pack
  ml/            data generation, training, evaluation gate
config/          policy.yaml, ai_inventory.yaml
data/            hand-written held-out set
tests/           24 tests, including in-process MCP client/server tests
```
