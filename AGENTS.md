# AGENTS.md — Viral Shorts Factory

This is the authoritative project memory for Command Code.

## Project overview

Read `@README.md` first.

Viral Shorts Factory (VSF) orchestrates short-form video production and delegates editing to the upstream `browser-use/video-use` project.

Correct dependency direction:

```text
viral-shorts-factory -> video-use
```

Never make `video-use` depend on this repository.

## Mandatory docs

Before architecture or implementation work, read:

- `@docs/01-PROJECT-SPEC.md`
- `@docs/02-ARCHITECTURE.md`
- `@docs/03-DATA-CONTRACTS.md`
- `@docs/04-PROVIDER-INTEGRATIONS.md`
- `@docs/05-IMPLEMENTATION-PLAN.md`
- `@docs/06-TESTING-ACCEPTANCE.md`
- `@docs/07-SECURITY-COMPLIANCE.md`
- `@docs/08-OPERATIONS.md`
- `@docs/09-COMMANDCODE-WORKFLOW.md`

## Non-negotiable architecture rules

1. Do not modify, vendor, or fork `browser-use/video-use` as part of VSF implementation.
2. VSF is the orchestrator; `video-use` is the editing engine.
3. Pexels/Pixabay integration uses documented APIs, not HTML scraping.
4. Pixabay API responses are cached for 24 hours.
5. Never invent rights/provenance metadata.
6. `UNVERIFIED` assets cannot be auto-selected.
7. YouTube/TikTok/Instagram ripping is outside MVP.
8. API secrets only come from environment/secrets management.
9. Original/downloaded source media is immutable after ingest.
10. Pipeline state must be persisted and resumable.
11. Preserve the upstream `video-use` edit-strategy approval gate.
12. No automatic publishing in MVP.
13. No project may reach `COMPLETE` if mandatory QC fails.

## Command Code conventions

Project skills:

```text
.commandcode/skills/
```

Project custom agents:

```text
.commandcode/agents/
```

Use `/skills` and `/agents` to inspect them.

For a new implementation milestone:

```text
/plan <task>
```

Review the plan first.

Then:

```text
/goal <approved implementation objective>
```

Do not run multiple milestones in one `/goal` unless the user explicitly changes the project plan.

## Technology baseline

Unless the repository already contains an approved alternative:

- Python 3.11+
- `uv`
- Pydantic
- httpx
- Typer
- SQLite
- pytest
- ruff
- mypy or pyright
- ffmpeg / ffprobe
- structured logging

Avoid Redis, Celery, Postgres, Docker orchestration, or web UI until a milestone explicitly requires them.

## Required package boundaries

```text
src/viral_shorts_factory/
├── cli/
├── config/
├── domain/
├── pipeline/
├── profiles/
├── providers/
├── assets/
├── ranking/
├── editing/
├── metadata/
├── persistence/
└── observability/
```

Provider response formats must not leak outside provider adapters.

## Required pipeline states

```text
INIT
BRIEF_READY
CONCEPT_READY
SCRIPT_READY
STORYBOARD_READY
ASSET_QUERIES_READY
ASSETS_DISCOVERED
ASSETS_SELECTED
EDIT_BRIEF_READY
EDIT_STRATEGY_PROPOSED
AWAITING_EDIT_STRATEGY_APPROVAL
EDITING
QC
COMPLETE
FAILED_RETRYABLE
FAILED_PERMANENT
CANCELLED
```

## Verification before completion

Before reporting a milestone complete:

1. run changed behavior tests;
2. run lint;
3. run type checks;
4. verify no secrets were added;
5. verify docs still match behavior;
6. show acceptance criteria evidence;
7. state known limitations;
8. stop before the next milestone.

Never claim a command passed unless it was actually executed successfully.
