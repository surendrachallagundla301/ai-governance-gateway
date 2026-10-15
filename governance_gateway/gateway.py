"""The enforcement point. Every tool call from an agent passes through the same checks, in order:

1. Permission  - is this agent allowed to call this tool (and has a human approved it, if required)?
2. Input scan  - do the arguments contain a prompt-injection attempt?
3. Execute     - call the underlying system.
4. Output scan - does the result carry an *indirect* injection (e.g. a poisoned document)? If so, quarantine it.
5. Redact      - strip personal data and secrets before anything goes back to the model.
6. Audit       - record the decision, findings, and timing in the tamper-evident log.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from governance_gateway.audit import AuditLog
from governance_gateway.injection import InjectionDetector
from governance_gateway.pii import redact
from governance_gateway.policy import PolicyEngine


class GovernanceError(Exception):
    """Raised when a call is blocked; the message is safe to show to the agent."""


@dataclass
class Gateway:
    policy: PolicyEngine
    detector: InjectionDetector
    audit: AuditLog
    tools: dict[str, Callable[..., str]]

    def call(self, agent_id: str, tool: str, arguments: dict, *, human_approved: bool = False) -> str:
        started = time.perf_counter()
        base = {"agent": agent_id, "tool": tool}

        decision = self.policy.authorize(agent_id, tool, human_approved=human_approved)
        if not decision.allowed:
            self.audit.record("tool_call_denied", **base, reason=decision.reason)
            raise GovernanceError(decision.reason)

        for name, value in arguments.items():
            if isinstance(value, str):
                scan = self.detector.scan(value)
                if scan.flagged:
                    self.audit.record("input_blocked", **base, argument=name, reasons=scan.reasons, score=scan.score)
                    raise GovernanceError(f"Argument '{name}' was blocked as a likely prompt injection.")

        try:
            raw = self.tools[tool](**arguments)
        except Exception as exc:  # noqa: BLE001 - record any downstream failure, then surface it
            self.audit.record("tool_error", **base, error=type(exc).__name__)
            raise GovernanceError(f"'{tool}' failed: {type(exc).__name__}") from exc

        output_scan = self.detector.scan(raw)
        quarantined = output_scan.flagged
        if quarantined:
            raw = (
                "[QUARANTINED] The tool result contained instructions aimed at the AI and was withheld. "
                "A human should review the source content."
            )

        safe, findings = redact(raw)
        self.audit.record(
            "tool_call_allowed",
            **base,
            redactions=sorted({f.kind for f in findings}),
            redaction_count=len(findings),
            quarantined=quarantined,
            output_reasons=output_scan.reasons,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return safe
