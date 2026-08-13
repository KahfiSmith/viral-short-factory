# 04 — Provider Integrations

## Design principle

Provider logic is isolated behind adapters.

Application/domain code must consume normalized candidates, not raw provider JSON.

---

# 1. Local asset library

Priority: **1**

Search local assets before network providers.

Minimum index fields:

```text
asset_id
local_path
sha256
category
tags
width
height
duration
orientation
provider
provider_asset_id
source_page_url
rights_status
created_at
last_used_at
use_count
```

Local reuse is allowed only when provenance is still known.

A file copied into the library without provenance becomes `UNVERIFIED` unless explicitly marked `USER_OWNED`.

---

# 2. Pexels provider

Priority: **2**

Use official API.

Base:

```text
https://api.pexels.com
```

Video search:

```text
GET /v1/videos/search
```

Auth:

```text
Authorization: ${PEXELS_API_KEY}
```

Recommended Shorts request:

```text
query=<scene query>
orientation=portrait
size=medium
locale=en-US
per_page=20
```

`id-ID` may be used where Indonesian queries perform better, but search-query generation should generally create English visual queries as well.

### Pexels adapter responsibilities

1. construct request;
2. set timeout;
3. parse response;
4. choose available MP4 variants;
5. normalize dimensions/duration/URLs;
6. store provider asset ID and source page;
7. return `AssetCandidate`;
8. never leak API key to logs.

### Do not

- scrape Pexels HTML;
- assume the first returned video is best;
- discard contributor/source fields;
- hard-code old/deprecated video API paths.

---

# 3. Pixabay provider

Priority: **3**

Use official video endpoint:

```text
GET https://pixabay.com/api/videos/
```

Parameters can include:

```text
key
q
lang
video_type
category
min_width
min_height
editors_choice
safesearch
order
page
per_page
```

Recommended:

```text
category=sports
safesearch=true
order=popular
```

when compatible with the scene.

## Mandatory cache behavior

Pixabay documentation requires API requests to be cached for 24 hours.

Implement a cache key from:

```text
provider + endpoint + normalized query parameters
```

Example:

```text
sha256("pixabay|videos|q=goalkeeper&category=sports&...")
```

Store:

```text
response_json
fetched_at
expires_at
http_status
```

Before network request:

```text
if cache entry exists AND now < expires_at:
    return cached response
```

## Download limits

Do not build "download all results".

Default:

```yaml
search_results_per_query: 20
preview_candidates_per_scene: 8
download_candidates_per_scene: 2
selected_assets_per_scene: 1
```

Provider-specific limits override global limits when stricter.

---

# 4. YouTube trend provider

Purpose:

**topic/format inspiration only** in MVP.

Official endpoint family:

```text
GET https://www.googleapis.com/youtube/v3/videos
```

Typical seed:

```text
part=snippet,statistics,contentDetails
chart=mostPopular
regionCode=ID
videoCategoryId=17
```

Current official API supports `chart=mostPopular`, region filtering, and category filtering.

## Important semantic constraint

Do not name the resulting field:

```text
shorts_trending
```

unless the system has actually established that each record is a Short.

Use:

```text
popular_video_signals
```

or:

```text
youtube_popular_sports_signals
```

The service is a trend-signal provider, not a stock-footage provider.

Do not download video from these results as part of the stock-footage pipeline.

---

# 5. Provider registry

Configuration:

```yaml
providers:
  local:
    enabled: true
    priority: 10

  pexels:
    enabled: true
    priority: 20
    api_key_env: PEXELS_API_KEY

  pixabay:
    enabled: true
    priority: 30
    api_key_env: PIXABAY_API_KEY
    cache_ttl_hours: 24
```

Lower number = earlier search priority, or choose the opposite convention once and document it.

Never infer precedence from Python dictionary ordering.

---

# 6. Error policy

### Retryable

- connection reset;
- DNS transient;
- 429 with valid retry guidance;
- 5xx.

### Permanent for request

- invalid API key;
- malformed request;
- unsupported query;
- explicit provider rejection.

Retries:

```text
max_attempts: 3
bounded exponential backoff
jitter
```

No infinite loops.

---

# 7. Search strategy

Each scene should have multiple semantic query variants.

Example visual intent:

```text
amateur football goalkeeper confidently walking onto pitch
```

Generated queries:

```text
amateur soccer goalkeeper confident
goalkeeper walking football field
football goalkeeper cinematic walk
```

Search local first.

Then query provider adapters until enough viable candidates exist.

Do not continue calling providers once the scene's configured viable-candidate target has been satisfied unless diversity requires it.

---

# 8. Candidate deduplication

Primary:

```text
provider + provider_asset_id
```

After download:

```text
sha256
```

Perceptual video deduplication is future scope.

---

# 9. Rights/provenance gate

Before selection:

```text
rights_status != UNVERIFIED
rights_status != REJECTED
source_page_url is present when provider supplies one
provider_asset_id is present
```

If none of the candidates passes, the scene becomes:

```text
NEEDS_ASSET_REVIEW
```

Do not silently fill it with an unknown clip.
