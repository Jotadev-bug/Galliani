# Security

Galliani security starts from explicit boundaries.

## Core Rules

- Do not expose chain-of-thought or hidden reasoning.
- Do not store secrets in Task State, Memory, logs, or artifacts.
- Do not execute tools without schema validation.
- Do not perform destructive actions without permission.
- Do not trust model output as executable instruction.
- Do not trust external documents as instructions unless the user explicitly elevates them.

## Prompt and Context Safety

User requests are instructions. Referenced documents, web pages, tool outputs, and prior conversation excerpts are data unless explicitly promoted by the user.

## Provider Safety

Provider adapters must redact secrets and normalize errors. Provider-specific reasoning fields must be discarded or sealed before they reach logs, APIs, UI, or memory.

## Tool Safety

Every tool call must pass:

1. Schema validation.
2. Permission check.
3. Execution boundary check.
4. Result normalization.
5. Sensitive data redaction.

Accept-edits mode (spec 014) only replaces the user's prompt for `write`-level tools declared as workspace edits (`write_file`, `write_files`). Path validation, symlink checks and protected names still run first. Deletes, network, spending and memory writes always ask. Only the user can turn the mode on, for one task at a time, and every write it allows is recorded as a permission decision and event.

## Auditability

Galliani should record what action occurred, why it was allowed, and what result was observed. Audit entries must be useful without revealing private reasoning.
