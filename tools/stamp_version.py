"""Write the release tag into the package version constant.

The app reports `uac_desktop.__version__` in the sidebar and compares it with
the newest GitHub release to decide whether an update exists. Those two numbers
come from different places — a hand-edited constant and a git tag — so they
drifted: v1.5.2 was published from a tree that still said 1.0.6, which made
every install believe it was out of date, and reinstalling produced the same
build again. An update prompt that reinstalling cannot clear.

Running this from the release job removes the hand-edit, so the binary cannot
disagree with the tag it was built from.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

INIT = pathlib.Path(__file__).resolve().parents[1] / "uac_desktop" / "__init__.py"

# The updater parses versions with strict SemVer, so a tag it cannot read would
# break update checks for everyone who installs that release.
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
VERSION_LINE = re.compile(r'^__version__\s*=\s*["\'][^"\']*["\']', re.MULTILINE)


def normalise(tag: str) -> str:
    """Turn a git tag into the bare version the app should report."""
    value = str(tag or "").strip()
    if value[:1] in ("v", "V"):
        value = value[1:]
    return value.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", help="release tag, with or without a leading v")
    parser.add_argument("--check", action="store_true",
                        help="validate only; do not write")
    args = parser.parse_args(argv)

    version = normalise(args.tag)
    if not SEMVER.fullmatch(version):
        print(
            f"::error::Release tag {args.tag!r} is not valid SemVer. Use vMAJOR."
            f"MINOR.PATCH (for example v1.5.2), otherwise the in-app update "
            f"check cannot read it.",
            file=sys.stderr,
        )
        return 2

    source = INIT.read_text(encoding="utf-8")
    if not VERSION_LINE.search(source):
        print(f"::error::No __version__ assignment found in {INIT}", file=sys.stderr)
        return 3
    if args.check:
        print(f"Tag {args.tag} is a valid version ({version}).")
        return 0

    INIT.write_text(
        VERSION_LINE.sub(f'__version__ = "{version}"', source, count=1),
        encoding="utf-8",
    )
    print(f"Stamped uac_desktop.__version__ = {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
