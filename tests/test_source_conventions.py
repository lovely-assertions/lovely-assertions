"""What the shipped source is allowed to say, checked rather than hoped for.

Everything under ``src/`` goes out in the wheel, and the wheel is all a reader
gets: no repository, no design notes, no test suite, no conversation. A comment
that points at any of those is a dead end for the only person who will ever read
it, and a style rule decays unless something fails when it is broken.

The scan reads comments and docstrings, never code. It goes through ``tokenize``
rather than a line-oriented regex so that a pattern appearing inside a *failure
message* -- which is code, and is a string this library exists to get right --
never counts against the file that produces it.

Not checked here, deliberately: prose that narrates the code's own history. Every
regex for it ("used to", "no longer", "previously") also matches ordinary English
about values -- an element that is no longer present, a flag used to pick a
branch -- so the guard would cost more in contorted wording than it saves. That
one stays a review rule.
"""

import ast
import io
import re
import tokenize
from pathlib import Path
from typing import Final

import pytest

SRC: Final = Path(__file__).resolve().parent.parent / "src" / "lovely_assertions"

MODULES: Final = sorted(SRC.glob("*.py"))

#: Things a reader of the installed package cannot open: design documents and
#: numbered decisions live in the repository, and the tests and benchmarks are
#: not in the wheel at all. Naming one tells the reader that an explanation
#: exists and that they do not have it, which is worse than saying nothing.
UNREACHABLE: Final = re.compile(
    r"""
      \bSPEC\b
    | \bCATALOGUE\b
    | \bDIVERGENCES\b
    | \bAPI-AUDIT\b
    | docs/[A-Za-z-]+\.md
    | \b(?:REFERENCE|EXTENDING|PLAN)\.md
    | \bMO-\d+\b
    | (?<![A-Za-z])D(?:[1-9]|10)(?![0-9A-Za-z])
    | \bmilestones?\b
    | \btests?/[a-z_0-9]+\.py
    | \btyping_tests/
    | \bbenchmarks/
    | §\s*\d
    """,
    re.VERBOSE,
)


def _prose(path: Path) -> list[tuple[int, str]]:
    """Every comment and docstring line in ``path``, as ``(line number, text)``.

    A string literal counts as prose only when it is triple-quoted. Every other
    string in this package is a message, a pattern or an error, and those are
    code even though they read like sentences.
    """
    lines: list[tuple[int, str]] = []
    readline = io.StringIO(path.read_text(encoding="utf-8")).readline
    for token in tokenize.generate_tokens(readline):
        if token.type == tokenize.COMMENT:
            lines.append((token.start[0], token.string))
        elif token.type == tokenize.STRING and token.string.lstrip("rbfuRBFU").startswith(
            ('"""', "'''")
        ):
            lines += [
                (token.start[0] + offset, line)
                for offset, line in enumerate(token.string.splitlines())
            ]
    return lines


def _assertions(path: Path) -> "list[tuple[int, str, str]]":
    """Every documented public assertion in ``path``, as ``(line, name, first line)``.

    An assertion is a method that can reach the failure primitive. That is a
    property of the body rather than of the name, so a method renamed out of the
    ``is_``/``has_`` conventions is still held to the rule.
    """
    found: list[tuple[int, str, str]] = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for klass in (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)):
        for node in klass.body:
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue
            reports = any(
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr in {"_fail", "_fail_narrowing"}
                for call in ast.walk(node)
            )
            doc = ast.get_docstring(node, clean=False)
            if reports and doc:
                found.append(
                    (node.lineno, f"{klass.name}.{node.name}", doc.splitlines()[0].strip())
                )
    return found


@pytest.mark.parametrize("module", MODULES, ids=lambda path: path.name)
def test_the_shipped_source_cites_nothing_a_reader_cannot_open(module: Path) -> None:
    """No comment or docstring in the wheel points at something outside the wheel."""
    offences = [
        f"  {module.name}:{lineno}: {line.strip()}"
        for lineno, line in _prose(module)
        if UNREACHABLE.search(line)
    ]
    assert not offences, (
        f"{module.name} cites something a reader of the installed package cannot open:\n"
        + "\n".join(offences)
        + "\nWrite the idea itself in a sentence or two instead of pointing at it."
    )


@pytest.mark.parametrize("module", MODULES, ids=lambda path: path.name)
def test_every_suppression_says_why(module: Path) -> None:
    """A silenced lint rule says why, in plain language, where the reader will look.

    In parentheses after the rule code, or in a comment on the line above when
    the line already carries a second directive and has no room. Without either,
    the next reader has a rule number and no way to tell whether the exemption
    still applies, so it is never removed and the rule stays off for good.
    """
    explained = {lineno for lineno, line in _prose(module) if line.lstrip().startswith("#")}
    offences = [
        f"  {module.name}:{lineno}: {line.strip()}"
        for lineno, line in _prose(module)
        if "# noqa:" in line
        and "(" not in line.partition("# noqa:")[2]
        and lineno - 1 not in explained
    ]
    assert not offences, (
        f"{module.name} silences a lint rule without saying why:\n"
        + "\n".join(offences)
        + "\nPut the reason in parentheses after the rule code, or in a comment above the line."
    )


@pytest.mark.parametrize("module", MODULES, ids=lambda path: path.name)
def test_every_assertion_opens_with_the_claim_it_makes(module: Path) -> None:
    """An assertion's first docstring line is one sentence beginning "Assert".

    That line is the whole description an editor shows on hover and the whole row
    the generated catalogue carries, so it has to stand alone and it has to read
    as a claim about the subject rather than as a note about the method.
    """
    offences = [
        f"  {module.name}:{lineno} {name}: {first!r}"
        for lineno, name, first in _assertions(module)
        if not first.startswith("Assert ") or not first.endswith(".")
    ]
    assert not offences, (
        f"{module.name} documents an assertion as something other than a claim:\n"
        + "\n".join(offences)
        + '\nOpen with "Assert ..." and end the first line with a full stop.'
    )
