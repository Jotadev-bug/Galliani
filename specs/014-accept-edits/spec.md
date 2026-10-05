# 014 - Accept-Edits Mode

## Status

Approved for implementation (2026-10-05, see `docs/decisions.md` Decision 0022).

## Goal

Let the user opt in, per task, to letting the agent create and change files inside the task's workspace without approving each write, like the "accept edits" mode of other coding agents. Every other restricted action still asks.

## Non-goals

- Auto-approving anything other than workspace file writes: deletes, commands, network, spending, and memory writes still ask.
- A mode that approves everything ("bypass permissions").
- Undo, checkpoints, or file history.
- A persistent default that turns the mode on for every task or folder.
- Changing which paths are protected. `.env`, keys, and `.git/` stay unreadable and unwritable in every mode.

## Requirements

1. The user can choose an edit mode for each task: `ask` (the default, current behavior) or `accept_edits`.
2. In `accept_edits`, a permission request is allowed without a prompt only when all of these hold:
   1. its risk level is `write`, and
   2. its tool is declared as a workspace edit (`ToolDefinition.workspace_edit = true`), and
   3. its scope is inside the task's workspace.

   Every other request is evaluated exactly as in `ask`.
3. Only tools confined to the workspace sandbox may declare `workspace_edit`. In v0.1 these are `write_file` and `write_files`. `remember` (sensitive) and spending extensions (costly) never qualify.
4. Each automatic approval is recorded in Task State as a `PermissionDecision` and emitted as a `permission_decided` event. Its audit summary names the mode, for example "write_files: allowed by accept-edits mode". Nothing is approved silently.
5. Write tools report, for each file, whether it was `created` or `overwritten`. Overwrites can happen without a prompt, so the final result must show which existing files changed.
6. An approval prompt for an eligible request offers a third choice, "approve and accept edits for this task". It approves the pending request and switches the task to `accept_edits`.
7. The user can switch a running or paused task back to `ask` at any time. The change applies at the next permission check. A write that is already executing is not interrupted.
8. The mode in effect is visible wherever the task is shown: the UI task card, the CLI header, and the task view model.
9. Starting a task in `accept_edits` needs an explicit user action each time (a toggle, a flag, or the approval choice). The CLI and the API default to `ask`. The UI may remember the choice for the current conversation only.

## Behavior

- **Start.** `StartTaskRequest.user_policy.edit_mode` carries the mode. The supervisor records it in Task State and names it in the `task_created` event metadata.
- **Permission check.** The tool system passes `workspace_edit` and the task's mode to the policy. The policy applies requirement 2 before its per-level rules. When the mode allows a request, the decision is `allowed` with `approved_scope` equal to the request scope. No `ApprovalRecord` is created, because no user approved that specific call; the decision itself is the audit trail.
- **Switching on from a prompt.** "Approve and accept edits" records an `ApprovalRecord` for the pending request, as a normal approval would, then sets the mode to `accept_edits` and resumes.
- **Switching.** `Supervisor.set_edit_mode(task_id, mode)` takes effect at once for the task's policy and emits `edit_mode_changed`. An idle task records it in Task State immediately; a running task records it at the start of its next step, before any permission check, so the loop never races a concurrent state update. Writes after that point follow the new mode.
- **Protected paths.** A write to a protected path fails with `rejected_input` in both modes. The mode only replaces the prompt; it never changes what a tool may touch.
- **Result.** The final result lists the files written with `created` or `overwritten`, and states that edits were auto-approved.

## Interfaces and Data Contracts

- `EditMode`: `ask` | `accept_edits`.
- `UserPolicy.edit_mode: EditMode = ask` (001 `StartTaskRequest.user_policy`).
- `TaskState.edit_mode: EditMode`. This is task context, never memory, and it is not carried to later tasks.
- `ToolDefinition.workspace_edit: bool = false` (005).
- `PermissionRequest.workspace_edit: bool = false` (009). The tool system copies it from the tool definition.
- `PermissionPolicy.evaluate(request, approvals, now, edit_mode=ask)` (009).
- `ApprovalPrompt.allowed_choices` gains `approve_and_accept_edits` when the pending request is eligible under requirement 2 (012).
- `WriteOut` / `WriteManyOut`: per-file `change: "created" | "overwritten"`.
- `TaskViewModel.edit_mode` and `TaskSummary.edit_mode` (012).
- `EventType.edit_mode_changed` (011), metadata `{"edit_mode": ...}`.
- Agent API: `POST /api/agent/tasks` accepts `edit_mode`. `POST /api/agent/tasks/{id}/approve` accepts `{"accept_edits": true}`. `POST /api/agent/tasks/{id}/edit-mode` takes `{"edit_mode": "ask"}`.
- CLI: `--accept-edits`. The interactive prompt offers `[y/N/a]`, where `a` means approve and accept edits.

