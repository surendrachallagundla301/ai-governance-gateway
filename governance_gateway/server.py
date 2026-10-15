"""MCP server that exposes enterprise tools to an AI agent, with every call governed by the gateway.

Run one gateway per agent so each has its own identity and permissions, e.g. in an MCP client config:

    {"command": "python", "args": ["-m", "governance_gateway.server", "--agent", "support-assistant"]}
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from governance_gateway.audit import AuditLog
from governance_gateway.gateway import Gateway, GovernanceError
from governance_gateway.injection import InjectionDetector
from governance_gateway.policy import PolicyEngine
from governance_gateway.tools import REGISTRY

ROOT = Path(__file__).resolve().parent.parent


def build_gateway(
    policy_path: Path = ROOT / "config" / "policy.yaml", audit_path: Path = ROOT / "var" / "audit.jsonl"
) -> Gateway:
    return Gateway(
        policy=PolicyEngine.from_yaml(policy_path),
        detector=InjectionDetector(),
        audit=AuditLog(audit_path),
        tools=REGISTRY,
    )


def build_server(gateway: Gateway, agent_id: str) -> MCPServer:
    """Only the tools this agent is permitted to use are advertised; the gateway still checks every call."""
    server = MCPServer(
        name="ai-governance-gateway",
        instructions="Enterprise tools behind a governance gateway. Results may be redacted or quarantined.",
    )
    allowed = gateway.policy.agents[agent_id].allowed_tools if agent_id in gateway.policy.agents else set()

    def governed(tool: str, **arguments) -> str:
        try:
            return gateway.call(agent_id, tool, arguments)
        except GovernanceError as exc:
            # Surfaces to the agent as an MCP tool error (is_error=True) with a safe message.
            raise ToolError(f"BLOCKED: {exc}") from exc

    if "search_knowledge_base" in allowed:

        @server.tool(description="Search the internal knowledge base for help articles.")
        def search_knowledge_base(query: str) -> str:
            return governed("search_knowledge_base", query=query)

    if "get_customer" in allowed:

        @server.tool(description="Look up a customer's account by id (personal data is redacted).")
        def get_customer(customer_id: str) -> str:
            return governed("get_customer", customer_id=customer_id)

    if "create_ticket" in allowed:

        @server.tool(description="Create a support ticket.")
        def create_ticket(summary: str, priority: str = "normal") -> str:
            return governed("create_ticket", summary=summary, priority=priority)

    if "export_customer_data" in allowed:

        @server.tool(description="Bulk-export customer data (high risk; requires human approval).")
        def export_customer_data(segment: str) -> str:
            return governed("export_customer_data", segment=segment)

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the governed MCP server for one agent (stdio).")
    parser.add_argument("--agent", required=True, help="Agent identity, as defined in config/policy.yaml")
    parser.add_argument("--policy", type=Path, default=ROOT / "config" / "policy.yaml")
    parser.add_argument("--audit", type=Path, default=ROOT / "var" / "audit.jsonl")
    args = parser.parse_args()
    gateway = build_gateway(args.policy, args.audit)
    if args.agent not in gateway.policy.agents:
        parser.error(f"Unknown agent '{args.agent}'. Define it in {args.policy}.")
    build_server(gateway, args.agent).run("stdio")


if __name__ == "__main__":
    main()
