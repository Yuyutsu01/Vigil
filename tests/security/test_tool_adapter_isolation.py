import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

BACKEND_SRC = Path(__file__).parents[2] / "backend"
sys.path.insert(0, str(BACKEND_SRC))

from app.adapters.bandit import BanditAdapter
from app.adapters.eslint import ESLintAdapter
from app.adapters.npm_audit import NpmAuditAdapter
from app.adapters.pip_audit import PipAuditAdapter
from app.adapters.ruff import RuffAdapter
from app.adapters.semgrep import SemgrepAdapter


ADAPTERS = [
    BanditAdapter(),
    SemgrepAdapter(),
    RuffAdapter(),
    ESLintAdapter(),
    PipAuditAdapter(),
    NpmAuditAdapter(),
]


@pytest.mark.parametrize("adapter", ADAPTERS, ids=lambda a: a.name)
def test_adapter_command_uses_list_form(adapter):
    """Command must be an explicit list of arguments, never a string or shell command."""
    cmd = adapter.build_command(Path("dummy_target.py"))
    assert isinstance(cmd, list), f"Adapter {adapter.name} build_command returned {type(cmd)}, expected list"
    assert len(cmd) >= 2, f"Adapter {adapter.name} command too short: {cmd}"
    # Target path must be present in arguments (except dependency audits that scan current dir/package)
    for part in cmd:
        assert isinstance(part, str)


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter", [BanditAdapter(), RuffAdapter(), SemgrepAdapter()], ids=lambda a: a.name)
async def test_adapter_invokes_subprocess_with_shell_false_and_readonly(adapter):
    """Subprocess.Popen must be called with shell=False."""
    popen_calls = []

    def mock_popen(*args, **kwargs):
        popen_calls.append((args, kwargs))
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (b"{}", b"")
        mock_proc.returncode = 0
        return mock_proc

    with patch.object(adapter, "is_available", return_value=True), \
         patch("subprocess.Popen", side_effect=mock_popen):

        source = 'print("Hello; rm -rf /; $(calc.exe)")\n'
        await adapter.run(source, "python")

    assert len(popen_calls) == 1
    args, kwargs = popen_calls[0]

    # Critical security assertions:
    assert kwargs.get("shell") is False, f"Adapter {adapter.name} ran with shell=True!"
    cmd = args[0] if args else kwargs.get("args")
    assert isinstance(cmd, list), f"Adapter {adapter.name} command was not passed as a list"
    # User content must not be present in the command args string
    assert not any("rm -rf" in str(arg) for arg in cmd)
