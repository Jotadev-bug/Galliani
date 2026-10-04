"""Spec 007 - Verification acceptance criteria."""

from __future__ import annotations

import pytest

from galliani.verification import (
    Criterion,
    VerificationRecommendation as Rec,
    VerificationRequest,
    VerificationStatus as VS,
    Verifier,
    VerifierUnavailable,
)


def vreq(*criteria: Criterion, refs=("r1",)) -> VerificationRequest:
    return VerificationRequest(task_id="t", step_id="s1", output_refs=list(refs), criteria=list(criteria))


C = Criterion


# AC: Task Done
async def test_all_criteria_satisfied_passes():
    result = await Verifier().verify(
        vreq(C(kind="contains", value="total"), C(kind="min_length", value=5), C(kind="regex", value=r"\d+")),
        {"r1": "The total is 42"},
    )
    assert result.status is VS.pass_ and result.recommendation is Rec.continue_
    assert len(result.satisfied_criteria) == 3 and result.reason_summary


# AC: Failure
async def test_missing_required_criterion_fails_with_retry():
    result = await Verifier().verify(vreq(C(kind="contains", value="total")), {"r1": "nothing here"})
    assert result.status is VS.fail and result.recommendation is Rec.retry
    assert result.failed_criteria == ["contains 'total'"]


async def test_bad_approach_failure_recommends_replan():
    result = await Verifier().verify(vreq(C(kind="contains", value="x", on_fail="replan")), {"r1": "y"})
    assert result.recommendation is Rec.replan


# AC: Inconclusive
async def test_missing_criteria_is_inconclusive_and_asks_user():
    result = await Verifier().verify(vreq(), {"r1": "anything"})
    assert result.status is VS.inconclusive and result.recommendation is Rec.ask_user


async def test_semantic_criterion_without_model_verifier_is_inconclusive():
    result = await Verifier().verify(vreq(C(kind="semantic", value="is polite")), {"r1": "hi"})
    assert result.status is VS.inconclusive


@pytest.mark.parametrize("kind,field,value,output,expected", [
    ("field_present", "a.b", None, {"a": {"b": 1}}, True),
    ("field_present", "a.c", None, {"a": {"b": 1}}, False),
    ("field_equals", "status", "ok", {"status": "ok"}, True),
    ("equals", None, 3, 3, True),
    ("not_contains", None, "error", "all good", True),
    ("contains", "text", "note", {"text": "a note"}, True),
])
async def test_deterministic_criteria(kind, field, value, output, expected):
    result = await Verifier().verify(vreq(C(kind=kind, field=field, value=value)), {"r1": output})
    assert (result.status is VS.pass_) is expected


async def test_missing_output_fails():
    result = await Verifier().verify(vreq(C(kind="contains", value="x")), {})
    assert result.status is VS.fail and result.recommendation is Rec.retry


async def test_semantic_verifier_boundary_and_unavailability():
    class Judge:
        def __init__(self, verdict, raises=False):
            self.verdict, self.raises = verdict, raises

        async def check(self, criterion, output, request):
            if self.raises:
                raise VerifierUnavailable()
            return self.verdict, "judged"

    crit = C(kind="semantic", value="answers the question")
    assert (await Verifier(Judge(True)).verify(vreq(crit), {"r1": "x"})).status is VS.pass_
    assert (await Verifier(Judge(False)).verify(vreq(crit), {"r1": "x"})).status is VS.fail
    unavailable = await Verifier(Judge(None, raises=True)).verify(vreq(crit), {"r1": "x"})
    assert unavailable.status is VS.inconclusive and unavailable.recommendation is Rec.retry


async def test_reason_summary_does_not_copy_output():
    result = await Verifier().verify(vreq(C(kind="contains", value="total")), {"r1": "PRIVATE-PAYLOAD"})
    assert "PRIVATE-PAYLOAD" not in result.model_dump_json()
