"""Prompt-injection screening: fast heuristic rules plus the trained classifier.

Rules catch well-known phrasings with no false-negative risk from model drift; the classifier catches
paraphrases the rules miss. Either one can flag a text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import joblib

DEFAULT_MODEL = Path(__file__).resolve().parent.parent / "models" / "injection_clf.joblib"

_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "override-instructions",
        re.compile(
            r"\b(ignore|disregard|forget|override|set aside)\b.{0,40}\b(previous|prior|above|earlier|all|your)\b"
            r".{0,20}\b(instructions?|rules|guidelines|directions|prompt)",
            re.I,
        ),
    ),
    (
        "reveal-system-prompt",
        re.compile(
            r"\b(reveal|print|show|repeat|output)\b.{0,40}\b(system (prompt|message)|hidden instructions?|"
            r"initial (prompt|instructions?))",
            re.I,
        ),
    ),
    (
        "role-hijack",
        re.compile(r"\byou are now\b.{0,40}\b(unrestricted|unfiltered|DAN|no (rules|filters|policy))", re.I),
    ),
    ("fake-system-tag", re.compile(r"<\s*/?\s*system\s*>|\bSYSTEM OVERRIDE\b|\badmin mode\b", re.I)),
    (
        "addressed-to-ai",
        re.compile(r"\b(note|message|instruction)s? (to|for) (the |any )?(ai|assistant|agent)s?\b", re.I),
    ),
]


@dataclass(frozen=True)
class ScanResult:
    flagged: bool
    score: float
    reasons: list[str] = field(default_factory=list)


class InjectionDetector:
    def __init__(self, model_path: str | Path | None = DEFAULT_MODEL, threshold: float = 0.5, min_words: int = 4):
        self.threshold = threshold
        # An injection needs a sentence; scoring one-word values (ids, "all", "high") only adds false positives.
        self.min_words = min_words
        path = Path(model_path) if model_path else None
        self._model = joblib.load(path) if path and path.exists() else None

    @property
    def has_model(self) -> bool:
        return self._model is not None

    def scan(self, text: str) -> ScanResult:
        if not text or not text.strip():
            return ScanResult(False, 0.0)
        reasons = [name for name, pattern in _RULES if pattern.search(text)]
        score = 0.0
        if self._model is not None and len(text.split()) >= self.min_words:
            score = float(self._model.predict_proba([text])[0][1])
        if score >= self.threshold:
            reasons.append(f"classifier score {score:.2f}")
        return ScanResult(bool(reasons), round(score, 4), reasons)
