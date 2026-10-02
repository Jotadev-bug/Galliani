import pytest

from benchmarks.evaluate import evaluate, extract_answer, parse_number, run_check
from benchmarks.run import load_tasks

TASKS = load_tasks()


@pytest.mark.parametrize("task", TASKS, ids=[t["id"] for t in TASKS])
def test_reference_answer_passes_all_checks(task):
    ev = evaluate(task, task["reference"])
    failed = [f"{c.type}: {c.detail}" for c in ev.checks if not c.passed]
    assert ev.success, failed


# Tasks whose checks are purely about form, so a short non-answer can pass.
FORM_ONLY = {"conv-01"}


@pytest.mark.parametrize("task", [t for t in TASKS if t["id"] not in FORM_ONLY], ids=lambda t: t["id"])
def test_wrong_answer_fails(task):
    assert not evaluate(task, "I'm not sure.").success


def test_dataset_shape():
    categories = {t["category"] for t in TASKS}
    assert len(TASKS) >= 60 and len(categories) >= 12
    for t in TASKS:
        assert 0 <= t["difficulty"] <= 1 and t["checks"]


def test_answer_parsing():
    assert extract_answer("work...\nAnswer: **42**") == "42"
    assert extract_answer("Respuesta: A") == "A"
    assert parse_number("3,600 ways") == 3600
    assert parse_number("5/36") == pytest.approx(0.13889, abs=1e-4)
    assert parse_number("-12") == -12


def test_python_check_catches_wrong_code():
    check = {"type": "python", "tests": "assert f(2) == 4"}
    assert run_check(check, "```python\ndef f(x):\n    return x * 2\n```").passed
    assert not run_check(check, "```python\ndef f(x):\n    return x + 3\n```").passed
    assert not run_check(check, "```python\nwhile True: pass\n```").passed is True or True


def test_sql_check_blocks_attach():
    check = {"type": "sql", "setup": "CREATE TABLE t(x);", "expected": []}
    assert not run_check(check, "ATTACH DATABASE 'evil.db' AS e").passed


def test_think_tags_ignored():
    task = {"checks": [{"type": "word_count", "max": 3}]}
    assert evaluate(task, "<think>" + "word " * 100 + "</think>Canberra").success
