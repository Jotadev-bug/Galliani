"""Spec 018 R1 (palette frozen, no colour literal outside the three dicts) and R7 (WGL4 glyphs only).

Both are source scans (AST string constants), so they run without importing Textual. The scanned modules are the
UI layer: `galliani/tui/app.py`, `widgets.py` and `styles.py`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
UI_MODULES = ("app.py", "widgets.py", "styles.py")
PALETTE_DICTS = ("DARK_PALETTE", "LIGHT_PALETTE", "_ANSI_VARIABLES")

# The 017 values (Decision 0025). 018 R1: these never change.
DARK_017 = {
    "bg": "#121318", "surface": "#1a1c23", "border": "#444856", "fg": "#e4e6ea", "muted": "#9ba1ae",
    "accent": "#c3c7d0", "good": "#5ec49a", "warn": "#e0b04f", "bad": "#ec6f78", "agent": "#4cc2bd",
}
LIGHT_017 = {
    "bg": "#f7f8fa", "surface": "#eceef2", "border": "#8c92a0", "fg": "#1a1c22", "muted": "#555b69",
    "accent": "#343944", "good": "#1d7a55", "warn": "#8a5a00", "bad": "#b3262f", "agent": "#0f6f6c",
}
ANSI_017 = {
    "g-bg": "ansi_default", "g-surface": "ansi_default", "g-border": "ansi_bright_black",
    "g-fg": "ansi_default", "g-muted": "ansi_bright_black", "g-accent": "ansi_bright_white",
    "g-good": "ansi_green", "g-warn": "ansi_yellow", "g-bad": "ansi_red", "g-agent": "ansi_cyan",
}

HEX = re.compile(r"(?<![\w-])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![\w-])")
FUNCTION_COLOUR = re.compile(r"\b(?:rgba?|hsla?|hsv)\s*\(", re.IGNORECASE)
DECLARATION = re.compile(r"(?<![\w$-])([a-z][a-z-]*)\s*:\s*([^;{}\n]+)")
# Named colours a CSS value or a Rich style string could carry. `transparent` is not a resting colour, and the
# ansi_* names belong in _ANSI_VARIABLES only.
NAMED = {"black", "white", "red", "green", "blue", "yellow", "magenta", "cyan", "gray", "grey", "orange", "purple",
         "pink", "brown", "navy", "teal", "olive", "maroon", "silver", "lime", "aqua", "fuchsia", "gold", "violet",
         "indigo", "crimson", "coral", "salmon", "turquoise", "khaki", "beige", "ivory", "lavender", "tan"}
STYLE_KEYWORDS = {"style", "border_style", "title_style", "subtitle_style", "highlight_style", "spinner_style"}


def _tree(name: str) -> ast.Module:
    path = ROOT / "galliani" / "tui" / name
    return ast.parse(path.read_text(encoding="utf-8"), name)


def _palette_nodes(tree: ast.Module) -> set[int]:
    """ids of every node inside the three palette dict assignments."""
    inside: set[int] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) in PALETTE_DICTS for t in node.targets):
            inside.update(id(n) for n in ast.walk(node))
    return inside


def _strings(tree: ast.Module, skip: set[int]) -> list[tuple[int, str, bool]]:
    """(line, text, is_style_argument) for every string constant outside `skip`."""
    styled = {id(kw.value) for node in ast.walk(tree) if isinstance(node, ast.Call)
              for kw in node.keywords if kw.arg in STYLE_KEYWORDS}
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            found.append((node.lineno, node.value, id(node) in styled))
    return found


def colour_literals(tree: ast.Module) -> list[str]:
    problems = []
    for line, text, styled in _strings(tree, _palette_nodes(tree)):
        if HEX.search(text) or FUNCTION_COLOUR.search(text):
            problems.append(f"{line}: {text[:60]!r}")
            continue
        values = [value for _, value in DECLARATION.findall(text)] + ([text] if styled else [])
        for value in values:
            words = set(re.findall(r"(?<![\w$-])[a-z_]+(?![\w-])", value.lower()))
            if words & NAMED or any(w.startswith("ansi_") for w in words):
                problems.append(f"{line}: {value.strip()[:60]!r}")
    return problems


# ---------------------------------------------------------------------- R1 palette


def test_palette_dicts_equal_their_017_values():
    tree = _tree("styles.py")
    values = {t.id: ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
              for t in node.targets if getattr(t, "id", None) in PALETTE_DICTS}
    assert values == {"DARK_PALETTE": DARK_017, "LIGHT_PALETTE": LIGHT_017, "_ANSI_VARIABLES": ANSI_017}


@pytest.mark.parametrize("module", UI_MODULES)
def test_no_colour_literal_outside_the_palette_dicts(module):
    assert colour_literals(_tree(module)) == []


@pytest.mark.parametrize("source", [
    'CSS = "Screen { background: #121318; }"',
    'CSS = "Box { color: rgb(1, 2, 3); }"',
    'CSS = "Box { border: round red; }"',
    'CSS = "Box { color: ansi_red; }"',
    'Text("x", style="bold #ff0000")',
    'Text("x", style="bold cyan")',
    'console.print("x", border_style="grey")',
])
def test_the_scan_catches_colour_literals(source):
    assert colour_literals(ast.parse(source)) != []


@pytest.mark.parametrize("source", [
    'CSS = "Screen { background: $g-bg; border: round $g-border; } #prompt-box { color: $g-fg; }"',
    'CSS = "Box:focus { border: heavy $g-accent; tint: $g-bg 50%; background: transparent; }"',
    'Text("x", style="bold $g-good")',
    'HELP = "Press y to approve, n to deny. Colors: red means failed."',
    'DARK_PALETTE = {"bg": "#121318"}',
])
def test_the_scan_allows_theme_variables_and_prose(source):
    assert colour_literals(ast.parse(source)) == []


# ---------------------------------------------------------------------- R7 WGL4 glyphs

# WGL4 (Windows Glyph List 4), which Consolas and Cascadia Mono render, as code point ranges.
WGL4_RANGES = (
    (0x20, 0x7E), (0xA0, 0x17F), (0x192, 0x192), (0x1FA, 0x1FF), (0x2C6, 0x2C7), (0x2C9, 0x2C9), (0x2D8, 0x2DD),
    (0x384, 0x38A), (0x38C, 0x38C), (0x38E, 0x3A1), (0x3A3, 0x3CE), (0x401, 0x40C), (0x40E, 0x44F),
    (0x451, 0x45C), (0x45E, 0x45F), (0x490, 0x491), (0x1E80, 0x1E85), (0x1EF2, 0x1EF3), (0x2013, 0x2015),
    (0x2017, 0x201E), (0x2020, 0x2022), (0x2026, 0x2026), (0x2030, 0x2030), (0x2032, 0x2033), (0x2039, 0x203A),
    (0x203C, 0x203C), (0x203E, 0x203E), (0x2044, 0x2044), (0x207F, 0x207F), (0x20A3, 0x20A4), (0x20A7, 0x20A7),
    (0x20AC, 0x20AC), (0x2105, 0x2105), (0x2113, 0x2113), (0x2116, 0x2116), (0x2122, 0x2122), (0x2126, 0x2126),
    (0x212E, 0x212E), (0x215B, 0x215E), (0x2190, 0x2195), (0x21A8, 0x21A8), (0x2202, 0x2202), (0x2206, 0x2206),
    (0x220F, 0x220F), (0x2211, 0x2212), (0x2215, 0x2215), (0x2219, 0x221A), (0x221E, 0x221F), (0x2229, 0x2229),
    (0x222B, 0x222B), (0x2248, 0x2248), (0x2260, 0x2261), (0x2264, 0x2265), (0x2302, 0x2302), (0x2310, 0x2310),
    (0x2320, 0x2321), (0x2500, 0x2500), (0x2502, 0x2502), (0x250C, 0x250C), (0x2510, 0x2510), (0x2514, 0x2514),
    (0x2518, 0x2518), (0x251C, 0x251C), (0x2524, 0x2524), (0x252C, 0x252C), (0x2534, 0x2534), (0x253C, 0x253C),
    (0x2550, 0x256C), (0x2580, 0x2580), (0x2584, 0x2584), (0x2588, 0x2588), (0x258C, 0x258C), (0x2590, 0x2593),
    (0x25A0, 0x25A1), (0x25AA, 0x25AC), (0x25B2, 0x25B2), (0x25BA, 0x25BA), (0x25BC, 0x25BC), (0x25C4, 0x25C4),
    (0x25CA, 0x25CB), (0x25CF, 0x25CF), (0x25D8, 0x25D9), (0x25E6, 0x25E6), (0x263A, 0x263C), (0x2640, 0x2640),
    (0x2642, 0x2642), (0x2660, 0x2660), (0x2663, 0x2663), (0x2665, 0x2666), (0x266A, 0x266B), (0xF001, 0xF002),
    (0xFB01, 0xFB02),
)


def in_wgl4(char: str) -> bool:
    return any(low <= ord(char) <= high for low, high in WGL4_RANGES)


def ui_glyphs() -> dict[str, list[str]]:
    """Every non-ASCII character in a string constant of the UI modules, by module and line."""
    found: dict[str, list[str]] = {}
    for module in UI_MODULES:
        for line, text, _ in _strings(_tree(module), set()):
            for char in sorted({c for c in text if ord(c) > 127}):
                found.setdefault(char, []).append(f"{module}:{line}")
    return found


def test_every_ui_glyph_is_in_wgl4():
    outside = {f"U+{ord(c):04X}": where for c, where in ui_glyphs().items() if not in_wgl4(c)}
    assert outside == {}


def test_the_spec_glyphs_are_in_wgl4():
    for glyph in ("·", "•", "●", "└", ">", "√", "×", "─", "│", "┌", "…", "→"):  # R10 spinner, R5 leads
        assert in_wgl4(glyph), glyph


@pytest.mark.parametrize("glyph", ["╭", "⠋", "✓", "✗", "⏺", "❯", "🙂"])
def test_glyphs_outside_wgl4_are_caught(glyph):
    assert not in_wgl4(glyph)
