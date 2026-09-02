from pathlib import Path

from agent.safety import Decision, SafetyPolicy


def test_workspace_operations_are_allowed_and_escape_is_denied(tmp_path: Path):
    policy = SafetyPolicy(tmp_path)
    assert policy.evaluate("read_file", {"path": "app.py"}).decision is Decision.ALLOW
    assert policy.evaluate("read_file", {"path": "../secret"}).decision is Decision.DENY


def test_dangerous_commands_are_denied_and_installs_require_confirmation(tmp_path: Path):
    policy = SafetyPolicy(tmp_path)
    assert policy.evaluate("run_command", {"command": "rm -rf /"}).decision is Decision.DENY
    assert policy.evaluate("run_command", {"command": "shutdown /s"}).decision is Decision.DENY
    assert policy.evaluate("run_command", {"command": "pip install flask"}).decision is Decision.CONFIRM
    assert policy.evaluate("run_command", {"command": "pytest"}).decision is Decision.ALLOW


def test_readonly_mode_blocks_mutations(tmp_path: Path):
    policy = SafetyPolicy(tmp_path, mode="readonly")
    assert policy.evaluate("edit_file", {"path": "app.py"}).decision is Decision.DENY
