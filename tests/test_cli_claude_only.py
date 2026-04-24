import subprocess
import sys


def test_peach_agent_claude_accepted():
    """--agent claude must work (or at least not raise BadParameter)."""
    result = subprocess.run(
        [sys.executable, "-m", "peach", "run", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    # Help text should mention the agent option
    assert "--agent" in result.stdout or "-a" in result.stdout


def test_peach_agent_gemini_rejected():
    """--agent gemini must fail with a clear error."""
    result = subprocess.run(
        [sys.executable, "-m", "peach", "run", "--agent", "gemini"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "claude" in combined or "invalid" in combined or "bad" in combined
