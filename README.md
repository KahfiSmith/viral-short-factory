# Viral Shorts Factory — Command Code Build Documentation

Status: **implementation-ready design/specification package**
Primary coding harness: **Command Code (`cmd`)**
Primary language: **Python 3.11+**
Editing engine: **browser-use/video-use (upstream, untouched)**

## 1. Goal

`viral-shorts-factory` is the orchestration layer that turns a short-form content brief into a prepared video project:

```text
brief
-> concept
-> script
-> storyboard
-> footage discovery
-> ranking/download/provenance
-> edit brief
-> video-use
-> edit strategy approval
-> render
-> QC
-> final package
```

`video-use` remains the editing engine. It is not the entry point of the finished product.

Correct dependency direction:

```text
Command Code
     |
     v
viral-shorts-factory
     |
     v
video-use
     |
     v
final.mp4
```

Never reverse it.

---

## 2. Native Command Code layout

This package is designed around Command Code's project-level memory, skills, and custom agents:

```text
viral-shorts-factory/
├── AGENTS.md
├── README.md
├── docs/
│   ├── 01-PROJECT-SPEC.md
│   ├── 02-ARCHITECTURE.md
│   ├── 03-DATA-CONTRACTS.md
│   ├── 04-PROVIDER-INTEGRATIONS.md
│   ├── 05-IMPLEMENTATION-PLAN.md
│   ├── 06-TESTING-ACCEPTANCE.md
│   ├── 07-SECURITY-COMPLIANCE.md
│   ├── 08-OPERATIONS.md
│   └── 09-COMMANDCODE-WORKFLOW.md
├── .commandcode/
│   ├── AGENTS.md
│   ├── agents/
│   │   ├── vsf-architect.md
│   │   ├── footage-engineer.md
│   │   ├── video-use-integrator.md
│   │   ├── qa-auditor.md
│   │   └── security-auditor.md
│   └── skills/
│       ├── viral-shorts-factory/
│       │   └── SKILL.md
│       └── footage-finder/
│           └── SKILL.md
├── prompts/
│   ├── COMMANDCODE_START.md
│   ├── COMMANDCODE_PLAN.md
│   ├── COMMANDCODE_GOAL.md
│   ├── BUILD_PROJECT.md
│   ├── PHASE_1_MVP.md
│   └── REVIEW_PROJECT.md
└── examples/
```

Command Code natively discovers project-level skills from `.commandcode/skills/` and custom agents from `.commandcode/agents/`.

---

## 3. First use

Place these docs in the root of your new project repository.

Then:

```bash
cd viral-shorts-factory
cmd
```

Inside Command Code:

```text
/skills
```

Confirm these project skills are visible:

```text
viral-shorts-factory
footage-finder
```

Then:

```text
/agents
```

Confirm the custom project agents are visible.

Start architecture/build planning:

```text
/plan Read AGENTS.md and all docs under docs/. Build only the first incomplete milestone from docs/05-IMPLEMENTATION-PLAN.md. Do not modify upstream video-use.
```

After reviewing the plan:

```text
/goal Implement only the approved current milestone. Run tests, lint, and type checks before declaring completion. Stop when this milestone is verified.
```

Detailed usage is in `docs/09-COMMANDCODE-WORKFLOW.md`.

---

### Quick Start (All-in-One Asset Collector)

To generate a project workspace and collect 8 video + 3 photo assets per scene in one step:

```bash
uv run vsf generate --topic "<YOUR_TOPIC>" --profile facts
```

With custom `script.json`:

```bash
uv run vsf generate --topic "<YOUR_TOPIC>" --profile facts --script /path/to/script.json
```

---

## 4. Command Code project memory

`AGENTS.md` is the authoritative project instruction file.

A mirrored/short project memory also exists at:

```text
.commandcode/AGENTS.md
```

The root file is intentionally the main source of truth.

Do not run `/init` after copying this package if it would overwrite the existing root `AGENTS.md`.

---

## 5. Skills vs custom agents

### Skills

Use skills for reusable workflow knowledge:

```text
.commandcode/skills/viral-shorts-factory/
.commandcode/skills/footage-finder/
```

They can be invoked from Command Code as slash skills when enabled.

### Custom agents

Use custom agents for delegated specialist work:

```text
vsf-architect
footage-engineer
video-use-integrator
qa-auditor
security-auditor
```

Reserved Command Code agent names such as `explore`, `plan`, `review`, and `general` are intentionally not used.

---

## 6. video-use integration rule

Do **not** copy custom VSF code into `browser-use/video-use`.

Recommended development layout:

```text
~/Developer/
├── video-use/
└── viral-shorts-factory/
```

`video-use` is external/upstream.

The VSF bridge prepares a project directory and an editing brief, then Command Code invokes/uses the `video-use` skill/workflow against that project.

The MVP preserves the upstream edit-strategy confirmation gate:

```text
EDIT_STRATEGY_PROPOSED
-> AWAITING_EDIT_STRATEGY_APPROVAL
-> human approval
-> EDITING
```

Do not silently auto-approve it.

---

## 7. Footage discovery rule

Default footage discovery:

```text
local verified asset library
-> Pexels API
-> Pixabay API
```

Use official APIs, not HTML scraping.

Do not make YouTube/TikTok/Instagram ripping a default or fallback.

Every selected file must have provenance in `source_manifest.json`.

---

## 8. Recommended first build sequence

```text
Milestone 0: verify upstream video-use
Milestone 1: scaffold + CLI
Milestone 2: SQLite state/cache
Milestone 3: Pexels adapter
Milestone 4: Pixabay adapter
Milestone 5: local asset library
Milestone 6: storyboard/query planning
Milestone 7: ranking
Milestone 8: downloader + provenance
Milestone 9: edit brief
Milestone 10: video-use bridge
Milestone 11: QC
Milestone 12: metadata
Milestone 13: optional trend signals
Milestone 14: hardening
```

Do not ask Command Code to implement all milestones in one unreviewed run.

---

## 9. Start prompt

Open `prompts/COMMANDCODE_START.md` and paste it into a fresh `cmd` session.

For implementation planning use `prompts/COMMANDCODE_PLAN.md`.

For implementation execution use `prompts/COMMANDCODE_GOAL.md`.

---

## 10. External references

- Command Code docs: https://commandcode.ai/docs
- Command Code memory: https://commandcode.ai/docs/core-concepts/memory
- Command Code skills: https://commandcode.ai/docs/skills
- Command Code custom agents: https://commandcode.ai/docs/core-concepts/custom-agents
- Command Code CLI: https://commandcode.ai/docs/reference/cli
- video-use: https://github.com/browser-use/video-use
- Pexels API: https://www.pexels.com/api/documentation/
- Pixabay API: https://pixabay.com/api/docs/
- YouTube Data API: https://developers.google.com/youtube/v3/docs/videos/list
