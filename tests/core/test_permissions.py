"""Spec 009 - Permissions acceptance criteria."""

from __future__ import annotations

from datetime import timedelta

from galliani.contracts import utcnow
from galliani.permissions import (
    ApprovalRecord,
    PermissionLevel,
    PermissionPolicy,
    PermissionRequest,
    PermissionStatus,
    scope_covers,
)


def req(level: PermissionLevel, scope: str = "notes/a.txt", action: str = "delete_file") -> PermissionRequest:
    return PermissionRequest(task_id="t", action=action, resource=scope, scope=scope, risk_level=level,
                             reason_summary="test")


# AC: Allowed
def test_read_only_action_allowed():
    assert PermissionPolicy().evaluate(req(PermissionLevel.read_only, action="read")).status is PermissionStatus.allowed


# AC: Needs User
def test_destructive_without_approval_needs_user_with_specific_prompt():
    decision = PermissionPolicy().evaluate(req(PermissionLevel.destructive))
    assert decision.status is PermissionStatus.needs_user
    assert "delete_file" in decision.user_prompt and "notes/a.txt" in decision.user_prompt


# AC: Denied (scope exceeds approval)
def test_scope_beyond_approval_denied():
    approval = ApprovalRecord(user_id="u", action="delete_file", scope="notes/a.txt")
    decision = PermissionPolicy().evaluate(req(PermissionLevel.destructive, scope="notes"), [approval])
    assert decision.status is PermissionStatus.denied


def test_matching_approval_allows_within_scope():
    approval = ApprovalRecord(user_id="u", action="delete_file", scope="notes")
    decision = PermissionPolicy().evaluate(req(PermissionLevel.destructive, scope="notes/a.txt"), [approval])
    assert decision.status is PermissionStatus.allowed and decision.approved_scope == "notes"


def test_expired_approval_requires_renewal():
    approval = ApprovalRecord(user_id="u", action="delete_file", scope="notes/a.txt",
                              expiration=utcnow() - timedelta(seconds=1))
    decision = PermissionPolicy().evaluate(req(PermissionLevel.destructive), [approval])
    assert decision.status is PermissionStatus.needs_user and "expired" in decision.user_prompt


def test_missing_policy_denies_restricted_actions():
    policy = PermissionPolicy(rules={})
    assert policy.evaluate(req(PermissionLevel.write)).status is PermissionStatus.denied
    assert policy.evaluate(req(PermissionLevel.read_only)).status is PermissionStatus.allowed


def test_policy_rule_can_deny_a_level():
    policy = PermissionPolicy(rules={PermissionLevel.destructive: PermissionStatus.denied})
    approval = ApprovalRecord(user_id="u", action="delete_file", scope="notes/a.txt")
    assert policy.evaluate(req(PermissionLevel.destructive), [approval]).status is PermissionStatus.denied


def test_approval_for_is_least_privilege():
    request = req(PermissionLevel.destructive)
    approval = PermissionPolicy.approval_for(request, "u")
    assert (approval.action, approval.scope) == ("delete_file", "notes/a.txt")


def test_scope_covers_uses_path_boundaries():
    assert scope_covers("notes", "notes/a.txt")
    assert not scope_covers("notes", "notes-private/a.txt")
    assert not scope_covers("notes/a.txt", "notes")