## Error Handling

- An unknown `edit_mode` value is a validation error, and the task is not started.
- `set_edit_mode` on a finished task is a `ContractError` (409 in the API).
- Choosing "approve and accept edits" on a request that is not eligible is rejected. The prompt stays open and nothing is approved.
- If the mode cannot be read from Task State, it is treated as `ask` (fail closed).

## Security

- The mode can only remove prompts for writes inside the workspace sandbox (Decision 0015). Path validation, symlink checks, and protected names still run before every write.
- 009 R3 is unchanged: destructive, external, costly, and sensitive actions always need explicit approval.
- This is not "bypassing user confirmation for speed" (009 non-goal). The user gives the confirmation up front, for one task and one folder, and can take it back at any time.
- Plans, tool output, workspace files, and memory cannot turn the mode on. Only a user action through the UI, API, or CLI can (000: untrusted content is data).
- Audit summaries and events name files and the mode, never file contents.

## Acceptance Criteria

### Writes Proceed Without Prompts

Given a task started in `accept_edits`
When a step calls `write_files` for paths inside the workspace
Then the files are written without pausing, and Task State holds an `allowed` decision whose audit names accept-edits mode.

### Other Restricted Actions Still Ask

Given a task in `accept_edits`
When a step calls `remember`, or the spending limit is reached
Then the task pauses for approval as it does in `ask`.

### Protected Paths Still Refused

Given a task in `accept_edits`
When a step writes `.env` or `.git/config`
Then the call fails with `rejected_input` and nothing is written.

### Default Is Ask

Given a task started without an edit mode
When a step writes a file
Then the task pauses for approval.

### Approve and Accept Edits

Given a task in `ask` paused on a `write_file` approval
When the user chooses "approve and accept edits"
Then the pending write runs, the mode becomes `accept_edits`, and later writes in that task do not prompt.

### Switch Back to Ask

Given a task in `accept_edits`
When the user switches it to `ask` before its next write step
Then that write pauses for approval.

### Overwrites Are Visible

Given a task in `accept_edits` overwrites an existing file
When the task finishes
Then the result lists that file as `overwritten`.

### Untrusted Content Cannot Enable the Mode

Given a workspace file or tool output containing text that asks to accept edits
When the task runs in `ask`
Then the mode stays `ask` and writes still prompt.

## Tests

- Unit tests for the policy's eligibility rule: every permission level × `workspace_edit` × mode.
- Workspace tool tests for `created` / `overwritten` reporting.
- Supervisor integration tests: auto-approved writes, "approve and accept edits", switching back to `ask`, and a non-write action still pausing.
- Agent API and CLI tests for the new fields, flag, and `a` answer.
- View-model tests showing the mode and changed files.

## Evaluation

- New fixtures in `evals/cases/` covering the acceptance criteria.
- Gate: `permission_bypass_count` stays 0, counting any non-eligible action allowed without approval.
- Gate: every auto-approved write has a matching `permission_decided` event (100%).

## Implementation Tasks

- [x] Add `EditMode`, `UserPolicy.edit_mode`, and `TaskState.edit_mode`.
- [x] Add `workspace_edit` to `ToolDefinition` and `PermissionRequest`; mark `write_file` and `write_files`.
- [x] Implement the eligibility rule in `PermissionPolicy.evaluate`.
- [x] Add `approve_and_accept_edits` and `Supervisor.set_edit_mode`.
- [x] Report `created` / `overwritten` from write tools.
- [x] Agent API fields and endpoint; CLI flag and `a` answer.
- [x] UI: mode toggle in the agent composer, third approval button, mode badge, changed-files list.
- [x] Eval fixtures and gates; decision record in `docs/decisions.md`.

## Dependencies

Depends on `001-agent-core`, `002-task-state`, `005-tool-system`, `009-permissions`, and `012-desktop-ui`.

## Open Questions

1. Should the UI remember `accept_edits` per folder across app restarts? This draft says no: it is remembered for one conversation at most (R9).
2. Should overwrites of files that existed before the task still prompt, with only new files auto-approved? This draft auto-approves both and makes overwrites visible (R5), as other coding agents do.
