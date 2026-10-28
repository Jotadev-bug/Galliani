"""Check that a wheel built from this checkout installs and runs without the source tree (spec 016 R27-R34).

    pip install -e ".[build]"
    python -m scripts.check_wheel [--keep]

Steps (R34): build the sdist and then the wheel from it; inspect the wheel; install `[tui]` into a fresh venv and run
the terminal checks; install `[desktop,tui]` into a second venv and run `galliani --smoke-test`; compare file
snapshots of each venv before and after (R32). It never runs a task or a one-shot objective, never calls a provider
and never prints environment variables. Exit codes: 0 all steps pass, 1 a step failed, 2 usage error.
"""

from __future__ import annotations

import argparse
import configparser
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# R29: every non-Python file the installed entry points read at runtime.
REQUIRED_FILES = (
    "app/defaults/models.yaml",
    "app/defaults/routing.yaml",
    "app/web/index.html",
    "app/web/logo.png",
)
# R31: the only top-level import packages.
ALLOWED_PACKAGES = frozenset({"app", "galliani"})
# R27: exactly these scripts, nothing else.
EXPECTED_SCRIPTS = {
    "galliani": "app.desktop:main",
    "galliacli": "galliani.tui.entry:main",
}
# R28: fixed message of the desktop app without pywebview.
R28_MESSAGE = ('galliani: the desktop app needs the "desktop" extra (pywebview is not installed). '
               'See the README "Install" section. For the terminal, run: galliacli')
FALLBACK_TEXT = "The interactive terminal needs a terminal"  # 017 R5, no-TTY case
COMMAND_TIMEOUT = 120


class StepFailed(Exception):
    """A check failed. The message names the step and the missing or unexpected item."""


def inspect_wheel(names: list[str], entry_points: str) -> list[str]:
    """R34 step 2: the problems in a wheel, given its file list and its entry_points.txt. Empty when fine."""
    problems: list[str] = []
    files = {n for n in names if not n.endswith("/")}
    for required in REQUIRED_FILES:
        if required not in files:
            problems.append(f"missing file: {required}")
    web = [f for f in files if f.startswith("app/web/")]
    if not web:
        problems.append("missing files: app/web/*")

    packages: set[str] = set()
    for name in files:
        top = name.split("/", 1)[0]
        if "/" not in name:
            problems.append(f"unexpected top-level file: {name}")
        elif top.endswith(".dist-info"):  # only the metadata; a `.data` folder could install files anywhere (Security)
            continue
        elif top not in ALLOWED_PACKAGES:
            packages.add(top)
    for extra in sorted(packages):
        problems.append(f"unexpected top-level package: {extra}")
    for wanted in sorted(ALLOWED_PACKAGES):
        if not any(f.startswith(wanted + "/") for f in files):
            problems.append(f"missing top-level package: {wanted}")

    parser = configparser.ConfigParser(delimiters=("=",), interpolation=None)
    parser.optionxform = str  # script names are case-sensitive
    try:
        parser.read_string(entry_points)
    except configparser.Error as exc:
        problems.append(f"entry_points.txt is not readable: {exc.__class__.__name__}")
        return problems
    for section in parser.sections():
        if section != "console_scripts":
            problems.append(f"unexpected entry point group: {section}")
    found = {k.strip(): v.strip() for k, v in parser.items("console_scripts")} if parser.has_section(
        "console_scripts") else {}
    for script, target in EXPECTED_SCRIPTS.items():
        if script not in found:
            problems.append(f"missing script: {script}")
        elif found[script] != target:
            problems.append(f"script {script} points to {found[script]}, expected {target}")
    for script in sorted(set(found) - set(EXPECTED_SCRIPTS)):
        problems.append(f"unexpected script: {script}")
    return problems


def sdist_problems(names: list[str]) -> list[str]:
    """R29: the sdist holds the same data files. Names carry a leading `<name>-<version>/` folder."""
    stripped = {n.split("/", 1)[1] for n in names if "/" in n}
    return [f"sdist is missing file: {r}" for r in REQUIRED_FILES if r not in stripped]


def snapshot(venv: Path) -> dict[str, tuple[int, int]]:
    """Every file under the venv with its size and mtime, ignoring __pycache__ and .pyc (R32)."""
    result: dict[str, tuple[int, int]] = {}
    for path in venv.rglob("*"):
        if "__pycache__" in path.parts or path.suffix == ".pyc" or not path.is_file():
            continue
        stat = path.stat()
        result[path.relative_to(venv).as_posix()] = (stat.st_size, stat.st_mtime_ns)
    return result


