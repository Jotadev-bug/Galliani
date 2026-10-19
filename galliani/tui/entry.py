"""Spec 017 R2-R5 and 018 R23-R25, R27: `galliacli`, `python -m galliani` and `python -m galliani.tui`.

With an objective this is exactly the one-shot `python -m galliani.cli` (R3). With none it starts an
interactive session, after checking that Textual is installed and the terminal can host it (R5).
Textual is imported only after those checks pass, inside `galliani.tui.app`, and never for `--version`.
The console script is `galliacli`; `galliani` belongs to the desktop app (018 R27).
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

import galliani
from galliani.cli import DEFAULT_BUDGET_USD
from galliani.permissions import EditMode

PROG = "galliacli"
ONE_SHOT_HINT = f'To run one objective without the interactive terminal: {PROG} "<objective>"'


def version_line() -> str:
    """018 R24: what `galliacli --version` prints."""
    return f"{PROG} {galliani.__version__}"


def is_wide_workspace(path: Path) -> bool:
    """018 R25: the resolved workspace is the user's home folder or a filesystem root (a drive on Windows).
    The session puts the result in `BannerInfo.wide_workspace`; the banner shows the warning. Nothing is stored."""
    resolved = Path(path).expanduser().resolve()
    try:
        home = Path.home().resolve()
    except (RuntimeError, OSError):  # no home folder known
        home = None
    return resolved == home or resolved.parent == resolved


def _parser(*, strict: bool = True) -> argparse.ArgumentParser:
    """The `galliacli` flags. `strict=False` checks no values, so `_objective_given` only finds the positional."""
    parser = argparse.ArgumentParser(
        prog=PROG, exit_on_error=strict, add_help=strict,
        description="Work with the Galliani supervisor in an interactive terminal session, "
                    "or run one objective (same as python -m galliani.cli).")
    loose = {} if strict else {"nargs": "?"}  # a missing flag value is the one-shot's error to report
    parser.add_argument("--version", action="store_true", help=f"print {PROG} and its version, then exit")
    parser.add_argument("objective", nargs="?", help="run this one objective and exit (the one-shot CLI)")
    parser.add_argument("--workspace", **loose, default=".",
                        help="directory the agent may read (and, with approval, write)")
    parser.add_argument("--budget", **loose, type=float if strict else str, default=DEFAULT_BUDGET_USD,
                        help=f"estimated USD per task before asking to spend more (default {DEFAULT_BUDGET_USD}; "
                             "0 or less means no limit)")
    parser.add_argument("--no-memory", action="store_true", help="do not read or save long-term memory")
    parser.add_argument("--accept-edits", action="store_true",
                        help="write files in the workspace without asking each time (other actions still ask)")
    parser.add_argument("--events", **loose, default=None,
                        help="append the redacted event log to this JSON Lines file")
    parser.add_argument("--theme", **loose, choices=("dark", "light") if strict else None, default="dark",
                        help="interactive theme (default dark)")
    parser.add_argument("--context", **loose, default=None, help="one-shot only: reference text for the planner")
    parser.add_argument("--non-interactive", action="store_true", help="one-shot only: stop instead of asking")
    return parser


def _textual_missing() -> bool:
    """True when `textual` cannot be imported. Checked without importing it."""
    if "textual" in sys.modules:
        return sys.modules["textual"] is None
    try:
        return importlib.util.find_spec("textual") is None
    except (ImportError, ValueError):
        return True


def _isatty(stream) -> bool:
    try:
        return stream is not None and stream.isatty()
    except (AttributeError, ValueError, OSError):
        return False


def _fallback_reason() -> str | None:
    """R5: why the interactive terminal cannot start here, or None."""
    if _textual_missing():
        return ('The interactive terminal needs Textual, which is not installed. '
                'Install it with: pip install "galliani[tui]"')
    if not (_isatty(sys.stdin) and _isatty(sys.stdout)):
        return "The interactive terminal needs a terminal: stdin and stdout must be a TTY."
    if os.environ.get("TERM", "").lower() == "dumb":
        return "The interactive terminal cannot run with TERM=dumb."
    return None


def _objective_given(argv: list[str]) -> bool:
    """R3: whether argv names an objective, found before any flag value is checked."""
    try:
        args, _ = _parser(strict=False).parse_known_args(argv)
    except (argparse.ArgumentError, SystemExit):
        return False
    return args.objective is not None


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    flags = argv[:argv.index("--")] if "--" in argv else argv  # after "--" everything is the objective
    if "--version" in flags:
        print(version_line())  # 018 R24: before anything else, with any other flags, without Textual
        return 0
    if _objective_given(argv):
        from galliani.cli import main as one_shot

        try:
            return one_shot(argv)  # R3: same arguments, output, usage errors and exit code as python -m galliani.cli
        except SystemExit as e:  # its argparse usage errors exit 2
            return int(e.code or 0)
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:  # --help exits 0; usage errors exit 2
        return int(e.code or 0)
    if args.context is not None or args.non_interactive:
        flag = "--context" if args.context is not None else "--non-interactive"
        print(f"{PROG}: {flag} needs an objective. {ONE_SHOT_HINT}", file=sys.stderr)
        return 2
    workspace = Path(args.workspace)
    if not workspace.is_dir():
        print(f"Workspace folder not found: {workspace.resolve()}\n"
              "Pass --workspace with an existing folder the agent may read (it can only touch files inside it).",
              file=sys.stderr)
        return 2
    reason = _fallback_reason()
    if reason is not None:
        print(f"{reason}\n{ONE_SHOT_HINT}", file=sys.stderr)
        return 2

    from galliani.tui.session import Session, SessionConfig

    session = Session(SessionConfig(
        workspace=workspace,
        budget_usd=args.budget if args.budget > 0 else None,
        memory_on=not args.no_memory,
        edit_mode=EditMode.accept_edits if args.accept_edits else EditMode.ask,
        events_path=Path(args.events) if args.events else None,
    ))
    from galliani.tui.app import run_app  # imports Textual; only reached after the R5 checks

    return run_app(session, theme=args.theme)
