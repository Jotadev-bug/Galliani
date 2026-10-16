"""Spec 012 R7, AC "pywebview Pin": the WebView2 check mirrors pywebview 6.2.1.
Spec 012 R20, AC "pywebview Init-Failure Report Pin": pywebview still logs the report R20 watches for."""

from __future__ import annotations

import ast
import importlib.util
import re
import tomllib
from importlib import metadata
from pathlib import Path

import pytest

from app.webview2 import INIT_FAILED_PREFIX

EXPECTED_SPEC = "pywebview>=6.2,<7"
MIN_VERSION = (6, 2)
MAX_EXCLUSIVE = (7,)
RECHECK = (
    "Re-check spec 012 R7 against the new webview/platforms/winforms.py "
    "_is_chromium() (and R8 against mshtml.py _set_ie_mode()), update the spec, "
    "then change the pin in pyproject.toml and this test together."
)


def _numeric_parts(version: str) -> tuple[int, ...]:
    match = re.match(r"\d+(?:\.\d+)*", version)
    assert match, f"Unparseable version {version!r}"
    return tuple(int(p) for p in match.group(0).split("."))


def _assert_inside_the_pin(version: str) -> None:
    parts = _numeric_parts(version)
    assert MIN_VERSION <= parts < MAX_EXCLUSIVE, (
        f"Installed pywebview {version} is outside >=6.2,<7. {RECHECK}"
    )


def test_installed_pywebview_is_inside_the_pin() -> None:
    try:
        version = metadata.version("pywebview")
    except metadata.PackageNotFoundError:
        pytest.skip("pywebview is not installed (the optional `desktop` extra); install it with "
                    "`pip install -e .[desktop]` to check the pin. An installed pywebview is always checked.")
    _assert_inside_the_pin(version)


@pytest.mark.parametrize("version, inside", [
    ("6.2", True), ("6.2.1", True), ("6.99.0", True), ("6.1.9", False), ("7.0", False), ("7.0.0rc1", False),
    ("5.4", False),
])
def test_the_pin_check_fails_outside_the_range(version: str, inside: bool) -> None:
    # The skip above covers only "not installed": any installed version outside the pin still fails.
    if inside:
        _assert_inside_the_pin(version)
    else:
        with pytest.raises(AssertionError, match="outside >=6.2,<7"):
            _assert_inside_the_pin(version)


def test_pyproject_desktop_extra_declares_the_pin() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    desktop = data["project"]["optional-dependencies"]["desktop"]
    declared = [d.replace(" ", "") for d in desktop if d.lower().startswith("pywebview")]
    assert declared == [EXPECTED_SPEC], (
        f"pyproject.toml desktop extra declares {declared}, expected [{EXPECTED_SPEC!r}]. {RECHECK}"
    )


# --------------------------------------------- spec 012 R20, AC "pywebview Init-Failure Report Pin"

R20_RECHECK = (
    "Re-check spec 012 R20: the WebView2 init-failure watcher in app/webview2.py matches pywebview's "
    "logger.error('WebView2 initialization failed ...') in EdgeChrome.on_webview_ready "
    "(webview/platforms/edgechromium.py). Update the spec and app.webview2.INIT_FAILED_PREFIX together."
)


def _pywebview_root() -> Path:
    """The installed `webview` package folder, found without importing it."""
    spec = importlib.util.find_spec("webview")
    if spec is None or not spec.submodule_search_locations:
        pytest.skip("pywebview is not installed (the optional `desktop` extra); install it with "
                    "`pip install -e .[desktop]` to check the R20 pin.")
    return Path(spec.submodule_search_locations[0])


def _leading_text(node: ast.expr) -> str | None:
    """The literal text a message starts with: 'a' + x, f'a{x}' and plain 'a' all start with 'a'."""
    while isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        node = node.left
    if isinstance(node, ast.JoinedStr) and node.values:
        node = node.values[0]
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _assert_reports_init_failure(source: str) -> None:
    tree = ast.parse(source)
    loggers = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "logger" for t in node.targets)]
    assert any(ast.unparse(node.value).endswith("getLogger('pywebview')")  # unparse always uses single quotes
               for node in loggers), f"edgechromium.py no longer logs on the 'pywebview' logger. {R20_RECHECK}"
    handlers = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                and node.name == "on_webview_ready"]
    assert handlers, f"edgechromium.py has no on_webview_ready. {R20_RECHECK}"
    reports = [call for handler in handlers for call in ast.walk(handler) if isinstance(call, ast.Call)
               and ast.unparse(call.func) == "logger.error" and call.args
               and (_leading_text(call.args[0]) or "").startswith(INIT_FAILED_PREFIX)]
    assert reports, (f"on_webview_ready no longer calls logger.error('{INIT_FAILED_PREFIX} ...'). {R20_RECHECK}")


