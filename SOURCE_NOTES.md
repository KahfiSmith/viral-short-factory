# Source Notes — Verified 2026-08-12

These external behaviors were checked while preparing this design package.

## browser-use/video-use

Repository:
https://github.com/browser-use/video-use

Relevant current behavior:

- raw footage is placed in a user project directory;
- session outputs live under the user's `<videos_dir>/edit/`;
- pipeline is transcript/LLM/EDL/render/self-eval oriented;
- current SKILL.md marks strategy confirmation before execution as a hard rule;
- current install guidance supports skill registration/symlink for Claude Code;
- ffmpeg is required;
- yt-dlp is described as optional for online sources.

Always re-check upstream docs during implementation because upstream can change.

## Pexels

Documentation:
https://www.pexels.com/api/documentation/

Current video search path documented as:

```text
GET https://api.pexels.com/v1/videos/search
```

Supported search fields include query, orientation, size, locale, page, and per_page.

## Pixabay

Documentation:
https://pixabay.com/api/docs/

Current video endpoint:

```text
GET https://pixabay.com/api/videos/
```

Important current documentation notes include:

- JSON API;
- default rate limit is documented per key;
- API requests must be cached for 24 hours;
- systematic mass downloads are not allowed.

## YouTube Data API

Documentation:
https://developers.google.com/youtube/v3/docs/videos/list

Current API documents:

```text
videos.list
chart=mostPopular
regionCode=<region>
videoCategoryId=<category>
```

Use this as a trend signal. The design intentionally does not call it a Shorts-only trending endpoint.

## Anthropic Claude Code

Documentation:
https://docs.anthropic.com/en/docs/claude-code/

Claude Code operates in the project/terminal context and can perform coding and shell workflows. This package intentionally keeps implementation contracts agent-agnostic where possible.


## Command Code — verified for this package

Documentation:
https://commandcode.ai/docs

Memory:
https://commandcode.ai/docs/core-concepts/memory

Skills:
https://commandcode.ai/docs/skills

Custom Agents:
https://commandcode.ai/docs/core-concepts/custom-agents

CLI:
https://commandcode.ai/docs/reference/cli

Current documented behaviors used by this package:

- project memory: `./AGENTS.md` or `./.commandcode/AGENTS.md`;
- project skills: `.commandcode/skills/<skill-name>/SKILL.md`;
- project custom agents: `.commandcode/agents/*.md`;
- `/skills` opens installed skills;
- `/agents` manages custom agents;
- `/plan <task>` enters/plans in plan mode;
- `/goal <objective>` sets an autonomous goal;
- `cmd` starts an interactive session;
- `cmd --plan` starts plan mode;
- `cmd --add-dir <directory>` adds workspace context;
- reserved custom-agent names include `explore`, `plan`, `review`, and `general`.

The package uses Command Code as the primary coding harness.
