"""Spec 016 R18-R21: MSIX manifest, identity handling, Store tile assets and one-folder staging."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import pytest
from PIL import Image

from scripts import build_msix
from scripts.build_msix import (LOCAL_TEST_IDENTITY, Identity, MsixError, load_identity, main, msix_version,
                                render_manifest, stage_package)
from scripts.make_icon import MSIX_ASSETS, MSIX_SCALES, MSIX_TILE_COLOR, write_msix_assets

NS = {"m": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
      "uap": "http://schemas.microsoft.com/appx/manifest/uap/windows10",
      "rescap": "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"}
IDENTITY = Identity("Jotade.Galliani", "CN=00000000-0000-0000-0000-000000000000", "Jotade", "Galliani")


def template() -> str:
    return build_msix.TEMPLATE_FILE.read_text(encoding="utf-8")


def manifest(identity: Identity = IDENTITY, version: str = "0.1.0.0") -> ET.Element:
    return ET.fromstring(render_manifest(template(), identity, version))


def tile_size(name: str, scale: int) -> tuple[int, int]:
    width, height = MSIX_ASSETS[name]
    return round(width * scale / 100), round(height * scale / 100)


# --------------------------------------------------------------------------- manifest (R18, R19)


def test_manifest_is_a_full_trust_desktop_app_with_the_partner_center_identity():
    root = manifest()
    identity = root.find("m:Identity", NS)
    assert identity.attrib == {"Name": "Jotade.Galliani", "Publisher": "CN=00000000-0000-0000-0000-000000000000",
                               "Version": "0.1.0.0", "ProcessorArchitecture": "x64"}
    assert root.find("m:Properties/m:PublisherDisplayName", NS).text == "Jotade"
    app = root.find("m:Applications/m:Application", NS)
    assert app.attrib["EntryPoint"] == "Windows.FullTrustApplication"
    assert app.attrib["Executable"] == "Galliani.exe"
    assert root.find("m:Capabilities/rescap:Capability", NS).attrib["Name"] == "runFullTrust"


def test_manifest_references_the_four_tile_images():
    root = manifest()
    visual = root.find("m:Applications/m:Application/uap:VisualElements", NS)
    refs = {visual.attrib["Square44x44Logo"], visual.attrib["Square150x150Logo"],
            visual.find("uap:DefaultTile", NS).attrib["Wide310x150Logo"], root.find("m:Properties/m:Logo", NS).text}
    assert refs == {f"Assets\\{name}.png" for name in MSIX_ASSETS}
    assert visual.attrib["BackgroundColor"] == "#121318"


def test_values_are_escaped_and_no_placeholder_is_left():
    identity = Identity("Jotade.Galliani", 'CN=A & "B" <c>', "Jo & Co", "Galliani")
    text = render_manifest(template(), identity, "0.1.0.0")
    assert "{{" not in text
    assert ET.fromstring(text).find("m:Identity", NS).attrib["Publisher"] == 'CN=A & "B" <c>'


def test_unknown_placeholder_is_refused():
    with pytest.raises(MsixError, match="Surprise"):
        render_manifest("<Package>{{Surprise}}</Package>", IDENTITY, "0.1.0.0")


@pytest.mark.parametrize("version,expected",
                         [("0.1.0", "0.1.0.0"), ("12.3.4", "12.3.4.0"), ("0.2.0-beta.1", "0.2.0.0")])
def test_msix_version_has_four_parts_and_the_store_reserved_zero(version, expected):
    assert msix_version(version) == expected


def test_msix_version_refuses_a_non_numeric_version():
    with pytest.raises(MsixError):
        msix_version("latest")


# --------------------------------------------------------------------------- identity config (R19)


def write_identity(tmp_path, **overrides):
    data = {"identity_name": "Jotade.Galliani", "publisher": "CN=0000", "publisher_display_name": "Jotade",
            "display_name": "Galliani", **overrides}
    path = tmp_path / "identity.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_the_committed_identity_is_never_invented():
    # Until Partner Center hands out the identity, the Store build must refuse rather than guess.
    data = json.loads(build_msix.IDENTITY_FILE.read_text(encoding="utf-8"))
    if data["identity_name"] is None or data["publisher"] is None:
        with pytest.raises(MsixError, match="Partner Center"):
            load_identity()
    else:
        assert load_identity().publisher.startswith("CN=")


def test_a_complete_identity_loads(tmp_path):
    assert load_identity(write_identity(tmp_path)) == Identity("Jotade.Galliani", "CN=0000", "Jotade", "Galliani")


@pytest.mark.parametrize("overrides,message", [
    ({"identity_name": None}, "identity_name"),
    ({"publisher": None}, "publisher"),
    ({"publisher": "Jotade"}, "CN="),
    ({"identity_name": "a b"}, "Identity Name"),
])
def test_an_incomplete_identity_is_refused(tmp_path, overrides, message):
    with pytest.raises(MsixError, match=message):
        load_identity(write_identity(tmp_path, **overrides))


def test_local_test_identity_is_clearly_not_a_store_identity():
    assert LOCAL_TEST_IDENTITY.publisher == "CN=Galliani Local Test"
    assert "LocalTest" in LOCAL_TEST_IDENTITY.identity_name


def test_main_refuses_a_store_build_without_an_identity(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(build_msix, "IDENTITY_FILE", write_identity(tmp_path, identity_name=None, publisher=None))
    monkeypatch.setattr(build_msix, "_build_onedir", lambda: pytest.fail("built before checking the identity"))
    assert main([]) == 1
    assert "Partner Center" in capsys.readouterr().err


def test_if_configured_skips_quietly_without_an_identity(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(build_msix, "IDENTITY_FILE", write_identity(tmp_path, identity_name=None, publisher=None))
    monkeypatch.setattr(build_msix, "_build_onedir", lambda: pytest.fail("built without an identity"))
    assert main(["--if-configured"]) == 0
    assert "Skipping" in capsys.readouterr().out


def test_if_configured_still_builds_with_an_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(build_msix, "IDENTITY_FILE", write_identity(tmp_path))
    built = []
    monkeypatch.setattr(build_msix, "_build_onedir", lambda: built.append(True) or 1)
    assert main(["--if-configured"]) == 1 and built == [True]


# --------------------------------------------------------------------------- Store tile assets (R21)


def test_every_tile_exists_at_its_declared_size_and_scale(tmp_path):
    write_msix_assets(Image.new("RGBA", (256, 256), (200, 200, 200, 255)), tmp_path)
    for name in MSIX_ASSETS:
        for scale in MSIX_SCALES:
            with Image.open(tmp_path / f"{name}.scale-{scale}.png") as image:
                assert image.size == tile_size(name, scale), (name, scale)


def test_the_unscaled_names_the_manifest_declares_exist(tmp_path):
    write_msix_assets(Image.new("RGBA", (256, 256), (200, 200, 200, 255)), tmp_path)
    for name in MSIX_ASSETS:
        with Image.open(tmp_path / f"{name}.png") as image:
            assert image.size == tile_size(name, 200), name


def test_wide_tile_centers_the_logo_on_the_tile_color(tmp_path):
    write_msix_assets(Image.new("RGBA", (256, 256), (200, 200, 200, 255)), tmp_path)
    with Image.open(tmp_path / "Wide310x150Logo.scale-100.png") as wide:
        assert wide.getpixel((2, 2)) == MSIX_TILE_COLOR
        assert wide.getpixel((155, 75))[:3] == (200, 200, 200)


def test_the_committed_assets_include_every_file_the_manifest_declares():
    declared = {ref for ref in ET.fromstring(template()).iter() for ref in ref.attrib.values()
                if ref.startswith("Assets\\")}
    declared |= {el.text for el in ET.fromstring(template()).iter() if el.text and el.text.startswith("Assets\\")}
    assert len(declared) == 4
    for ref in declared:
        assert (build_msix.ASSETS_DIR / ref.removeprefix("Assets\\")).is_file(), ref


def test_the_committed_assets_match_what_the_generator_declares():
    for name in MSIX_ASSETS:
        for scale in MSIX_SCALES:
            with Image.open(build_msix.ASSETS_DIR / f"{name}.scale-{scale}.png") as image:
                assert image.size == tile_size(name, scale), (name, scale)


# --------------------------------------------------------------------------- staging (R20)


def make_app(tmp_path):
    app = tmp_path / "app"
    (app / "_internal").mkdir(parents=True)
    (app / "Galliani.exe").write_bytes(b"exe")
    (app / "_internal" / "lib.dll").write_bytes(b"dll")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "StoreLogo.scale-100.png").write_bytes(b"png")
    return app, assets


def test_staging_lays_out_the_one_folder_app_assets_and_manifest(tmp_path):
    app, assets = make_app(tmp_path)
    staging = stage_package(app, assets, "<Package/>", tmp_path / "stage")
    assert (staging / "Galliani.exe").read_bytes() == b"exe"
    assert (staging / "_internal" / "lib.dll").exists()
    assert (staging / "Assets" / "StoreLogo.scale-100.png").exists()
    assert (staging / "AppxManifest.xml").read_text(encoding="utf-8") == "<Package/>"


def test_staging_starts_from_a_clean_folder(tmp_path):
    app, assets = make_app(tmp_path)
    stale = tmp_path / "stage"
    stale.mkdir()
    (stale / "old.txt").write_text("old", encoding="utf-8")
    assert not (stage_package(app, assets, "<Package/>", stale) / "old.txt").exists()


def test_staging_refuses_a_missing_exe_or_missing_tiles(tmp_path):
    app, assets = make_app(tmp_path)
    (app / "Galliani.exe").unlink()
    with pytest.raises(MsixError, match="Galliani.exe"):
        stage_package(app, assets, "<Package/>", tmp_path / "stage")
    (app / "Galliani.exe").write_bytes(b"exe")
    (assets / "StoreLogo.scale-100.png").unlink()
    with pytest.raises(MsixError, match="make_icon"):
        stage_package(app, assets, "<Package/>", tmp_path / "stage")
