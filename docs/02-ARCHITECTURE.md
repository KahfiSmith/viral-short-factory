# 02 — Architecture

## 1. Architectural style

Local-first modular monolith with ports/adapters.

Reasons:

- same workstation as `video-use`;
- easier for AI coding agents to understand;
- no need for service discovery/auth between repos;
- simple SQLite persistence;
- provider APIs are external adapters;
- can later split workers if needed.

Do not start with microservices.

## 2. Context diagram

```text
                         +----------------------+
                         |      AI Agent        |
                         | Command Code    |
                         +----------+-----------+
                                    |
                                    v
+---------+               +---------+----------+
|  User   |-------------->| Viral Shorts       |
+---------+               | Factory            |
                          +----+-----------+----+
                               |           |
               +---------------+           +----------------+
               v                                            v
       +-------+---------+                           +-------+--------+
       | Stock Providers |                           | local library  |
       | Pexels/Pixabay  |                           | SQLite + files |
       +-----------------+                           +----------------+
                               |
                               v
                       +-------+--------+
                       | video-use      |
                       | upstream skill |
                       +-------+--------+
                               |
                               v
                       +-------+--------+
                       | ffmpeg/ffprobe |
                       +----------------+
```

## 3. Runtime workspace

Repository code and generated projects must be separate.

```text
viral-shorts-factory/          # source code
video-use/                     # upstream source code

~/Videos/vsf-projects/
└── 20260812-kiper-neuer-abc123/
    ├── project.json
    ├── concept.json
    ├── script.json
    ├── storyboard.json
    ├── asset_queries.json
    ├── source_manifest.json
    ├── edit_brief.md
    ├── sources/
    ├── metadata/
    ├── logs/
    └── edit/                  # produced/managed by video-use
```

## 4. Recommended Python package layout

```text
viral-shorts-factory/
├── pyproject.toml
├── README.md
├── AGENTS.md
├── .env.example
├── config.example.yaml
├── src/
│   └── viral_shorts_factory/
│       ├── __init__.py
│       ├── cli/
│       │   ├── app.py
│       │   ├── new.py
│       │   ├── run.py
│       │   ├── resume.py
│       │   └── inspect.py
│       ├── config/
│       │   ├── models.py
│       │   └── loader.py
│       ├── domain/
│       │   ├── project.py
│       │   ├── script.py
│       │   ├── storyboard.py
│       │   ├── assets.py
│       │   ├── manifest.py
│       │   └── states.py
│       ├── pipeline/
│       │   ├── orchestrator.py
│       │   ├── context.py
│       │   └── stages/
│       ├── profiles/
│       │   ├── base.py
│       │   └── football_comedy.py
│       ├── providers/
│       │   ├── base.py
│       │   ├── pexels.py
│       │   ├── pixabay.py
│       │   └── youtube_trends.py
│       ├── assets/
│       │   ├── library.py
│       │   ├── downloader.py
│       │   ├── probe.py
│       │   └── hashing.py
│       ├── ranking/
│       │   ├── ranker.py
│       │   └── scoring.py
│       ├── editing/
│       │   ├── brief.py
│       │   ├── video_use_bridge.py
│       │   └── qc.py
│       ├── metadata/
│       │   └── generator.py
│       ├── persistence/
│       │   ├── db.py
│       │   ├── repositories.py
│       │   └── migrations.py
│       └── observability/
│           └── logging.py
└── tests/
```

## 5. Core domain ports

### FootageProvider

```python
class FootageProvider(Protocol):
    name: str

    async def search(
        self,
        request: AssetSearchRequest,
    ) -> list[AssetCandidate]: ...

    async def download(
        self,
        candidate: AssetCandidate,
        destination: Path,
    ) -> DownloadedAsset: ...
```

The exact code can differ, but the boundary must remain.

### AssetRepository

Responsibilities:

- query local reusable assets;
- register downloaded assets;
- detect duplicates by checksum;
- retrieve provenance.

### EditingEngine

```text
prepare(project) -> EditHandoff
propose_strategy(handoff) -> EditStrategyProposal
execute(handoff, approved_strategy) -> EditResult
```

The `video-use` implementation may rely on AI-agent skill invocation rather than a pure Python API. Do not pretend upstream exposes an HTTP service if it does not.

## 6. Pipeline state machine

```text
INIT
 |
 v
BRIEF_READY
 |
 v
CONCEPT_READY
 |
 v
SCRIPT_READY
 |
 v
STORYBOARD_READY
 |
 v
ASSET_QUERIES_READY
 |
 v
ASSETS_DISCOVERED
 |
 v
ASSETS_SELECTED
 |
 v
EDIT_BRIEF_READY
 |
 v
EDIT_STRATEGY_PROPOSED
 |
 v
AWAITING_EDIT_STRATEGY_APPROVAL
 | approved
 v
EDITING
 |
 v
QC
 |
 v
COMPLETE
```

Every transition is persisted.

A failed network provider may result in:

```text
FAILED_RETRYABLE
```

Invalid configuration or missing required executable:

```text
FAILED_PERMANENT
```

## 7. Handoff to video-use

Do not copy files into the `video-use` repository.

Give `video-use` a project media directory.

Preferred prepared layout:

```text
<project>/
├── sources/
│   ├── scene_001_asset_*.mp4
│   └── ...
├── storyboard.json
├── source_manifest.json
└── edit_brief.md
```

If upstream operates best when source files are directly in the target directory, create a dedicated edit-input directory inside the project and keep manifest references stable.

## 8. Approval boundary

`video-use` currently defines strategy confirmation as a hard production rule.

Therefore VSF must not conflate:

```text
"project brief approved"
```

with:

```text
"edit strategy approved"
```

They are different states.

Persist:

```json
{
  "strategy_id": "...",
  "strategy_text": "...",
  "created_at": "...",
  "approved_at": null,
  "approved_by": null
}
```

After approval, store who/what approved it.

MVP valid approver:

```text
human
```

## 9. Trend discovery

Trend discovery is optional and isolated.

```text
TrendProvider
  |
  +--> YouTubeMostPopularProvider
  +--> future provider
```

YouTube `mostPopular` is a useful regional/category signal but must not be represented to the user as an official "Shorts trending feed".

For football:

```text
regionCode=ID
videoCategoryId=17
```

Use trend data to inspire topics/format patterns, not to download/reuse copyrighted video content.

## 10. Scaling path

Only after the local-first pipeline is stable:

Phase A:
- background worker
- Postgres
- object storage

Phase B:
- web UI
- review/approval screen

Phase C:
- team workflows
- publishing connectors

None are required for MVP.
