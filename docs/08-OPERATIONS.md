# 08 — Operations and Usage Model

## 1. Example lifecycle

```bash
vsf doctor

vsf new \
  --profile football_comedy \
  --topic "kiper tarkam merasa dirinya Neuer" \
  --duration 28

vsf run <project-id>
```

Expected pause:

```text
STATE: AWAITING_EDIT_STRATEGY_APPROVAL

video-use proposed strategy:
<plain-English strategy>

Approve:
vsf resume <project-id> --approve-edit-strategy
```

Then:

```text
EDITING
QC
COMPLETE
```

## 2. Project inspection

```bash
vsf inspect <project-id>
```

Should show:

```text
Project
Profile
Current state
Last successful stage
Assets selected
Provider calls/cache hits
Edit strategy status
Final output
QC status
```

## 3. Re-run behavior

Examples:

```bash
vsf run <id>
```

If current state is `ASSETS_SELECTED`, it continues from edit-brief generation.

It should not re-download valid selected assets.

Force flags should be explicit:

```text
--refresh-search
--redownload-assets
--rebuild-edit-brief
```

Do not make destructive refresh the default.

## 4. Asset library

Optional command model:

```bash
vsf assets list
vsf assets inspect <asset-id>
vsf assets search "goalkeeper confident"
```

Deletion requires explicit confirmation in interactive mode.

## 5. Provider diagnostics

```bash
vsf providers status
```

Output:

```text
local      enabled
pexels     enabled / key present
pixabay    enabled / key present / cache TTL 24h
youtube    disabled
```

Never print keys.

## 6. Logs

Project-specific:

```text
<project>/logs/run.jsonl
```

Global application log optional.

Each event:

```json
{
  "timestamp": "...",
  "run_id": "...",
  "project_id": "...",
  "stage": "ASSETS_DISCOVERED",
  "event": "provider_search_completed",
  "provider": "pexels",
  "result_count": 20,
  "elapsed_ms": 340
}
```

## 7. Backup

The project workspace and SQLite DB contain operational state.

Do not assume stock-provider download URLs remain valid forever.

For reproducibility retain:

- downloaded source;
- source manifest;
- checksum;
- script/storyboard;
- edit brief;
- final output;
- project state.

## 8. Cleanup

Generated preview/cache storage can grow.

Future cleanup command:

```bash
vsf clean --older-than 30d --previews
```

Never delete source/final/provenance by default.

## 9. Compatibility

`video-use` compatibility should be checked by:

- presence of expected skill file;
- presence of documented helper/workflow assumptions;
- actual smoke test.

Do not parse GitHub star count/version as a compatibility signal.

## 10. End-to-end walkthrough (verified)

This is the complete usage flow from an empty state to a project waiting for
edit-strategy approval. Every command below was verified against a real
project.

### 10.1 Prerequisites

```bash
vsf doctor
```

All checks must be `[PASS]`:

```text
[PASS] Python version
[PASS] ffmpeg
[PASS] ffprobe
[PASS] writable project root
[PASS] video-use path
[PASS] video-use SKILL.md
[WARN] PEXELS_API_KEY missing     # optional — local assets work without it
[WARN] PIXABAY_API_KEY missing    # optional — local assets work without it
```

The `[WARN]` lines mean the network providers are unavailable; the pipeline
still runs using only the local asset library. Set `PEXELS_API_KEY` /
`PIXABAY_API_KEY` in the environment to enable those providers.

### 10.2 All-in-one generate (create → plan → collect 8v+3i assets)

```bash
vsf generate --topic "<YOUR_TOPIC>" --profile facts
```

Or with a custom `script.json`:

```bash
vsf generate --topic "<YOUR_TOPIC>" --profile facts --script /path/to/script.json
```

Creates the project workspace, generates/loads the script, plans 8 video + 3 photo search queries per scene, and downloads all collected media into `<workspace>/assets/`.

### 10.3 Create a project

```bash
vsf new --profile football_comedy --topic "kiper tarkam merasa dirinya Neuer" --duration 28
```

