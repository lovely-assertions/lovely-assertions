"""The direction imports run in, which is what keeps the packages separable.

The package is a set of small packages now, and the property that makes that
worth anything is that they can be read one at a time: options know nothing of
the walk, the walk nothing of the report. That holds today. Nothing was checking
it, which is how it would stop holding -- one import added for convenience, in a
diff about something else, and the layering is gone without a line of prose
changing.

Three kinds of import have to be told apart, and a check that does not tell them
apart is worse than none. A module-level import runs when the module loads and is
what a cycle would break. An import under ``if TYPE_CHECKING`` never runs at all,
so two packages naming each other's types are not in a cycle in any sense that
matters. An import inside a function runs on the call, by which time both modules
are loaded, which is precisely why it is the way out of a cycle the design needs.

Folded into one graph the three produce cycles that are not there. This file
keeps them apart, and pins the two deliberate back-edges by name.
"""

import ast
from collections import defaultdict
from pathlib import Path
from typing import Final

import lovely_assertions
from _package import sources

SRC: Final = Path(lovely_assertions.__file__).parent

#: The two imports that point back up the chain, each inside the function that
#: needs it and each commented at its call site with the cycle it breaks. Keyed
#: by the file, valued by the package it reaches. Deferring them is not a dodge:
#: the alternative is a module-level cycle, and the comment beside each one says
#: so. :func:`test_every_back_edge_is_still_load_bearing` is what stops this
#: table growing a third entry nobody argued for.
DEFERRED_BACK_EDGES: Final = {
    "_core/_found.py": "_subjects",
    "_names/_expressions.py": "_core",
}

#: Pinned, so an entry cannot join the table unremarked.
BACK_EDGE_COUNT: Final = 2


def _package_of(path: Path) -> str:
    """The top-level package a file belongs to, or the module's own name."""
    parts = path.relative_to(SRC).parts
    return parts[0] if len(parts) > 1 else path.stem


def _import_kinds(path: Path) -> dict[str, set[str]]:
    """Every package this file imports, split by when the import runs."""
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    here = _package_of(path)

    type_only: set[int] = set()
    inside_a_function: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and ast.unparse(node.test).strip() == "TYPE_CHECKING":
            type_only.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            inside_a_function.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))

    found: dict[str, set[str]] = {"module": set(), "typing": set(), "deferred": set()}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module is None or not node.module.startswith("lovely_assertions"):
            continue
        parts = node.module.split(".")
        if len(parts) < 2 or parts[1] == here:
            continue
        kind = (
            "typing"
            if node.lineno in type_only
            else "deferred"
            if node.lineno in inside_a_function
            else "module"
        )
        found[kind].add(parts[1])
    return found


def _graph(kind: str) -> dict[str, set[str]]:
    edges: dict[str, set[str]] = defaultdict(set)
    for path in sources(SRC):
        edges[_package_of(path)] |= _import_kinds(path)[kind]
    return dict(edges)


def _cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    found: list[list[str]] = []
    seen: set[frozenset[str]] = set()

    def walk(node: str, path: list[str], open_: frozenset[str]) -> None:
        if node in open_:
            cycle = path[path.index(node) :]
            if frozenset(cycle) not in seen:
                seen.add(frozenset(cycle))
                found.append(cycle)
            return
        for onward in sorted(graph.get(node, ())):
            walk(onward, [*path, onward], open_ | {node})

    for start in sorted(graph):
        walk(start, [start], frozenset())
    return found


def test_the_runtime_import_graph_has_no_cycle() -> None:
    """What one package imports at load time, another must not import back.

    Worth being exact about what this adds, because it is less than it looks. A
    module-level cycle in this package does not go unnoticed: it raises
    ``ImportError: partially initialized module`` somewhere, and the suite stops
    at collection. Tried against a deliberate one, this test never got the chance
    to run -- the import that loads it had already failed.

    What it adds is the diagnosis. A partially-initialised-module traceback names
    the file that happened to be second in the import order, not the pair that
    disagree, and reads the same whether the cause is a cycle or a typo. This
    names both packages and says what to do. That is a smaller claim than
    catching something nothing else catches, and it is the true one.
    """
    cycles = _cycles(_graph("module"))

    assert not cycles, (
        "these packages import each other at module level:\n"
        + "\n".join("  " + " -> ".join(cycle) for cycle in cycles)
        + "\nDefer one of the imports into the function that needs it, and say "
        "at the call site which cycle it breaks."
    )


def test_the_type_checking_import_graph_has_no_cycle() -> None:
    """Annotations may name each other freely, and here they do not need to.

    Nothing would break if they did -- a ``TYPE_CHECKING`` block never runs. It
    is checked because a cycle among them is a sign of two packages that have not
    decided which one owns a concept, and that is worth seeing while it is still
    only a type.
    """
    cycles = _cycles(_graph("typing"))

    assert not cycles, "these packages name each other's types in a cycle:\n" + "\n".join(
        "  " + " -> ".join(cycle) for cycle in cycles
    )


def test_only_the_two_named_imports_point_back_up() -> None:
    """A deferred import is the way out of a cycle, so it is worth counting.

    Deferring makes any import legal, which is exactly why an unremarked one is a
    problem: it is the shape a layering violation takes once the loud version has
    been silenced.
    """
    assert len(DEFERRED_BACK_EDGES) == BACK_EDGE_COUNT

    found = {
        path.relative_to(SRC).as_posix(): sorted(reaches)
        for path in sources(SRC)
        if (reaches := _import_kinds(path)["deferred"])
    }
    expected = {file: [package] for file, package in DEFERRED_BACK_EDGES.items()}

    assert found == expected, (
        f"deferred imports between packages are {found}, not {expected}. A new one "
        f"is either a cycle worth breaking -- say so at the call site and add it "
        f"here -- or an import that belongs at module level."
    )


def test_every_back_edge_is_still_load_bearing() -> None:
    """An exemption whose import moved is a slot the next one drops into.

    Pinning the count alone would not catch that: a stale entry leaves room for
    an unargued import to take its place without the total ever changing.
    """
    stale = [
        f"  {file} -> {package}"
        for file, package in sorted(DEFERRED_BACK_EDGES.items())
        if package not in _import_kinds(SRC / file)["deferred"]
    ]

    assert not stale, "these back-edges no longer exist:\n" + "\n".join(stale) + "\nDrop the entry."
