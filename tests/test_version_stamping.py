from __future__ import annotations

import pathlib
import sys

import pytest

import uac_desktop
from uac_desktop.update_checker import InvalidVersion, SemVersion

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import stamp_version  # noqa: E402


def test_package_version_is_readable_by_the_updater():
    """A version the updater cannot parse breaks update checks for that build."""
    try:
        SemVersion.parse(uac_desktop.__version__)
    except InvalidVersion as exc:  # pragma: no cover - failure path
        pytest.fail(f"__version__ is not valid SemVer: {exc}")


@pytest.mark.parametrize("tag, expected", [
    ("v1.5.2", "1.5.2"),
    ("1.5.2", "1.5.2"),
    ("V2.0.0", "2.0.0"),
    ("  v1.5.2  ", "1.5.2"),
    ("v1.5.2-beta.1", "1.5.2-beta.1"),
])
def test_tags_normalise_to_the_bare_version(tag, expected):
    assert stamp_version.normalise(tag) == expected


@pytest.mark.parametrize("tag", [
    "v.1.20",   # the malformed tag already published on this repository
    "v1.5",
    "release-2",
    "v1.5.2.3",
    "",
])
def test_malformed_tags_are_rejected_before_a_build_ships(tag):
    """A bad tag has to fail the release job, not produce an unusable build."""
    assert stamp_version.main([tag, "--check"]) == 2


def test_stamping_rewrites_the_version_constant(tmp_path, monkeypatch):
    init = tmp_path / "__init__.py"
    init.write_text('"""Doc."""\n\n__version__ = "1.0.6"\n', encoding="utf-8")
    monkeypatch.setattr(stamp_version, "INIT", init)

    assert stamp_version.main(["v1.5.2"]) == 0
    assert '__version__ = "1.5.2"' in init.read_text(encoding="utf-8")
    # The docstring and everything else must survive.
    assert '"""Doc."""' in init.read_text(encoding="utf-8")


def test_stamping_fails_loudly_when_there_is_no_version_to_replace(
        tmp_path, monkeypatch):
    init = tmp_path / "__init__.py"
    init.write_text("# nothing here\n", encoding="utf-8")
    monkeypatch.setattr(stamp_version, "INIT", init)

    assert stamp_version.main(["v1.5.2"]) == 3


def test_stamped_version_is_what_the_updater_would_compare(tmp_path, monkeypatch):
    """End to end: tag in, comparable version out."""
    init = tmp_path / "__init__.py"
    init.write_text('__version__ = "0.0.1"\n', encoding="utf-8")
    monkeypatch.setattr(stamp_version, "INIT", init)
    stamp_version.main(["v1.5.2"])

    stamped = init.read_text(encoding="utf-8").split('"')[1]
    assert SemVersion.parse(stamped) == SemVersion.parse("1.5.2")
    # The whole point: a build tagged v1.5.2 must not look older than v1.5.2.
    assert not SemVersion.parse(stamped) < SemVersion.parse("1.5.2")
