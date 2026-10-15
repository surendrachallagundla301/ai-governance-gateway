"""Generate a Markdown audit-evidence pack: AI inventory with risk tiers, obligations, gaps,
control mapping, and audit-log integrity and activity.

Usage: python -m governance_gateway.report --inventory config/ai_inventory.yaml --audit var/audit.jsonl
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from governance_gateway.audit import AuditLog
from governance_gateway.inventory import CONTROL_MAP, OBLIGATIONS, RiskTier, load_inventory

ROOT = Path(__file__).resolve().parent.parent


def build_report(inventory_path: Path, audit_path: Path) -> str:
    systems = load_inventory(inventory_path)
    audit = AuditLog(audit_path)
    verify = audit.verify()
    events = Counter(e["event"] for e in audit.entries())

    lines = [
        "# AI Governance Evidence Pack",
        f"_Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC. Risk tiers are a rules-based triage, not legal advice._",
        "",
        "## 1. AI system inventory",
        "",
        "| System | Owner | Use case | Risk tier | Why |",
        "| --- | --- | --- | --- | --- |",
    ]
    tiers = Counter()
    for s in systems:
        tier, why = s.classify()
        tiers[tier] += 1
        lines.append(f"| {s.name} | {s.owner or '—'} | {s.use_case} | **{tier.value}** | {why} |")

    lines += ["", "Summary: " + ", ".join(f"{t.value}: {tiers.get(t, 0)}" for t in RiskTier), ""]

    lines += ["## 2. Obligations by system", ""]
    for s in systems:
        tier, _ = s.classify()
        lines.append(f"### {s.name} ({tier.value})")
        lines += [f"- {o}" for o in OBLIGATIONS[tier]]
        for gap in s.gaps():
            lines.append(f"- ⚠️ Gap: {gap}")
        lines.append("")

    lines += [
        "## 3. Controls and framework mapping",
        "",
        "| Control | Standard / regulation | NIST AI RMF |",
        "| --- | --- | --- |",
    ]
    lines += [f"| {c} | {std} | {nist} |" for c, std, nist in CONTROL_MAP]

    lines += [
        "",
        "## 4. Runtime evidence (gateway audit log)",
        "",
        f"- Log integrity: {'verified ✅' if verify.ok else f'BROKEN at line {verify.first_bad_line} ❌'}"
        f" ({verify.entries} entries)",
    ]
    for event, count in sorted(events.items()):
        lines.append(f"- {event}: {count}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=ROOT / "config" / "ai_inventory.yaml")
    parser.add_argument("--audit", type=Path, default=ROOT / "var" / "audit.jsonl")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    report = build_report(args.inventory, args.audit)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
    else:
        print(report)


if __name__ == "__main__":
    main()
