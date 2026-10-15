from pathlib import Path

import pytest

from governance_gateway.server import build_gateway

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def gateway(tmp_path):
    return build_gateway(ROOT / "config" / "policy.yaml", tmp_path / "audit.jsonl")
