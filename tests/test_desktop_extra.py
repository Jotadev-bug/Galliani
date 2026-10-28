"""Spec 016 Phase 5a R28: `galliani` without the "desktop" extra (pywebview) prints one message and exits 2."""

from __future__ import annotations

import sys
import types

import pytest

from app import desktop

R28_MESSAGE = ('galliani: the desktop app needs the "desktop" extra (pywebview is not installed). '
               'See the README "Install" section. For the terminal, run: galliacli')


@pytest.fixture
def no_webview(monkeypatch, tmp_path):
    """pywebview unimportable (a `None` entry in sys.modules); the server, folder and port are recorded fakes."""
    monkeypatch.setitem(sys.modules, "webview", None)
    for name in ("ROUTER_DESKTOP", "ROUTER_APP_TOKEN", "ROUTER_LOG_PATH"):
        monkeypatch.setenv(name, "unset")
    calls = types.SimpleNamespace(servers=[], data_dirs=0, smoke=[])

    def user_data_dir():
        calls.data_dirs += 1
        return tmp_path

    def start_server(port):
        calls.servers.append(port)
        return types.SimpleNamespace(should_exit=False)

    monkeypatch.setattr(desktop, "user_data_dir", user_data_dir)
    monkeypatch.setattr(desktop, "free_port", lambda: 49731)
    monkeypatch.setattr(desktop, "start_server", start_server)
    monkeypatch.setattr(desktop, "smoke_test", lambda base, token: calls.smoke.append(base) or 0)
    return calls


def test_the_message_is_the_fixed_spec_text():
    assert desktop.DESKTOP_EXTRA_MISSING == R28_MESSAGE
    assert desktop.EXIT_DESKTOP_EXTRA_MISSING == 2


@pytest.mark.parametrize("argv", [[], ["--debug"], ["--simulate-missing-webview2"]])
def test_without_pywebview_it_exits_2_before_the_server_starts(no_webview, capsys, argv):
    assert desktop.main(argv) == 2
    out, err = capsys.readouterr()
    assert err == R28_MESSAGE + "\n" and out == ""  # one line, no traceback, not the WebView2 message
    assert no_webview.servers == [] and no_webview.smoke == []
    assert no_webview.data_dirs == 0  # nothing is created or logged before the check


def test_smoke_test_does_not_need_pywebview(no_webview, capsys):
    assert desktop.main(["--smoke-test"]) == 0
    assert no_webview.servers == [49731] and no_webview.smoke == ["http://127.0.0.1:49731"]
    assert R28_MESSAGE not in capsys.readouterr().err


def test_the_check_looks_pywebview_up_without_importing_it(monkeypatch):
    monkeypatch.delitem(sys.modules, "webview", raising=False)
    looked_up = []

    def find_spec(name):
        looked_up.append(name)
        return None

    monkeypatch.setattr(desktop.importlib.util, "find_spec", find_spec)
    assert desktop.webview_installed() is False
    assert looked_up == ["webview"] and "webview" not in sys.modules


def test_an_already_imported_pywebview_counts_as_installed(monkeypatch):
    monkeypatch.setitem(sys.modules, "webview", types.SimpleNamespace())  # a module without __spec__
    assert desktop.webview_installed() is True
