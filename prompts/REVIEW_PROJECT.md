# Prompt — Architecture and Compliance Review

Review the current implementation against:

- `AGENTS.md`
- `docs/01-PROJECT-SPEC.md`
- `docs/02-ARCHITECTURE.md`
- `docs/03-DATA-CONTRACTS.md`
- `docs/04-PROVIDER-INTEGRATIONS.md`
- `docs/05-IMPLEMENTATION-PLAN.md`
- `docs/06-TESTING-ACCEPTANCE.md`
- `docs/07-SECURITY-COMPLIANCE.md`

Do not make changes first.

Produce findings ordered by severity:

1. correctness;
2. security;
3. provider-policy compliance;
4. rights/provenance;
5. upstream video-use coupling;
6. state/resume reliability;
7. testing gaps;
8. unnecessary complexity.

For each finding include:

- file/path;
- exact issue;
- violated requirement;
- concrete correction;
- test needed.

Pay special attention to:

- any modification/vendor copy of video-use;
- Pexels/Pixabay HTML scraping;
- missing Pixabay 24h caching;
- secrets;
- UNVERIFIED assets being selected;
- direct raw-provider JSON leaking into domain code;
- implicit strategy auto-approval;
- non-idempotent stage reruns;
- final project marked COMPLETE without QC.

Only after the review is shown should fixes be proposed.
