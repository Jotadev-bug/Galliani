"""Spec 016 R14-R16 and "winget Install": the manifest generator."""

from __future__ import annotations

import hashlib
import zipfile

import pytest
import yaml

from scripts.winget_manifest import Release, build_manifests, main, write_manifests

SHA = "ab" * 32


def parsed(release: Release) -> dict[str, dict]:
    return {name: yaml.safe_load(text) for name, text in build_manifests(release).items()}


def test_three_files_named_after_the_identifier():
    assert set(build_manifests(Release("v0.1.0", SHA))) == {
        "Jotade.Galliani.yaml", "Jotade.Galliani.installer.yaml", "Jotade.Galliani.locale.en-US.yaml"}


def test_installer_is_portable_with_versioned_url_checksum_and_alias():
    installer = parsed(Release("v0.1.0", SHA))["Jotade.Galliani.installer.yaml"]
    assert installer["InstallerType"] == "portable"
    assert installer["Commands"] == ["galliani"]
    entry = installer["Installers"][0]
    assert entry["InstallerUrl"] == "https://github.com/Jotadev-bug/Galliani/releases/download/v0.1.0/Galliani.exe"
    assert "latest" not in entry["InstallerUrl"]
    assert entry["InstallerSha256"] == SHA.upper()
    assert entry["Architecture"] == "x64"


def test_locale_has_license_and_urls():
    locale = parsed(Release("v0.1.0", SHA))["Jotade.Galliani.locale.en-US.yaml"]
    assert locale["License"] == "AGPL-3.0-or-later"
    assert locale["PackageUrl"] == "https://galliani.vercel.app/"
    assert locale["PrivacyUrl"] == "https://galliani.vercel.app/privacy.html"
    assert locale["LicenseUrl"].startswith("https://github.com/Jotadev-bug/Galliani/")
    assert locale["PublisherUrl"] == "https://github.com/Jotadev-bug/Galliani"
    assert locale["ManifestType"] == "defaultLocale"
    assert "OpenRouter" in locale["Description"]


def test_every_file_carries_identifier_version_and_manifest_version():
    for name, data in parsed(Release("v0.2.1", SHA, identifier="Acme.Galliani")).items():
        assert name.startswith("Acme.Galliani")
        assert data["PackageIdentifier"] == "Acme.Galliani"
        assert data["PackageVersion"] == "0.2.1"
        assert data["ManifestVersion"] == "1.6.0"


def test_version_manifest_names_the_default_locale():
    assert parsed(Release("v0.1.0", SHA))["Jotade.Galliani.yaml"]["DefaultLocale"] == "en-US"


def test_release_date_is_optional():
    without = parsed(Release("v0.1.0", SHA))["Jotade.Galliani.installer.yaml"]
    with_date = parsed(Release("v0.1.0", SHA, release_date="2026-10-06"))["Jotade.Galliani.installer.yaml"]
    assert "ReleaseDate" not in without
    assert str(with_date["ReleaseDate"]) == "2026-10-06"


@pytest.mark.parametrize("kwargs", [
    {"tag": "0.1.0"}, {"tag": "v0.1"}, {"tag": "v0.1.0; rm -rf /"},
    {"sha256": "abc"}, {"sha256": "z" * 64},
    {"identifier": "Galliani"}, {"identifier": "Bad Name.Galliani"},
    {"release_date": "06/10/2026"},
])
def test_invalid_input_is_refused(kwargs):
    base = {"tag": "v0.1.0", "sha256": SHA}
    with pytest.raises(ValueError):
        build_manifests(Release(**{**base, **kwargs}))


def test_main_hashes_the_exe_and_writes_manifests_and_zip(tmp_path, capsys):
    exe = tmp_path / "Galliani.exe"
    exe.write_bytes(b"not really an exe")
    out = tmp_path / "out"
    assert main(["--tag", "v0.1.0", "--exe", str(exe), "--out", str(out), "--zip-dir", str(tmp_path / "dist")]) == 0
    installer = yaml.safe_load((out / "Jotade.Galliani.installer.yaml").read_text(encoding="utf-8"))
    assert installer["Installers"][0]["InstallerSha256"] == hashlib.sha256(b"not really an exe").hexdigest().upper()
    with zipfile.ZipFile(tmp_path / "dist" / "galliani-winget-0.1.0.zip") as archive:
        assert sorted(archive.namelist()) == sorted(p.name for p in out.iterdir())


def test_main_refuses_a_bad_tag(tmp_path, capsys):
    assert main(["--tag", "main", "--sha256", SHA, "--out", str(tmp_path)]) == 1
    assert "'main'" in capsys.readouterr().err
    assert not list(tmp_path.iterdir())


def test_main_refuses_a_missing_exe(tmp_path, capsys):
    assert main(["--tag", "v0.1.0", "--exe", str(tmp_path / "nope.exe"), "--out", str(tmp_path / "o")]) == 1
    assert not (tmp_path / "o").exists()


def test_write_manifests_uses_lf_line_endings(tmp_path):
    for path in write_manifests(Release("v0.1.0", SHA), tmp_path):
        assert b"\r" not in path.read_bytes()