def test_pywebview_still_reports_a_failed_webview2_initialization() -> None:
    _assert_reports_init_failure((_pywebview_root() / "platforms" / "edgechromium.py").read_text(encoding="utf-8"))


_GOOD = """
import logging
logger = logging.getLogger('pywebview')
class EdgeChrome:
    def on_webview_ready(self, sender, args):
        if not args.IsSuccess:
            logger.error('WebView2 initialization failed with exception:\\n ' + str(args.InitializationException))
            return
"""


@pytest.mark.parametrize("source, passes", [
    (_GOOD, True),
    (_GOOD.replace("'WebView2 initialization failed with exception:\\n ' + str(args.InitializationException)",
                   "f'WebView2 initialization failed: {args.InitializationException}'"), True),
    (_GOOD.replace("WebView2 initialization failed", "WebView2 failed to initialize"), False),  # reworded
    (_GOOD.replace("logger.error(", "logger.warning("), False),  # another level
    (_GOOD.replace("on_webview_ready", "on_ready"), False),  # moved
    (_GOOD.replace("logger.error(", "print("), False),  # removed
    (_GOOD.replace("getLogger('pywebview')", "getLogger(__name__)"), False),  # another logger
])
def test_the_r20_pin_fails_when_the_report_changes(source: str, passes: bool) -> None:
    if passes:
        _assert_reports_init_failure(source)
    else:
        with pytest.raises(AssertionError, match="Re-check spec 012 R20"):
            _assert_reports_init_failure(source)


def _is_pywebview_logger(node: ast.expr, names: set[str]) -> bool:
    text = ast.unparse(node)
    return text in names or (isinstance(node, ast.Call) and text.endswith("getLogger('pywebview')"))


def _hides_error_records(path: Path, tree: ast.Module) -> list[str]:
    """Every statement in one pywebview module that could stop an ERROR record on the `pywebview` logger from
    reaching its handlers: a level other than DEBUG, `logging.disable`, a logger filter, removed handlers,
    `disabled`, or `logging.config` (which disables existing loggers by default). Aliases count
    (`import logging as _logging`, `_log = _logging.getLogger('pywebview')`, `getLogger('pywebview').x`)."""
    aliases = {"logging"} | {a.asname for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
                             if a.name == "logging" and a.asname}
    imported = {a.asname or a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                and (n.module or "").startswith("logging") for a in n.names}
    names = {ast.unparse(target) for n in ast.walk(tree) if isinstance(n, ast.Assign)
             and isinstance(n.value, ast.Call) and ast.unparse(n.value).endswith("getLogger('pywebview')")
             for target in n.targets}
    skipped = {id(n) for f in ast.walk(tree) if isinstance(f, ast.FunctionDef) and f.name == "_setup_logger"
               and path.name == "__init__.py" and path.parent.name == "webview" for n in ast.walk(f)}
    allowed_levels = {f"{a}.DEBUG" for a in aliases}
    hits = []
    for node in ast.walk(tree):
        if id(node) in skipped:
            continue
        if isinstance(node, ast.Call):
            func, text = node.func, ast.unparse(node.func)
            module_call = text.split(".")[-1] in ("disable", "dictConfig", "fileConfig") and (
                text.split(".")[0] in aliases or text in imported)
            handlers_of_logger = (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute)
                                  and _is_pywebview_logger(func.value.value, names))  # logger.handlers.clear()
            on_logger = isinstance(func, ast.Attribute) and (_is_pywebview_logger(func.value, names)
                                                             or (func.attr == "clear" and handlers_of_logger))
            if module_call:
                hits.append(ast.unparse(node))
            elif on_logger and func.attr in ("setLevel", "addFilter", "removeHandler", "clear", "disable"):
                if not (func.attr == "setLevel" and [ast.unparse(a) for a in node.args] in
                        [[level] for level in allowed_levels]):
                    hits.append(ast.unparse(node))
            elif text == "setattr" and node.args and _is_pywebview_logger(node.args[0], names):
                hits.append(ast.unparse(node))
        elif isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            hits += [ast.unparse(t) for t in targets if isinstance(t, ast.Attribute) and (
                (t.attr in ("level", "disabled", "filters", "handlers") and _is_pywebview_logger(t.value, names))
                or ast.unparse(t).endswith("manager.disable"))]
    return hits