def diff_snapshots(before: dict[str, tuple[int, int]], after: dict[str, tuple[int, int]]) -> list[str]:
    problems = [f"created: {p}" for p in sorted(after.keys() - before.keys())]
    problems += [f"deleted: {p}" for p in sorted(before.keys() - after.keys())]
    problems += [f"changed: {p}" for p in sorted(p for p in before.keys() & after.keys() if before[p] != after[p])]
    return problems


def project_version(pyproject: Path | None = None) -> str:
    with open(pyproject or ROOT / "pyproject.toml", "rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def clean_env() -> dict[str, str]:
    env = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "PYTHONSTARTUP"):
        env.pop(name, None)
    return env


def run(cmd: list[str], *, cwd: Path, step: str, input_text: str | None = None,
        timeout: int = COMMAND_TIMEOUT) -> subprocess.CompletedProcess:
    """Run a command in `cwd` with a clean environment. Output is captured and shown only when a step fails."""
    try:
        # A pipe is never a TTY (NUL can look like one on Windows), so stdin always comes from `input`.
        return subprocess.run(cmd, cwd=cwd, env=clean_env(), input=input_text or "",
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise StepFailed(f"{step}: timed out after {timeout}s: {Path(cmd[0]).name} {' '.join(cmd[1:3])}") from None


def tail(text: str, lines: int = 12) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def venv_paths(venv: Path) -> tuple[Path, Path]:
    scripts = venv / ("Scripts" if os.name == "nt" else "bin")
    suffix = ".exe" if os.name == "nt" else ""
    return scripts / f"python{suffix}", scripts


def make_venv(venv: Path, wheel: Path, extras: str, cwd: Path, step: str) -> tuple[Path, Path]:
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, capture_output=True, cwd=cwd,
                   env=clean_env())
    python, scripts = venv_paths(venv)
    done = run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "--quiet",
                f"{wheel}[{extras}]"], cwd=cwd, step=step, timeout=600)
    if done.returncode != 0:
        raise StepFailed(f"{step}: pip install of {wheel.name}[{extras}] failed\n{tail(done.stderr)}")
    return python, scripts


PROBE = r"""
import importlib.metadata as md, pathlib, sys
import app, galliani
venv = pathlib.Path(sys.prefix).resolve()
for mod in (app, galliani):
    where = pathlib.Path(mod.__file__).resolve()
    if venv not in where.parents:
        sys.exit(f"{mod.__name__} is imported from outside the venv")
from app.config import CONFIG_DIR, load_routing_config
from app.models.registry import ModelRegistry
ModelRegistry.from_yaml(CONFIG_DIR / "models.yaml")
load_routing_config()
import galliani.tui.app
try:
    import benchmarks
except ImportError:
    pass
else:
    sys.exit("benchmarks is importable")
print(md.version("galliani"))
"""


def terminal_checks(python: Path, scripts: Path, cwd: Path, expected_version: str) -> None:
    """R34 step 3, run from an empty folder."""
    step = "step 3 (terminal environment)"
    probe = run([str(python), "-I", "-c", PROBE], cwd=cwd, step=step)
    if probe.returncode != 0:
        raise StepFailed(f"{step}: import probe failed\n{tail(probe.stderr)}")
    installed = probe.stdout.strip().splitlines()[-1] if probe.stdout.strip() else ""
    if installed != expected_version:
        raise StepFailed(f"{step}: installed version {installed!r} differs from pyproject.toml {expected_version!r}")

    want = f"galliacli {expected_version}"
    for label, cmd in (("galliacli --version", [str(scripts / "galliacli"), "--version"]),
                       ("python -m galliani --version", [str(python), "-I", "-m", "galliani", "--version"])):
        done = run(cmd, cwd=cwd, step=step)
        if done.returncode != 0 or done.stdout.strip() != want:
            raise StepFailed(f"{step}: {label} printed {done.stdout.strip()!r} (exit {done.returncode}), "
                             f"expected {want!r}")

    helped = run([str(scripts / "galliacli"), "--help"], cwd=cwd, step=step)  # R32: --help is a checked command
    if helped.returncode != 0 or "usage: galliacli" not in helped.stdout:
        raise StepFailed(f"{step}: galliacli --help exited {helped.returncode} without 'usage: galliacli'\n"
                         f"{tail(helped.stderr)}")

    fallback = run([str(scripts / "galliacli")], cwd=cwd, step=step, input_text="")
    if fallback.returncode != 2 or FALLBACK_TEXT not in fallback.stdout + fallback.stderr:
        raise StepFailed(f"{step}: galliacli without a TTY exited {fallback.returncode}, expected 2 with the "
                         f"017 R5 fallback text\n{tail(fallback.stderr)}")

    desktop = run([str(scripts / "galliani")], cwd=cwd, step=step, timeout=60)
    if desktop.returncode != 2 or desktop.stderr.strip() != R28_MESSAGE:
        raise StepFailed(f"{step}: galliani without the desktop extra exited {desktop.returncode} with "
                         f"{tail(desktop.stderr)!r}, expected exit 2 and the R28 message")


