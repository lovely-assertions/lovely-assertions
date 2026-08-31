"""The guidance names files that exist, in the tree it is guidance for.

``CLAUDE.md`` and ``.claude/rules/`` are read at the start of every session and
are the only account of why this package is arranged the way it is. Nothing was
checking them, and it showed: a decomposition that turned flat modules into
packages left them naming files that had not existed for twenty commits, in
sentences a reader has no reason to doubt.

Prose that is merely out of date is a nuisance. Prose that names a path is worse,
because a reader follows it, finds nothing, and has to work out whether the
document or their checkout is wrong. This makes that case loud.

What it cannot check is the half that matters more -- whether a claim is *true*.
``_subjects.py`` existing says nothing about whether the sentence around it is
still right. That half is read by a person, or by an agent told to run what the
sentence says; this only guarantees that the nouns are real.
"""

import re
from pathlib import Path
from typing import Final

TESTS: Final = Path(__file__).resolve().parent
ROOT: Final = TESTS.parent

#: Where a reader would try a path the documentation names, in the order they
#: would try it. A bare ``_subjects.py`` means the one in the package; a bare
#: ``testing.md`` in the rules directory means its neighbour.
ROOTS: Final = (
    "",
    "src/lovely_assertions/",
    "tests/",
    "scripts/",
    "docs/",
    "typing_tests/",
    "fuzz/",
    "benchmarks/",
    ".claude/",
    ".claude/rules/",
    ".claude/skills/",
    ".github/workflows/",
    ".github/",
)

#: Names that look like paths and are not. Two shapes so far: a stand-in in a
#: sentence about naming, and the wrong spelling quoted as the thing not to write
#: -- a rule against filenames in prose has to print one to say so. Keyed by
#: the document as well as the
#: token, because the same spelling could be a real path somewhere else.
#: :func:`test_every_exemption_is_still_in_its_document` keeps this honest.
NOT_A_PATH: Final = frozenset(
    {
        (".claude/rules/code-style.md", "_name.py"),
        (".claude/rules/comments-and-docs.md", "_core.py"),
        (".claude/agents/standards-reviewer.md", "_subject.py"),
    }
)

#: Pinned, so a name cannot join the exemptions unremarked.
EXEMPTION_COUNT: Final = 3

#: The documents this covers. ``docs/`` is here too: its Python blocks are run by
#: ``tests/test_documentation.py``, but nothing was reading the paths in its prose,
#: and two of them had gone stale the same way.
DOCUMENTS: Final = [
    ROOT / "CLAUDE.md",
    ROOT / "README.md",
    *sorted((ROOT / ".claude" / "rules").glob("*.md")),
    *sorted((ROOT / ".claude" / "agents").glob("*.md")),
    *sorted((ROOT / "docs").rglob("*.md")),
]

#: ``some/path.py`` or ``some/directory/`` inside single or double backticks.
_PATHLIKE: Final = re.compile(
    r"``?([A-Za-z_][\w./-]*\.(?:py|md|toml|json|yml|yaml)|[A-Za-z_][\w./-]*/)``?"
)


def _named_paths(text: str) -> set[str]:
    """Every path-shaped token the document quotes, without its backticks."""
    return {match.group(1) for match in _PATHLIKE.finditer(text)}


def _exists(candidate: str, beside: Path) -> bool:
    """Whether a reader could open this, from the roots they would try.

    ``beside`` first: a page linking to its neighbour writes the neighbour's name
    alone, and that is the reading a reader gives it before any other.
    """
    if (beside.parent / candidate).exists():
        return True
    return any((ROOT / (base + candidate)).exists() for base in ROOTS)


def test_every_path_the_documentation_names_exists() -> None:
    """A path a reader cannot follow is a claim they cannot check."""
    missing: list[str] = []
    for document in DOCUMENTS:
        where = document.relative_to(ROOT).as_posix()
        text = document.read_text(encoding="utf-8")
        for candidate in sorted(_named_paths(text)):
            if (where, candidate) in NOT_A_PATH or _exists(candidate, document):
                continue
            line = text[: text.index(candidate)].count("\n") + 1
            missing.append(f"  {where}:{line}: {candidate}")

    assert not missing, (
        "the documentation names these, and they do not exist:\n"
        + "\n".join(missing)
        + "\nA module that became a package is spelled without the `.py`. A name "
        "that is an example rather than a file belongs in `NOT_A_PATH`."
    )


def test_every_exemption_is_still_in_its_document() -> None:
    """An exemption whose sentence is gone is a free pass waiting for a real path.

    Pinning the count alone would not catch it: a stale entry leaves a slot that a
    genuinely missing file can be dropped into without the total ever moving.
    """
    assert len(NOT_A_PATH) == EXEMPTION_COUNT

    stale = [
        f"  {where}: {token}"
        for where, token in sorted(NOT_A_PATH)
        if token not in _named_paths((ROOT / where).read_text(encoding="utf-8"))
    ]

    assert not stale, (
        "these exemptions no longer name anything in their document:\n"
        + "\n".join(stale)
        + "\nDrop the entry rather than leaving a name nothing checks."
    )
