# Memory

Applies to the main agent in Claude Code. Uses the `claude-memory:structured-memory` skill. See `AGENTS.md` "Working Memory" for the project rules; this file is the short operating version.

## Recall: before responding

Check memory when the message involves past decisions, preferences, system knowledge or prior work ("last time", "we decided"). Read the `MEMORY.md` index, scan descriptions, load only matching files. Skip when the topic is already fully in context.

## Remember: after responding

1. Did this exchange contain a user directive, a reasoning conclusion or a durable fact? If not, stop.
2. Does an overlapping memory exist? Update it; if it contradicts, replace it; otherwise create a new file.
3. Is it worth storing? Multi-source synthesis or user context that search cannot recover: yes. A single-query fact or something the repo already records: no.

Follow the format already used in the memory directory (frontmatter with `name`, `description` and `metadata.type` of `user`, `feedback`, `project` or `reference`). For `feedback` and `project`, add **Why:** and **How to apply:** lines. After any change, update the one-line entry in `MEMORY.md`.

## Never save

- Secrets, API keys, tokens, prompts containing credentials, or hidden reasoning.
- Code, architecture, specs, decisions or history that the repo already records.
- Debugging fixes and details that only matter in the current session.

## Subagents

Subagents never write memory. They list `Memory:` candidates in their handoff; the main agent decides.
