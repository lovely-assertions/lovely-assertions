"""The pipeline's own conventions, checked the way the source ones are.

`zizmor` covers the security properties of these files and CI runs it. What it
does not check is the half of the convention that exists for a *reader*: that a
pinned SHA carries the version it stands for, that `uvx` tools are pinned at all,
and above all that the single required status check actually depends on every job
it is supposed to collapse. A job missing from that `needs:` list is a gate that
cannot block anything, and nothing else in the repository would notice.

Deliberately regex, not a YAML parser: the package has zero runtime dependencies
and the development group is the tooling that enforces that, not a library
imported to read six files whose formatting this repository controls.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
WORKFLOWS: Final = REPO_ROOT / ".github" / "workflows"

#: `uses: owner/repo[/subdir]@<40 hex>  # v1.2.3` -- the comment is not optional.
#: A bare SHA is unreadable, and a reviewer who cannot see which version a pin
#: stands for cannot tell an ordinary bump from a substitution.
PINNED_USE: Final = re.compile(
    r"^\s*-?\s*uses:\s*(?P<action>[\w.-]+/[\w./-]+)@(?P<ref>\S+)(?P<comment>\s*#.*)?$"
)
FULL_SHA: Final = re.compile(r"^[0-9a-f]{40}$")
VERSION_COMMENT: Final = re.compile(r"#\s*v?\d[\w.-]*")

#: A `uvx` tool resolves the newest release at run time unless it is pinned, so
#: a gate can change its mind without a commit.
UVX_CALL: Final = re.compile(r"\buvx\s+(?:--from\s+)?(?P<tool>[a-zA-Z]\S*)")

#: Top-level job keys, at exactly two spaces of indentation under `jobs:`.
JOB_KEY: Final = re.compile(r"^  (?P<name>[a-z][a-z0-9-]*):$", re.MULTILINE)


def _workflows() -> list[Path]:
    return sorted(WORKFLOWS.glob("*.yml"))


def _identifier(path: Path) -> str:
    return path.name


WORKFLOW_FILES: Final = _workflows()


def test_there_are_workflows_to_check() -> None:
    """A guard that silently finds nothing to guard is not a guard."""
    assert WORKFLOW_FILES, f"no workflows found under {WORKFLOWS}"


@pytest.mark.parametrize("workflow", WORKFLOW_FILES, ids=_identifier)
def test_every_action_is_pinned_to_a_sha_and_says_which_version(workflow: Path) -> None:
    unpinned: list[str] = []
    uncommented: list[str] = []

    for number, line in enumerate(workflow.read_text(encoding="utf-8").splitlines(), start=1):
        match = PINNED_USE.match(line)
        if match is None:
            continue
        if not FULL_SHA.match(match["ref"]):
            unpinned.append(f"{workflow.name}:{number} {match['action']}@{match['ref']}")
            continue
        comment = match["comment"] or ""
        if not VERSION_COMMENT.search(comment):
            uncommented.append(f"{workflow.name}:{number} {match['action']}")

    assert not unpinned, (
        f"every action is pinned to a full commit SHA, never a tag or a branch: {unpinned}"
    )
    assert not uncommented, (
        "a pinned SHA carries the version it stands for in a trailing comment "
        f"(`# v1.2.3`), or nobody can review the bump: {uncommented}"
    )


#: Owners GitHub counts as its own. The repository's Actions policy is set to
#: *selected* actions with ``github_owned_allowed``, so anything under these is
#: permitted without being listed.
GITHUB_OWNED: Final = ("actions", "github")

#: Every third-party action this repository is allowed to run, and the whole
#: list. It is a copy: the policy itself lives in the repository's Actions
#: settings, where nothing in this tree can read it.
#:
#: That copy is the point. An action absent from the *setting* does not fail a
#: pull request -- it fails the workflow at startup, after the merge, with no
#: annotation saying why, because a workflow that cannot start produces no
#: output to annotate. A pull request adding one can be green in every check and
#: still be broken. Adding an entry here is the step that makes somebody go and
#: add it there too.
ALLOWED_THIRD_PARTY_ACTIONS: Final = (
    "SonarSource/sonarqube-scan-action",
    "astral-sh/setup-uv",
    "googleapis/release-please-action",
    "ossf/scorecard-action",
    "pypa/gh-action-pypi-publish",
)


@pytest.mark.parametrize("workflow", WORKFLOW_FILES, ids=_identifier)
def test_every_action_is_one_the_repository_is_allowed_to_run(workflow: Path) -> None:
    """An action outside the allow-list fails at startup, not at review.

    The failure mode this covers is the quiet one. GitHub refuses to start a
    workflow using an action the policy does not permit, and reports it as a
    startup failure with no annotation -- so the diagnosis is a guess unless
    somebody already knows the policy exists.
    """
    disallowed: list[str] = []

    for number, line in enumerate(workflow.read_text(encoding="utf-8").splitlines(), start=1):
        match = PINNED_USE.match(line)
        if match is None:
            continue
        action = match["action"]
        owner = action.split("/", 1)[0]
        if owner in GITHUB_OWNED:
            continue
        # A path into a repository (`owner/repo/subdir`) is still that repository.
        repository = "/".join(action.split("/")[:2])
        if repository not in ALLOWED_THIRD_PARTY_ACTIONS:
            disallowed.append(f"{workflow.name}:{number} {action}")

    assert not disallowed, (
        f"these actions are not on the repository's allow-list: {disallowed}. "
        f"Add them to `ALLOWED_THIRD_PARTY_ACTIONS` *and* to the repository's "
        f"Actions settings -- adding only one of the two leaves a workflow that "
        f"passes review and then refuses to start."
    )


def test_the_tag_release_please_creates_is_the_tag_the_release_workflow_waits_for() -> None:
    """Two files have to agree about one string, and nothing else makes them.

    release-please tags the release; ``release.yml`` triggers on a tag pattern.
    Neither reads the other, and the defaults do not match: ``include-
    component-in-tag`` defaults to *true*, which would tag
    ``lovely-assertions-v0.1.0`` -- a tag ``v*`` does not select.

    The failure that follows is the expensive kind, because every visible part of
    it succeeds. The release pull request merges, the version is written, the tag
    is pushed and the GitHub release appears; only the publish never runs, and
    nothing says so. It reads as "the release worked" until somebody looks for
    the version on PyPI.
    """
    config = json.loads((REPO_ROOT / "release-please-config.json").read_text(encoding="utf-8"))
    package = config["packages"]["."]

    assert package.get("include-component-in-tag") is False, (
        "release-please must not put the component in the tag: it defaults to true, "
        "which tags `lovely-assertions-vX.Y.Z`, and release.yml only wakes for `v*`."
    )
    assert package.get("include-v-in-tag") is not False, (
        "release-please must keep the `v` in the tag, which is what release.yml selects on."
    )

    release = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
    assert 'tags: ["v*"]' in release, (
        "release.yml no longer triggers on `v*`. Whatever it triggers on now has to "
        "match the tag release-please creates, and this test has to say so."
    )


def test_the_allow_list_has_no_stale_entries() -> None:
    """An entry nothing uses is a permission granted for no reason."""
    used = {
        "/".join(match["action"].split("/")[:2])
        for workflow in WORKFLOW_FILES
        for line in workflow.read_text(encoding="utf-8").splitlines()
        if (match := PINNED_USE.match(line)) is not None
    }
    unused = sorted(set(ALLOWED_THIRD_PARTY_ACTIONS) - used)
    assert not unused, (
        f"`ALLOWED_THIRD_PARTY_ACTIONS` permits actions no workflow uses: {unused}. "
        f"Remove them here and from the repository's Actions settings."
    )


@pytest.mark.parametrize("workflow", WORKFLOW_FILES, ids=_identifier)
def test_every_workflow_starts_read_only(workflow: Path) -> None:
    text = workflow.read_text(encoding="utf-8")
    jobs_at = text.index("\njobs:")
    header = text[:jobs_at]

    assert "\npermissions:\n  contents: read\n" in header, (
        f"{workflow.name} does not declare top-level `permissions: contents: read`. "
        "A job that needs more elevates for itself; nothing is granted workflow-wide."
    )


@pytest.mark.parametrize("workflow", WORKFLOW_FILES, ids=_identifier)
def test_no_checkout_leaves_the_token_on_disk(workflow: Path) -> None:
    lines = workflow.read_text(encoding="utf-8").splitlines()
    leaking: list[str] = []

    for index, line in enumerate(lines):
        if "actions/checkout@" not in line:
            continue
        # The step's `with:` block is what follows, up to the next step. Six
        # lines is more than any checkout in this repository uses.
        window = "\n".join(lines[index : index + 7])
        if "persist-credentials: false" not in window:
            leaking.append(f"{workflow.name}:{index + 1}")

    assert not leaking, (
        "every `actions/checkout` sets `persist-credentials: false`, so the token "
        f"is not left in `.git/config` for later steps to reach: {leaking}"
    )


@pytest.mark.parametrize("workflow", WORKFLOW_FILES, ids=_identifier)
def test_every_uvx_tool_is_version_pinned(workflow: Path) -> None:
    floating: list[str] = []

    for line in workflow.read_text(encoding="utf-8").splitlines():
        # A comment may well *quote* an unpinned invocation in order to explain
        # why it is wrong -- and this file's own convention notes do exactly that.
        if line.lstrip().startswith("#"):
            continue
        floating += [
            match["tool"] for match in UVX_CALL.finditer(line) if "==" not in match["tool"]
        ]

    assert not floating, (
        "`uvx <tool>` resolves the newest release at run time, so a gate could "
        f"change behaviour without a commit. Write `<tool>==<version>`: {floating}"
    )


@pytest.mark.parametrize("workflow", WORKFLOW_FILES, ids=_identifier)
def test_every_setup_uv_pins_the_uv_it_installs(workflow: Path) -> None:
    lines = workflow.read_text(encoding="utf-8").splitlines()
    unpinned: list[str] = []

    for index, line in enumerate(lines):
        if "astral-sh/setup-uv@" not in line:
            continue
        window = "\n".join(lines[index : index + 5])
        if "version:" not in window:
            unpinned.append(f"{workflow.name}:{index + 1}")

    assert not unpinned, (
        "with no `version:`, setup-uv resolves uv over the network on every job. "
        f"Pass the workflow's `UV_VERSION`: {unpinned}"
    )


def test_the_workflow_audit_can_actually_fail() -> None:
    """A gate that reports findings and then exits 0 is not a gate.

    ``zizmor --format sarif`` exits 0 even when it finds something, because SARIF
    is a report format whose consumer is the code-scanning UI rather than a shell.
    A job that runs only that form uploads its findings and then reports success,
    which reads as green and blocks nothing -- the same failure mode as a job
    missing from ``CI success``, and just as invisible.

    So the SARIF run produces the report and a second, default-form run supplies
    the verdict. This pins the pair.
    """
    text = (WORKFLOWS / "security.yml").read_text(encoding="utf-8")

    runs = [
        line
        for line in text.splitlines()
        if "uvx zizmor" in line and not line.lstrip().startswith("#")
    ]
    reporting = [line for line in runs if "--format sarif" in line]
    judging = [line for line in runs if "--format" not in line]

    assert reporting, "security.yml no longer produces a SARIF report from zizmor"
    assert judging, (
        "every zizmor run in security.yml passes `--format sarif`, which exits 0 on a "
        "finding -- so the job uploads what it found and then reports success. Keep a "
        "second run in the default form to supply the exit code."
    )


def test_the_required_check_depends_on_every_job() -> None:
    """The one thing branch protection looks at has to see everything.

    `CI success` exists so branch protection never enumerates a matrix. That only
    holds while its `needs:` names every other job in the file -- a job left out
    is a gate that runs, reports, and blocks nothing.
    """
    text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    jobs_at = text.index("\njobs:")
    declared = {match["name"] for match in JOB_KEY.finditer(text[jobs_at:])}

    aggregator = "ci-success"
    assert aggregator in declared, "ci.yml no longer defines the `ci-success` job"

    needs_line = re.search(
        rf"^  {aggregator}:.*?\n    needs: \[(?P<needs>[^\]]*)\]",
        text[jobs_at:],
        re.MULTILINE | re.DOTALL,
    )
    assert needs_line is not None, "`ci-success` declares no `needs:` list"
    needed = {name.strip() for name in needs_line["needs"].split(",") if name.strip()}

    missing = declared - needed - {aggregator}
    assert not missing, (
        f"these jobs run but cannot block anything -- add them to `{aggregator}`'s "
        f"`needs:`: {sorted(missing)}"
    )

    invented = needed - declared
    assert not invented, f"`{aggregator}` needs jobs that do not exist: {sorted(invented)}"
