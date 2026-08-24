"""Project maintenance script, invoked via poe (`uv run poe project:upgrade`)."""

import os
import re
import sys
import uuid
from pathlib import Path
from typing import Final, NamedTuple

import urllib3


class VersionBump(NamedTuple):
    before: str
    after: str

    @property
    def changed(self) -> bool:
        return self.before != self.after


REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
TASKS_PATH: Final[Path] = REPO_ROOT / "src" / "pyinfra_alertmanager" / "tasks.py"
README_PATH: Final[Path] = REPO_ROOT / "README.md"
PYTHON_VERSION_PATH: Final[Path] = REPO_ROOT / ".python-version"
LATEST_RELEASE_URL: Final[str] = (
    "https://api.github.com/repos/prometheus/alertmanager/releases/latest"
)
PYTHON_RELEASES_URL: Final[str] = "https://endoflife.date/api/python.json"
CURRENT_VERSION_PATTERN: Final[re.Pattern] = re.compile(
    r'^DEFAULT_VERSION(?::\s*Final\[str\])?\s*=\s*"(?P<version>[^"]+)"$', re.MULTILINE
)
VERSION_PATTERN: Final[re.Pattern] = re.compile(
    r'^(?P<prefix>DEFAULT_VERSION(?::\s*Final\[str\])?\s*=\s*)"[^"]+"$', re.MULTILINE
)
README_SAMPLE_PATTERN: Final[re.Pattern] = re.compile(
    r'(?<=\n    version=")[^"]+(?=",\n)'
)
README_TABLE_PATTERN: Final[re.Pattern] = re.compile(
    r"(\| `install`\s*\| `version`\s*\| `)[^`]+(`\s*\|)"
)


def fetch_latest_version() -> str:
    """Return the latest alertmanager release version (eg ``0.30.1``), without the ``v`` prefix."""
    response = urllib3.request("GET", LATEST_RELEASE_URL)
    return response.json()["tag_name"].removeprefix("v")


def fetch_latest_python_version(current: str) -> str:
    """Return the latest patch release for the same major.minor cycle as ``current``."""
    major_minor = ".".join(current.split(".")[:2])
    response = urllib3.request("GET", PYTHON_RELEASES_URL)
    for cycle in response.json():
        if cycle["cycle"] == major_minor:
            return str(cycle["latest"])

    print(
        f"Could not find Python {major_minor} release cycle at {PYTHON_RELEASES_URL}",
        file=sys.stderr,
    )
    sys.exit(1)


def upgrade_alertmanager() -> VersionBump:
    """Bump DEFAULT_VERSION in tasks.py and README.md to the latest upstream alertmanager release."""
    content = TASKS_PATH.read_text()
    current_match = CURRENT_VERSION_PATTERN.search(content)
    if current_match is None:
        print(f"Could not find DEFAULT_VERSION in {TASKS_PATH}", file=sys.stderr)
        sys.exit(1)
    current = current_match.group("version")

    latest = fetch_latest_version()

    updated, count = VERSION_PATTERN.subn(rf'\g<prefix>"{latest}"', content, count=1)
    if count == 0:
        print(f"Could not find DEFAULT_VERSION in {TASKS_PATH}", file=sys.stderr)
        sys.exit(1)

    TASKS_PATH.write_text(updated)
    print(f"DEFAULT_VERSION set to {latest} in {TASKS_PATH.relative_to(REPO_ROOT)}")

    readme = README_PATH.read_text()
    readme_updated, sample_count = README_SAMPLE_PATTERN.subn(latest, readme, count=1)
    readme_updated, table_count = README_TABLE_PATTERN.subn(
        rf"\g<1>{latest}\g<2>", readme_updated, count=1
    )
    if sample_count == 0 or table_count == 0:
        print(
            f"Could not find DEFAULT_VERSION reference(s) in {README_PATH}",
            file=sys.stderr,
        )
        sys.exit(1)

    README_PATH.write_text(readme_updated)
    print(f"DEFAULT_VERSION set to {latest} in {README_PATH.relative_to(REPO_ROOT)}")

    return VersionBump(current, latest)


