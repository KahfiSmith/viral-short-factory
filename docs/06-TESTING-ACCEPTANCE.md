# 06 — Testing and Acceptance

## Testing pyramid

### Unit tests

Mandatory for:

- config validation;
- state transitions;
- provider response normalization;
- cache keys/TTL;
- ranking;
- rights/provenance gate;
- filename sanitization;
- manifest serialization;
- ffprobe parser.

### Integration tests

Use mocked HTTP for provider clients.

Test:

- rate limit response handling;
- retries;
- cache interception;
- corrupt response;
- missing video variant;
- downloader checksum;
- DB persistence.

### External integration smoke tests

Opt-in only:

```text
pytest -m external
```

Require real API keys.

Do not run them in every unit-test invocation.

### E2E

Use a tiny controlled media fixture.

E2E flow:

```text
new project
-> validate storyboard fixture
-> fake/mock provider search
-> copy fixture assets
-> manifest
-> edit brief
-> mocked video-use strategy
-> approval
-> mocked/fixture final
-> QC
-> complete
```

Have a separate manual E2E with actual `video-use`.

## Acceptance matrix

| Area | Acceptance |
|---|---|
| Upstream isolation | `git status` in video-use remains clean |
| Secrets | no API key committed/logged |
| Pexels | official API adapter works |
| Pixabay | repeated same request <24h does not call API twice |
| Provenance | all selected assets traceable |
| Rights | UNVERIFIED never auto-selected |
| Resume | restart continues from persisted stage |
| Approval | editing cannot transition from proposal to execution without approval |
| QC | invalid final cannot reach COMPLETE |
| Reuse | local asset can satisfy later scene |
| Determinism | ranker v1 stable for same inputs |

## Failure scenarios to test

1. Pexels unavailable.
2. Pixabay unavailable.
3. Both providers return no result.
4. API key missing.
5. Provider returns invalid JSON.
6. Download interrupted.
7. Downloaded URL says MP4 but content is not video.
8. ffprobe cannot parse downloaded file.
9. Duplicate asset across providers.
10. Insufficient portrait footage.
11. Edit strategy proposed but not approved.
12. `video-use` final missing.
13. final file corrupt.
14. duration outside required range.
15. project process terminated and restarted.

## `vsf doctor`

Should report at minimum:

```text
[PASS] Python version
[PASS] ffmpeg
[PASS] ffprobe
[PASS] writable project root
[PASS] SQLite
[PASS] video-use path
[PASS] video-use SKILL.md
[WARN] PEXELS_API_KEY missing
[WARN] PIXABAY_API_KEY missing
```

Never print secret values.

## Quality gates

Suggested CI:

```text
ruff check .
ruff format --check .
mypy src
pytest
```

If tooling choices change, preserve equivalent gates.

## Completion evidence

A coding agent must not say "done" only because files exist.

It must report:

- test command run;
- pass/fail counts;
- lint/type result;
- example CLI command;
- generated sample artifact paths;
- known limitations.
