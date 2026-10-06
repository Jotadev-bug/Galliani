"""Check a release tag against pyproject.toml before anything is built (spec 016 R1, Decision 0026).

    python -m scripts.release_tag v0.1.0

The version is read from pyproject.toml *at that tag* (`git show <tag>:pyproject.toml`), so a manual
Release run started from `main` checks the tag it will publish, not the branch it was started from.
Exits non-zero, naming the tag and the version, when the tag is malformed, missing or mismatched.
On GitHub Actions it writes `prerelease=true|false` to `$GITHUB_OUTPUT`.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAG_PATTERN = re.compile(r"^v\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?$")


@dataclass(frozen=True)
class TagCheck:
    tag: str
    version: str
    prerelease: bool
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def check_tag(tag: str, version: str) -> TagCheck:
    """`v0.1.0` and `v0.1.0-beta.1` match version `0.1.0`; a suffix marks a pre-release."""
    prerelease = "-" in tag
    if not TAG_PATTERN.match(tag):
        return TagCheck(tag, version, prerelease,
                        f"Tag {tag!r} is not a release tag like v1.2.3 or v1.2.3-beta.1 "
                        f"(pyproject.toml version {version})")
    base = tag.removeprefix("v").split("-", 1)[0]
    if base != version:
        return TagCheck(tag, version, prerelease, f"Tag {tag} does not match pyproject.toml version {version}")
    return TagCheck(tag, version, prerelease)


def version_from_toml(text: str) -> str:
    return tomllib.loads(text)["project"]["version"]


def version_at_tag(tag: str) -> str | None:
    """pyproject.toml's version at `tag`, or None when the tag does not exist locally."""
    result = subprocess.run(["git", "show", f"refs/tags/{tag}:pyproject.toml"],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    return version_from_toml(result.stdout) if result.returncode == 0 else None


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -m scripts.release_tag <tag>", file=sys.stderr)
        return 2
    tag = args[0]
    branch_version = version_from_toml((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    # Validate the shape first, so a malformed input never reaches git.
    if not TAG_PATTERN.match(tag):
        print(check_tag(tag, branch_version).error, file=sys.stderr)
        return 1
    version = version_at_tag(tag)
    if version is None:
        print(f"Tag {tag} does not exist (pyproject.toml version {branch_version})", file=sys.stderr)
        return 1
    result = check_tag(tag, version)
    if not result.ok:
        print(result.error, file=sys.stderr)
        return 1
    print(f"Tag {tag} matches pyproject.toml version {version}"
          + (" (pre-release)" if result.prerelease else ""))
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as f:
            f.write(f"prerelease={'true' if result.prerelease else 'false'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
