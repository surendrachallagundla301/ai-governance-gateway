import pytest

from governance_gateway.policy import PolicyEngine

RAW = {
    "tools": {"read": {"risk": "low"}, "export": {"risk": "high", "requires_human_approval": True}},
    "agents": {"bot": {"allowed_tools": ["read", "export"], "max_calls_per_minute": 2}},
}


def engine(clock):
    e = PolicyEngine.from_dict(RAW)
    e.clock = clock
    return e


def test_default_deny_for_unknown_agent_and_unregistered_tool():
    e = engine(lambda: 0.0)
    assert not e.authorize("intruder", "read").allowed
    assert "not registered" in e.authorize("bot", "delete_everything").reason


def test_high_risk_tool_needs_human_approval():
    e = engine(lambda: 0.0)
    assert not e.authorize("bot", "export").allowed
    assert e.authorize("bot", "export", human_approved=True).allowed


def test_rate_limit_uses_a_sliding_window():
    now = [0.0]
    e = engine(lambda: now[0])
    assert e.authorize("bot", "read").allowed
    assert e.authorize("bot", "read").allowed
    assert "exceeded" in e.authorize("bot", "read").reason
    now[0] = 61.0
    assert e.authorize("bot", "read").allowed


def test_policy_cannot_grant_unregistered_tools():
    with pytest.raises(ValueError, match="not registered"):
        PolicyEngine.from_dict({"tools": {}, "agents": {"bot": {"allowed_tools": ["ghost"]}}})
