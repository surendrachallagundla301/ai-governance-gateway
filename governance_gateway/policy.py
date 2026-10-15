"""Agent permissioning: which agent may call which tool, how often, and which tools need a human."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class AgentPolicy:
    agent_id: str
    allowed_tools: frozenset[str]
    max_calls_per_minute: int = 30
    owner: str = ""


@dataclass(frozen=True)
class ToolPolicy:
    name: str
    risk: str = "low"  # low | medium | high
    requires_human_approval: bool = False


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


@dataclass
class PolicyEngine:
    """Default-deny: an agent can only call tools explicitly granted to it."""

    agents: dict[str, AgentPolicy]
    tools: dict[str, ToolPolicy]
    clock: callable = time.monotonic
    _calls: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    @classmethod
    def from_yaml(cls, path: str | Path) -> PolicyEngine:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict) -> PolicyEngine:
        tools = {
            name: ToolPolicy(
                name=name,
                risk=spec.get("risk", "low"),
                requires_human_approval=bool(spec.get("requires_human_approval", False)),
            )
            for name, spec in (raw.get("tools") or {}).items()
        }
        agents = {
            agent_id: AgentPolicy(
                agent_id=agent_id,
                allowed_tools=frozenset(spec.get("allowed_tools", [])),
                max_calls_per_minute=int(spec.get("max_calls_per_minute", 30)),
                owner=spec.get("owner", ""),
            )
            for agent_id, spec in (raw.get("agents") or {}).items()
        }
        unknown = {t for a in agents.values() for t in a.allowed_tools} - tools.keys()
        if unknown:
            raise ValueError(f"Policy grants tools that are not registered: {sorted(unknown)}")
        return cls(agents=agents, tools=tools)

    def authorize(self, agent_id: str, tool: str, *, human_approved: bool = False) -> Decision:
        agent = self.agents.get(agent_id)
        if agent is None:
            return Decision(False, f"Unknown agent '{agent_id}'.")
        tool_policy = self.tools.get(tool)
        if tool_policy is None:
            return Decision(False, f"Tool '{tool}' is not registered with the gateway.")
        if tool not in agent.allowed_tools:
            return Decision(False, f"Agent '{agent_id}' is not permitted to call '{tool}'.")
        if tool_policy.requires_human_approval and not human_approved:
            return Decision(False, f"'{tool}' is {tool_policy.risk}-risk and requires human approval.")
        if not self._within_rate_limit(agent):
            return Decision(False, f"Agent '{agent_id}' exceeded {agent.max_calls_per_minute} calls/minute.")
        return Decision(True, "allowed")

    def _within_rate_limit(self, agent: AgentPolicy) -> bool:
        now = self.clock()
        window = self._calls[agent.agent_id]
        while window and now - window[0] >= 60:
            window.popleft()
        if len(window) >= agent.max_calls_per_minute:
            return False
        window.append(now)
        return True
