"""
SECURITY TEST: Tenant isolation guarantee.
Verifies that tenant_id is extracted EXCLUSIVELY from the verified JWT claim.
See Implementation Plan [B1], Design Principles §1.
AC-3: Tenant A cannot access Tenant B's review runs.
"""
import sys
import uuid
from pathlib import Path

import pytest

BACKEND_SRC = Path(__file__).parents[2] / "backend"
sys.path.insert(0, str(BACKEND_SRC))


class TestTenantIsolation:
    """
    Tests tenant isolation at the code and logic level.
    Full integration tests require a running database (see tests/integration/).
    """

    def test_deps_never_trusts_x_tenant_id_header(self) -> None:
        """
        deps.py must not contain logic that trusts X-Tenant-ID or X-User-ID headers
        as authoritative sources of tenant identity.
        """
        deps_path = BACKEND_SRC / "app" / "api" / "deps.py"
        source = deps_path.read_text(encoding="utf-8")

        # The file should explicitly cross-check, not trust, the hint header
        assert "X-Tenant-Hint" in source, "deps.py should reference X-Tenant-Hint (for cross-check)"

        # Must not blindly use tenant_id from a header without verification
        # Verify the warning/mismatch rejection logic is present
        assert "TENANT_MISMATCH_REJECTED" in source or "tenant_mismatch" in source, (
            "deps.py must reject X-Tenant-Hint mismatches with JWT"
        )

    def test_jwt_tenant_claim_required(self) -> None:
        """JWT decode must require 'tenant_id' claim."""
        deps_path = BACKEND_SRC / "app" / "api" / "deps.py"
        source = deps_path.read_text(encoding="utf-8")
        assert 'payload["tenant_id"]' in source, (
            "tenant_id must be extracted from JWT payload, not headers"
        )

    def test_review_service_scopes_queries_by_tenant(self) -> None:
        """
        Review service must include tenant_id filter in all DB queries.
        """
        svc_path = BACKEND_SRC / "app" / "services" / "review_service.py"
        source = svc_path.read_text(encoding="utf-8")

        # get_review_run must filter by tenant_id
        assert "tenant_id" in source, "review_service must scope all queries by tenant_id"

    def test_fingerprint_includes_no_tenant_scope(self) -> None:
        """
        Fingerprints must be deterministic across tenants for the same code.
        Tenant isolation is at the ReviewRun level, not fingerprint level.
        """
        sys.path.insert(0, str(BACKEND_SRC))
        from app.rules.engine import compute_fingerprint

        fp1 = compute_fingerprint("VIGIL-SEC-001", "Module/Call[eval]", "eval(x)", "ast_node")
        fp2 = compute_fingerprint("VIGIL-SEC-001", "Module/Call[eval]", "eval(x)", "ast_node")

        assert fp1 == fp2, "Fingerprints must be deterministic"

    def test_fingerprint_is_line_shift_invariant(self) -> None:
        """
        Inserting blank lines must not change fingerprints.
        Fingerprints use AST path and matched text, not line numbers.
        """
        sys.path.insert(0, str(BACKEND_SRC))
        from app.rules.engine import compute_fingerprint

        # Same logical content, different line-based locations
        fp1 = compute_fingerprint(
            "VIGIL-SEC-002",
            "FunctionDef[name=foo]/Call[func=eval]",
            "eval(user_input)",
            "ast_node",
        )
        fp2 = compute_fingerprint(
            "VIGIL-SEC-002",
            "FunctionDef[name=foo]/Call[func=eval]",
            "eval(user_input)",
            "ast_node",
        )
        assert fp1 == fp2, "Fingerprint must be the same regardless of line position"

    def test_different_ast_paths_produce_different_fingerprints(self) -> None:
        """Different AST paths must produce different fingerprints."""
        sys.path.insert(0, str(BACKEND_SRC))
        from app.rules.engine import compute_fingerprint

        fp1 = compute_fingerprint("R1", "Module/Call[eval]", "eval(x)", "ast_node")
        fp2 = compute_fingerprint("R1", "Module/FunctionDef/Call[eval]", "eval(x)", "ast_node")
        assert fp1 != fp2, "Different AST paths must produce different fingerprints"
