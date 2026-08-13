"""Streaming SHA-256 file hashing."""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK_SIZE = 64 * 1024


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 of a file, streamed in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()
