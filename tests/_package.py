"""One walk over the package's own source, shared by every guard that needs it.

Several guards in this suite state a rule about *every module in the package*.
Each of them needs the same two answers -- which files those are, and what each
one is called on an ``import`` line -- and a walk written per guard answers them
per guard.

Both answers are easy to get subtly wrong, and the two mistakes are not equally
survivable. Building an import name by pasting a bare filename onto
``lovely_assertions.`` raises ``ModuleNotFoundError`` the moment a module sits in
a subpackage, which is loud and therefore harmless. A non-recursive walk just
stops returning the file: the rule keeps its wording and quietly applies to fewer
files than it claims, and the build stays green. A guard that covers less than it
says is worse than a guard nobody wrote, because the green build is now evidence
for something that was never checked.

So the walk lives here, and the guards share it. The point is not the lines
saved; it is that a subpackage has one thing left to get wrong rather than one
per guard. ``tests/test_guard_enumeration.py`` is what holds this module, and
them, to that.
"""

from pathlib import Path

__all__ = ["module_name", "sources"]


def sources(root: Path) -> list[Path]:
    """Every ``.py`` file under ``root``, subpackages included, in a stable order.

    Sorted, so a caller parametrising over the result gets test ids that do not
    move between one run and the next.
    """
    return sorted(root.rglob("*.py"))


def module_name(path: Path, package: Path) -> str:
    """The dotted import name of one source file inside ``package``.

    ``__init__.py`` is the package it sits in rather than a module beneath it, so
    it resolves to the directory's own name -- which is what makes the root
    ``__init__.py`` come out as ``lovely_assertions`` and a subpackage's come out
    as ``lovely_assertions.<name>`` rather than as something ending in
    ``.__init__`` that is importable but is not how anyone spells it.
    """
    parts = path.relative_to(package.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
