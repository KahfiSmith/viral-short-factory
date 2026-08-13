# 09 — Command Code Workflow

This document defines how to build VSF using Command Code.

## 1. Open the project

```bash
cd viral-shorts-factory
cmd
```

Command Code should read the project `AGENTS.md`.

Do not run `/init` if the provided `AGENTS.md` is already present and correct.

## 2. Verify skills

Inside Command Code:

```text
/skills
```

Expected project skills:

```text
viral-shorts-factory
footage-finder
```

The project-local skill source is:

```text
.commandcode/skills/
```

## 3. Verify custom agents

```text
/agents
```

Expected:

```text
vsf-architect
footage-engineer
video-use-integrator
qa-auditor
security-auditor
```

Names intentionally avoid Command Code reserved names such as:

```text
explore
plan
review
general
```

## 4. Planning a milestone

Use Command Code's plan mode before implementation:

```text
/plan Read AGENTS.md and docs/05-IMPLEMENTATION-PLAN.md. Inspect the repository and plan only Milestone 1. Do not modify upstream video-use. Include files, tests, risks, and acceptance checks.
```

Alternative from shell:

```bash
cmd --plan
```

Then enter the same task.

## 5. Implement after reviewing the plan

```text
/goal Implement the approved Milestone 1 plan only. Run tests, lint, and type checks. Report acceptance evidence and stop before Milestone 2.
```

`/goal` is suitable for autonomous progress toward one bounded objective.

## 6. Delegate specialist review

The primary Command Code session may delegate based on agent descriptions.

You can also explicitly ask:

```text
Use the vsf-architect custom agent to review the current architecture against docs/02-ARCHITECTURE.md.
```

For provider work:

```text
Use the footage-engineer agent to implement the current provider milestone exactly as documented.
```

For video-use bridge:

```text
Use the video-use-integrator agent to review the handoff design. Upstream video-use must remain untouched.
```

For completion:

```text
Use qa-auditor and security-auditor to review this milestone before we mark it complete.
```

## 7. Skill invocation

Command Code exposes installed/enabled skills in the slash menu.

Example:

```text
/viral-shorts-factory Create/validate the production artifacts for this project but do not bypass edit-strategy approval.
```

Or inline:

```text
Follow /footage-finder while implementing the asset search stage.
```

## 8. Recommended build loop

For every milestone:

```text
READ
-> /plan
-> user reviews plan
-> /goal
-> implementation
-> tests/lint/typecheck
-> specialist review
-> acceptance evidence
-> STOP
```

Then start a new plan for the next milestone.

This keeps the agent from silently expanding scope.

## 9. video-use installation model

Treat `video-use` as an upstream external dependency.

Development layout:

```text
~/Developer/video-use/
~/Developer/viral-shorts-factory/
```

Command Code supports installing Agent Skills from GitHub, but VSF implementation should not assume an install command succeeded merely because a repository exists.

During Milestone 0, verify the actual installed `video-use` skill/workflow in the target environment and run a real smoke test.

If using a project-local Command Code skill installation, preserve the complete upstream skill folder and helper files required by video-use.

Never reduce video-use to only its `SKILL.md` if its workflow depends on adjacent helpers.

## 10. Workspace access

If `video-use` or shared media lives outside the current repo and Command Code needs filesystem context, use an explicit supported workspace mechanism such as:

```bash
cmd --add-dir ~/Developer/video-use
```

when appropriate.

Do not give write access conceptually to upstream merely because it was added to context. The project instruction remains: read/use upstream, do not modify it.

## 11. Non-interactive automation

Command Code supports print/non-interactive sessions, but do not use zero-review automation for the upstream edit-strategy approval gate in MVP.

CI-like review examples can use:

```bash
cmd -p "Review this milestone against AGENTS.md and docs/06-TESTING-ACCEPTANCE.md"
```

Implementation autonomy must still follow project safety and approval boundaries.

## 12. Definition of complete

The agent must report:

- milestone implemented;
- exact test/lint/type commands run;
- outputs;
- acceptance criteria evidence;
- remaining limitations;
- whether upstream video-use remained clean.

No evidence = not complete.
