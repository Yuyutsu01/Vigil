"""
Unit tests for the host runsc binary startup probe (H6).
Verifies that missing binaries or versions below 20240903.0 halt startup with RuntimeError.
"""
from unittest.mock import MagicMock, patch
import pytest

from app.config import Settings
from app.sandbox.gvisor import verify_runsc_available


def test_runsc_probe_missing_binary():
    """Verify that a nonexistent runsc binary path raises RuntimeError."""
    settings = Settings(
        runsc_binary_path="/nonexistent/path/to/runsc",
        runsc_minimum_version="20240903.0",
    )
    with pytest.raises(RuntimeError, match="runsc not found at configured path"):
        verify_runsc_available(settings)


def test_runsc_probe_version_below_minimum():
    """Verify that an outdated runsc binary version raises RuntimeError."""
    settings = Settings(
        runsc_binary_path="/mock/bin/runsc",
        runsc_minimum_version="20240903.0",
    )

    with patch("os.path.exists", return_value=True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="runsc version release-20230501.0\n",
                stderr="",
            )
            with pytest.raises(RuntimeError, match="below required minimum"):
                verify_runsc_available(settings)


def test_runsc_probe_success():
    """Verify that a compliant runsc version passes probe without error."""
    settings = Settings(
        runsc_binary_path="/mock/bin/runsc",
        runsc_minimum_version="20240903.0",
    )

    with patch("os.path.exists", return_value=True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="runsc version release-20240903.0\nspec: 1.1.0\n",
                stderr="",
            )
            # Must complete without exception
            verify_runsc_available(settings)


def test_version_10_greater_than_9():
    """Verify numeric version comparison (H1): 20250101.0 > 20240903.0 passes, 20240101.0 fails."""
    settings = Settings(
        runsc_binary_path="/mock/bin/runsc",
        runsc_minimum_version="20240903.0",
    )

    with patch("os.path.exists", return_value=True):
        # 1. Newer version passes
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="runsc version release-20250101.0\n",
                stderr="",
            )
            verify_runsc_available(settings)

        # 2. Older version fails
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="runsc version release-20240101.0\n",
                stderr="",
            )
            with pytest.raises(RuntimeError, match="below required minimum"):
                verify_runsc_available(settings)