def upgrade_python() -> VersionBump:
    """Bump .python-version to the latest patch release of the currently pinned cycle."""
    current = PYTHON_VERSION_PATH.read_text().strip()
    latest = fetch_latest_python_version(current)

    if latest == current:
        print(f"Already at the latest Python version ({current})")
        return VersionBump(current, latest)

    PYTHON_VERSION_PATH.write_text(f"{latest}\n")
    print(
        f"Python version set to {latest} in {PYTHON_VERSION_PATH.relative_to(REPO_ROOT)}"
    )
    return VersionBump(current, latest)


def upgrade() -> None:
    """Bump DEFAULT_VERSION in tasks.py/README.md and .python-version to their latest releases."""
    upgrade_alertmanager()
    upgrade_python()


def _write_github_output(values: dict[str, str]) -> None:
    """Append ``key=value`` pairs to the ``$GITHUB_OUTPUT`` file, using heredocs for multi-line values."""
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        print("GITHUB_OUTPUT is not set; skipping output write", file=sys.stderr)
        sys.exit(1)

    with Path(output_path).open("a") as fh:
        for key, value in values.items():
            if "\n" in value:
                delimiter = f"EOF_{uuid.uuid4().hex}"
                fh.write(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")
            else:
                fh.write(f"{key}={value}\n")


def upgrade_ci() -> None:
    """Bump alertmanager/Python versions and write the diff as GitHub Actions step outputs.

    Used by the Dependabot++ workflow (`.github/workflows/dependabot-plus-plus.yml`) in place of
    hand-rolled bash diffing, so the "what changed" and "how to describe it" logic lives in one
    tested place alongside the upgrade logic itself.
    """
    am = upgrade_alertmanager()
    py = upgrade_python()

    if not am.changed and not py.changed:
        _write_github_output({"updated": "false"})
        return

    summary_parts: list[str] = []
    branch_parts: list[str] = []
    changes_lines: list[str] = []
    release_notes_lines: list[str] = []

    if am.changed:
        summary_parts.append(f"alertmanager to {am.after}")
        branch_parts.append(f"am-{am.after}")
        changes_lines.append(
            f"- `src/pyinfra_alertmanager/tasks.py` / `README.md`: `DEFAULT_VERSION` `{am.before}` → `{am.after}`"
        )
        release_notes_lines.append(
            f"- [alertmanager v{am.after} release notes]"
            f"(https://github.com/prometheus/alertmanager/releases/tag/v{am.after})"
        )

    if py.changed:
        summary_parts.append(f"Python to {py.after}")
        branch_parts.append(f"py-{py.after}")
        changes_lines.append(f"- `.python-version`: `{py.before}` → `{py.after}`")
        release_notes_lines.append(
            f"- [Python {py.after} release notes]"
            f"(https://www.python.org/downloads/release/python-{py.after.replace('.', '')}/)"
        )

    summary = ", ".join(summary_parts)
    title = f"build(deps): bump {summary}"
    workflow_url = (
        f"https://github.com/{os.environ.get('GITHUB_REPOSITORY', '')}"
        "/actions/workflows/dependabot-plus-plus.yml"
    )
    body = "\n".join(
        [
            "## Summary",
            f"Automated project upgrade bumping {summary}.",
            "",
            "## Changes",
            *changes_lines,
            "",
            "## Release Notes",
            *release_notes_lines,
            "",
            "---",
            f"🤖 This PR was created automatically by the [Dependabot++ workflow]({workflow_url})",
        ]
    )
    commit_message = (
        f"{title}\n\nBumps {summary} as part of the automated project upgrade."
    )

    _write_github_output(
        {
            "updated": "true",
            "title": title,
            "branch": f"automation-upgrade-{'-'.join(branch_parts)}",
            "commit_message": commit_message,
            "body": body,
        }
    )
