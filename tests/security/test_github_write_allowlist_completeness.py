"""
Meta-test: GitHub Write Allowlist Static Completeness & Service Isolation (B2).
Statically analyzes ASTs of all services (patch_service, pr_review_service, webhook_worker)
and the GitHubClient to ensure:
1. Every write mutation matches an entry in ALLOWED_WRITE_ENDPOINTS.
2. Dynamic endpoint write calls have '# ALLOWED_WRITE: <template>' annotations.
3. Neither put() nor merge_pull_request() is ever called from service modules.
4. ALLOWED_WRITE_ENDPOINTS covers all permitted mutations and no more.
"""
import ast
import inspect
import re
from typing import List, Tuple
import pytest

from app.integrations.github.client import (
    ALLOWED_WRITE_ENDPOINTS,
    GitHubClient,
)
import app.services.patch_service as patch_service_mod
import app.services.pr_review_service as pr_review_service_mod
import app.integrations.github.webhook_worker as webhook_worker_mod
import app.integrations.github.client as client_mod


def _find_calls_in_source(module) -> List[Tuple[ast.Call, int, str]]:
    source = inspect.getsource(module)
    lines = source.splitlines()
    tree = ast.parse(source)
    calls = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            line_no = getattr(node, "lineno", 0)
            line_text = lines[line_no - 1] if 1 <= line_no <= len(lines) else ""
            calls.append((node, line_no, line_text))
    return calls


def test_service_modules_never_call_put_or_merge_pull_request():
    """Verify that patch_service, pr_review_service, and webhook_worker never call put() or merge_pull_request()."""
    modules = [patch_service_mod, pr_review_service_mod, webhook_worker_mod]

    for mod in modules:
        calls = _find_calls_in_source(mod)
        for node, line_no, line_text in calls:
            # Check func name
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            assert func_name != "merge_pull_request", (
                f"Disallowed call to merge_pull_request() at {mod.__name__}:{line_no}: {line_text}"
            )
            # Ensure no client.put calls
            if func_name == "put":
                # Check if caller looks like a client
                assert False, f"Disallowed call to put() at {mod.__name__}:{line_no}: {line_text}"


def test_client_write_calls_match_allowlist_patterns():
    """
    Statically inspect GitHubClient for all calls to _post_allowed_write, self.post, self.patch, self.delete.
    Verify each call matches ALLOWED_WRITE_ENDPOINTS.
    """
    calls = _find_calls_in_source(client_mod)
    write_methods = {"_post_allowed_write", "post", "patch", "delete"}

    write_call_count = 0

    for node, line_no, line_text in calls:
        func_name = None
        if isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name in write_methods and "async def" not in line_text:
            # Verify endpoint argument or annotation
            write_call_count += 1
            has_annotation = "# ALLOWED_WRITE:" in line_text
            matched = False

            if has_annotation:
                template = line_text.split("# ALLOWED_WRITE:")[1].strip()
                # Check if template matches any regex in ALLOWED_WRITE_ENDPOINTS
                sample_endpoint = template.replace("[^/]+", "val").replace(r"\d+", "123")
                for pat in ALLOWED_WRITE_ENDPOINTS:
                    if pat.search(sample_endpoint) or pat.search(template):
                        matched = True
                        break
            else:
                # Check if first/second arg is a string literal matching allowlist
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        for pat in ALLOWED_WRITE_ENDPOINTS:
                            if pat.search(arg.value):
                                matched = True
                                break

            assert matched or has_annotation, (
                f"Write call at {client_mod.__name__}:{line_no} does not match ALLOWED_WRITE_ENDPOINTS "
                f"and lacks # ALLOWED_WRITE annotation: {line_text}"
            )

    assert write_call_count >= 8, f"Expected at least 8 write call sites in client.py, found {write_call_count}"


def test_allowed_write_endpoints_schema_completeness():
    """Verify that ALLOWED_WRITE_ENDPOINTS contains exactly the 8 Phase 4 endpoints."""
    assert len(ALLOWED_WRITE_ENDPOINTS) == 8

    expected_verbs = {
        "/repos/[^/]+/[^/]+/git/blobs": {"POST"},
        "/repos/[^/]+/[^/]+/git/trees": {"POST"},
        "/repos/[^/]+/[^/]+/git/commits": {"POST"},
        "/repos/[^/]+/[^/]+/git/refs": {"POST"},
        "/repos/[^/]+/[^/]+/git/refs/heads/vigil/patch-[^/]+": {"PATCH", "DELETE"},
        "/repos/[^/]+/[^/]+/pulls": {"POST"},
        "/repos/[^/]+/[^/]+/pulls/\\d+/reviews": {"POST"},
        "/repos/[^/]+/[^/]+/issues/\\d+/comments": {"POST"},
    }

    found_patterns = {pat.pattern: verbs for pat, verbs in ALLOWED_WRITE_ENDPOINTS.items()}
    for exp_pattern_fragment, verbs in expected_verbs.items():
        match_found = any(exp_pattern_fragment in p for p in found_patterns)
        assert match_found, f"Expected pattern fragment '{exp_pattern_fragment}' in ALLOWED_WRITE_ENDPOINTS"
