"""AI system inventory and EU AI Act risk classification.

This is a simplified, rules-based triage to help organize an AI inventory and decide where to look
first. It is not legal advice; final classification of any system needs review by legal/compliance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import yaml


class RiskTier(StrEnum):
    PROHIBITED = "prohibited"
    HIGH = "high"
    LIMITED = "limited"
    MINIMAL = "minimal"


# Practices banned outright (Article 5, simplified).
PROHIBITED_USES = {
    "social_scoring",
    "manipulative_techniques",
    "exploiting_vulnerabilities",
    "untargeted_facial_scraping",
    "emotion_recognition_workplace",
    "realtime_remote_biometric_id_public",
}

# Areas listed as high-risk (Annex III, simplified).
HIGH_RISK_AREAS = {
    "biometric_identification",
    "critical_infrastructure",
    "education_assessment",
    "employment_hiring",
    "essential_services_credit",
    "insurance_pricing",
    "law_enforcement",
    "migration_border",
    "justice_democratic",
}

OBLIGATIONS = {
    RiskTier.PROHIBITED: ["Do not deploy. Decommission or redesign the use case."],
    RiskTier.HIGH: [
        "Risk management system across the lifecycle",
        "Data governance and quality controls for training/validation data",
        "Technical documentation and record-keeping (automatic logs)",
        "Transparency and instructions for use for deployers",
        "Human oversight measures",
        "Accuracy, robustness and cybersecurity testing",
        "Conformity assessment and registration before deployment",
    ],
    RiskTier.LIMITED: [
        "Tell people they are interacting with an AI system",
        "Label AI-generated or manipulated content",
    ],
    RiskTier.MINIMAL: ["No mandatory obligations; follow internal AI policy and voluntary codes"],
}

# Which gateway control supports which framework expectation (for audit evidence).
CONTROL_MAP = [
    (
        "Agent permissioning (default-deny, human approval for high-risk tools)",
        "ISO/IEC 42001 A.9 (use of AI systems)",
        "NIST AI RMF: GOVERN, MANAGE",
    ),
    (
        "Prompt-injection screening of inputs and tool outputs",
        "ISO/IEC 42001 A.6 (AI system life cycle)",
        "NIST AI RMF: MEASURE, MANAGE",
    ),
    ("PII and secret redaction", "ISO/IEC 42001 A.7 (data for AI systems)", "NIST AI RMF: MANAGE"),
    ("Tamper-evident audit log", "EU AI Act Art. 12 (record-keeping)", "NIST AI RMF: GOVERN, MEASURE"),
    (
        "Model card and evaluation gate for the classifier",
        "EU AI Act Art. 11/15 (documentation, accuracy)",
        "NIST AI RMF: MEASURE",
    ),
]


@dataclass
class AISystem:
    name: str
    owner: str
    purpose: str
    use_case: str
    provider: str = ""
    interacts_with_people: bool = False
    generates_content: bool = False
    data_categories: list[str] = field(default_factory=list)
    human_oversight: str = ""

    def classify(self) -> tuple[RiskTier, str]:
        if self.use_case in PROHIBITED_USES:
            return RiskTier.PROHIBITED, f"'{self.use_case}' is a prohibited practice"
        if self.use_case in HIGH_RISK_AREAS:
            return RiskTier.HIGH, f"'{self.use_case}' is a listed high-risk area"
        if self.interacts_with_people or self.generates_content:
            return RiskTier.LIMITED, "interacts with people or generates content (transparency duties)"
        return RiskTier.MINIMAL, "no prohibited, high-risk, or transparency trigger"

    def gaps(self) -> list[str]:
        tier, _ = self.classify()
        issues = []
        if not self.owner:
            issues.append("No accountable owner")
        if tier is RiskTier.HIGH and not self.human_oversight:
            issues.append("High-risk system without a documented human-oversight measure")
        if "special_category" in self.data_categories and tier is not RiskTier.PROHIBITED:
            issues.append("Processes special-category personal data: confirm lawful basis and DPIA")
        return issues


def load_inventory(path: str | Path) -> list[AISystem]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return [AISystem(**entry) for entry in raw.get("systems", [])]
