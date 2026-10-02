"""Deterministic, automatic quality checks for benchmark responses.

Every task lists `checks`; a response's quality is the fraction of checks it passes and it
counts as a success only if it passes all of them. No LLM judge: checks are cheap and
reproducible (PROJECT.md section 12 defers evaluators).

Code checks (`python`, `sql`) execute model-generated code in a subprocess / sandboxed
SQLite connection with a timeout. The runner can exclude those tasks (`--no-exec`).
"""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CODE_TIMEOUT_S = 10
EXEC_CHECKS = {"python", "sql"}


def normalize(text: str) -> str:
    """Casefold and strip accents so 'Mañana' matches 'manana' and 'ß' matches 'ss'."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def extract_code(text: str, lang: str) -> str:
    blocks = re.findall(rf"```(?:{lang})?[^\n]*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return blocks[-1] if blocks else text


def extract_json(text: str) -> Any:
    candidate = extract_code(text, "json") if "```" in text else text
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = candidate.find(opener), candidate.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("no JSON found")


_ANSWER_RE = re.compile(r"(?:answer|respuesta)\s*[:：]\s*\**\s*([^\n]+)", re.IGNORECASE)


def extract_answer(text: str) -> str | None:
    matches = _ANSWER_RE.findall(text)
    return matches[-1].strip().strip("*").strip() if matches else None


def parse_number(text: str) -> float | None:
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)  # thousands separators
    frac = re.search(r"(-?\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", text)
    if frac and float(frac.group(2)) != 0:
        return float(frac.group(1)) / float(frac.group(2))
    num = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(num.group(0)) if num else None


def _json_path(data: Any, path: str | None) -> Any:
    if not path:
        return data
    for part in path.split("."):
        data = data[int(part)] if isinstance(data, list) else data[part]
    return data


def _values_equal(actual: Any, expected: Any, tol: float = 1e-6) -> bool:
    if isinstance(expected, bool) or expected is None:
        return actual == expected
    if isinstance(expected, (int, float)):
        try:
            return abs(float(actual) - expected) <= tol
        except (TypeError, ValueError):
            return False
    if isinstance(expected, str):
        return isinstance(actual, str) and normalize(actual.strip()) == normalize(expected.strip())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            _values_equal(a, e, tol) for a, e in zip(actual, expected)
        )
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and _values_equal(actual[k], v, tol) for k, v in expected.items())
    return actual == expected


def _run_python(code: str, tests: str) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "check.py"
        script.write_text(code + "\n\n# --- tests ---\n" + tests + "\n", encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(script)], cwd=tmp, capture_output=True, text=True, timeout=CODE_TIMEOUT_S
            )
        except subprocess.TimeoutExpired:
            return False, "timeout"
    return proc.returncode == 0, proc.stderr[-300:]


def _deny_attach(action: int, *args: object) -> int:
    return sqlite3.SQLITE_DENY if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH) else sqlite3.SQLITE_OK


def _run_sql(query: str, setup: str, expected: list[list[Any]], ordered: bool) -> tuple[bool, str]:
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(setup)
        conn.set_authorizer(_deny_attach)
        rows = [list(r) for r in conn.execute(query.strip().rstrip(";")).fetchall()]
    except sqlite3.Error as e:
        return False, str(e)
    finally:
        conn.close()
    if not ordered:
        rows, expected = sorted(rows, key=repr), sorted(expected, key=repr)
    return _values_equal(rows, expected, tol=0.01), f"got {rows[:5]}"


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _in_range(n: float, check: dict) -> bool:
    return check.get("min", float("-inf")) <= n <= check.get("max", float("inf"))


@dataclass
class CheckResult:
    type: str
    passed: bool
    detail: str = ""


@dataclass
class Evaluation:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def score(self) -> float:
        return sum(c.passed for c in self.checks) / len(self.checks) if self.checks else 0.0

    @property
    def success(self) -> bool:
        return bool(self.checks) and all(c.passed for c in self.checks)


def run_check(check: dict, text: str) -> CheckResult:
    kind = check["type"]
    norm = normalize(text)
    try:
        if kind == "contains":
            return CheckResult(kind, normalize(check["value"]) in norm)
        if kind == "contains_all":
            missing = [v for v in check["values"] if normalize(v) not in norm]
            return CheckResult(kind, not missing, f"missing {missing}" if missing else "")
        if kind == "contains_any":
            return CheckResult(kind, any(normalize(v) in norm for v in check["values"]))
        if kind == "not_contains":
            found = [v for v in check["values"] if normalize(v) in norm]
            return CheckResult(kind, not found, f"found {found}" if found else "")
        if kind == "regex":
            return CheckResult(kind, re.search(check["pattern"], text) is not None)
        if kind == "count_regex":
            n = len(re.findall(check["pattern"], text))
            return CheckResult(kind, _in_range(n, check), f"count={n}")
        if kind == "word_count":
            n = _word_count(text)
            return CheckResult(kind, _in_range(n, check), f"words={n}")
        if kind == "line_count":
            n = len([ln for ln in text.splitlines() if ln.strip()])
            return CheckResult(kind, _in_range(n, check), f"lines={n}")
        if kind == "paragraphs":
            n = len([p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()])
            return CheckResult(kind, _in_range(n, check), f"paragraphs={n}")
        if kind == "answer":
            ans = extract_answer(text)
            if ans is None:
                return CheckResult(kind, False, "no 'Answer:' line")
            expected = check["value"]
            if isinstance(expected, (int, float)):
                got = parse_number(ans)
                ok = got is not None and abs(got - expected) <= check.get("tol", 1e-6)
                return CheckResult(kind, ok, f"got {ans!r}")
            if "pattern" in check:
                return CheckResult(kind, re.search(check["pattern"], ans, re.IGNORECASE) is not None, f"got {ans!r}")
            return CheckResult(kind, normalize(ans).strip(" .") == normalize(str(expected)), f"got {ans!r}")
        if kind == "json":
            data = extract_json(text)
            value = _json_path(data, check.get("path"))
            if "equals" in check and not _values_equal(value, check["equals"], check.get("tol", 0.01)):
                return CheckResult(kind, False, f"got {str(value)[:120]}")
            if "keys" in check and not (isinstance(value, dict) and all(k in value for k in check["keys"])):
                return CheckResult(kind, False, "missing keys")
            if "length" in check and not (isinstance(value, list) and len(value) == check["length"]):
                return CheckResult(kind, False, f"length={len(value) if isinstance(value, list) else 'n/a'}")
            return CheckResult(kind, True)
        if kind == "python":
            ok, detail = _run_python(extract_code(text, "python|py"), check["tests"])
            return CheckResult(kind, ok, detail)
        if kind == "sql":
            ok, detail = _run_sql(extract_code(text, "sql"), check["setup"], check["expected"], check.get("ordered", True))
            return CheckResult(kind, ok, detail)
        if kind == "validator":
            # Trusted validator code from the task file: defines validate(text) -> bool.
            scope: dict[str, Any] = {"re": re}
            exec(check["code"], scope)  # noqa: S102
            return CheckResult(kind, bool(scope["validate"](text)))
    except Exception as e:  # a malformed response fails the check, never the run
        return CheckResult(kind, False, f"{type(e).__name__}: {e}")
    raise ValueError(f"Unknown check type {kind!r}")


def needs_exec(task: dict) -> bool:
    return any(c["type"] in EXEC_CHECKS for c in task["checks"])


def evaluate(task: dict, text: str) -> Evaluation:
    text = strip_think(text)
    return Evaluation([run_check(c, text) for c in task["checks"]])
