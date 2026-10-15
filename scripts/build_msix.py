"""Build Galliani.msix for the Microsoft Store (spec 016 R18-R22, Decision 0030).

    python -m scripts.build_msix                  # Store package: needs the Partner Center identity in packaging/msix/identity.json
    python -m scripts.build_msix --local-test     # throwaway identity, signed with a throwaway self-signed certificate

It builds the one-folder app (`build_desktop --onedir`, which also runs the app's smoke test), lays the package
out in build/msix/, fills in AppxManifest.xml, and packs it with `makeappx` from the Windows SDK.

The Store signs the package itself, so a Store build is left unsigned. `--local-test` signs with a certificate that is
generated for the run, removed from the certificate store afterwards, and only its public `.cer` is written (next to the
package, under dist/, which is git-ignored). Nothing here trusts that certificate for you: installing the test package
needs you to trust it yourself (see docs/release-checklist.md).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
MSIX_DIR = ROOT / "packaging" / "msix"
IDENTITY_FILE = MSIX_DIR / "identity.json"
TEMPLATE_FILE = MSIX_DIR / "AppxManifest.template.xml"
ASSETS_DIR = MSIX_DIR / "Assets"
ONEDIR_APP = ROOT / "dist" / "onedir" / "Galliani"
STAGING = ROOT / "build" / "msix"
DEFAULT_OUT = ROOT / "dist" / "Galliani.msix"

IDENTITY_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]{2,49}$")
PUBLISHER_PATTERN = re.compile(r"^CN=.+")
PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


class MsixError(Exception):
    """A problem the maintainer can fix; the message says how."""


@dataclass(frozen=True)
class Identity:
    identity_name: str
    publisher: str
    publisher_display_name: str
    display_name: str


# A made-up identity that only ever appears in a locally signed test package (R18), never in a Store build (R19).
LOCAL_TEST_IDENTITY = Identity(
    identity_name="Galliani.LocalTest",
    publisher="CN=Galliani Local Test",
    publisher_display_name="Galliani Local Test",
    display_name="Galliani (local test)",
)


def load_identity(path: Path | None = None) -> Identity:
    """The Partner Center identity (R19). Refuses null or malformed values rather than inventing any."""
    path = path or IDENTITY_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [key for key in ("identity_name", "publisher", "publisher_display_name", "display_name")
               if not data.get(key)]
    if missing:
        raise MsixError(
            f"{path.name} has no value for {', '.join(missing)}. Reserve 'Galliani' in Partner Center and copy "
            "Identity Name and Publisher from Product identity (docs/release-checklist.md), or use --local-test.")
    identity = Identity(data["identity_name"], data["publisher"], data["publisher_display_name"], data["display_name"])
    if not IDENTITY_NAME_PATTERN.match(identity.identity_name):
        raise MsixError(f"Identity Name {identity.identity_name!r} is not a valid package name")
    if not PUBLISHER_PATTERN.match(identity.publisher):
        raise MsixError(f"Publisher {identity.publisher!r} must start with CN= (copy it from Partner Center)")
    return identity


def identity_configured() -> bool:
    try:
        load_identity()
    except MsixError:
        return False
    return True


def msix_version(project_version: str) -> str:
    """`0.1.0` -> `0.1.0.0`. MSIX versions have four numeric parts; the Store reserves the last one."""
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:[-+.].*)?", project_version)
    if not match:
        raise MsixError(f"Cannot make an MSIX version from {project_version!r}")
    return ".".join([*match.groups(), "0"])


def project_version() -> str:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def render_manifest(template: str, identity: Identity, version: str) -> str:
    values = {
        "IdentityName": identity.identity_name,
        "Publisher": identity.publisher,
        "PublisherDisplayName": identity.publisher_display_name,
        "DisplayName": identity.display_name,
        "Version": version,
    }

    def fill(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise MsixError(f"The manifest template uses an unknown field {{{{{key}}}}}")
        return escape(values[key], {'"': "&quot;"})  # safe in an XML attribute or in text

    return PLACEHOLDER.sub(fill, template)


def stage_package(app_dir: Path, assets_dir: Path, manifest: str, staging: Path = STAGING) -> Path:
    """Package root: the one-folder app, `Assets\\` and `AppxManifest.xml`."""
    if not (app_dir / "Galliani.exe").is_file():
        raise MsixError(f"{app_dir / 'Galliani.exe'} is missing; run without --skip-build to build it")
    if not any(assets_dir.glob("*.png")):
        raise MsixError(f"No tile images in {assets_dir}; run python -m scripts.make_icon")
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(app_dir, staging)
    shutil.copytree(assets_dir, staging / "Assets")
    (staging / "AppxManifest.xml").write_text(manifest, encoding="utf-8", newline="\n")
    return staging


def find_sdk_tool(name: str) -> Path:
    """`makeappx.exe` or `signtool.exe`: on PATH, else the newest Windows SDK under Program Files (x86)."""
    if found := shutil.which(name):
        return Path(found)
    kits = Path(r"C:\Program Files (x86)\Windows Kits\10\bin")
    candidates = sorted(kits.glob(f"10.*/x64/{name}"), key=lambda p: [int(n) for n in p.parts[-3].split(".")])
    if not candidates:
        raise MsixError(f"{name} not found. Install the Windows 10/11 SDK (it ships with Visual Studio's "
                        "'Windows SDK' component) or run this on a GitHub windows-latest runner.")
    return candidates[-1]


def pack(staging: Path, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(find_sdk_tool("makeappx.exe")), "pack", "/d", str(staging), "/p", str(out), "/o"], check=True)


def sign_for_local_test(package: Path, publisher: str) -> Path:
    """Sign with a throwaway self-signed certificate, drop it from the store, and return its public `.cer`."""
    cer = package.with_suffix(".cer")
    script = (
        "$ErrorActionPreference = 'Stop';"
        f"$cert = New-SelfSignedCertificate -Type Custom -Subject '{publisher}' -KeyUsage DigitalSignature "
        "-FriendlyName 'Galliani local test' -CertStoreLocation 'Cert:\\CurrentUser\\My' "
        "-TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3', '2.5.29.19={text}');"
        f"Export-Certificate -Cert $cert -FilePath '{cer}' | Out-Null;"
        f"& '{find_sdk_tool('signtool.exe')}' sign /fd SHA256 /sha1 $cert.Thumbprint '{package}';"
        "$code = $LASTEXITCODE;"
        "Remove-Item -LiteralPath (Join-Path 'Cert:\\CurrentUser\\My' $cert.Thumbprint) -DeleteKey;"
        "exit $code"
    )
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], check=True)
    return cer


def _build_onedir() -> int:
    from scripts import build_desktop  # imported here: it needs PyInstaller, which tests and `--skip-build` do not

    return build_desktop.main(["--onedir"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.build_msix", description=__doc__.split("\n")[0])
    parser.add_argument("--local-test", action="store_true",
                        help="use a throwaway identity and sign with a throwaway self-signed certificate")
    parser.add_argument("--skip-build", action="store_true", help="reuse dist/onedir/Galliani from an earlier build")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--if-configured", action="store_true",
                        help="exit 0 without building when identity.json has no Partner Center identity yet (CI)")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        if args.if_configured and not args.local_test and not identity_configured():
            print("Skipping the MSIX: packaging/msix/identity.json has no Partner Center identity yet.")
            return 0
        identity = LOCAL_TEST_IDENTITY if args.local_test else load_identity()
        manifest = render_manifest(TEMPLATE_FILE.read_text(encoding="utf-8"), identity, msix_version(project_version()))
        if not args.skip_build and (code := _build_onedir()) != 0:
            print("The one-folder build failed its smoke test; no package was made.", file=sys.stderr)
            return code
        staging = stage_package(ONEDIR_APP, ASSETS_DIR, manifest)
        pack(staging, args.out)
        print(f"Built {args.out} ({args.out.stat().st_size / 1e6:.0f} MB)")
        if args.local_test:
            cer = sign_for_local_test(args.out, identity.publisher)
            print(f"Signed with a throwaway certificate. Public certificate: {cer}")
    except MsixError as error:
        print(error, file=sys.stderr)
        return 1
    except (subprocess.CalledProcessError, OSError) as error:
        print(f"MSIX packaging failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
