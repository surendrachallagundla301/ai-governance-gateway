"""HTTP API for applications that are not MCP clients: scan text, verify the audit log, get the evidence pack.

Run: uvicorn governance_gateway.api:app --port 8000
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from governance_gateway.audit import AuditLog
from governance_gateway.injection import InjectionDetector
from governance_gateway.pii import redact
from governance_gateway.report import build_report

ROOT = Path(__file__).resolve().parent.parent
AUDIT_PATH = Path(os.getenv("GATEWAY_AUDIT_PATH", ROOT / "var" / "audit.jsonl"))
INVENTORY_PATH = Path(os.getenv("GATEWAY_INVENTORY_PATH", ROOT / "config" / "ai_inventory.yaml"))

app = FastAPI(title="AI Governance Gateway", version="0.1.0")
detector = InjectionDetector()


class ScanRequest(BaseModel):
    text: str = Field(max_length=20_000)


class ScanResponse(BaseModel):
    injection_flagged: bool
    injection_score: float
    injection_reasons: list[str]
    redacted_text: str
    pii_types: list[str]


@app.get("/healthz")
def health() -> dict:
    return {"status": "ok", "classifier_loaded": detector.has_model}


@app.post("/v1/scan", response_model=ScanResponse)
def scan(body: ScanRequest) -> ScanResponse:
    result = detector.scan(body.text)
    redacted, findings = redact(body.text)
    return ScanResponse(
        injection_flagged=result.flagged,
        injection_score=result.score,
        injection_reasons=result.reasons,
        redacted_text=redacted,
        pii_types=sorted({f.kind for f in findings}),
    )


@app.get("/v1/audit/verify")
def verify_audit() -> dict:
    v = AuditLog(AUDIT_PATH).verify()
    return {"ok": v.ok, "entries": v.entries, "first_bad_line": v.first_bad_line}


@app.get("/v1/evidence", response_class=PlainTextResponse)
def evidence() -> str:
    return build_report(INVENTORY_PATH, AUDIT_PATH)
