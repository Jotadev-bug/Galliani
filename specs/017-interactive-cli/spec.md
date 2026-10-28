# 017 - Interactive CLI (terminal UI)

## Status

Approved by the user (2026-10-19). Design choices: `docs/decisions.md` Decision 0034 (Accepted).

Amended 2026-10-19 by user decision (Decision 0035, spec 018 R27): the terminal console script is `galliacli`, not `galliani`. The name `galliani` belongs to the desktop app (spec 016 R15 winget alias and the future R24 script). The code still uses `galliani` until spec 018 task C2 lands. The other changes spec 018 makes to this spec (R20, R22, R28, Behavior "Start") apply only once the whole of spec 018 is approved.

## Goal

Let the user work with Galliani in a terminal session, the way Claude Code works: type an objective, watch the supervised task plan, run and verify, answer approvals and questions inline, then type the next objective, all in one keyboard-driven full-screen terminal UI (TUI). The supervisor, permissions, memory and observability are reused unchanged; the TUI is a new front end, not new capability.

## Non-goals

- Streaming token output. The supervisor and adapters return whole worker outputs (no streaming API exists in `galliani/`); streaming is a follow-up that needs its own spec amendment to 001/006/011.
- Session resume, a persistent transcript, a persistent prompt history, or any settings file.
- More than one task at a time.
- Plugins, or themes or keymaps loaded from disk.
- Mouse-only interactions. The mouse may work where Textual supports it; nothing requires it.
- Image rendering, and opening links from rendered output.
- New tools, permission levels, approval kinds, or a "bypass permissions" mode.
- Bundling the TUI into `Galliani.exe` (release-engineer follow-up, Open Items).
- Changing the one-shot `python -m galliani.cli "<objective>"` in any way.

## Requirements

### Entry points and packaging

1. The TUI ships as an optional extra: `tui = ["textual>=8.2.8,<9"]` in `pyproject.toml` (8.2.8 released 2026-06-30, verified on PyPI 2026-10-19). Only `galliani/tui/app.py`, `galliani/tui/widgets.py` and `galliani/tui/styles.py` may import `textual` or `rich`. No other module under `galliani/` imports them, directly or transitively.
2. Two entry points run `galliani.tui.entry:main(argv)`: `python -m galliani.tui` and the console script `galliacli` (`[project.scripts] galliacli = "galliani.tui.entry:main"`; amended, spec 018 R27). `argparse` `prog` and every usage and help string name `galliacli`.
3. When `argv` contains an objective (a positional argument), `main` calls `galliani.cli.main(argv)` with the same arguments and returns its exit code. One-shot behavior, flags, output and exit codes are exactly those of `python -m galliani.cli`.
4. With no objective, `main` starts an interactive session. Session flags: `--workspace` (default `.`), `--budget` (default `DEFAULT_BUDGET_USD`; `<= 0` means no limit), `--no-memory`, `--accept-edits`, `--events PATH`, `--theme dark|light` (default `dark`). `--context` and `--non-interactive` without an objective are a usage error (exit 2). A missing workspace folder prints the one-shot's message and exits 2.
5. Fallback: if `textual` cannot be imported, or stdin or stdout is not a TTY, or `TERM=dumb`, `main` prints one message to stderr naming the cause, the install hint (when Textual is missing) and the one-shot form `galliacli "<objective>"`, and exits 2. The hint names no PyPI command: `Install the "tui" extra from your clone or the release wheel: pipx install ".[tui]"`. Amended 2026-10-28 (Decision 0039, spec 016 Open Question 8(a)), approved by the user: the project does not own the PyPI name `galliani`, so the earlier `pip install "galliani[tui]"` hint is removed. `textual` is imported only after these checks pass.

### Session controller (`galliani/tui/session.py`, no Textual)