Creates `<project_root>/<project-id>/` with `project.json` (status `INIT`) and
empty `sources/`, `metadata/`, `logs/`, `edit/`.

### 10.3 Plan (storyboard + asset queries)

```bash
vsf plan <project-id>
```

Reads `script.json` (or generates the profile's deterministic 4-beat fixture),
builds `storyboard.json` + `asset_queries.json`, and advances the state to
`ASSET_QUERIES_READY`. Four scenes (hook → setup → escalation → payoff) with
English portrait queries are generated for `football_comedy`.

### 10.4 Run (discovery → download → brief → proposal)

```bash
vsf run <project-id>
```

Executes, in order:

1. **Local discovery** — searches the local asset library by token overlap with
   the scene queries (`local_first_search`).
2. **Provider discovery** — Pexels then Pixabay, if API keys are configured.
   Provider failures are logged as warnings and skipped (best-effort).
3. **Ranking** — deterministic `rules-v1` scoring per scene
   (query match, orientation, resolution, duration, source confidence,
   duplicate penalty).
4. **Materialize** — downloads the top remote candidate, or copies the top
   local library asset, into `sources/<scene>_<provider>_<id>.mp4`.
5. **Manifest** — writes `source_manifest.json` with full provenance
   (sha256, rights, provider, query, local path).
6. **Edit brief** — writes `edit_brief.md` (concept, pacing, per-scene mapping).
7. **Proposal** — writes `edit/proposed_strategy.json` and stops at
   `AWAITING_EDIT_STRATEGY_APPROVAL`.

Output:

```text
project <id> is at AWAITING_EDIT_STRATEGY_APPROVAL
message: awaiting edit strategy approval
workspace: ~/Videos/vsf-projects/<id>

next step: vsf resume <project-id> --approve-edit-strategy
```

Expected workspace after `vsf run`:

```text
<project>/
├── project.json
├── script.json
├── storyboard.json
├── asset_queries.json
├── source_manifest.json
├── edit_brief.md
├── sources/
│   ├── scene_001_local_asset_<id>.mp4
│   └── ...
└── edit/
    └── proposed_strategy.json
```

### 10.5 Approve the edit strategy

```bash
vsf resume <project-id> --approve-edit-strategy
```

Marks the proposal `APPROVED` (approver `human`) and advances the state to
`EDITING`. This is the mandatory human gate — the pipeline never bypasses it
(docs/02 §8).

### 10.6 Verify state

```bash
vsf inspect <project-id>
```

Should show `Status: EDITING` (or `AWAITING_EDIT_STRATEGY_APPROVAL` if not yet
approved), plus the profile, topic, duration, and workspace path.

### 10.7 Resume / re-run behavior

- `vsf run <id>` from `AWAITING_EDIT_STRATEGY_APPROVAL` re-proposes the
  strategy (idempotent — the state machine guards invalid transitions).
- `vsf run <id>` from a state before `ASSET_QUERIES_READY` fails with a clear
  error telling you to run `vsf plan` first.
- Completed downloads are not re-run unless the project is reset.

### 10.8 Local-asset reuse (no network)

To run the pipeline entirely offline:

```bash
vsf assets register ./footage.mp4 --category football --tag goalkeeper --tag soccer --rights PROVIDER_LICENSED
```

The registered asset (hashed + probed, deduplicated by SHA-256) is then found
by `vsf run` via local discovery — no provider call needed. This satisfies the
Milestone 5 acceptance: a registered asset is reused in a second project
without a network hit.

### 10.9 Known limitations

- With no API keys set, only local-library assets are usable; if none match a
  scene's queries, `vsf run` fails with `no viable candidates for <scene>`.
- After `EDITING`, rendering via upstream `video-use` is performed by the
  editing agent (per docs/09), followed by QC and metadata — not yet wired into
  a single `vsf run`.
- `vsf run` does not yet have `--refresh-search` / `--redownload-assets` force
  flags; destructive refresh is intentionally not the default.
