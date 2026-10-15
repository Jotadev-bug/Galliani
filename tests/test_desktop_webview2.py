"""Spec 012 R6-R15: missing WebView2 on Windows (Decision 0031).

Detection runs through a fake registry reader and the launcher flow through injected message box, link
opener, renderer probe and a fake `webview` module, so every test runs on any machine and offline.
"""

from __future__ import annotations

import ast
import functools
import importlib.util
import random
import logging
import socket
import subprocess
import sys
import threading
import types
from pathlib import Path

import httpx
import pytest

from app import desktop
from app import webview2 as w
from app.webview2 import MISSING, WEBVIEW2_URL, WebView2Status, WindowHooks, detect_webview2

ROOT = Path(__file__).resolve().parents[1]
DOTNET_OK, DOTNET_OLD = 528040, 394254
TOKEN = "tok-SECRET-abcdefghijklmnopqrstuvwxyz0123456789"


# ------------------------------------------------------------------------------------------- helpers

RUNTIME, BETA, DEV, CANARY = w.CLIENT_KEYS
UNREADABLE = object()  # a key whose read raises (access denied)


def hkcu(client):
    return ("HKCU", w.CLIENT_PATH.format(client))


def hklm_native(client):  # SOFTWARE\Microsoft\EdgeUpdate\Clients\{id}
    return ("HKLM", w.CLIENT_PATH.format(client))


def hklm_wow(client):  # SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{id}
    return ("HKLM", w.CLIENT_PATH_WOW64.format(client))


def registry(pvs: dict | None = None, dotnet: object = DOTNET_OK) -> dict:
    """{(hive, key path): {value name: value} or UNREADABLE}. `dotnet=None` leaves the .NET key out."""
    keys = {key: (pv if pv is UNREADABLE else {"pv": pv}) for key, pv in (pvs or {}).items()}
    if dotnet is not None:
        keys[("HKLM", w.DOTNET_KEY)] = dotnet if dotnet is UNREADABLE else {"Release": dotnet}
    return keys


def reader_for(keys: dict, calls: list | None = None):
    """The injected reader over a fake registry: read-only, and it records every call with its view."""
    def read(hive, key_path, name, view):
        if calls is not None:
            calls.append((hive, key_path, name, view))
        key = keys.get((hive, key_path))
        if key is UNREADABLE:
            raise PermissionError("access denied")
        return None if key is None else key.get(name)

    return read