6. `Session` drives one `Supervisor` through `start`, `approve`, `deny`, `clarify`, `cancel` and `set_edit_mode` only. It adds no supervisor API and calls no tool directly.
7. The runtime comes from `galliani.cli.build_runtime` (with `out` discarding output) plus the session's own `EventSink`. Keys come from `galliani.cli.load_keys` (environment, then OS credential store). Memory is opened once per session with `galliani.cli.open_memory`; memory scopes come from `galliani.cli.memory_scopes`.
8. Settings that `build_runtime` fixes (workspace, budget, memory on/off) change only while idle and apply to the next task; the controller closes the old runtime (`Runtime.aclose`) and builds a new one before that task starts.
9. Each submitted objective starts a new task with `Objective(goal=text, context=...)`, where the context is `galliani.cli.workspace_overview(workspace)` followed, when earlier tasks in this session finished, by "Earlier tasks in this session:" and up to the last 3 lines `- <objective> -> <status>: <summary>` (the desktop's rule, Decision 0020). This context is data in the new task's Task State; nothing is written to Memory.
10. Only one task runs at a time. Submitting an objective while a task is running or waiting adds a notice entry ("A task is still running. Answer it, wait for it, or press Esc to stop it.") and starts nothing.
11. Cancel uses `Supervisor.cancel` only, never `asyncio` task cancellation of a supervisor call (that would bypass the supervisor's safe-failure handling). A running task stops at its next checkpoint; until then the phase is `canceling`. A model call already in flight finishes or times out first.
12. The controller keeps per-task and per-session estimated cost from `worker_completed` event usage (the same arithmetic as `galliani.cli.UsageTotals`), the last routed worker from `route_selected` metadata `worker_id`, and the live plan as `viewmodel.PlanView` built with `build_task_view` after each supervisor call and on `plan_created`/`plan_revised` events.
13. Edit mode: the session default starts as `ask`, or `accept_edits` with `--accept-edits`. `/edit-mode` changes the default for later tasks and, when a task is active, calls `Supervisor.set_edit_mode` for it (014 R7). "Approve and accept edits" switches only the current task (014 R6); the session default is unchanged. The default is never persisted (014 R9: remembered for this conversation only).
14. The controller never raises to the UI. A call in the wrong phase adds a notice entry and returns. An unexpected exception adds an error entry with the exception type name only (and `safe_summary` for `GallianiError`), and the phase returns to `idle` (or stays `awaiting_*` if the supervisor still waits).
15. If no provider key is found, the session starts, shows the one-shot's "No model provider key found. Set one of: ..." as an error entry, and refuses objectives with the same text; slash commands still work.

### Transcript and rendering

16. The transcript is an ordered list of `TranscriptEntry` (Interfaces). It holds: user turns, plan outlines (`plan_created`, `plan_revised`, with step lines), tool calls, verification results, retries and replans, approval and question records (with the answer given), notices and errors, and the final result. Default event set = `galliani.cli.SHOWN_EVENTS`; with `/events on`, every other event type is added as `verbose` entries.
17. Entry text comes only from redacted `LifecycleEvent.public_summary` and metadata, `build_task_view` (which reads `TaskState.for_display()`), `ApprovalPrompt` fields, the clarification text, and the user's own input. Raw `TaskResult.output` and unredacted Task State are never rendered.
18. Every displayed string passes `sanitize()`, in this order: (1) `redact_text` from `galliani.redaction`; (2) removal of ESC and every C0/C1 control character except `\n` and `\t`, and of bidirectional override and isolate characters (U+202A-U+202E, U+2066-U+2069); (3) `redact_text` again, so a secret split by a removed character (for example `ESC[0m`, U+202E, BEL or NUL) and rejoined by step 2 is still masked. This applies to every source shown: `TranscriptEntry` `text`, `detail` and `body`, `PendingApproval` fields, the clarification question, the status bar, and the live plan. The `PlanView` held in `SessionState.plan` is sanitized when the controller stores it (each step's `purpose` and the plan's `revision_reason`), not at render time, so the UI never receives an unsanitized plan. Untrusted text is never parsed as Rich or Textual markup.
19. The final result entry shows status, summary, verification, files changed (`created`/`overwritten`, 014 R5), and "edits auto-approved: N" when non-zero. Its body is the result output when it is text, else `ResultView.preview`, rendered as Markdown (`markdown=True`) with links not opened and images not loaded. Bodies over 20,000 characters are cut with "(N more characters not shown)". A usage line closes each task.

### Terminal UI (`galliani/tui/app.py`, `widgets.py`, `styles.py`)

20. Layout: a single-column transcript; a plan panel; a status bar; a multi-line prompt at the bottom. At 100 columns or more the plan panel docks on the right; below 100 it is a one-line summary ("Plan v2 - step 2/4 - running") above the prompt that expands in place. `Ctrl+T` toggles it. At 60-99 columns nothing is cut except the status bar, which drops fields right to left (memory, then route) before truncating the workspace path from the left. Below 60 columns a one-line notice asks for a wider terminal; the app keeps working.
21. Status bar fields: workspace (folder name), last route (worker id), estimated task cost vs per-task budget (`$0.0123 / $0.50`, or `no limit`), edit mode (`ask` or `accept-edits`, the active task's mode while one runs), memory (`memory on`/`memory off`/`memory unavailable`), and the phase label (from `viewmodel.STATUS_LABELS` while a task runs).
22. Prompt keys: `Enter` sends; `Shift+Enter` (where the terminal reports it), `Alt+Enter` and `Ctrl+J` insert a newline; `Up`/`Down` on the first/last line recall session history (in memory only, max 100 entries, never written to disk); when idle, `Ctrl+C` with text clears the prompt. While a task is active, R25 takes precedence.
23. Approvals render inline as a focused prompt card showing `action_summary`, `risk_summary` and `scope`, with keys `y` approve, `n` deny, `a` approve and accept edits (shown and accepted only when `approve_and_accept_edits` is in `allowed_choices`), `Esc` deny. Other keys do nothing; there is no default on `Enter`. Focus returns to the prompt afterwards.
24. Clarification questions render inline as a focused single-line answer field: `Enter` sends a non-empty answer; `Esc` cancels the task (the one-shot's "empty to cancel" rule).
25. While a task runs: `Esc` or `Ctrl+C` cancels it (R11). A second `Ctrl+C` within 2 seconds quits. When idle, `Ctrl+C` on an empty prompt shows "Press Ctrl+C again to quit" and a second press within 2 seconds quits; `Ctrl+Q` and `/quit` quit. Quitting with a task active calls `cancel`, waits at most 3 seconds for the run to return, then closes the runtime and exits 0.
26. Slash commands (parsed by `galliani/tui/commands.py`):

    | Command | Effect | While a task is active |
    |---|---|---|
    | `/help` | lists commands and keys | allowed |
    | `/clear` | clears the visible transcript (not history, not the task) | allowed |
    | `/workspace [PATH]` | shows, or switches to an existing folder | refused |
    | `/edit-mode [ask\|accept-edits]` | shows or sets (R13) | allowed |
    | `/budget [USD\|off]` | shows or sets the per-task budget | refused |
    | `/memory [list]` | lists records in the session's scopes, sensitive ones redacted (010 Security) | allowed |
    | `/memory forget ID` | deletes that record if it is in the session's scopes | refused |
    | `/memory on\|off` | reads and saves memory for later tasks, or not | refused |
    | `/events [on\|off]` | toggles verbose public events | allowed |
    | `/theme [dark\|light]` | switches theme for this session | allowed |
    | `/quit` | quits (R25) | allowed |

    An unknown command or bad argument adds an error entry with the usage line and changes nothing. A line starting with `//` is sent as an objective with one `/` removed.
27. Themes: `dark` (default) and `light`, built from Decision 0025's palette: dark background `#121318`, silver accent; light background near-white, graphite accent; status colors good/warn/bad and the agent teal keep their meaning. Body text contrast is at least 4.5:1 against its background in both themes in true color.
28. Degradation: with `NO_COLOR` set, no color is emitted and every state stays readable from text alone. In 16-color terminals only ANSI named colors are used. No information is carried by color alone: status, edit mode and step states always have a word or glyph (`[ok]`, `[x]`, `>`, `...`). The spinner is the only animation; it is replaced by static "working..." when Textual's animation level is `none` (`TEXTUAL_ANIMATIONS=none`) or `GALLIANI_REDUCED_MOTION=1`.
29. Keyboard-only: every action has a key; focus is always visible; `Tab`/`Shift+Tab` move between prompt, transcript (scrollable with `PageUp`/`PageDown`/`Home`/`End`) and plan panel. Textual's command palette is disabled, and no binding or system command saves a screenshot or exports the screen.

### Safety and privacy

30. Only public summaries are rendered (R17). Hidden reasoning, provider reasoning fields and raw tool arguments never reach the TUI; the TUI adds no path by which they could.
31. Nothing is written to disk by the TUI: no transcript, history, settings, log or screenshot file. The only files are those the existing stack writes: memory through approved `remember` calls, and the redacted JSONL event log when the user passes `--events`.
32. No telemetry and no network access of its own; the only network traffic is the provider calls the supervisor already makes.
33. Approvals go through `Supervisor.approve`/`deny` unchanged. The TUI cannot approve anything the one-shot `interact` loop could not, and never approves without a key press for that prompt.
34. Untrusted content (model output, tool output, file names, memory text) cannot change TUI settings, run slash commands, or answer prompts: slash commands are parsed only from text the user typed into the prompt.

## Behavior

- **Start.** `galliacli` -> fallback checks (R5) -> `Session(config)` -> `run_app(session, theme=...)`. The transcript opens with one notice: workspace, edit mode, budget, memory state, and "Type an objective, or /help".
- **Turn.** User presses Enter -> UI calls `session.submit(text)` in a Textual worker -> a user entry is added -> `Supervisor.start` runs; events append entries and refresh the plan and status through the listener -> the call returns when the task finishes or pauses.
- **Pause.** `state.phase` becomes `awaiting_approval` (with `pending_approval`) or `awaiting_answer` (with `question`); the UI focuses the inline card; its key calls `approve`/`deny`/`answer`/`cancel`, each awaited in a worker.
- **Finish.** A result entry and a usage line are added; the phase returns to `idle`; focus returns to the prompt.

```text
idle --submit--> running --pause--> awaiting_approval | awaiting_answer --key--> running
running --cancel--> canceling --run returns--> idle
running --finish/block/fail--> idle          awaiting_* --deny/cancel--> idle
any --quit--> closed
```

## Interfaces and Data Contracts

These signatures are the contract between task A (controller) and task B (Textual layer). Names, fields and semantics are stable; A may add private helpers only.

```python
# galliani/tui/session.py  -- imports nothing from textual or rich
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal

from galliani.cli import DEFAULT_BUDGET_USD, Runtime
from galliani.memory import MemoryStore
from galliani.observability import EventSink
from galliani.permissions import EditMode
from galliani.viewmodel import PlanView

class Phase(str, Enum):
    idle = "idle"
    running = "running"
    awaiting_approval = "awaiting_approval"
    awaiting_answer = "awaiting_answer"
    canceling = "canceling"
    closed = "closed"

class EntryKind(str, Enum):
    user = "user"; plan = "plan"; route = "route"; tool = "tool"; verification = "verification"
    retry = "retry"; replan = "replan"; approval = "approval"; question = "question"; edit_mode = "edit_mode"
    event = "event"            # any other public event (verbose)
    result = "result"; usage = "usage"; notice = "notice"; error = "error"

@dataclass(frozen=True)
class TranscriptEntry:
    seq: int                     # 1-based, strictly increasing for the session
    kind: EntryKind
    text: str                    # sanitized (R18); one line or a short paragraph
    detail: tuple[str, ...] = () # extra sanitized lines (plan steps, files changed)
    body: str | None = None      # sanitized long text: the result output
    markdown: bool = False       # render `body` as Markdown (result only)
    verbose: bool = False        # shown only while verbose events are on
    task_id: str | None = None
    step_id: str | None = None

@dataclass(frozen=True)
class PendingApproval:
    action_summary: str
    risk_summary: str
    scope: str
    can_accept_edits: bool       # "approve_and_accept_edits" in allowed_choices

@dataclass(frozen=True)
class StatusSnapshot:
    workspace: Path
    route: str | None
    task_cost_usd: float
    session_cost_usd: float
    budget_usd: float | None     # None = no limit
    edit_mode: EditMode          # active task's mode, else the session default
    memory: Literal["on", "off", "unavailable"]
    verbose_events: bool
    status_label: str | None     # viewmodel.STATUS_LABELS value while a task is active

@dataclass(frozen=True)
class SessionState:
    phase: Phase
    status: StatusSnapshot
    plan: PlanView | None        # sanitized when stored (R18): step purpose, revision_reason
    pending_approval: PendingApproval | None
    question: str | None
    cleared_after: int           # entries with seq <= this are hidden (/clear)

@dataclass(frozen=True)
class UiAction:
    kind: Literal["quit", "theme"]
    value: str | None = None     # theme name for "theme"

@dataclass
class SessionConfig:
    workspace: Path
    budget_usd: float | None = DEFAULT_BUDGET_USD
    memory_on: bool = True
    edit_mode: EditMode = EditMode.ask
    verbose_events: bool = False
    events_path: Path | None = None

RuntimeFactory = Callable[[SessionConfig, Sequence[EventSink], MemoryStore | None], Runtime]
Listener = Callable[[], None]    # "state or entries changed"; called on the event loop thread

class Session:
    def __init__(self, config: SessionConfig, *, runtime_factory: RuntimeFactory | None = None,
                 memory: MemoryStore | None | Literal["open"] = "open") -> None: ...
    @property
    def state(self) -> SessionState: ...
    def entries(self, after: int = 0) -> list[TranscriptEntry]: ...   # seq > after, verbose filtered
    def subscribe(self, listener: Listener) -> Callable[[], None]: ...  # returns unsubscribe
    async def submit(self, text: str) -> UiAction | None: ...  # slash command or objective; returns when the
                                                               # task stops running (done, paused, finished)
    async def approve(self, *, accept_edits: bool = False) -> None: ...
    async def deny(self) -> None: ...
    async def answer(self, text: str) -> None: ...
    def cancel(self) -> None: ...                # cooperative (R11); safe in any phase
    async def aclose(self, timeout: float = 3.0) -> None: ...   # R25 quit path; phase -> closed

def sanitize(text: str) -> str: ...              # R18: redact, strip controls, redact again
```

```python
# galliani/tui/commands.py  -- pure, no I/O
@dataclass(frozen=True)
class CommandSpec:
    name: str                    # "memory"
    usage: str                   # "/memory [list|forget ID|on|off]"
    summary: str
    allowed_while_active: bool   # per the R26 table; for /memory, decided per sub-command

@dataclass(frozen=True)
class Command:
    name: str
    args: tuple[str, ...]

class CommandError(ValueError): ...   # str(e) is a safe, user-facing message with the usage line

COMMANDS: dict[str, CommandSpec]
def parse_command(text: str) -> Command | None: ...  # None if not a command (incl. "//..."); raises CommandError
```

```python
# galliani/tui/entry.py  -- no textual import at module level
def main(argv: list[str] | None = None) -> int: ...

# galliani/tui/app.py  -- task B
def run_app(session: Session, *, theme: Literal["dark", "light"] = "dark") -> int: ...  # exit code
```

- `galliani/tui/__main__.py`: `sys.exit(main())`.
- Styles are Python string constants in `galliani/tui/styles.py` (no `.tcss` files), so no package-data change is needed.

## Error Handling

- Textual missing, not a TTY, `TERM=dumb`: R5 message, exit 2.
- Missing workspace (start or `/workspace`): the one-shot's message; at start exit 2, in session an error entry and no change.
- No provider key: R15.
- Supervisor or runtime exception: R14; the next submit rebuilds the runtime.
- `approve(accept_edits=True)` on an ineligible prompt: the supervisor's `ContractError` becomes an error entry; the prompt stays open (014 Error Handling).
- Memory unavailable at start: notice entry, `memory: unavailable`, tasks run without memory (010 Error Handling). `/memory forget` of an unknown or out-of-scope id: error entry, nothing deleted.
- Terminal resized below 60 columns: notice (R20); no crash.
- Textual exception at runtime: Textual restores the terminal; `run_app` returns 1 and prints only the exception type to stderr.

## Security

- Trust boundary: everything shown except the user's own typing is untrusted (000). It is redacted and sanitized (R18), never interpreted as markup, commands or answers (R34), and rendered Markdown opens no links and loads no images (R19).
- Terminal escape injection (OSC 52 clipboard writes, OSC 8 links, cursor and title control) from model or file content is blocked by R18. qa-security tests it. R18 redacts again after stripping, because stripping can rejoin a secret that a control or bidi character had split.
- Permissions: unchanged (R33, 009, 014). `a` is offered only when the supervisor offers it. `Esc` on an approval denies (fail closed). No key sequence approves more than one prompt.
- Privacy: R30-R32. The prompt history and transcript live in process memory only and are gone on exit. Task State is discarded with the session; Memory changes only through the existing approved `remember` tool and the user's explicit `/memory forget`.
- Secrets: keys come only from `load_keys`; the TUI never shows, logs or asks for them. User input echoed in the transcript is redacted like everything else (R18).
- Developer-tooling environment variables (`TEXTUAL=devtools`, `TEXTUAL_LOG`) are Textual's own and set only by the user; the app does not set them, and the docs say they can expose transcript text to a local devtools console or log file.

## Acceptance Criteria

### One-Shot Unchanged

Given `galliacli "Summarize notes" --workspace W`
When it runs
Then the output and exit code equal `python -m galliani.cli "Summarize notes" --workspace W`.

### Fallback Without Textual Or TTY

Given Textual is not importable, or stdout is not a TTY
When `galliacli` runs with no objective
Then it prints the R5 message to stderr, exits 2, and never imports `textual`.

### Send Objective

Given an idle session with a scripted runtime
When the user types an objective and presses Enter
Then a user entry, a plan entry with its steps, tool and verification entries, a result entry and a usage line appear in order, and the phase returns to `idle`.

### Approval y / n / a

Given a task paused on a `write_file` approval
When the user presses `y` / `n` / `a`
Then the write runs / the task is blocked / the write runs and the task's mode is `accept-edits` while the session default stays `ask`; for a spending approval `a` does nothing and is not shown.

### Esc Denies

Given a task paused on any approval
When the user presses `Esc`
Then `Supervisor.deny` is called and the task ends `blocked`.

### Clarification

Given the planner asks a question
When the user types an answer and presses Enter
Then `Supervisor.clarify` receives it and the task continues; when the user presses `Esc` instead, the task ends `canceled`.

### Cancel While Running

Given a task is running
When the user presses `Esc` or `Ctrl+C`
Then `Supervisor.cancel` is called, the status shows the canceling phase, the task ends `canceled`, and no `asyncio` cancellation of the supervisor call occurs.

### Double Ctrl+C Quits

Given a task is running
When the user presses `Ctrl+C` twice within 2 seconds
Then the task is canceled and the app exits 0 within 3 seconds of the second press.

### One Task At A Time

Given a task is running
When the user submits another objective
Then a notice is shown and no second task starts.

### Slash Commands

Given an idle session
When the user runs each R26 command with valid and invalid arguments
Then valid ones take effect as the table says, invalid ones show the usage line and change nothing, and commands marked "refused" are refused while a task is active.

### Memory Forget Is Scoped

Given a memory record outside the session's scopes
When the user runs `/memory forget <its id>`
Then nothing is deleted and an error entry is shown.

### No Hidden Reasoning Or Secrets

Given a scripted run whose adapter returns a reasoning field and whose output contains an `sk-` key, an ANSI/OSC escape sequence and `[bold]markup[/bold]`
When the run finishes
Then the transcript holds no reasoning text, the key is masked, no ESC character remains, and the markup text is shown literally.

### Split Secret Stays Masked

Given text containing an `sk-` key split by `ESC[0m`, U+202E, BEL or NUL, arriving in a result output, an approval field, a plan step `purpose` or a plan `revision_reason`
When it is shown in the transcript, the approval card or the plan panel
Then the rejoined key is masked and no control or bidi character remains, and `SessionState.plan` already holds the sanitized text.

### Untrusted Text Cannot Run Commands

Given model output containing the line `/edit-mode accept-edits`
When the result is rendered
Then the edit mode is unchanged.

### Narrow Width

Given an 80x24 terminal
When a task with a 4-step plan runs
Then the plan panel is a one-line summary, the status bar fits on one line, and nothing overflows horizontally; at 60 columns the same holds.

### NO_COLOR

Given `NO_COLOR=1`
When the app renders the transcript, an approval and the status bar
Then no color is emitted and edit mode, step states and status are readable from text.

### Nothing Written To Disk

Given a session that runs a task, answers an approval and quits, without `--events`
When the run ends
Then no new file exists outside the workspace files the task wrote with approval and the memory file.

## Tests

- **Controller (A), `tests/tui/`:** `Session` with a runtime built by `build_runtime` on `MockProvider` (as `tests/core/test_cli.py` does) or on `galliani.testing` scripted adapters. Happy path and at least one failure path for: submit, approve y/n/a (eligible and ineligible), deny, clarify and cancel-by-answer, cancel while running (cooperative), quit with a task active, one-task-at-a-time, earlier-task context (R9), runtime rebuild after `/budget`, `/workspace`, `/memory off`, no keys, memory unavailable, supervisor exception -> error entry, `sanitize` (redaction, C0/C1, ESC, bidi, markup literal, a secret split by a removed character masked after rejoining), and `state.plan` sanitized on store (step `purpose`, `revision_reason`). `parse_command`: every command, every bad argument, `//` escape. `entry.main`: objective delegates to `galliani.cli.main`; usage and fallback text name `galliacli`; no-objective fallbacks (Textual blocked via `sys.modules["textual"] = None`, non-TTY); flag errors.
- **Import boundary (A):** an AST scan of `galliani/` asserting `textual`/`rich` are imported only by the three R1 modules, and importing `galliani.tui.session` and `galliani.tui.entry` with Textual blocked succeeds.
- **Golden (A):** the plain-text rendering of `entries()` (kind, text, detail, body) for one scripted three-step run with a write approval, compared with `tests/tui/golden/transcript_basic.txt`. Ids, timestamps and costs that vary are not in entry text.
- **Pilot (B), `tests/tui/test_app_pilot.py`:** `App.run_test(size=...)` for: send objective, approval y/n/a and Esc, clarification answer and Esc, cancel with Esc and Ctrl+C, double Ctrl+C quit, history Up/Down, newline keys, each slash command's UI effect (`/clear`, `/theme`, `/events`, `/quit`), narrow widths 80 and 60, `NO_COLOR`, reduced motion (no spinner timer), command palette disabled. At least one failure path each (wrong key ignored, invalid command).
- **CI:** CI installs the `tui` extra and sets `GALLIANI_REQUIRE_TUI=1`; with it set, Pilot tests fail instead of skipping when Textual is missing. Locally they skip via `pytest.importorskip("textual")`.
- **Security (D):** the "No Hidden Reasoning Or Secrets", "Split Secret Stays Masked", "Untrusted Text Cannot Run Commands" and "Nothing Written To Disk" criteria as tests; review of R18 against OSC 52/OSC 8/CSI payloads.

## Evaluation

- `permission_bypass_count` stays 0: run the existing approval eval fixtures through `Session` instead of `interact` and compare decisions (no new eval fixtures needed for v1).
- Hidden reasoning leak count and secret persistence count stay 0 in the TUI tests.
- Manual check on Windows Terminal and on a 16-color console: theme legibility, focus visibility, narrow width. Recorded in the PR.

## Implementation Tasks

- [ ] A: `galliani/tui/{__init__,__main__,entry,session,commands}.py` and controller, import-boundary and golden tests (R1-R19, R26 parsing, R30-R34 controller side).
- [ ] B: `galliani/tui/{app,widgets,styles}.py` and Pilot tests (R20-R29).
- [ ] C: `pyproject.toml` extra and console script, CI and release workflow installs, `CHANGELOG.md` (R1, R2, Tests CI).
- [ ] D: qa-security review and security tests; `docs/security.md` section for the TUI trust boundary.
- [ ] E: README "Interactive terminal" section (product-growth), after B.

## Dependencies

Depends on `001-agent-core` (supervisor API), `009-permissions`, `010-memory`, `011-observability`, `012-desktop-ui` (`viewmodel`), `014-accept-edits`, and on `galliani/cli` (Decision 0015). External: Textual `>=8.2.8,<9` (MIT).

## Open Items (not blocking approval)

1. Packaging into `Galliani.exe` or a separate terminal binary (release-engineer follow-up).
2. Streaming token output (needs a 001/006/011 amendment).
3. SVG screenshot snapshots with `pytest-textual-snapshot` (1.1.0, January 2025, pins `syrupy==4.8.0`; compatibility with Textual 8 unverified). v1 uses the plain-text golden instead.
4. Resolved 2026-10-19 by the user (Decision 0035): the desktop keeps `galliani` (016 R15 winget alias and the future 016 R24 script), and the terminal is `galliacli`. Until 016 Phase 5 adds package data, `galliacli` works only from a source or editable install.
5. The desktop app and a TUI session can run at once and share `memory.json`; concurrent writes are last-writer-wins, as today with the one-shot CLI. Resolved by spec 010 Amendment A (Decision 0040, approved 2026-10-28): every change is a locked re-read and apply by record id, and reads refresh from disk. Read from the code, the current behavior is worse than last-writer-wins: a stale snapshot can erase the other process's records.