def desktop_checks(scripts: Path, cwd: Path) -> None:
    """R34 step 4: every smoke check prints PASS, including 'UI served' and 'logo bundled'."""
    step = "step 4 (desktop environment)"
    done = run([str(scripts / "galliani"), "--smoke-test"], cwd=cwd, step=step)
    lines = [ln.strip() for ln in done.stdout.splitlines()]
    passed = {ln[4:].strip() for ln in lines if ln.startswith("PASS")}
    failed = [ln for ln in lines if ln.startswith("FAIL")]
    if done.returncode != 0 or failed:
        raise StepFailed(f"{step}: galliani --smoke-test exited {done.returncode}; failed checks: {failed or 'none printed'}")
    for name in ("UI served", "logo bundled"):
        if name not in passed:
            raise StepFailed(f"{step}: smoke check {name!r} did not print PASS")


def build(work: Path) -> tuple[Path, Path]:
    """R34 step 1: `python -m build` builds the sdist and then the wheel from it."""
    step = "step 1 (build)"
    dist = work / "dist"
    done = run([sys.executable, "-m", "build", "--outdir", str(dist), str(ROOT)], cwd=work, step=step, timeout=900)
    if done.returncode != 0:
        raise StepFailed(f"{step}: python -m build failed (pip install \".[build]\" provides it)\n{tail(done.stderr)}")
    wheels, sdists = sorted(dist.glob("*.whl")), sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise StepFailed(f"{step}: expected one wheel and one sdist, found {len(wheels)} and {len(sdists)}")
    return wheels[0], sdists[0]


def inspect_artifacts(wheel: Path, sdist: Path) -> None:
    import tarfile

    step = "step 2 (wheel inspection)"
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        entry = [n for n in names if n.endswith(".dist-info/entry_points.txt")]
        entry_text = archive.read(entry[0]).decode("utf-8") if entry else ""
    problems = inspect_wheel(names, entry_text)
    with tarfile.open(sdist) as archive:
        problems += sdist_problems(archive.getnames())
    if problems:
        raise StepFailed(f"{step}: " + "; ".join(problems))


def checked_venv(work: Path, name: str, wheel: Path, extras: str, step: str, check) -> None:
    """Create a venv, snapshot it, run `check(python, scripts, empty_cwd)`, snapshot again (R32)."""
    cwd = work / f"empty-{name}"
    cwd.mkdir()
    venv = work / f"venv-{name}"
    python, scripts = make_venv(venv, wheel, extras, work, step)
    before = snapshot(venv)
    check(python, scripts, cwd)
    changes = diff_snapshots(before, snapshot(venv))
    if changes:
        raise StepFailed(f"step 5 (nothing written into the install, {name}): " + "; ".join(changes[:10]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.check_wheel", description=__doc__.split("\n\n")[0])
    parser.add_argument("--keep", action="store_true", help="keep the temporary folders for debugging")
    parser.add_argument("--dist-dir", type=Path,
                        help="after every step passes, copy the checked wheel and sdist here (used by the Release "
                             "workflow, spec 016 R38)")
    try:
        options = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    version = project_version()
    work = Path(tempfile.mkdtemp(prefix="galliani-check-wheel-")).resolve()
    try:
        wheel, sdist = build(work)
        print(f"built {wheel.name} and {sdist.name}")
        inspect_artifacts(wheel, sdist)
        print("step 2 ok: wheel contents and entry points")
        checked_venv(work, "tui", wheel, "tui", "step 3 (terminal environment)",
                     lambda python, scripts, cwd: terminal_checks(python, scripts, cwd, version))
        print("step 3 ok: terminal environment")
        checked_venv(work, "desktop", wheel, "desktop,tui", "step 4 (desktop environment)",
                     lambda python, scripts, cwd: desktop_checks(scripts, cwd))
        print("step 4 ok: desktop smoke test")
        print("step 5 ok: nothing written into either venv")
        if options.dist_dir:
            options.dist_dir.mkdir(parents=True, exist_ok=True)
            for artifact in (wheel, sdist):
                shutil.copy2(artifact, options.dist_dir / artifact.name)
            print(f"copied the checked artifacts to {options.dist_dir}")
        return 0
    except StepFailed as exc:
        print(f"check_wheel FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        if options.keep:
            print(f"kept {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)  # step 6, also after a failure


if __name__ == "__main__":
    sys.exit(main())
