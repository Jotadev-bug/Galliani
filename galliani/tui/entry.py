"""Spec 017 R2-R5: `galliani` and `python -m galliani.tui`.

With an objective this is exactly the one-shot `python -m galliani.cli` (R3). With none it starts an
interactive session, after checking that Textual is installed and the terminal can host it (R5).
Textual is imported only after those checks pass, inside `galliani.tui.app`.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

from galliani.cli import DEFAULT_BUDGET_USD
from galliani.permissions import EditMode

ONE_SHOT_HINT = 'To run one objective without the interactive terminal: galliani "<objective>"'


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="galliani", description="Work with the Galliani supervisor in an interactive terminal session, "
                                     "or run one objective (same as python -m galliani.cli).")
    parser.add_argument("objective", nargs="?", help="run this one objective and exit (the one-shot CLI)")
    parser.add_argument("--workspace", default=".", help="directory the agent may read (and, with approval, write)")
    parser.add_argument("--budget", type=float, default=DEFAULT_BUDGET_USD,
                        help=f"estimated USD per task before asking to spend more (default {DEFAULT_BUDGET_USD}; "
                             "0 or less means no limit)")
    parser.add_argument("--no-memory", action="store_true", help="do not read or save long-term memory")
    parser.add_argument("--accept-edits", action="store_true",
                        help="write files in the workspace without asking each time (other actions still ask)")
    parser.add_argument("--events", default=None, help="append the redacted event log to this JSON Lines file")
    parser.add_argument("--theme", choices=("dark", "light"), default="dark", help="interactive theme (default dark)")
    parser.add_argument("--context", default=None, help="one-shot only: reference text for the planner")
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


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:  # --help exits 0; usage errors exit 2
        return int(e.code or 0)
    if args.objective is not None:
        from galliani.cli import main as one_shot

        return one_shot(argv)  # R3: same arguments, output and exit code as python -m galliani.cli
    if args.context is not None or args.non_interactive:
        flag = "--context" if args.context is not None else "--non-interactive"
        print(f"galliani: {flag} needs an objective. {ONE_SHOT_HINT}", file=sys.stderr)
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
