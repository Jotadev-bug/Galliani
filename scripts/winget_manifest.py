"""Generate the winget manifest for a release (spec 016 R14-R16, Decision 0029).

    python -m scripts.winget_manifest --tag v0.1.0 --exe dist/Galliani.exe --out packaging/winget/0.1.0
    python -m scripts.winget_manifest --tag v0.1.0 --sha256 <hash> --zip-dir dist

Writes the three files winget-pkgs expects (version, installer, default-locale) for a portable package
that points at the *versioned* release URL, never `latest`. `--zip-dir` also bundles them as
`galliani-winget-<version>.zip` so the maintainer can submit without editing by hand. It does not open the
winget-pkgs pull request (that needs a personal access token, deferred).
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

from scripts.release_tag import TAG_PATTERN

MANIFEST_VERSION = "1.6.0"
SCHEMA_BASE = "https://aka.ms/winget-manifest"
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
IDENTIFIER_PATTERN = re.compile(r"^[^\s.\\/:*?\"<>|]+(\.[^\s.\\/:*?\"<>|]+){1,7}$")

REPO_URL = "https://github.com/Jotadev-bug/Galliani"
SITE_URL = "https://galliani.vercel.app/"
DEFAULT_IDENTIFIER = "Jotade.Galliani"
ASSET_NAME = "Galliani.exe"
COMMAND_ALIAS = "galliani"


@dataclass(frozen=True)
class Release:
    tag: str
    sha256: str
    identifier: str = DEFAULT_IDENTIFIER
    release_date: str | None = None  # YYYY-MM-DD

    @property
    def version(self) -> str:
        return self.tag.removeprefix("v")

    @property
    def installer_url(self) -> str:
        return f"{REPO_URL}/releases/download/{self.tag}/{ASSET_NAME}"


def validate(release: Release) -> None:
    if not TAG_PATTERN.match(release.tag):
        raise ValueError(f"Tag {release.tag!r} is not a release tag like v1.2.3")
    if not SHA256_PATTERN.match(release.sha256):
        raise ValueError("SHA-256 must be 64 hexadecimal characters")
    if not IDENTIFIER_PATTERN.match(release.identifier):
        raise ValueError(f"Package identifier {release.identifier!r} must look like Publisher.Package")
    if release.release_date is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", release.release_date):
        raise ValueError("Release date must be YYYY-MM-DD")


def _header(release: Release, schema: str) -> list[str]:
    return [
        f"# yaml-language-server: $schema={SCHEMA_BASE}.{schema}.{MANIFEST_VERSION}.schema.json",
        "",
        f"PackageIdentifier: {release.identifier}",
        f"PackageVersion: {release.version}",
    ]


def version_manifest(release: Release) -> str:
    lines = _header(release, "version") + [
        "DefaultLocale: en-US",
        "ManifestType: version",
        f"ManifestVersion: {MANIFEST_VERSION}",
    ]
    return "\n".join(lines) + "\n"


def installer_manifest(release: Release) -> str:
    lines = _header(release, "installer") + [
        "InstallerLocale: en-US",
        "InstallerType: portable",
        "Platform:",
        "- Windows.Desktop",
        "Commands:",
        f"- {COMMAND_ALIAS}",
    ]
    if release.release_date:
        lines.append(f"ReleaseDate: {release.release_date}")
    lines += [
        "Installers:",
        "- Architecture: x64",
        f"  InstallerUrl: {release.installer_url}",
        f"  InstallerSha256: {release.sha256.upper()}",
        "ManifestType: installer",
        f"ManifestVersion: {MANIFEST_VERSION}",
    ]
    return "\n".join(lines) + "\n"


def locale_manifest(release: Release) -> str:
    lines = _header(release, "defaultLocale") + [
        "PackageLocale: en-US",
        "Publisher: Galliani contributors",
        f"PublisherUrl: {REPO_URL}",
        f"PublisherSupportUrl: {REPO_URL}/issues",
        f"PrivacyUrl: {SITE_URL}privacy.html",
        "PackageName: Galliani",
        f"PackageUrl: {SITE_URL}",
        "License: AGPL-3.0-or-later",
        f"LicenseUrl: {REPO_URL}/blob/main/LICENSE",
        "ShortDescription: Picks the right AI model for every message and shows what you saved.",
        "Description: >-",
        "  Galliani is a desktop app that routes each chat message to the cheapest model that can answer it,",
        "  and shows the model, the cost and the savings for every answer. Its Agent mode plans a task, uses",
        "  tools in a folder you choose, asks before writing files, and verifies the result before it finishes.",
        "  You bring your own OpenRouter key; it is kept in the OS credential store and nothing is collected.",
        "Moniker: galliani",
        "Tags:",
        "- ai",
        "- agent",
        "- llm",
        "- openrouter",
        "- router",
        f"ReleaseNotesUrl: {REPO_URL}/releases/tag/{release.tag}",
        "ManifestType: defaultLocale",
        f"ManifestVersion: {MANIFEST_VERSION}",
    ]
    return "\n".join(lines) + "\n"


def build_manifests(release: Release) -> dict[str, str]:
    """File name -> contents, named `<Id>.yaml`, `<Id>.installer.yaml`, `<Id>.locale.en-US.yaml`."""
    validate(release)
    return {
        f"{release.identifier}.yaml": version_manifest(release),
        f"{release.identifier}.installer.yaml": installer_manifest(release),
        f"{release.identifier}.locale.en-US.yaml": locale_manifest(release),
    }


def write_manifests(release: Release, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, text in build_manifests(release).items():
        path = out_dir / name
        path.write_text(text, encoding="utf-8", newline="\n")
        paths.append(path)
    return paths


def write_zip(paths: list[Path], zip_path: Path) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(paths):
            archive.write(path, arcname=path.name)
    return zip_path


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.winget_manifest", description=__doc__.split("\n")[0])
    parser.add_argument("--tag", required=True, help="release tag, for example v0.1.0")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--exe", type=Path, help="the built Galliani.exe; its SHA-256 is computed")
    source.add_argument("--sha256", help="the .exe's SHA-256, from Galliani.exe.sha256")
    parser.add_argument("--identifier", default=DEFAULT_IDENTIFIER)
    parser.add_argument("--release-date", help="YYYY-MM-DD")
    parser.add_argument("--out", type=Path, help="folder for the three manifest files")
    parser.add_argument("--zip-dir", type=Path, help="folder for galliani-winget-<version>.zip")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.out is None and args.zip_dir is None:
        parser.error("give --out, --zip-dir or both")

    try:
        sha256 = args.sha256 if args.sha256 else sha256_of(args.exe)
        release = Release(args.tag, sha256, args.identifier, args.release_date)
        validate(release)
    except (ValueError, OSError) as error:
        print(error, file=sys.stderr)
        return 1

    out_dir = args.out or (args.zip_dir / f"winget-{release.version}")
    paths = write_manifests(release, out_dir)
    for path in paths:
        print(path)
    if args.zip_dir is not None:
        print(write_zip(paths, args.zip_dir / f"galliani-winget-{release.version}.zip"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
