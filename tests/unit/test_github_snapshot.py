"""
Unit tests for Git LFS pointer detection and snapshot constraints (FR-104).
"""
import pytest

from app.integrations.github.snapshot import (
    MAX_FILE_BYTES,
    MAX_TOTAL_BYTES,
    SnapshotFile,
    is_git_lfs_pointer,
)


def test_git_lfs_pointer_detection():
    lfs_content = (
        b"version https://git-lfs.github.com/spec/v1\n"
        b"oid sha256:4d7a214614ab2935c943f9e0ff69d22eca521325ec8f199a956ac75b92a44396\n"
        b"size 12345\n"
    )
    normal_content = b"import os\nprint('Hello world')\n"

    assert is_git_lfs_pointer(lfs_content) is True
    assert is_git_lfs_pointer(normal_content) is False


def test_snapshot_file_attributes_and_bounds():
    long_path = "a" * 2000 + ".py"
    sf = SnapshotFile(
        path=long_path,
        content="x = 1",
        language="python",
        size_bytes=5,
    )

    # Path truncated to 1024 characters max
    assert len(sf.path) == 1024
    assert sf.language == "python"
    assert sf.content == "x = 1"
