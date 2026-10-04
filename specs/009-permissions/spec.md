# 009 - Permissions

        ## Status

        Approved for v0.1 implementation (2026-10-04, see `docs/decisions.md` Decision 0006).

        ## Goal

        Define permission checks for tools, external actions, destructive operations, and user approval flows.

        ## Non-goals

        - Identity provider implementation.
- Enterprise policy engine design.
- Bypassing user confirmation for speed.

        ## Requirements

        1. Every tool must declare a permission level.
2. The permission system must approve, deny, or request user approval.
3. Destructive, external, costly, or sensitive actions must require explicit approval.
4. Permission decisions must be recorded in Task State.
5. Denied permissions must safely block execution.

        ## Behavior

        - A component requests permission before a restricted action.
- Policy is evaluated against action type, scope, user settings, and task context.
- The system returns allowed, denied, or needs_user.
- The supervisor pauses when user approval is required.

        ## Interfaces and Data Contracts

        - `PermissionRequest`: task_id, action, resource, scope, risk_level, reason_summary.
- `PermissionDecision`: status, approved_scope, expires_at, user_prompt, audit_summary.
- `PermissionStatus`: allowed, denied, needs_user.
- `ApprovalRecord`: approval_id, user_id, scope, timestamp, expiration.

        ## Error Handling

        - Missing policy defaults to deny for restricted actions.
- Expired approval requires renewed permission.
- Scope mismatch returns denied.

        ## Security

        - Permission prompts must be specific and understandable.
- Approval scope must be least-privilege.
- Audit logs must not contain secrets or hidden reasoning.

        ## Acceptance Criteria

        ### Allowed

Given a read-only safe action is requested

When policy permits it

Then the system returns allowed.

### Needs User

Given a destructive action is requested

When no approval exists

Then the system asks the user and pauses execution.

### Denied

Given an action exceeds approved scope

When permission is checked

Then the system denies execution.

        ## Tests

        - Unit tests for policy decisions.
- Integration tests with tool execution.
- Expiration and scope mismatch tests.

        ## Evaluation

        - Permission bypass count must be zero.
- False approval rate on restricted fixtures must be zero.
- Prompt clarity reviewed manually.

        ## Implementation Tasks

        - [ ] Define permission levels.
- [ ] Define decision contract.
- [ ] Integrate with Tool System and Execution Engine.
- [ ] Add approval records to Task State.

        ## Dependencies

        Depends on `000-foundation` and supports `005-tool-system` and `006-execution-engine`.
