"""Themes and CSS for the terminal UI (spec 017 R20-R29).

Styles are Python string constants; there are no `.tcss` files, so no package-data change is needed.
The palette follows Decision 0025: graphite surfaces, a silver accent, and the status colours that keep
their meaning (good / warn / bad / agent teal). Every colour is a `$g-*` theme variable, so one CSS string
serves the dark theme, the light theme and the ANSI theme used under `NO_COLOR` and in 16-colour terminals.
"""

from __future__ import annotations

from dataclasses import replace

from textual.theme import BUILTIN_THEMES, Theme

DARK = "galliani-dark"
LIGHT = "galliani-light"
ANSI = "galliani-ansi"

# name -> (hex colour) used for contrast checks and the Theme objects below.
DARK_PALETTE = {
    "bg": "#121318", "surface": "#1a1c23", "border": "#444856", "fg": "#e4e6ea", "muted": "#9ba1ae",
    "accent": "#c3c7d0", "good": "#5ec49a", "warn": "#e0b04f", "bad": "#ec6f78", "agent": "#4cc2bd",
}
LIGHT_PALETTE = {
    "bg": "#f7f8fa", "surface": "#eceef2", "border": "#8c92a0", "fg": "#1a1c22", "muted": "#555b69",
    "accent": "#343944", "good": "#1d7a55", "warn": "#8a5a00", "bad": "#b3262f", "agent": "#0f6f6c",
}

# The ANSI theme names only terminal colours, so a 16-colour console shows what it can and NO_COLOR strips them.
_ANSI_VARIABLES = {
    "g-bg": "ansi_default", "g-surface": "ansi_default", "g-border": "ansi_bright_black",
    "g-fg": "ansi_default", "g-muted": "ansi_bright_black", "g-accent": "ansi_bright_white",
    "g-good": "ansi_green", "g-warn": "ansi_yellow", "g-bad": "ansi_red", "g-agent": "ansi_cyan",
}


def _variables(palette: dict[str, str]) -> dict[str, str]:
    return {f"g-{name}": value for name, value in palette.items()}


def _theme(name: str, palette: dict[str, str], *, dark: bool) -> Theme:
    return Theme(
        name=name, primary=palette["accent"], secondary=palette["agent"], accent=palette["accent"],
        success=palette["good"], warning=palette["warn"], error=palette["bad"],
        foreground=palette["fg"], background=palette["bg"], surface=palette["surface"],
        panel=palette["surface"], dark=dark, variables=_variables(palette),
    )


DARK_THEME = _theme(DARK, DARK_PALETTE, dark=True)
LIGHT_THEME = _theme(LIGHT, LIGHT_PALETTE, dark=False)
# Built on Textual's own ansi-dark theme, which defines the variables its widgets need in ANSI mode.
ANSI_THEME = replace(BUILTIN_THEMES["ansi-dark"], name=ANSI,
                     variables={**BUILTIN_THEMES["ansi-dark"].variables, **_ANSI_VARIABLES})
THEMES = (DARK_THEME, LIGHT_THEME, ANSI_THEME)

# Focus is shown by a heavier border as well as a colour, so it survives NO_COLOR.
APP_CSS = """
Screen {
    layout: vertical;
    background: $g-bg;
    color: $g-fg;
}
#narrow {
    display: none;
    height: auto;
    padding: 0 1;
    color: $g-warn;
    text-style: bold;
}
#narrow.-show { display: block; }
#body { height: 1fr; }

TranscriptView {
    width: 1fr;
    height: 1fr;
    padding: 0 1 0 0;
    background: $g-bg;
    border-left: tall $g-border;
    scrollbar-size-vertical: 1;
    scrollbar-background: $g-bg;
    scrollbar-color: $g-border;
    scrollbar-color-hover: $g-accent;
    scrollbar-color-active: $g-accent;
}
TranscriptView:focus { border-left: heavy $g-accent; }
TranscriptView > .entry { height: auto; width: 1fr; padding: 0 0 0 1; }
TranscriptView > .entry.-gap { margin-top: 1; }
TranscriptView > .-user { color: $g-accent; text-style: bold; }
TranscriptView > .-plan { color: $g-fg; text-style: bold; }
TranscriptView > .-tool, TranscriptView > .-route, TranscriptView > .-retry,
TranscriptView > .-replan, TranscriptView > .-edit_mode, TranscriptView > .-event,
TranscriptView > .-usage { color: $g-muted; }
TranscriptView > .-verification { color: $g-agent; }
TranscriptView > .-approval, TranscriptView > .-question { color: $g-warn; }
TranscriptView > .-notice { color: $g-muted; text-style: italic; }
TranscriptView > .-error { color: $g-bad; text-style: bold; }
TranscriptView > .-result { color: $g-good; text-style: bold; }
TranscriptView > .-verbose { text-style: dim; }
TranscriptView > .body { color: $g-fg; padding: 0 0 0 3; text-style: none; }
TranscriptView > Markdown.body {
    margin: 0;
    padding: 0 0 0 3;
    background: $g-bg;
    color: $g-fg;
}

PlanPanel {
    display: none;
    width: 40;
    height: 1fr;
    padding: 0 1;
    background: $g-surface;
    border: round $g-border;
    border-title-color: $g-muted;
}
PlanPanel:focus { border: heavy $g-accent; border-title-color: $g-accent; }
PlanPanel.-docked { display: block; }

PlanSummary {
    display: none;
    height: auto;
    max-height: 9;
    padding: 0 1;
    background: $g-surface;
    color: $g-fg;
    border-left: tall $g-border;
}
PlanSummary:focus { border-left: heavy $g-accent; }
PlanSummary.-compact { display: block; }

#dock { height: auto; }
StatusBar {
    height: 1;
    padding: 0 1;
    background: $g-surface;
    color: $g-muted;
}
#hint { height: auto; padding: 0 1; color: $g-warn; display: none; }
#hint.-show { display: block; }

ApprovalCard {
    height: auto;
    padding: 0 1;
    background: $g-surface;
    border: round $g-warn;
}
ApprovalCard:focus { border: heavy $g-warn; }
QuestionInput {
    display: none;
    height: 3;
    background: $g-bg;
    color: $g-fg;
    border: round $g-border;
}
QuestionInput.-show { display: block; }
QuestionInput:focus { border: heavy $g-accent; }

PromptArea {
    height: auto;
    min-height: 3;
    max-height: 9;
    background: $g-bg;
    color: $g-fg;
    border: round $g-border;
    border-title-color: $g-muted;
    border-subtitle-color: $g-muted;
}
PromptArea:focus { border: heavy $g-accent; border-title-color: $g-accent; }
PromptArea > .text-area--cursor-line { background: transparent; }
PromptArea.-hidden { display: none; }
"""
