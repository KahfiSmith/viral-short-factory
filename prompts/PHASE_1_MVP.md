# Prompt — Start MVP Implementation

Implement Milestone 1 only: Project scaffold.

Required deliverables:

- Python package using `src/` layout.
- Typer CLI.
- `vsf doctor`.
- `vsf new`.
- `vsf inspect`.
- Pydantic configuration model.
- Project workspace creation outside source repository.
- Project/pipeline typed states.
- Structured logging foundation.
- Unit tests.

Do not implement provider network calls yet.
Do not implement video-use integration yet.
Do not add a web frontend.
Do not add Postgres/Redis/Celery.

Acceptance:

- `vsf new` creates a valid project workspace.
- invalid config fails with clear error.
- state is persisted.
- `vsf doctor` detects ffmpeg/ffprobe and configured video-use path without exposing secrets.
- tests/lint/type checks pass.

Read `AGENTS.md` and the complete docs before coding.
