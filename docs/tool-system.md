# Tool System

Tools are explicit capabilities, not arbitrary side effects.

## Tool Registry

Every tool must define:

- Name.
- Description.
- Input schema.
- Output schema.
- Permission level.
- Timeout.
- Idempotency behavior.
- Failure modes.

## Tool Call Lifecycle

1. Supervisor proposes a tool call.
2. Permission system checks whether approval is required.
3. Input is validated against the schema.
4. Execution engine invokes the tool.
5. Tool returns a structured result.
6. Observation is recorded.
7. Verification decides whether the result satisfies the plan step.

## Tool Result Contract

Tool results should include:

- `status`.
- `data`.
- `error`.
- `observation`.
- `artifacts`.
- `metadata`.

## Safety

Destructive, external, or costly actions require explicit permissions. Tool logs must redact secrets and must not contain hidden reasoning.
