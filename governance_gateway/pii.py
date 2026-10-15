"""Data-leakage control: find and redact personal data and secrets before they reach a model or leave the gateway."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    kind: str
    start: int
    end: int


def _luhn_ok(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _card_ok(match: str) -> bool:
    digits = re.sub(r"\D", "", match)
    return 13 <= len(digits) <= 19 and _luhn_ok(digits)


# Order matters: more specific patterns first so they win overlapping spans.
_PATTERNS: list[tuple[str, re.Pattern[str], callable | None]] = [
    ("AWS_ACCESS_KEY", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), None),
    ("API_KEY", re.compile(r"\b(?:sk|pk|rk)[-_](?:live|test|proj)?[-_]?[A-Za-z0-9]{20,}\b"), None),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), None),
    ("US_SSN", re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"), None),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]?){12,18}\d\b"), _card_ok),
    ("US_PHONE", re.compile(r"(?<!\d)(?:\+1[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}(?!\d)"), None),
    (
        "IP_ADDRESS",
        re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"),
        None,
    ),
]


def find_pii(text: str) -> list[Finding]:
    findings: list[Finding] = []
    taken: list[tuple[int, int]] = []
    for kind, pattern, validator in _PATTERNS:
        for m in pattern.finditer(text):
            if validator and not validator(m.group()):
                continue
            if any(m.start() < end and start < m.end() for start, end in taken):
                continue
            findings.append(Finding(kind, m.start(), m.end()))
            taken.append((m.start(), m.end()))
    return sorted(findings, key=lambda f: f.start)


def redact(text: str) -> tuple[str, list[Finding]]:
    """Replace each finding with a typed placeholder such as [REDACTED:EMAIL]."""
    findings = find_pii(text)
    out, cursor = [], 0
    for f in findings:
        out.append(text[cursor : f.start])
        out.append(f"[REDACTED:{f.kind}]")
        cursor = f.end
    out.append(text[cursor:])
    return "".join(out), findings