@pytest.fixture
def offline(monkeypatch):
    """Any network connection or subprocess fails the test."""
    def refuse(*_a, **_k):
        raise AssertionError("no network or subprocess call is allowed here")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(httpx.Client, "send", refuse)
    monkeypatch.setattr(httpx.AsyncClient, "send", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


class Recorder:
    def __init__(self, answer: bool = False, renderer: str = "edgechromium", status=None, ask_error=None):
        self.boxes: list[w.MessageBox] = []
        self.opened: list[str] = []
        self.detect_calls = 0
        self._answer, self._ask_error = answer, ask_error
        self._status = status or WebView2Status(True, "120.0.2210.91")
        self.hooks = WindowHooks(detect=self.detect, renderer=lambda: renderer, ask=self.ask, open_url=self.opened.append)

    def detect(self):
        self.detect_calls += 1
        return self._status

    def ask(self, box):
        self.boxes.append(box)
        if self._ask_error:
            raise self._ask_error
        return self._answer


class FakeServer:
    should_exit = False


@pytest.fixture
def launcher(monkeypatch, tmp_path, offline):
    """Run `desktop.main` on Windows with a fake server and a fake pywebview module."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(desktop, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(desktop, "free_port", lambda: 49731)
    monkeypatch.setattr(desktop.secrets, "token_urlsafe", lambda _n: TOKEN)
    for name in ("ROUTER_DESKTOP", "ROUTER_APP_TOKEN", "ROUTER_LOG_PATH"):
        monkeypatch.setenv(name, "unset")
    servers: list[FakeServer] = []
    monkeypatch.setattr(desktop, "start_server", lambda _port: servers.append(FakeServer()) or servers[-1])

    webview = types.SimpleNamespace(created=[], started=0, start_error=None, shown=False)

    def create_window(*args, **kwargs):
        webview.created.append((args, kwargs))
        shown = types.SimpleNamespace(is_set=lambda: webview.shown)
        return types.SimpleNamespace(events=types.SimpleNamespace(shown=shown))

    def start(**_kwargs):
        webview.started += 1
        if webview.start_error:
            raise webview.start_error

    webview.create_window, webview.start = create_window, start
    monkeypatch.setitem(sys.modules, "webview", webview)

    def run(recorder: Recorder, *argv: str) -> int:
        return desktop.main(list(argv), hooks=recorder.hooks)

    run.webview, run.servers, run.log = webview, servers, tmp_path / "desktop.log"
    return run


def log_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


CASES = ("webview2_missing", "webview2_legacy_engine", "window_start_failed")


def case_lines(path: Path) -> list[str]:
    """The R13 lines: those that name one of the three cases."""
    return [line for line in log_lines(path) if any(f" {case} version=" in line for case in CASES)]


# ------------------------------------------------------------------------------------ R7 detection

V120 = "120.0.2210.91"


def present(version):
    return WebView2Status(True, version)


# (id, platform.machine(), fake registry, expected result, pywebview 6.2.1's `_is_chromium()` answer).
# "error" means pywebview's own check raises (its `finally` closes a .NET key it never opened), which also
# leaves no usable Chromium; the spec makes that "missing" (R7: absent .NET is missing).
DETECTION_CASES = [
    # --- AC "WebView2 Detected"
    ("hkcu-only", "AMD64", registry({hkcu(RUNTIME): V120}), present(V120), True),
    ("a-hklm-wow64-on-amd64", "AMD64", registry({hklm_wow(RUNTIME): V120}), present(V120), True),
    ("a-hklm-wow64-on-arm64", "ARM64", registry({hklm_wow(RUNTIME): V120}), present(V120), True),
    ("a-hklm-native-on-x86", "x86", registry({hklm_native(RUNTIME): V120}), present(V120), True),
    ("c-86.0.0.0", "AMD64", registry({hkcu(RUNTIME): "86.0.0.0"}), present("86.0.0.0"), True),
    ("c-86.0.621.99", "AMD64", registry({hklm_wow(RUNTIME): "86.0.621.99"}), present("86.0.621.99"), True),
    ("d-too-old-continues", "AMD64", registry({hkcu(RUNTIME): "85.0.564.40", hklm_wow(RUNTIME): V120}),
     present(V120), True),
    ("d-zero-continues", "AMD64", registry({hkcu(RUNTIME): "0.0.0.0", hkcu(BETA): "121.0.5.2"}),
     present("121.0.5.2"), True),
    ("d-runtime-before-beta", "AMD64", registry({hkcu(RUNTIME): V120, hkcu(BETA): "130.0.1.1"}), present(V120), True),
    ("d-beta-before-dev", "AMD64", registry({hkcu(DEV): "130.0.1.1", hklm_wow(BETA): "121.0.5.2"}),
     present("121.0.5.2"), True),
    ("d-hkcu-before-hklm", "AMD64", registry({hkcu(RUNTIME): V120, hklm_wow(RUNTIME): "130.0.1.1"}),
     present(V120), True),
    ("d-canary-only", "AMD64", registry({hklm_wow(CANARY): V120}), present(V120), True),
    ("d-dev-only", "ARM64", registry({hkcu(DEV): V120}), present(V120), True),
    ("unreadable-key-continues", "AMD64", registry({hkcu(RUNTIME): UNREADABLE, hklm_wow(RUNTIME): V120}),
     present(V120), True),
    ("absent-pv-value-continues", "AMD64", {**registry({hklm_wow(RUNTIME): V120}), hkcu(RUNTIME): {}},
     present(V120), True),
    ("dword-pv", "AMD64", registry({hkcu(RUNTIME): 120}), present("120"), True),
    # --- AC "WebView2 Absent or Unusable"
    ("no-client-keys", "AMD64", registry({}), MISSING, False),
    ("only-0.0.0.0", "AMD64", registry({hkcu(RUNTIME): "0.0.0.0"}), MISSING, False),
    ("only-85", "AMD64", registry({hklm_wow(RUNTIME): "85.0.564.40"}), MISSING, False),
    ("only-empty", "AMD64", registry({hkcu(RUNTIME): ""}), MISSING, False),
    ("dotnet-too-old", "AMD64", registry({hkcu(RUNTIME): V120}, dotnet=DOTNET_OLD), MISSING, False),
    ("dotnet-absent", "AMD64", registry({hkcu(RUNTIME): V120}, dotnet=None), MISSING, "error"),
    ("dotnet-unreadable", "AMD64", registry({hkcu(RUNTIME): V120}, dotnet=UNREADABLE), MISSING, "error"),
    ("dotnet-not-a-number", "AMD64", registry({hkcu(RUNTIME): V120}, dotnet="528040"), MISSING, False),
    ("every-key-unreadable", "AMD64", registry({key(c): UNREADABLE for c in w.CLIENT_KEYS for key in (hkcu, hklm_wow)}),
     MISSING, False),
    ("a-hklm-native-on-amd64", "AMD64", registry({hklm_native(RUNTIME): V120}), MISSING, False),
    ("a-hklm-native-on-arm64", "ARM64", registry({hklm_native(RUNTIME): V120}), MISSING, False),
    ("a-hklm-wow64-on-x86", "x86", registry({hklm_wow(RUNTIME): V120}), MISSING, False),
    ("d-empty-stops-before-hklm", "AMD64", registry({hkcu(RUNTIME): "", hklm_wow(RUNTIME): V120}), MISSING, False),
    ("d-abc-stops-before-hklm", "AMD64", registry({hkcu(RUNTIME): "abc", hklm_wow(RUNTIME): V120}), MISSING, False),
    ("d-abc-stops-before-beta", "AMD64", registry({hkcu(RUNTIME): "abc", hkcu(BETA): V120}), MISSING, False),
    ("d-empty-stops-before-beta", "ARM64", registry({hkcu(RUNTIME): "", hklm_wow(BETA): V120}), MISSING, False),
    ("not-a-version", "AMD64", registry({hklm_wow(RUNTIME): "not-a-version"}), MISSING, False),
]
CASE_IDS = [case[0] for case in DETECTION_CASES]


@pytest.mark.parametrize("_id, machine, keys, expected, pywebview", DETECTION_CASES, ids=CASE_IDS)
def test_detection_gives_pywebviews_answer(_id, machine, keys, expected, pywebview, offline):
    assert detect_webview2(reader_for(keys), machine=machine) == expected
    assert expected.present == (pywebview is True)  # the listed pywebview 6.2.1 answer agrees


class _FakeKey:
    def __init__(self, values):
        self.values = values

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class _FakeWinreg:
    """Just enough of `winreg` to run pywebview's own `_is_chromium()` over the same fake registry."""

    HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE = "HKCU", "HKLM"

    def __init__(self, keys):
        self.keys = keys

    def OpenKey(self, root, path, *_args):  # noqa: N802 - winreg's names
        key = self.keys.get((root, path))
        if key is UNREADABLE:
            raise PermissionError("access denied")
        if key is None:
            raise FileNotFoundError(path)
        return _FakeKey(key)

    def QueryValueEx(self, key, name):  # noqa: N802
        if name not in key.values:
            raise FileNotFoundError(name)
        return key.values[name], 1

    def CloseKey(self, _key):  # noqa: N802
        pass


@functools.lru_cache(maxsize=1)
def _pywebview_rule_code():
    spec = importlib.util.find_spec("webview")
    if spec is None:
        return None
    source = (Path(spec.submodule_search_locations[0]) / "platforms" / "winforms.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("_is_new_version", "_is_chromium")]
    assert len(tree.body) == 2, "pywebview's rule moved: re-check spec 012 R7 against the new winforms.py"
    return compile(tree, "winforms.py", "exec")


def _pywebview_rule(keys, machine):
    """pywebview 6.2.1's `_is_new_version` and `_is_chromium`, taken from its source without importing its
    Windows backend (which needs pythonnet and Windows) and run against the fake registry."""
    code = _pywebview_rule_code()
    if code is None:
        pytest.skip("pywebview is not installed")
    namespace = {"winreg": _FakeWinreg(keys), "machine": lambda: machine, "settings": {"WEBVIEW2_RUNTIME_PATH": None},
                 "logger": logging.getLogger("test.pywebview-rule")}
    exec(code, namespace)  # noqa: S102 - the installed pywebview's own code
    try:
        return namespace["_is_chromium"]()
    except Exception:  # noqa: BLE001
        return "error"


@pytest.mark.parametrize("_id, machine, keys, expected, pywebview", DETECTION_CASES, ids=CASE_IDS)
def test_the_installed_pywebview_gives_the_listed_answer(_id, machine, keys, expected, pywebview):
    # Differential check: the table above is pywebview's real answer, not our reading of its code.
    assert _pywebview_rule(keys, machine) == pywebview


@pytest.mark.parametrize("release, present", [(394802, True), (394801, False), (528040, True)])
def test_dotnet_boundary_is_4_6_2_exactly(release, present, offline):
    # qa-security mutation check: MIN_DOTNET_RELEASE + 1 survived the table above (no case at the boundary).
    keys = registry({hkcu(RUNTIME): V120}, dotnet=release)
    assert detect_webview2(reader_for(keys), machine="AMD64").present is present
    assert _pywebview_rule(keys, "AMD64") is present


_ABSENT = object()
_PV_POOL = [_ABSENT, _ABSENT, _ABSENT, UNREADABLE, "", "abc", "0.0.0.0", "85.0.564.40", "86", "86.0.0.0", V120,
            " 120.0", "1_20.0", "+120", "120abc.0", "-1.0", "086.0", "١٢٠.0", 120, 85, b"120", ["120.0"]]
_NET_POOL = [_ABSENT, UNREADABLE, DOTNET_OK, 394802, 394801, "528040", b"\x00"]
_ALL_KEYS = [f(c) for c in w.CLIENT_KEYS for f in (hkcu, hklm_wow, hklm_native)]


def _random_registry(rng: random.Random) -> dict:
    keys: dict = {}
    for key in _ALL_KEYS:
        pv = rng.choice(_PV_POOL) if rng.random() < 0.35 else _ABSENT
        if pv is not _ABSENT:
            keys[key] = pv if pv is UNREADABLE else {"pv": pv}
    net = rng.choice(_NET_POOL)
    if net is not _ABSENT:
        keys[("HKLM", w.DOTNET_KEY)] = net if net is UNREADABLE else {"Release": net}
    return keys


def test_detection_matches_pywebview_on_random_registries(offline):
    # qa-security: a differential check beyond the hand-written table. Seeded random registries over all
    # twelve client paths, odd value types (DWORD, binary, multi-string, padded, underscored, non-ASCII
    # digits) and .NET values; our answer must equal what the installed pywebview's own `_is_chromium()`
    # returns. REG_NONE is excluded: see the strict xfail below.
    rng = random.Random(20261015)
    for _ in range(1500):
        keys, machine = _random_registry(rng), rng.choice(["AMD64", "ARM64", "x86"])
        ours = detect_webview2(reader_for(keys), machine=machine).present
        assert ours == (_pywebview_rule(keys, machine) is True), (machine, keys)


@pytest.mark.xfail(strict=True, reason="qa-security: an empty REG_NONE `pv` reads as None through winreg, the "
                   "same as an absent value, so the search continues; pywebview's str(None) -> int() stops it "
                   "(R7 'present but not a number'). Low: R8 still refuses the legacy engine (R12, exit 4). "
                   "Owner core-engineer.")
def test_an_empty_reg_none_pv_stops_the_search_like_pywebview(offline):
    keys = {**registry({hklm_wow(RUNTIME): V120}), hkcu(RUNTIME): {"pv": None}}  # value present, no data
    assert _pywebview_rule(keys, "AMD64") is False
    # windows_registry_reader returns winreg's None for this value, which is what reader_for passes on.
    assert detect_webview2(reader_for(keys), machine="AMD64") == MISSING


def test_every_read_uses_the_default_view_and_dotnet_is_read_once(offline):
    calls: list = []
    keys = registry({hkcu(RUNTIME): "85.0.564.40", hklm_wow(RUNTIME): "", hkcu(BETA): V120})
    assert detect_webview2(reader_for(keys, calls), machine="AMD64") == MISSING  # stopped at the empty value
    assert calls and all(view is None for *_rest, view in calls)
    assert [c for c in calls if c[2] == "Release"] == [("HKLM", w.DOTNET_KEY, "Release", None)]
    assert calls[1:] == [("HKCU", w.CLIENT_PATH.format(RUNTIME), "pv", None),
                         ("HKLM", w.CLIENT_PATH_WOW64.format(RUNTIME), "pv", None)]  # HKCU first, then stop


def test_b_dotnet_only_in_an_explicit_view_is_missing(offline):
    # AC "Absent or Unusable" (b): the fake returns .NET only when a view flag is passed.
    plain = reader_for(registry({hkcu(RUNTIME): V120}, dotnet=None))

    def read(hive, key_path, name, view):
        if (hive, key_path, name) == ("HKLM", w.DOTNET_KEY, "Release") and view is not None:
            return DOTNET_OK
        return plain(hive, key_path, name, view)

    assert detect_webview2(read, machine="AMD64") == MISSING


@pytest.mark.parametrize("machine, path", [("x86", w.CLIENT_PATH), ("AMD64", w.CLIENT_PATH_WOW64)])
def test_the_hklm_path_follows_the_real_platform_machine(monkeypatch, machine, path, offline):
    monkeypatch.setattr(w, "platform_machine", lambda: machine)
    calls: list = []
    detect_webview2(reader_for(registry({}), calls))
    assert ("HKLM", path.format(RUNTIME), "pv", None) in calls


@pytest.mark.parametrize("error", [PermissionError("denied"), OSError("broken hive"), ValueError("odd type")])
def test_unreadable_keys_count_as_missing_never_a_crash(error):
    def reader(*_args):
        raise error

    assert detect_webview2(reader) == MISSING


@pytest.mark.skipif(sys.platform != "win32", reason="real registry only on Windows")
def test_real_registry_check_is_fast_and_safe(offline):
    import time

    started = time.monotonic()
    status = detect_webview2()
    assert time.monotonic() - started < 1.0
    assert status == MISSING or (status.present and int(status.version.split(".")[0]) >= w.MIN_MAJOR)
    assert w.windows_registry_reader("HKCU", r"SOFTWARE\Galliani-test-no-such-key", "pv", None) is None


def test_non_windows_skips_the_check_and_shows_no_dialog(tmp_path, offline):
    rec = Recorder()
    rec.hooks.detect = lambda: pytest.fail("the check must not run off Windows")
    rec.hooks.renderer = lambda: pytest.fail("the renderer probe must not run off Windows")
    opened: list[int] = []
    code = w.launch_window(lambda: opened.append(1), log_path=tmp_path / "desktop.log", hooks=rec.hooks,
                           platform="darwin")
    assert (code, opened, rec.boxes, log_lines(tmp_path / "desktop.log")) == (0, [1], [], [])


# ----------------------------------------------------------------------------- R9, R10, R12 golden

def test_golden_message_boxes_and_url():
    assert WEBVIEW2_URL == "https://developer.microsoft.com/microsoft-edge/webview2/"
    missing = w.missing_box()
    assert missing.title == "Galliani needs Microsoft Edge WebView2"
    assert missing.text == (
        "Galliani uses Microsoft Edge WebView2, a free component from Microsoft, to show its window. It is not "
        "installed on this PC. Nothing has been downloaded or changed on this PC. Nothing was sent anywhere.\n\n"
        "Open Microsoft's WebView2 page now?\n\n"
        "Yes opens the page in your browser, where you can install the Evergreen Runtime and then open "
        "Galliani again; No closes Galliani."
    )
    assert (missing.icon, missing.buttons, missing.default) == ("information", "yes_no", "no")

    failed = w.failed_box(r"C:\Users\me\AppData\Local\Galliani\desktop.log")
    assert failed.title == "Galliani could not open its window"
    assert failed.text == (
        "Galliani could not open its window. Microsoft Edge WebView2 may be damaged or out of date. Reinstalling "
        "or updating it often helps.\n\n"
        "Select Yes to open Microsoft's WebView2 download page in your browser. Select No to close Galliani.\n\n"
        "Details were saved on this PC only, in:\n"
        "C:\\Users\\me\\AppData\\Local\\Galliani\\desktop.log"
    )
    assert (failed.icon, failed.buttons, failed.default) == ("warning", "yes_no", "no")


def test_native_box_flags_are_yes_no_with_no_as_default():
    # MB_YESNO 0x4, MB_DEFBUTTON2 0x100, MB_SETFOREGROUND 0x10000; MB_ICONINFORMATION 0x40, MB_ICONWARNING 0x30.
    assert w.message_box_flags(w.missing_box()) == 0x4 | 0x100 | 0x10000 | 0x40
    assert w.message_box_flags(w.failed_box("x")) == 0x4 | 0x100 | 0x10000 | 0x30


def test_the_url_is_defined_in_exactly_one_place():
    hits = [p for folder in ("app", "galliani") for p in (ROOT / folder).rglob("*.py")
            if "microsoft-edge/webview2" in p.read_text(encoding="utf-8")]
    assert hits == [ROOT / "app" / "webview2.py"]
    assert (ROOT / "app" / "webview2.py").read_text(encoding="utf-8").count("microsoft-edge/webview2") == 1
    assert "?" not in WEBVIEW2_URL and "#" not in WEBVIEW2_URL


# ---------------------------------------------------------------------------------- launcher flow

def test_window_opens_normally_when_webview2_is_present(launcher):
    rec = Recorder()
    assert launcher(rec) == 0
    assert rec.boxes == [] and rec.opened == [] and log_lines(launcher.log) == []
    (args, _kw), = launcher.webview.created
    assert args[1] == f"http://127.0.0.1:49731/?token={TOKEN}" and launcher.webview.started == 1
    assert launcher.servers[0].should_exit


def test_missing_yes_opens_microsofts_page_once_and_exits_3(launcher):
    rec = Recorder(answer=True, status=MISSING)
    assert launcher(rec) == 3
    assert rec.boxes == [w.missing_box()] and rec.opened == [WEBVIEW2_URL]
    assert launcher.webview.created == [] and launcher.webview.started == 0
    assert launcher.servers[0].should_exit


def test_missing_no_opens_nothing_and_exits_3(launcher):
    rec = Recorder(answer=False, status=MISSING)
    assert launcher(rec) == 3
    assert rec.boxes == [w.missing_box()] and rec.opened == []
    assert launcher.webview.created == [] and launcher.servers[0].should_exit


@pytest.mark.parametrize("answer, opened", [(True, [WEBVIEW2_URL]), (False, [])])
def test_legacy_engine_shows_the_r12_box_and_exits_4(launcher, answer, opened):
    # AC "Legacy Engine Refused" (R8): never the R9 box, whose "nothing changed" may be untrue here (R10).
    rec = Recorder(renderer="mshtml", answer=answer)
    assert launcher(rec) == 4
    assert rec.boxes == [w.failed_box(launcher.log)] and rec.opened == opened
    assert launcher.webview.created == [] and launcher.webview.started == 0 and launcher.servers[0].should_exit
    lines = log_lines(launcher.log)
    assert len(lines) == 1 and " webview2_legacy_engine version=120.0.2210.91 answer=" in lines[0]


@pytest.mark.parametrize("answer, opened", [(True, [WEBVIEW2_URL]), (False, [])])
def test_window_start_failure_shows_the_log_path_and_exits_4(launcher, answer, opened):
    rec = Recorder(answer=answer)
    launcher.webview.start_error = RuntimeError(f"navigation to http://127.0.0.1:49731/?token={TOKEN} failed")
    assert launcher(rec) == 4
    assert rec.boxes == [w.failed_box(launcher.log)] and str(launcher.log) in rec.boxes[0].text
    assert rec.opened == opened and launcher.servers[0].should_exit


def test_renderer_probe_failure_counts_as_window_start_failure(launcher):
    rec = Recorder()

    def broken():
        raise ImportError("pythonnet cannot be loaded")

    rec.hooks.renderer = broken
    assert launcher(rec) == 4 and launcher.webview.created == [] and rec.boxes == [w.failed_box(launcher.log)]
    (line,) = case_lines(launcher.log)
    assert " window_start_failed version=120.0.2210.91 answer=closed error=ImportError: pythonnet cannot be loaded" in line


def test_simulation_flag_forces_the_message_even_with_webview2_installed(launcher):
    rec = Recorder(answer=True)
    assert launcher(rec, "--simulate-missing-webview2") == 3
    assert rec.boxes == [w.missing_box()] and rec.opened == [WEBVIEW2_URL]
    assert launcher.webview.created == [] and rec.detect_calls == 0
    assert " webview2_missing version=none answer=opened_download_page" in log_lines(launcher.log)[0]


def test_simulation_works_off_windows_too(launcher, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    rec = Recorder(answer=False)
    assert launcher(rec, "--simulate-missing-webview2") == 3 and rec.boxes == [w.missing_box()]


def test_simulation_flag_is_documented_in_help(capsys):
    with pytest.raises(SystemExit):
        desktop.main(["--help"])
    assert "--simulate-missing-webview2" in capsys.readouterr().out


def test_a_box_that_cannot_be_shown_still_logs_and_exits(launcher):
    rec = Recorder(status=MISSING, ask_error=OSError("no desktop session"))
    assert launcher(rec) == 3 and rec.opened == []
    lines = log_lines(launcher.log)
    assert len(lines) == 1 and " webview2_missing version=none answer=closed" in lines[0]


def test_an_error_after_the_window_was_shown_is_not_a_start_failure(launcher):
    rec = Recorder(answer=True)
    launcher.webview.shown, launcher.webview.start_error = True, RuntimeError("GUI loop failed at shutdown")
    with pytest.raises(RuntimeError, match="at shutdown"):
        launcher(rec)
    assert rec.boxes == [] and rec.opened == [] and case_lines(launcher.log) == []
    text = launcher.log.read_text(encoding="utf-8")  # the re-raised traceback is logged, through the filter
    assert "The desktop app stopped with an error." in text and "RuntimeError: GUI loop failed at shutdown" in text
    assert launcher.servers[0].should_exit


def test_a_browser_that_fails_to_open_does_not_change_the_exit(launcher):
    rec = Recorder(answer=True, status=MISSING)

    def no_browser(_url):
        raise OSError("no browser")

    rec.hooks.open_url = no_browser
    assert launcher(rec) == 3


def test_a_check_that_raises_counts_as_missing_never_a_crash(launcher):
    # 012 Error handling: an unreadable registry is "missing". Covers the launcher's own guard around detect(),
    # not only the per-key guard in detect_webview2 (a mutant without it survived the suite before).
    rec = Recorder(answer=False)

    def broken():
        raise OSError("registry unavailable")

    rec.hooks.detect = broken
    assert launcher(rec) == 3
    assert rec.boxes == [w.missing_box()] and rec.opened == [] and launcher.webview.created == []
    lines = log_lines(launcher.log)
    assert len(lines) == 1 and " webview2_missing version=none answer=closed" in lines[0]


def test_next_launch_rechecks_and_opens_normally(launcher):
    first = Recorder(answer=False, status=MISSING)
    assert launcher(first) == 3
    second = Recorder()  # the user installed WebView2 in between; nothing was remembered
    assert launcher(second) == 0
    assert second.detect_calls == 1 and second.boxes == [] and launcher.webview.started == 1


# --------------------------------------------------------------------------------------- R13 log

@pytest.mark.parametrize("case, setup, expected", [
    ("webview2_missing", dict(status=MISSING, answer=False), "version=none answer=closed"),
    ("webview2_legacy_engine", dict(renderer="mshtml", answer=True),
     "version=120.0.2210.91 answer=opened_download_page"),
    ("window_start_failed", dict(answer=False), "version=120.0.2210.91 answer=closed error=RuntimeError: "),
])
def test_one_log_line_per_case_without_token_or_url(launcher, case, setup, expected):
    url = f"http://127.0.0.1:49731/?token={TOKEN}"
    launcher.webview.start_error = RuntimeError(f"could not load {url}\nsecond line, key sk-abcdefghijklmnop1234")
    launcher(Recorder(**setup))
    (line,) = case_lines(launcher.log)  # AC: exactly one line names the case (R12 adds its traceback lines)
    assert f" {case} {expected}" in line
    text = launcher.log.read_text(encoding="utf-8")
    for secret in (TOKEN, url, "127.0.0.1:49731", "sk-abcdefghijklmnop1234"):
        assert secret not in text


# ------------------------------------------------------------- R7, R14: backend not loaded before the check

class _BackendImportBlocker:
    """A meta-path finder that records and refuses any import of pywebview's platform backends."""

    def __init__(self):
        self.attempts: list[str] = []

    def find_spec(self, name, _path=None, _target=None):
        if name.startswith("webview.platforms"):
            self.attempts.append(name)
            raise ImportError(f"{name} must not be imported before the WebView2 check decides")
        return None


@pytest.mark.parametrize("argv", [(), ("--simulate-missing-webview2",)])
def test_backend_is_not_loaded_before_the_check(launcher, monkeypatch, argv):
    # AC "Backend Not Loaded Before the Check": the real detection (fake registry: no runtime) and the real
    # renderer probe; pywebview's start and guilib.initialize only count calls; registry writes fail the test.
    assert "webview.platforms.winforms" not in sys.modules  # nothing (not even importing app.desktop) loaded it
    blocker = _BackendImportBlocker()
    monkeypatch.setattr(sys, "meta_path", [blocker, *sys.meta_path])
    calls = {"initialize": 0}

    def initialize(*_a, **_k):
        calls["initialize"] += 1
        return types.SimpleNamespace(renderer="edgechromium")

    monkeypatch.setitem(sys.modules, "webview.guilib", types.SimpleNamespace(initialize=initialize))
    try:
        import winreg
    except ImportError:  # not Windows: a stand-in module, so the same writer guard applies
        winreg = types.ModuleType("winreg")
        monkeypatch.setitem(sys.modules, "winreg", winreg)

    def no_write(*_a, **_k):
        raise AssertionError("the WebView2 path must not write to the registry")

    for writer in ("SetValue", "SetValueEx", "CreateKey", "CreateKeyEx", "DeleteKey", "DeleteKeyEx", "DeleteValue"):
        monkeypatch.setattr(winreg, writer, no_write, raising=False)

    rec = Recorder(answer=False)
    rec.hooks = WindowHooks(detect=lambda: detect_webview2(reader_for(registry({})), machine="AMD64"),
                            ask=rec.ask, open_url=rec.opened.append)  # default renderer: the real probe
    assert launcher(rec, *argv) == 3 and rec.boxes == [w.missing_box()]
    assert "webview.platforms.winforms" not in sys.modules and blocker.attempts == []
    assert calls["initialize"] == 0 and launcher.webview.started == 0 and launcher.webview.created == []


# --------------------------------------------------------- R13, Security: everything in desktop.log redacted

KEY = "sk-abcdefghijklmnop1234"
URL = f"http://127.0.0.1:49731/?token={TOKEN}"


def assert_clean(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    for secret in (TOKEN, URL, "127.0.0.1:49731", KEY, "abcdefghijklmnop1234"):
        assert secret not in text
    return text


@pytest.mark.parametrize("after_shown", [False, True])
def test_pywebview_logger_and_tracebacks_are_redacted(launcher, after_shown):
    # AC "pywebview Logger and Tracebacks Redacted": pywebview's logger carries the URL, the window start
    # raises with the URL and a key; it is logged with its traceback (R12) or re-raised after shown().
    def start(**_kwargs):
        pywebview = logging.getLogger("pywebview")
        pywebview.info("Loading %s", URL)
        pywebview.warning("token=%s", TOKEN, stack_info=True)
        try:
            raise ValueError(f"inner {URL} {KEY}")
        except ValueError:
            pywebview.exception("navigation failed")
            raise RuntimeError(f"could not load {URL} with {KEY}")  # noqa: B904 - chained on purpose

    launcher.webview.start, launcher.webview.shown = start, after_shown
    rec = Recorder()
    if after_shown:
        with pytest.raises(RuntimeError):
            launcher(rec)
    else:
        assert launcher(rec) == 4
    text = assert_clean(launcher.log)
    assert "pywebview: Loading [redacted]" in text and "pywebview: token=[redacted]" in text
    assert "ValueError: inner [redacted] [redacted]" in text and "Traceback (most recent call last):" in text
    assert "RuntimeError: could not load [redacted] with [redacted]" in text
    if after_shown:
        assert case_lines(launcher.log) == [] and "The desktop app stopped with an error." in text
    else:
        (line,) = case_lines(launcher.log)  # the R13 case line is still written
        assert " window_start_failed version=120.0.2210.91 answer=closed error=RuntimeError: " in line


def test_windowed_output_and_thread_errors_go_through_the_filter(tmp_path):
    # The windowed build has no console: print(), stderr and thread tracebacks reach desktop.log only as
    # filtered records. Everything is restored afterwards.
    log = tmp_path / "desktop.log"
    before = (sys.stdout, sys.stderr, threading.excepthook, logging.getLogger().handlers[:])
    with desktop.desktop_log(log, (URL, "http://127.0.0.1:49731", TOKEN), windowed=True):
        print(f"opening {URL}")
        sys.stderr.write(f"partial {TOKEN} ")
        sys.stderr.write(f"and {KEY}\n")

        def fail():
            raise RuntimeError(f"api thread saw {URL}")

        thread = threading.Thread(target=fail, name="api")
        thread.start()
        thread.join()
        print("unterminated tail", end="")
    assert (sys.stdout, sys.stderr, threading.excepthook, logging.getLogger().handlers) == before
    text = assert_clean(log)
    assert "galliani.desktop.output: opening [redacted]" in text
    assert "galliani.desktop.output: partial [redacted] and [redacted]" in text
    assert "Uncaught exception in thread api." in text and "RuntimeError: api thread saw [redacted]" in text
    assert "unterminated tail" in text


def test_a_record_that_cannot_be_formatted_is_never_written_raw(tmp_path):
    log = tmp_path / "desktop.log"
    with desktop.desktop_log(log, (TOKEN,), windowed=False) as handler:  # pytest's own handler would raise first
        handler.handle(logging.makeLogRecord({"name": "pywebview", "levelno": logging.ERROR,
                                              "msg": "%d items for " + TOKEN, "args": ("not-a-number",)}))
    text = log.read_text(encoding="utf-8")
    assert TOKEN not in text and "could not be formatted" in text


def test_the_filter_itself_renders_tracebacks_and_stacks(tmp_path):
    # qa-security mutation check: dropping the exc_info or stack_info rendering in RedactingFilter survived,
    # because pytest's own capture handler formats records first and caches `exc_text`. In the app no other
    # handler runs first, so the R12 "details" would be lost. Fresh records straight to the handler:
    log = tmp_path / "desktop.log"
    try:
        raise RuntimeError(f"start failed at {URL}") from ValueError(f"cause {KEY}")
    except RuntimeError:
        exc_info = sys.exc_info()
    with desktop.desktop_log(log, (URL, TOKEN), windowed=False) as handler:
        handler.handle(logging.makeLogRecord({"name": "pywebview", "levelno": logging.ERROR, "levelname": "ERROR",
                                              "msg": "failed", "exc_info": exc_info}))
        handler.handle(logging.makeLogRecord({"name": "pywebview", "levelno": logging.WARNING, "levelname": "WARNING",
                                              "msg": "where", "stack_info": f"Stack (most recent call last):\n  {TOKEN}"}))
    text = assert_clean(log)
    assert "Traceback (most recent call last):" in text and "RuntimeError: start failed at [redacted]" in text
    assert "ValueError: cause [redacted]" in text and "Stack (most recent call last):" in text


def test_pywebview_gets_no_stderr_handler_of_its_own(tmp_path):
    # pywebview's `_setup_logger` adds a raw StreamHandler unless its logger already has a handler; desktop_log
    # pre-empts it so pywebview's records reach desktop.log only through the filtered root handler.
    pywebview = logging.getLogger("pywebview")
    before = pywebview.handlers[:]
    with desktop.desktop_log(tmp_path / "desktop.log", (TOKEN,), windowed=False):
        assert pywebview.handlers and all(isinstance(h, logging.NullHandler) for h in pywebview.handlers[len(before):])
        assert pywebview.propagate
    assert pywebview.handlers == before


# ---------------------------------------------------------------------------------- R15 smoke test

@pytest.mark.parametrize("platform, status, line", [
    ("win32", WebView2Status(True, "120.0.2210.91"), "INFO  webview2: 120.0.2210.91"),
    ("win32", MISSING, "INFO  webview2: missing"),
    ("linux", WebView2Status(True, "1.0"), "INFO  webview2: missing"),
])
def test_smoke_line(platform, status, line):
    assert w.smoke_line(platform, lambda: status) == line


def test_smoke_line_never_raises():
    def broken():
        raise RuntimeError("boom")

    assert w.smoke_line("win32", broken) == "INFO  webview2: missing"


class _Response:
    def __init__(self, status=200, body=None, text="", headers=None):
        self.status_code, self._body, self.text, self.headers = status, body or {}, text, headers or {}

    def json(self):
        return self._body


@pytest.mark.parametrize("webview2, passing, code", [
    (WebView2Status(True, "120.0.2210.91"), True, 0), (MISSING, True, 0), ("raise", True, 0), (MISSING, False, 1),
    (WebView2Status(True, "120.0.2210.91"), False, 1),
])
def test_smoke_test_exit_code_ignores_webview2(monkeypatch, capsys, webview2, passing, code):
    def fake_get(url, headers=None, timeout=None):
        authed = bool(headers)
        if url.endswith("/logo.png"):
            return _Response(headers={"content-type": "image/png"})
        if url.endswith("/"):
            return _Response(text="Welcome to Galliani")
        if not authed:
            return _Response(403)  # the no-token calls are still refused
        if url.endswith("/api/agent/config"):
            return _Response(body={"enabled": passing})
        return _Response(body={"desktop": True})

    def detect():
        if webview2 == "raise":
            raise OSError("registry unavailable")
        return webview2

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(desktop, "_agent_runtime_builds", lambda: True)
    monkeypatch.setattr(w, "detect_webview2", detect)
    assert desktop.smoke_test("http://127.0.0.1:1", TOKEN) == code
    out = capsys.readouterr().out.splitlines()
    assert sum(line.startswith("INFO  webview2: ") for line in out) == 1
    assert ("PASS  config without token rejected" in out) and ("PASS  agent API without token rejected" in out)
