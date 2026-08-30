"""The list of type-checker suppressions must stay frozen and documented.

pyright and mypy already refuse to let a suppression outlive the divergence it
covers (`reportUnnecessaryTypeIgnoreComment`, `warn_unused_ignores`). What they
cannot check is the other direction: that a suppression added to `src/` was ever
*justified in writing*. That is what this test is for.
"""

import re
from pathlib import Path
from typing import Final

from _package import sources

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
SRC_DIR: Final = REPO_ROOT / "src"
DIVERGENCES_DOC: Final = REPO_ROOT / "docs" / "concepts" / "typing-divergences.md"

_MYPY_IGNORE_RE: Final = re.compile(r"#\s*type:\s*ignore\[(?P<codes>[^\]]*)\]")
_PYRIGHT_IGNORE_RE: Final = re.compile(r"#\s*pyright:\s*ignore\[(?P<codes>[^\]]*)\]")
_BARE_IGNORE_RE: Final = re.compile(r"#\s*type:\s*ignore(?!\[)|#\s*pyright:\s*ignore(?!\[)")


class Suppression:
    """One coded suppression found in the shipped source."""

    __slots__ = ("code", "line", "path")

    def __init__(self, path: Path, line: int, code: str) -> None:
        self.path = path
        self.line = line
        self.code = code

    def __repr__(self) -> str:
        return f"{self.path.relative_to(REPO_ROOT)}:{self.line} [{self.code}]"


def _source_files() -> list[Path]:
    return sources(SRC_DIR)


def _suppressions() -> list[Suppression]:
    found: list[Suppression] = []
    for path in _source_files():
        for offset, text in enumerate(path.read_text(encoding="utf-8").splitlines()):
            for pattern in (_MYPY_IGNORE_RE, _PYRIGHT_IGNORE_RE):
                match = pattern.search(text)
                if match is None:
                    continue
                found.extend(
                    Suppression(path, offset + 1, code.strip())
                    for code in match.group("codes").split(",")
                )
    return found


def test_no_bare_suppressions_in_src() -> None:
    """A suppression without a rule code silences whatever happens to be there."""
    offenders: list[str] = []
    for path in _source_files():
        for offset, text in enumerate(path.read_text(encoding="utf-8").splitlines()):
            if _BARE_IGNORE_RE.search(text):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{offset + 1}")
    assert not offenders, (
        f"bare type-ignore comments in src: {offenders}. "
        f"Always suffix the rule code, e.g. `# type: ignore[overload-overlap]`."
    )


def test_every_suppression_code_is_documented() -> None:
    """Each code used in `src/` must have an entry in docs/concepts/typing-divergences.md."""
    documented = DIVERGENCES_DOC.read_text(encoding="utf-8")
    undocumented = sorted(
        {s.code for s in _suppressions() if f"`{s.code}`" not in documented},
    )
    assert not undocumented, (
        f"suppression codes used in src but absent from "
        f"docs/concepts/typing-divergences.md: {undocumented}. "
        f"The list is frozen and documented, or it is not a list."
    )


def test_divergences_doc_exists_and_is_substantive() -> None:
    """A stub document would make the test above vacuous."""
    assert DIVERGENCES_DOC.is_file()
    assert len(DIVERGENCES_DOC.read_text(encoding="utf-8")) > 500
