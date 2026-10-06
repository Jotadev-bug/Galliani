"""Spec 016 R1 and "Mismatched Tag Refused": the Release workflow's tag check."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from scripts import release_tag
from scripts.release_tag import check_tag, main


def test_matching_tag_is_a_stable_release():
    result = check_tag("v0.1.0", "0.1.0")
    assert result.ok and not result.prerelease


def test_suffix_marks_a_pre_release():
    result = check_tag("v0.2.0-beta.1", "0.2.0")
    assert result.ok and result.prerelease


def test_mismatched_tag_names_tag_and_version():
    result = check_tag("v0.2.0", "0.1.0")
    assert not result.ok
    assert "v0.2.0" in result.error and "0.1.0" in result.error


def test_pre_release_of_another_version_is_refused():
    assert not check_tag("v0.2.0-rc.1", "0.1.0").ok


@pytest.mark.parametrize("tag", ["0.1.0", "v0.1", "v0.1.0-", "v0.1.0_beta", "v0.1.0; rm -rf /", "refs/tags/v0.1.0"])
def test_malformed_tags_are_refused(tag):
    result = check_tag(tag, "0.1.0")
    assert not result.ok and "0.1.0" in result.error


# --------------------------------------------------------------------------- main(), against a real git repo


def git(repo, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                   cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.1.0"\n', encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "pyproject.toml")
    git(tmp_path, "commit", "-q", "-m", "0.1.0")
    git(tmp_path, "tag", "v0.1.0")
    monkeypatch.setattr(release_tag, "ROOT", tmp_path)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    return tmp_path


def test_main_accepts_matching_tag_and_writes_output(repo, tmp_path_factory, monkeypatch):
    output = tmp_path_factory.mktemp("gh") / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    assert main(["v0.1.0"]) == 0
    assert output.read_text(encoding="utf-8") == "prerelease=false\n"


def test_main_reads_version_at_the_tag_not_the_branch(repo):
    # A manual run starts from main, which may already be bumped past the tag being published.
    (repo / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.2.0"\n', encoding="utf-8")
    git(repo, "commit", "-q", "-am", "0.2.0")
    assert main(["v0.1.0"]) == 0


def test_main_refuses_missing_tag(repo, capsys):
    assert main(["v0.2.0"]) == 1
    err = capsys.readouterr().err
    assert "v0.2.0" in err and "does not exist" in err and "0.1.0" in err


def test_main_refuses_tag_on_mismatched_version(repo, capsys):
    git(repo, "tag", "v0.2.0")
    assert main(["v0.2.0"]) == 1
    assert "does not match pyproject.toml version 0.1.0" in capsys.readouterr().err


def test_main_refuses_malformed_tag_without_calling_git(repo, monkeypatch, capsys):
    monkeypatch.setattr(release_tag, "version_at_tag", lambda tag: pytest.fail("git was called"))
    assert main(["main"]) == 1
    assert "'main'" in capsys.readouterr().err
