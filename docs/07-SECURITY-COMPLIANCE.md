# 07 — Security, Rights, and Provider Compliance

## 1. Secrets

Environment variables:

```text
PEXELS_API_KEY
PIXABAY_API_KEY
YOUTUBE_API_KEY
ELEVENLABS_API_KEY
```

Not every key is mandatory for every phase.

Rules:

- `.env` is gitignored;
- `.env.example` contains names only;
- redact Authorization headers;
- never serialize keys into project JSON;
- never expose keys in stack traces/log output.

## 2. Download safety

For each external download:

1. HTTPS only;
2. validate hostname against provider-returned URL policy where practical;
3. timeout;
4. maximum bytes;
5. stream to temporary file;
6. compute checksum;
7. inspect with ffprobe;
8. atomic rename only after successful validation.

Never blindly execute downloaded content.

## 3. Filesystem safety

- sanitize filenames;
- reject `..`;
- resolve destination under configured project root;
- never allow provider metadata to choose arbitrary filesystem paths;
- sources immutable after ingest.

## 4. Rights and provenance

The system is not a copyright oracle.

It records provider/source assertions and blocks assets whose status is unknown.

MVP default sources:

- user-owned local footage;
- Pexels via official API;
- Pixabay via official API.

Do not implement social-video downloading as a silent fallback.

## 5. Pixabay constraints

Provider adapter must enforce or document:

- 24-hour API-response caching;
- no systematic mass downloads;
- bounded result/download counts.

## 6. Pexels

Use official API and preserve provider/source/contributor information available in the API response.

The product UI, if added later, must follow provider attribution/link requirements applicable to API use.

## 7. Trend vs footage

A trend source is not automatically a footage source.

For example:

```text
YouTube popular video
```

may inform:

```text
topic = football comedy
format = expectation/reality
```

but must not automatically become:

```text
download this copyrighted broadcast clip
```

## 8. Content safety

At project-policy level, allow future profile rules to block:

- sexual content;
- graphic violence;
- illegal activity promotion;
- dangerous challenge encouragement;
- deceptive impersonation.

This is separate from media-provider safe-search flags.

## 9. Audit log

Persist meaningful events:

```text
asset searched
asset selected
asset downloaded
asset rejected
strategy proposed
strategy approved
edit invoked
QC passed/failed
```

Do not audit raw secret headers.

## 10. Dependency security

- pin/lock dependencies;
- use official package sources;
- review subprocess command construction;
- no shell interpolation from untrusted provider text;
- pass subprocess arguments as arrays where possible.

## 11. Upstream update policy

`video-use` is external.

Pin a known-good commit/tag in production automation if stability matters.

Update intentionally:

1. pull/update upstream;
2. read upstream changelog/docs/diff;
3. run VSF integration test;
4. update compatibility notes;
5. only then promote.

Do not automatically track upstream `main` in unattended production.
