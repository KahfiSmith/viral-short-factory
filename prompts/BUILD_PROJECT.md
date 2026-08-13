# Prompt — Build Viral Shorts Factory

You are the senior engineer responsible for implementing this repository.

Before writing code:

1. Read `AGENTS.md`.
2. Read every file in `docs/`.
3. Read `README.md`.
4. Inspect the existing repository.
5. Inspect the locally installed `browser-use/video-use` repository if it exists.
6. Do not modify `video-use`.
7. Summarize the architecture and current milestone.
8. Identify any conflict between existing code and the documentation.

Then implement **only the next incomplete milestone** from `docs/05-IMPLEMENTATION-PLAN.md`.

Engineering rules:

- Python 3.11+.
- Prefer `uv`.
- Typed domain models.
- Provider adapters.
- SQLite persistence.
- Tests for every new behavior.
- No secrets in source/logs.
- No HTML scraping of Pexels/Pixabay.
- Pixabay API cache TTL must be 24 hours.
- Do not implement social-platform ripping.
- Do not auto-publish.
- Preserve `video-use` strategy approval as a human gate.
- Do not claim completion until tests/lint/type checks have actually run.

At the end of the milestone:

1. run tests;
2. run lint;
3. run type checks;
4. show changed files;
5. show acceptance criteria and evidence;
6. list remaining known issues;
7. stop.

Do not continue automatically into the next milestone.
