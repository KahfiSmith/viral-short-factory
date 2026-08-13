# 01 — Project Specification

## Project name

**Viral Shorts Factory (VSF)**

## Product statement

A local-first AI-agent orchestration system that prepares short-form video projects from a brief, discovers compliant stock footage, builds a traceable production workspace, and delegates editing to `browser-use/video-use`.

## Problem

`video-use` is strong at editing footage that already exists in a directory. It is not a full content-production orchestrator.

A creator who wants repeatable YouTube Shorts production still has to manually:

- choose a concept;
- create a script;
- decide which visual is needed for each scene;
- search stock footage;
- download and organize assets;
- remember asset sources;
- translate the plan into an editing brief;
- invoke the editing workflow.

VSF automates those upstream production tasks.

## Goals

### G1 — One content brief becomes one reproducible project workspace

Input example:

```yaml
profile: football_comedy
platform: youtube_shorts
language: id-ID
topic: "kiper tarkam merasa dirinya Neuer"
target_duration_seconds: 28
```

Expected prepared outputs:

```text
project.json
concept.json
script.json
storyboard.json
asset_queries.json
source_manifest.json
edit_brief.md
sources/
```

After editing:

```text
edit/final.mp4
metadata/title.txt
metadata/description.txt
metadata/hashtags.txt
```

### G2 — Footage discovery is provider-independent

The domain layer must not know Pexels/Pixabay response formats.

Provider interface:

```text
search(request) -> list[AssetCandidate]
download(candidate, destination) -> DownloadedAsset
```

### G3 — Every selected source is auditable

No anonymous `scene_01.mp4` without provenance.

Each selected asset must have a manifest entry.

### G4 — Local assets are reusable

Previously downloaded assets should be indexed and searched before external API requests when relevant.

### G5 — `video-use` remains upstream-clean

VSF must not patch upstream files to function.

### G6 — Resumable pipeline

If a run stops after downloading assets, restart from the next valid stage rather than repeating provider queries/downloads.

## Non-goals

- bypassing copyright enforcement;
- removing platform watermarks;
- cloning another creator's Short;
- bulk scraping social networks;
- replacing a professional NLE in every use case;
- auto-posting without a separate explicit feature;
- multi-user cloud product in MVP.

## Primary persona

Solo creator or small content team producing repeated Shorts with an AI coding agent.

## Initial content profile

`football_comedy`

Profile behavior:

- Indonesian language;
- vertical short-form;
- fast opening;
- expectation-vs-reality comedy;
- strong reaction/punchline retention;
- stock-footage-friendly scripting;
- avoid dependence on match-broadcast clips.

## Functional requirements

### FR-01 Project initialization

CLI can create a project ID and workspace.

### FR-02 Configuration

Config supports:

- provider order;
- API keys through env-var references;
- target platform;
- target aspect ratio;
- duration range;
- locale;
- download limits;
- cache configuration;
- local asset library path;
- `video-use` repository/skill path.

### FR-03 Concept generation contract

The AI agent writes `concept.json` that validates against the domain schema.

### FR-04 Script contract

The script contains:

- hook;
- setup;
- escalation;
- payoff/punchline;
- optional CTA;
- estimated duration;
- voice/dialogue text;
- visual intention.

### FR-05 Storyboard contract

Every scene declares:

- scene ID;
- narrative purpose;
- target time window;
- spoken text;
- visual intent;
- 1..N search queries;
- asset constraints.

### FR-06 Asset search

Search order defaults to:

```text
local library
-> Pexels
-> Pixabay
```

A provider can be disabled.

### FR-07 Candidate normalization

All provider results map to a common `AssetCandidate`.

### FR-08 Candidate ranking

Initial ranking is deterministic/rule-based.

Suggested factors:

- semantic query match;
- portrait/vertical suitability;
- resolution;
- duration fit;
- subject visibility metadata where available;
- provider confidence;
- duplicate penalty;
- already-used penalty.

AI/vision ranking can be added later.

### FR-09 Download controls

- maximum N candidates downloaded per scene;
- content-length/size limits;
- timeout;
- checksum;
- filename sanitization;
- immutable storage after download.

### FR-10 Provenance manifest

Generate `source_manifest.json` before editing.

### FR-11 Edit brief

Generate a human-readable `edit_brief.md` containing:

- content concept;
- target runtime;
- scene order;
- selected source files;
- subtitle style;
- pacing;
- sound direction;
- grade direction;
- must-preserve moments;
- output spec.

### FR-12 `video-use` handoff

The bridge provides the prepared source directory and edit brief to the editing agent.

### FR-13 Strategy approval

When `video-use` proposes strategy:

- persist the proposal;
- set pipeline state to `AWAITING_EDIT_STRATEGY_APPROVAL`;
- surface it to the user;
- resume only after approval.

### FR-14 QC

At minimum validate:

- output exists;
- video stream exists;
- audio stream expectation is known;
- width/height;
- aspect ratio;
- duration;
- file size > 0;
- ffprobe readable;
- project references existing final file.

### FR-15 Metadata package

Generate suggested:

- title;
- description;
- hashtags.

Do not publish in MVP.

## Non-functional requirements

### Reliability

- bounded retries;
- resumable stages;
- cache external search responses;
- checksum downloaded files.

### Observability

- run ID;
- structured logs;
- stage start/end;
- provider request result count;
- selected asset IDs;
- subprocess exit code.

### Security

- environment secrets;
- no secret logs;
- sanitize paths;
- HTTPS providers only;
- validate content type before trusting downloaded files.

### Performance

MVP target is creator workstation usage, not high-throughput server workloads.

Optimize network use with caching and local reuse before concurrency.

## Success criteria

A fresh environment with valid API keys and working `video-use` can:

1. create a football-comedy project;
2. produce a valid storyboard;
3. find compliant stock candidates;
4. select/download footage;
5. generate complete provenance;
6. prepare an edit brief;
7. invoke/hand off to `video-use`;
8. pause at strategy approval;
9. resume after approval;
10. produce a valid final video package.

## Explicit MVP constraint

"Fully automated" means every deterministic stage can run without manual file handling.

It does **not** mean the system silently bypasses the upstream `video-use` human strategy-approval rule.
