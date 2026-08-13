"""Provider ports and shared errors.

Provider adapters implement the FootageProvider protocol and must never expose
their raw response formats to domain code. Download is a Milestone 8 concern and
is intentionally not part of the protocol yet.
"""

from __future__ import annotations

from typing import Protocol

from viral_shorts_factory.domain.assets import AssetCandidate, AssetSearchRequest


class ProviderError(Exception):
    """Base class for provider failures."""


class ProviderAuthError(ProviderError):
    """Invalid or rejected API credentials (permanent, no retry)."""


class ProviderRateLimitError(ProviderError):
    """Provider rate limit reached."""


class ProviderServerError(ProviderError):
    """Provider returned a 5xx after retries were exhausted."""


class ProviderResponseError(ProviderError):
    """Provider response could not be parsed as valid data."""


class FootageProvider(Protocol):
    """Port every footage provider adapter implements."""

    name: str

    async def search(self, request: AssetSearchRequest) -> list[AssetCandidate]:
        """Return normalized candidates for a search request."""
        ...
