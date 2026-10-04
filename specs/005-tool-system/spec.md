# 005 - Tool System

        ## Status

        Approved for v0.1 implementation (2026-10-04, see `docs/decisions.md` Decision 0006).

        ## Goal

        Define how Galliani registers, validates, authorizes, executes, and observes tools.

        ## Non-goals

        - Implementing every possible tool.
- Bypassing user permission policy.
- Treating tool output as trusted instruction.

        ## Requirements

        1. Every tool must be registered with input and output schemas.
2. Every tool must declare permission level and side-effect category.
3. Tool input must be validated before execution.
4. Tool output must be normalized as a ToolResult.
5. Tool observations must be recorded in Task State.

        ## Behavior

        - The execution engine requests a tool call.
- The permission system approves, denies, or asks the user.
- The tool system validates arguments and executes the call.
- The tool result is normalized and returned to the supervisor.

        ## Interfaces and Data Contracts

        - `ToolDefinition`: name, description, input_schema, output_schema, permission_level, side_effects, timeout_ms.
- `ToolCall`: tool_name, call_id, arguments, idempotency_key, requested_by_step.
- `ToolResult`: call_id, status, data, error, observation_summary, artifacts, metadata.
- `ToolError`: code, message, retryable, safe_summary.

        ## Error Handling

        - Schema validation errors prevent execution.
- Timeouts return retryable or non-retryable errors according to tool policy.
- Permission denial returns a safe blocked result.
- Tool crashes are normalized without leaking sensitive internals.

        ## Security

        - Restricted tools require explicit permission.
- Tool arguments and results must be redacted before logs and UI.
- Tool outputs are untrusted data until interpreted by the supervisor.

        ## Acceptance Criteria

        ### Schema Validation

Given a tool call has invalid arguments

When execution is requested

Then the tool is not run and a validation error is returned.

### Permission Required

Given a destructive tool is requested

When no approval exists

Then the system asks for permission and pauses execution.

### Tool Success

Given a valid approved tool call

When the tool runs

Then a structured ToolResult and observation are produced.

        ## Tests

        - Unit tests for registry lookup.
- Schema validation tests.
- Permission boundary integration tests.
- Tool failure normalization tests.

        ## Evaluation

        - Tool call success rate on fixtures.
- Invalid call rejection rate must be 100%.
- Permission bypass count must be zero.

        ## Implementation Tasks

        - [x] Define tool registry interface.
- [x] Define ToolCall and ToolResult contracts.
- [x] Integrate permission checks.
- [x] Add timeout and error normalization.

        ## Dependencies

        Depends on `000-foundation`, `002-task-state`, and `009-permissions`.
