"""Pydantic configuration models mirroring examples/config.example.yaml."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class AppPaths(BaseModel):
    """Filesystem locations used by the application."""

    project_root: Path = Path("~/Videos/Video Editor/Projects/vsf").expanduser()
    asset_library_root: Path = Path("~/.local/share/viral-shorts-factory/assets").expanduser()
    database_path: Path = Path("~/.local/share/viral-shorts-factory/vsf.sqlite3").expanduser()


class VideoUseConfig(BaseModel):
    """Path to the upstream video-use repository and approval policy."""

    repo_path: Path
    require_strategy_approval: bool = True


class DefaultsConfig(BaseModel):
    """Default delivery settings for new projects."""

    platform: str = "youtube_shorts"
    language: str = "id-ID"
    aspect_ratio: str = "9:16"
    width: int = 1080
    height: int = 1920


class ProviderConfig(BaseModel):
    """A single footage/signal provider's enabled state, priority, and configuration.

    `api_key_env` holds the name of the environment variable that contains the
    secret — never the secret itself.
    """

    enabled: bool = True
    priority: int = 100
    api_key_env: str | None = None
    per_page: int = 20
    cache_ttl_hours: int | None = None
    user_agent: str | None = None
    language: str | None = None
    region_code: str | None = None
    video_category_id: str | None = None


class DownloadLimits(BaseModel):
    """Download safety limits."""

    max_candidates_per_scene: int = Field(default=2, ge=0)
    max_file_size_mb: int = Field(default=250, ge=1)
    timeout_seconds: int = Field(default=60, ge=1)


class RankingWeights(BaseModel):
    """Deterministic v1 ranking weights; must sum to 1.0."""

    query_match: float = 0.30
    orientation: float = 0.25
    resolution: float = 0.15
    duration_fit: float = 0.15
    source_confidence: float = 0.10
    duplicate_penalty: float = 0.05

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> RankingWeights:
        total = sum(
            (
                self.query_match,
                self.orientation,
                self.resolution,
                self.duration_fit,
                self.source_confidence,
                self.duplicate_penalty,
            )
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"ranking weights must sum to 1.0, got {total:.4f}")
        return self


class RankingConfig(BaseModel):
    """Ranking configuration; mirrors the nested `ranking:` block in YAML."""

    weights: RankingWeights = Field(default_factory=RankingWeights)


class ProfileConfig(BaseModel):
    """Duration bounds and locale for a content profile."""

    min_duration_seconds: int = Field(ge=0)
    max_duration_seconds: int = Field(ge=0)
    locale: str = "id-ID"

    @model_validator(mode="after")
    def _bounds_ordered(self) -> ProfileConfig:
        if self.min_duration_seconds > self.max_duration_seconds:
            raise ValueError(
                "min_duration_seconds must be <= max_duration_seconds"
                f" (got {self.min_duration_seconds} > {self.max_duration_seconds})"
            )
        return self


class AppConfig(BaseModel):
    """Top-level application configuration."""

    app: AppPaths = Field(default_factory=AppPaths)
    video_use: VideoUseConfig
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    providers: dict[str, ProviderConfig]
    downloads: DownloadLimits = Field(default_factory=DownloadLimits)
    ranking: RankingConfig = Field(default_factory=RankingConfig)
    profiles: dict[str, ProfileConfig]

    @model_validator(mode="after")
    def _provider_priorities_unique(self) -> AppConfig:
        priorities = [p.priority for p in self.providers.values() if p.enabled]
        if len(priorities) != len(set(priorities)):
            raise ValueError("enabled providers must have unique priorities")
        return self

    def get_provider(self, name: str) -> ProviderConfig | None:
        """Return the provider config or None if unknown/disabled."""
        provider = self.providers.get(name)
        if provider is None or not provider.enabled:
            return None
        return provider
