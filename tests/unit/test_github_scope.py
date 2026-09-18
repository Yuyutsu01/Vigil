"""
Unit tests for repository policy, file eligibility, and path normalization (FR-104, M4).
"""
import pytest

from app.integrations.github.policy import (
    is_file_eligible,
    is_path_ignored,
    normalize_path,
)


def test_path_normalization_and_case_handling():
    # Slashes are converted to POSIX forward slashes
    assert normalize_path("src\\utils\\helper.py") in ("src/utils/helper.py", "src/utils/helper.py".lower())


def test_ignored_path_matching():
    ignored = [
        "vendor/**",
        "node_modules/**",
        "*.min.js",
        ".git/**",
    ]

    assert is_path_ignored("vendor/bundle/code.py", ignored) is True
    assert is_path_ignored("node_modules/express/index.js", ignored) is True
    assert is_path_ignored("assets/bundle.min.js", ignored) is True
    assert is_path_ignored(".git/config", ignored) is True

    # Legitimate code should NOT be ignored
    assert is_path_ignored("backend/app/main.py", ignored) is False
    assert is_path_ignored("src/components/App.tsx", ignored) is False


def test_file_eligibility_by_language_and_policy():
    enabled_langs = ["python", "javascript", "typescript"]
    ignored = ["vendor/**"]

    # Eligible Python file
    eligible, lang = is_file_eligible("app/main.py", enabled_langs, ignored)
    assert eligible is True
    assert lang == "python"

    # Eligible TypeScript file
    eligible, lang = is_file_eligible("frontend/src/index.tsx", enabled_langs, ignored)
    assert eligible is True
    assert lang == "typescript"

    # Ineligible language (e.g. Ruby if not enabled)
    eligible, lang = is_file_eligible("script.rb", enabled_langs, ignored)
    assert eligible is False

    # Ignored path takes precedence
    eligible, lang = is_file_eligible("vendor/lib/plugin.py", enabled_langs, ignored)
    assert eligible is False
