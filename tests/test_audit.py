import json

from governance_gateway.audit import AuditLog


def test_chain_verifies_and_survives_reopen(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.record("tool_call_allowed", agent="a", tool="t")
    log.record("tool_call_denied", agent="a", tool="x")
    reopened = AuditLog(path)
    reopened.record("tool_call_allowed", agent="b", tool="t")
    assert reopened.verify().ok
    assert reopened.verify().entries == 3


def test_editing_an_entry_breaks_the_chain(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    for i in range(3):
        log.record("tool_call_allowed", agent="a", n=i)
    lines = path.read_text().splitlines()
    tampered = json.loads(lines[1])
    tampered["agent"] = "someone-else"
    lines[1] = json.dumps(tampered, sort_keys=True)
    path.write_text("\n".join(lines) + "\n")
    result = AuditLog(path).verify()
    assert not result.ok and result.first_bad_line == 2


def test_deleting_an_entry_breaks_the_chain(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    for i in range(3):
        log.record("e", n=i)
    lines = path.read_text().splitlines()
    path.write_text("\n".join([lines[0], lines[2]]) + "\n")
    assert not AuditLog(path).verify().ok
