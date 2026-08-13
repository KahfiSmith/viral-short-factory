# 03 — Data Contracts

All JSON written by the pipeline must validate through typed models.

Use explicit schema versions.

## 1. Project

```json
{
  "schema_version": "1.0",
  "project_id": "20260812-kiper-neuer-abc123",
  "status": "STORYBOARD_READY",
  "profile": "football_comedy",
  "platform": "youtube_shorts",
  "language": "id-ID",
  "topic": "kiper tarkam merasa dirinya Neuer",
  "target_duration_seconds": 28,
  "created_at": "2026-08-12T05:45:00+07:00",
  "updated_at": "2026-08-12T05:46:00+07:00"
}
```

## 2. Concept

```json
{
  "schema_version": "1.0",
  "project_id": "20260812-kiper-neuer-abc123",
  "title": "Kiper Tarkam Merasa Prime Neuer",
  "premise": "Kiper terlalu percaya diri keluar dari gawang lalu gagal total.",
  "hook": "Kiper baru kita katanya gaya mainnya kayak Neuer.",
  "comedy_mechanism": "expectation_vs_reality",
  "payoff": "Kepercayaan diri jauh di atas kemampuan.",
  "stock_footage_feasibility": "high"
}
```

## 3. Script

```json
{
  "schema_version": "1.0",
  "target_duration_seconds": 28,
  "beats": [
    {
      "id": "beat_001",
      "type": "hook",
      "text": "Kiper baru kita katanya gaya mainnya kayak Neuer.",
      "estimated_seconds": 3.0
    }
  ]
}
```

Allowed beat types initially:

```text
hook
setup
escalation
payoff
reaction
cta
```

## 4. Storyboard

```json
{
  "schema_version": "1.0",
  "scenes": [
    {
      "scene_id": "scene_001",
      "order": 1,
      "purpose": "hook",
      "target_duration_seconds": 3.0,
      "spoken_text": "Kiper baru kita katanya gaya mainnya kayak Neuer.",
      "visual_intent": "amateur goalkeeper standing confidently on a football field",
      "queries": [
        "amateur soccer goalkeeper confident",
        "football goalkeeper standing field"
      ],
      "constraints": {
        "orientation": "portrait_preferred",
        "min_height": 1080,
        "min_duration_seconds": 2,
        "max_duration_seconds": 15,
        "people_allowed": true
      }
    }
  ]
}
```

## 5. Search request

```json
{
  "scene_id": "scene_001",
  "query": "amateur soccer goalkeeper confident",
  "locale": "en-US",
  "orientation": "portrait",
  "minimum_height": 1080,
  "max_results": 20
}
```

## 6. Normalized asset candidate

```json
{
  "candidate_id": "pexels:123456",
  "provider": "pexels",
  "provider_asset_id": "123456",
  "source_page_url": "https://...",
  "preview_url": "https://...",
  "download_variants": [
    {
      "url": "https://...",
      "width": 1080,
      "height": 1920,
      "file_type": "video/mp4"
    }
  ],
  "width": 1080,
  "height": 1920,
  "duration_seconds": 8.4,
  "tags": [],
  "contributor_name": "Example",
  "query": "amateur soccer goalkeeper confident",
  "rights_status": "PROVIDER_LICENSED",
  "raw_metadata_hash": "sha256:..."
}
```

Rights status enum:

```text
PROVIDER_LICENSED
USER_OWNED
PUBLIC_DOMAIN
ATTRIBUTION_REQUIRED
UNVERIFIED
REJECTED
```

## 7. Candidate score

```json
{
  "candidate_id": "pexels:123456",
  "scene_id": "scene_001",
  "total": 0.87,
  "components": {
    "query_match": 0.80,
    "orientation": 1.00,
    "resolution": 1.00,
    "duration_fit": 0.90,
    "duplicate_penalty": 0.00
  },
  "ranker_version": "rules-v1"
}
```

Scoring must be explainable.

Do not let an opaque AI score be the only selection criterion in MVP.

## 8. Downloaded asset

```json
{
  "asset_id": "asset_01J...",
  "candidate_id": "pexels:123456",
  "local_path": "sources/scene_001_pexels_123456.mp4",
  "sha256": "...",
  "bytes": 10293847,
  "probe": {
    "duration_seconds": 8.42,
    "width": 1080,
    "height": 1920,
    "fps": 30.0,
    "video_codec": "h264",
    "has_audio": false
  }
}
```

## 9. Source manifest

```json
{
  "schema_version": "1.0",
  "project_id": "20260812-kiper-neuer-abc123",
  "assets": [
    {
      "scene_id": "scene_001",
      "asset_id": "asset_01J...",
      "provider": "pexels",
      "provider_asset_id": "123456",
      "source_page_url": "https://...",
      "contributor_name": "Example",
      "query": "amateur soccer goalkeeper confident",
      "rights_status": "PROVIDER_LICENSED",
      "downloaded_at": "2026-08-12T05:50:00+07:00",
      "local_path": "sources/scene_001_pexels_123456.mp4",
      "sha256": "..."
    }
  ]
}
```

## 10. Edit strategy proposal

```json
{
  "schema_version": "1.0",
  "strategy_id": "strategy_01J...",
  "project_id": "20260812-kiper-neuer-abc123",
  "strategy_text": "Open on ...",
  "status": "PENDING_APPROVAL",
  "created_at": "...",
  "approved_at": null,
  "approved_by": null
}
```

## 11. Pipeline event

```json
{
  "run_id": "run_01J...",
  "project_id": "...",
  "from_state": "ASSETS_SELECTED",
  "to_state": "EDIT_BRIEF_READY",
  "timestamp": "...",
  "metadata": {}
}
```

## 12. Schema evolution

Rules:

- every persisted JSON has `schema_version`;
- new optional fields may be backwards-compatible;
- breaking field changes require schema-version bump;
- migrations must be explicit;
- no "best guess" loading of incompatible versions.
