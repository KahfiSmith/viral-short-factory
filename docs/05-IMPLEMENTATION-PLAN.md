# 05 — Implementation Plan

Implement in small verified milestones.

Do not start a later milestone until the previous milestone acceptance criteria pass.

---

# Milestone 0 — Verify upstream video-use

## Goal

Prove the external editing engine works independently.

## Tasks

1. clone/install `browser-use/video-use` according to upstream docs;
2. verify `ffmpeg` and `ffprobe`;
3. install Python dependencies;
4. configure required transcription/API dependency;
5. symlink/register skill for the target coding agent;
6. create tiny local test-footage directory;
7. invoke video-use;
8. confirm it inventories/transcribes and proposes strategy;
9. approve strategy manually;
10. confirm `edit/final.mp4`.

## Acceptance

- source repo remains clean;
- sample final video exists;
- agent can locate `SKILL.md` and helpers;
- upstream output is written to the media project's `edit/`.

Do not proceed until this works.

---

# Milestone 1 — Project scaffold

## Deliverables

- `pyproject.toml`
- Python package layout
- Typer CLI
- config loader
- project workspace creation
- typed pipeline states
- structured logging

Commands:

```text
vsf doctor
vsf new --profile football_comedy --topic "..."
vsf inspect <project>
```

## Tests

- invalid configuration rejected;
- project IDs unique;
- workspace not created inside source repo;
- state starts at expected value.

---

# Milestone 2 — Persistence and cache

## Deliverables

SQLite database for:

- projects;
- pipeline events;
- provider response cache;
- asset library;
- asset usage.

## Required behavior

- transaction boundaries;
- migrations/version table;
- 24h TTL cache support;
- state transition validation.

## Tests

- cache hit before expiration;
- cache miss after expiration;
- forbidden state jump rejected;
- interrupted run resumes.

---

# Milestone 3 — Pexels provider

## Deliverables

- API client;
- normalized result mapping;
- timeout/retry policy;
- query parameters for portrait video;
- provider contract tests with mocked HTTP.

## Acceptance

Given a fixture response, the provider emits valid `AssetCandidate` objects without exposing raw provider structure to domain code.

---

# Milestone 4 — Pixabay provider

## Deliverables

Same adapter contract as Pexels.

Special acceptance:

- identical request within 24h uses cache;
- no extra network call on cache hit;
- candidate mapping supports available video variants.

---

# Milestone 5 — Local asset library

## Deliverables

- register downloaded assets;
- search by tags/category;
- hash files;
- ffprobe metadata;
- duplicate prevention.

## Acceptance

A downloaded asset can be found/reused in a second project without hitting a network provider when query/tag match is sufficient.

---

# Milestone 6 — Storyboard and query planner

## Deliverables

- content profile abstraction;
- `football_comedy` profile;
- JSON validators for concept/script/storyboard;
- scene query generator contract;
- AI-agent prompt template for filling these schemas.

## Important

Do not embed LLM vendor calls deeply into domain logic in MVP.

Preferred first implementation:

```text
AI coding agent generates/updates validated JSON artifacts
Python validates and executes pipeline
```

This keeps the project agent-agnostic.

---

# Milestone 7 — Candidate ranking and selection

## Deterministic v1 score

Suggested:

```text
query relevance metadata      30%
orientation fit               25%
resolution                    15%
duration fit                  15%
provider/source confidence    10%
reuse/duplicate penalty        5%
```

Weights are configurable.

Do not pretend metadata relevance is true visual understanding.

## Acceptance

Same inputs/config produce same ranking.

---

# Milestone 8 — Downloader and manifest

## Deliverables

- controlled downloader;
- size/time limits;
- content-type validation;
- SHA-256;
- ffprobe;
- stable local filename;
- source manifest writer.

## Acceptance

Every file under `sources/` selected for edit has exactly one valid manifest record.

---

# Milestone 9 — Edit brief

Generate `edit_brief.md`.

For `football_comedy` it should capture:

- hook under ~1–2 seconds where material supports it;
- expectation-vs-reality structure;
- preserve reaction beats;
- target vertical format;
- subtitle direction;
- do not hide faces/ball with captions;
- fast cuts but preserve punchline timing;
- final runtime range.

These are profile directions, not hardcoded upstream `video-use` modifications.

---

# Milestone 10 — video-use bridge

## Goal

Create a safe, observable handoff.

## Bridge responsibilities

- verify upstream path/skill;
- verify project sources;
- generate invocation brief;
- capture proposed strategy;
- persist proposal;
- set `AWAITING_EDIT_STRATEGY_APPROVAL`;
- resume after explicit approval;
- locate resulting `final.mp4`.

## Important

Do not assume `video-use` has a stable Python package API unless upstream documents one.

Integration may initially be an AI-agent orchestration contract.

---

# Milestone 11 — QC

Run `ffprobe` on final output.

Check configured target:

```text
aspect ratio: vertical
resolution target: 1080x1920 where final config requests it
duration: within profile bounds
valid video stream
readable file
```

Also persist QC report:

```json
{
  "passed": true,
  "checks": [...]
}
```

Never mark project `COMPLETE` if mandatory QC fails.

---

# Milestone 12 — Metadata output

Generate:

```text
metadata/title.txt
metadata/description.txt
metadata/hashtags.txt
```

No publishing.

---

# Milestone 13 — Optional YouTube trend signal

Use official YouTube Data API popular-video chart as a seed.

For Indonesian football:

```text
regionCode=ID
videoCategoryId=17
```

Persist raw trend signal separately from generated concepts.

No downloading of trend-source video.

---

# Milestone 14 — Hardening

- full E2E test;
- failure injection;
- API-limit tests;
- secret scan;
- docs update;
- packaging;
- `vsf doctor`.

---

# Release definition: MVP 0.1

MVP is complete when:

```text
brief
-> script/storyboard
-> compliant footage search
-> selected/downloaded assets
-> provenance
-> edit brief
-> video-use strategy proposal
-> human approval
-> render
-> QC
-> final package
```

works in one resumable project.
