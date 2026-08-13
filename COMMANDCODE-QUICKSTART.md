# Command Code Quickstart

## 1. Copy this documentation package into the root of your VSF repository.

Expected:

```text
AGENTS.md
README.md
docs/
.commandcode/
prompts/
examples/
```

## 2. Enter project

```bash
cd viral-shorts-factory
cmd
```

## 3. Confirm memory

Do not run `/init` if the supplied `AGENTS.md` is already present.

Use:

```text
/memory
```

if you want to inspect project memory.

## 4. Confirm skills

```text
/skills
```

Expected:

- viral-shorts-factory
- footage-finder

## 5. Confirm agents

```text
/agents
```

Expected:

- vsf-architect
- footage-engineer
- video-use-integrator
- qa-auditor
- security-auditor

## 6. First prompt

Paste `prompts/COMMANDCODE_START.md`.

## 7. First plan

Paste:

```text
/plan Read AGENTS.md and docs/05-IMPLEMENTATION-PLAN.md. Plan only Milestone 0 first: verify upstream video-use without modifying it.
```

After Milestone 0 succeeds, plan Milestone 1.

## 8. Build milestone

After you approve the plan:

```text
/goal Implement only the approved current milestone. Verify it fully and stop before the next milestone.
```
