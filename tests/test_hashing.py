"""SHA-256 file hashing tests."""

from __future__ import annotations

import hashlib
from pathlib import Path


def test_sha256_matches_reference(tmp_path: Path) -> None:
    from viral_shorts_factory.assets.hashing import sha256_file

    path = tmp_path / "a.bin"
    content = b"hello world" * 100
    path.write_bytes(content)
    assert sha256_file(path) == hashlib.sha256(content).hexdigest()


def test_sha256_differs_between_files(tmp_path: Path) -> None:
    from viral_shorts_factory.assets.hashing import sha256_file

    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"one")
    b.write_bytes(b"two")
    assert sha256_file(a) != sha256_file(b)


def test_sha256_chunked_large_file(tmp_path: Path) -> None:
    from viral_shorts_factory.assets.hashing import sha256_file

    path = tmp_path / "big.bin"
    content = b"x" * (300 * 1024)  # > chunk size (64 KiB)
    path.write_bytes(content)
    assert sha256_file(path) == hashlib.sha256(content).hexdigest()
