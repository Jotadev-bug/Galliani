"""Spec 009 - Permissions: approve, deny or ask the user before restricted actions.

Least privilege: an approval covers exactly one action and a scope; a request is covered only when its
scope equals the approved scope or sits beneath it (path semantics). Restricted actions with no policy
rule are denied.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field

from galliani.contracts import new_id, utcnow


class PermissionLevel(str, Enum):
    read_only = "read_only"
    write = "write"
    destructive = "destructive"
    external = "external"
    costly = "costly"
    sensitive = "sensitive"


RESTRICTED_LEVELS = frozenset(level for level in PermissionLevel if level is not PermissionLevel.read_only)


class PermissionStatus(str, Enum):
    allowed = "allowed"
    denied = "denied"
    needs_user = "needs_user"


class PermissionRequest(BaseModel):
    task_id: str
    action: str
    resource: str
    scope: str
    risk_level: PermissionLevel
    reason_summary: str


class PermissionDecision(BaseModel):
    status: PermissionStatus
    action: str
    scope: str
    approved_scope: str | None = None
    expires_at: datetime | None = None
    user_prompt: str | None = None
    audit_summary: str


class ApprovalRecord(BaseModel):
    approval_id: str = Field(default_factory=lambda: new_id("appr"))
    user_id: str
    action: str
    scope: str
    timestamp: datetime = Field(default_factory=utcnow)
    expiration: datetime | None = None

    def expired(self, now: datetime) -> bool:
        return self.expiration is not None and now >= self.expiration


class ApprovalPrompt(BaseModel):
    """What the user sees when a task pauses (012 contract, produced by 009)."""

    prompt_id: str = Field(default_factory=lambda: new_id("prompt"))
    action_summary: str
    risk_summary: str
    allowed_choices: list[str] = Field(default_factory=lambda: ["approve", "deny"])
    scope: str


def scope_covers(approved: str, requested: str) -> bool:
    approved, requested = approved.rstrip("/"), requested.rstrip("/")
    return requested == approved or requested.startswith(approved + "/")


DEFAULT_RULES: dict[PermissionLevel, PermissionStatus] = {
    PermissionLevel.read_only: PermissionStatus.allowed,
    **{level: PermissionStatus.needs_user for level in RESTRICTED_LEVELS},
}


class PermissionPolicy:
    """Evaluates requests against per-level rules (user settings) and the task's approvals."""

    def __init__(self, rules: dict[PermissionLevel, PermissionStatus] | None = None):
        self.rules = dict(DEFAULT_RULES if rules is None else rules)

    def evaluate(
        self, request: PermissionRequest, approvals: Iterable[ApprovalRecord] = (), now: datetime | None = None
    ) -> PermissionDecision:
        now = now or utcnow()
        level = request.risk_level

        def decide(status: PermissionStatus, audit: str, **kw) -> PermissionDecision:
            return PermissionDecision(status=status, action=request.action, scope=request.scope, audit_summary=audit, **kw)

        rule = self.rules.get(level)
        if rule is None:
            if level is PermissionLevel.read_only:
                return decide(PermissionStatus.allowed, f"{request.action}: read-only action allowed")
            return decide(PermissionStatus.denied, f"{request.action}: no policy for {level.value} actions; denied")
        if rule is PermissionStatus.denied:
            return decide(PermissionStatus.denied, f"{request.action}: {level.value} actions are denied by policy")
        if rule is PermissionStatus.allowed:
            return decide(
                PermissionStatus.allowed, f"{request.action}: {level.value} actions allowed by policy",
                approved_scope=request.scope,
            )

        matching = [a for a in approvals if a.action == request.action]
        covering = [a for a in matching if scope_covers(a.scope, request.scope)]
        valid = [a for a in covering if not a.expired(now)]
        if valid:
            approval = valid[0]
            return decide(
                PermissionStatus.allowed,
                f"{request.action}: approved by {approval.user_id} for scope {approval.scope}",
                approved_scope=approval.scope,
                expires_at=approval.expiration,
            )
        if covering:  # only expired approvals cover this scope
            return decide(
                PermissionStatus.needs_user,
                f"{request.action}: approval expired; renewed permission required",
                user_prompt=self._prompt(request, renewed=True),
            )
        if matching:
            return decide(
                PermissionStatus.denied,
                f"{request.action}: requested scope {request.scope} exceeds the approved scope",
            )
        return decide(
            PermissionStatus.needs_user,
            f"{request.action}: {level.value} action requires user approval",
            user_prompt=self._prompt(request),
        )

    @staticmethod
    def _prompt(request: PermissionRequest, renewed: bool = False) -> str:
        prefix = "Your earlier approval expired. " if renewed else ""
        return (
            f"{prefix}Allow '{request.action}' ({request.risk_level.value}) on '{request.resource}' "
            f"limited to scope '{request.scope}'? Reason: {request.reason_summary}"
        )

    @staticmethod
    def approval_for(request: PermissionRequest, user_id: str, ttl: timedelta | None = None) -> ApprovalRecord:
        """Least-privilege approval: exactly the requested action and scope."""
        return ApprovalRecord(
            user_id=user_id,
            action=request.action,
            scope=request.scope,
            expiration=(utcnow() + ttl) if ttl else None,
        )

    @staticmethod
    def prompt_for(request: PermissionRequest, decision: PermissionDecision) -> ApprovalPrompt:
        return ApprovalPrompt(
            action_summary=decision.user_prompt or f"Allow '{request.action}' on '{request.resource}'?",
            risk_summary=f"{request.risk_level.value} action",
            scope=request.scope,
        )