def _assert_never_hides_error_records(root: Path) -> None:
    for path in root.rglob("*.py"):
        hits = _hides_error_records(path, ast.parse(path.read_text(encoding="utf-8")))
        assert not hits, f"{path.name}: {hits} could hide pywebview's ERROR record. {R20_RECHECK}"


def test_pywebview_never_raises_its_logger_above_error() -> None:
    # R13, R20: R20 needs pywebview's ERROR record. pywebview's own `logger` (the `pywebview` logger in every
    # module) may get a level only in `webview/__init__.py` `_setup_logger` (skipped: desktop_log adds a
    # handler first) or DEBUG (start(debug=True), where the app's level is DEBUG already). Nothing disables
    # it, filters it, drops its handlers, or calls logging.disable or logging.config.
    _assert_never_hides_error_records(_pywebview_root())


def _src(*lines: str) -> str:
    return "\n".join(lines) + "\n"


_PYWEBVIEW_LOGGER = "logger = logging.getLogger('pywebview')"


@pytest.mark.parametrize("source, passes", [
    (_src("import logging", _PYWEBVIEW_LOGGER, "logger.setLevel(logging.DEBUG)"), True),
    (_src("import logging", _PYWEBVIEW_LOGGER, "logger.info('x')", "window.setLevel_(3)"), True),
    (_src("import logging", _PYWEBVIEW_LOGGER, "logger.setLevel(logging.CRITICAL)"), False),
    # Aliases like pywebview's own `webview/platforms/win32.py` (`import logging as _logging`, `_log`).
    (_src("import logging as _logging", "_log = _logging.getLogger('pywebview')", "_log.setLevel(_logging.CRITICAL)"),
     False),
    (_src("import logging as _logging", "_logging.disable(_logging.ERROR)"), False),
    (_src("from logging import disable", "disable(50)"), False),
    (_src("import logging", "logging.getLogger('pywebview').setLevel(logging.ERROR + 10)"), False),
    (_src("import logging", _PYWEBVIEW_LOGGER, "logger.addFilter(lambda r: False)"), False),
    (_src("import logging", _PYWEBVIEW_LOGGER, "logger.disabled = True"), False),
    (_src("import logging", _PYWEBVIEW_LOGGER, "logger.handlers.clear()"), False),
    (_src("import logging", _PYWEBVIEW_LOGGER, "setattr(logger, 'level', 50)"), False),
    (_src("import logging.config", "logging.config.dictConfig({'version': 1})"), False),
    (_src("import logging", "logging.root.manager.disable = 40"), False),
    (_src("import logging", "class W:", "    def __init__(self):", "        self._log = logging.getLogger('pywebview')",
          "        self._log.setLevel(logging.CRITICAL)"), False),
])
def test_the_logger_level_pin_sees_aliases_and_other_ways_to_hide_errors(tmp_path, source, passes) -> None:
    # QA review: the pin must not miss an alias (pywebview's win32.py already uses `_logging` and `_log`).
    package = tmp_path / "webview" / "platforms"
    package.mkdir(parents=True)
    (package / "mod.py").write_text(source, encoding="utf-8")
    if passes:
        _assert_never_hides_error_records(tmp_path / "webview")
    else:
        with pytest.raises(AssertionError, match="Re-check spec 012 R20"):
            _assert_never_hides_error_records(tmp_path / "webview")


def test_the_logger_level_pin_skips_only_pywebviews_own_setup(tmp_path) -> None:
    setup = _src("import logging, os", "def _setup_logger():", "    logger = logging.getLogger('pywebview')",
                 "    logger.setLevel(getattr(logging, os.environ.get('PYWEBVIEW_LOG', 'INFO')))")
    (tmp_path / "webview").mkdir()
    (tmp_path / "webview" / "__init__.py").write_text(setup, encoding="utf-8")
    _assert_never_hides_error_records(tmp_path / "webview")  # skipped: desktop_log adds a handler first
    (tmp_path / "webview" / "other.py").write_text(setup, encoding="utf-8")
    with pytest.raises(AssertionError, match="Re-check spec 012 R20"):
        _assert_never_hides_error_records(tmp_path / "webview")


def test_a_missing_desktop_extra_skips_with_a_reason(monkeypatch) -> None:
    def not_installed(_name: str) -> str:
        raise metadata.PackageNotFoundError("pywebview")

    monkeypatch.setattr(metadata, "version", not_installed)
    with pytest.raises(pytest.skip.Exception, match="pywebview is not installed"):
        test_installed_pywebview_is_inside_the_pin()
