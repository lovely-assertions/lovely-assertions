"""Every ``>>>`` example in the shipped source is executed, not just displayed.

An example is the part of a docstring a reader trusts most and checks least: it
looks like evidence. One that has drifted from the code is worse than no example
at all, because it teaches a call that no longer works and nothing anywhere goes
red about it.

An example runs against the namespace its reader has: the module it sits in,
plus everything the package exports. So an example on a public function may use
any other public name without importing it, and one on a private helper may use
its neighbours -- which is what a maintainer reading that file has in front of
them, and nothing more.
"""

import doctest
import importlib
import io
from pathlib import Path
from typing import Final

import pytest

import lovely_assertions
from _package import module_name, sources

SRC: Final = Path(lovely_assertions.__file__).parent

#: Every module in the package, by import name.
MODULES: Final = sorted({module_name(path, SRC) for path in sources(SRC)})

#: What every example may use without importing it: the package's public API,
#: exactly as ``from lovely_assertions import ...`` would give it. A module's own
#: globals are layered on top, so a name defined there wins.
PUBLIC: Final = {name: getattr(lovely_assertions, name) for name in lovely_assertions.__all__}

#: ``ELLIPSIS`` so an example may write ``...`` for a memory address or a long
#: tail; ``IGNORE_EXCEPTION_DETAIL`` is deliberately *not* set, because the text
#: of a failure message is the thing this library is for.
OPTIONS: Final = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE


def _run(name: str) -> tuple[int, int, str]:
    """Run one module's examples, as ``(attempted, failed, report)``."""
    module = importlib.import_module(name)
    runner = doctest.DocTestRunner(optionflags=OPTIONS)
    report = io.StringIO()
    globs = {**PUBLIC, **vars(module)}
    for test in doctest.DocTestFinder().find(module, name, globs=globs):
        runner.run(test, out=report.write)
    return runner.tries, runner.failures, report.getvalue()


@pytest.mark.parametrize("module", MODULES, ids=lambda name: name.rpartition(".")[2])
def test_every_example_in_a_docstring_still_works(module: str) -> None:
    """A ``>>>`` example produces what it says it produces."""
    _, failed, report = _run(module)
    assert not failed, f"{module} shows an example that no longer holds:\n{report}"


def test_the_examples_are_actually_being_run() -> None:
    """A guard over zero examples would pass for the wrong reason.

    The count is a floor rather than an exact figure: examples are added freely,
    and a test that has to be edited every time one is would be edited without
    being read. What it catches is the collection breaking silently.
    """
    attempted = sum(_run(module)[0] for module in MODULES)
    assert attempted >= 20, f"only {attempted} examples ran; the finder is not finding them"
