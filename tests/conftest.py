"""One guarantee for the whole suite: no test leaves a soft scope behind.

A leaked collector is the only failure this library has that makes tests *stop*
failing. It is not confined to the test that caused it either: the ``ContextVar``
belongs to the thread, so every later test in that worker files its failures into
a sink nobody reads and passes without asserting anything. The suite would look
greener than before.

So the invariant is checked where it can name the culprit -- after each test,
before the next one starts, so the report lands on the test that leaked rather
than on the first one that was silenced by it.

The ``ContextVar`` object is captured **once, at import**, out of the module
namespace by name: a direct attribute access across modules is what pyright
reports, and looking the attribute up per test would read whatever a test has
monkeypatched over it (``tests/test_happy_path.py`` replaces that very name with
a booby trap) instead of the variable the library actually routes through.
"""

import inspect
import sys
from typing import TYPE_CHECKING, Any, Final

import pytest
from benchmarks import watching_the_interpreter

import _happy_calls
from _happy_calls import library_modules
from lovely_assertions import _core
from lovely_assertions._core import Expect

if TYPE_CHECKING:
    from collections.abc import Iterator
    from contextvars import ContextVar
    from types import FrameType

_ACTIVE_COLLECTOR: "ContextVar[object | None]" = vars(_core)["_ACTIVE_COLLECTOR"]


@pytest.fixture(autouse=True)
def no_soft_scope_outlives_its_test() -> "Iterator[None]":
    """Fail the test that left assertion routing pointing at a dead scope."""
    yield
    leaked = _ACTIVE_COLLECTOR.get()
    assert leaked is None, (
        f"this test left a soft-assertion scope active ({leaked!r}). Every failing "
        f"assertion after it -- in this test and in every later test on this thread -- "
        f"is collected instead of raised, so they pass without asserting anything. "
        f"A scope must be left in the context that opened it, in the order it was opened."
    )


#: The happy-call table's fixture, resolved here so both of its readers see it.
#: ``tests/_happy_calls.py`` defines it beside the table it feeds; pytest looks a
#: fixture up **by name** in the test module and its conftests, so importing it
#: into each of the two test modules would be an import no linter can see used,
#: while naming it once here is what a conftest is for.
world = _happy_calls.world


class Detonator:
    """Anything a passing assertion must not reach.

    No leading underscore, by the rule ``_happy_calls.py`` spells out: a name
    imported across a module boundary is that module's public surface, and
    pyright says so with ``reportPrivateUsage``.
    """

    def __getattr__(self, name: str) -> Any:
        message = f"the happy path reached {name!r}, which belongs to the failure path"
        raise AssertionError(message)

    def __call__(self, *_args: object, **_kwargs: object) -> Any:
        raise AssertionError("the happy path called into the failure path")


#: Every escape hatch a passing assertion must never take, by the name each module
#: binds it under. Trapped *wherever* it is bound rather than only in ``_core``:
#: ``from ... import resolve_subject_name`` binds the function into the importing
#: module, so patching one copy leaves every other caller going straight past it.
#:
#: ``_ACTIVE`` is the formatting options' ``ContextVar``. Reading one allocates
#: nothing, so the sweep in ``test_performance_invariants.py`` cannot see it and
#: this is the only instrument that can.
TRAPPED: Final = ("resolve_subject_name", "_ACTIVE_COLLECTOR", "_report", "_ACTIVE")


@pytest.fixture
def no_failure_machinery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Booby-trap every escape hatch a passing assertion must never take.

    One fixture, in the one file every test module already reads, because private
    copies of a trap diverge: each module learns about a new escape hatch on its
    own schedule, and the module that sweeps the *whole* public surface has no
    more reason to hear about one than the module that checks a single family --
    so the broadest guard in the suite ends up with the narrowest trap.

    Anything added to :data:`TRAPPED` is added for every test module at once,
    which is the only arrangement in which that cannot happen.
    """
    for module in library_modules():
        for name in TRAPPED:
            if hasattr(module, name):
                monkeypatch.setattr(module, name, Detonator())
    monkeypatch.setattr(Expect, "_fail", Detonator())
    monkeypatch.setattr(Expect, "_fail_narrowing", Detonator())


# ---------------------------------------------------------------------------
# Every assertion must be shown failing, not only passing
# ---------------------------------------------------------------------------
#: Assertions that cannot fail, and why. Each is a continuation or a naming step
#: rather than a claim about the subject.
#:
#: Anything not here must be *seen* failing at least once over a full run, which
#: is what :func:`pytest_sessionfinish` checks. ``tests/_happy_calls.py`` proves
#: the same completeness for the passing direction with a table of one passing
#: call per assertion; this direction needs no table, because a suite this size
#: already exercises nearly all of it and the only useful question is which part
#: it misses.
CANNOT_FAIL: Final[dict[tuple[str, str], str]] = {
    ("Expect", "described_as"): "names the subject and returns it; there is nothing to test",
    ("CollectionExpect", "extracting"): "transforms the subject into another subject",
    ("SequenceExpect", "extracting"): "transforms the subject into another subject",
    ("DateTimeExpect", "is_within"): (
        "hands back a `WithinDelta`; the assertion is in its `.before` / `.after`, "
        "and an unfinished chain warns through `__del__` rather than failing"
    ),
}

#: Assertions seen to fail during this session, filled in by the monitor below.
OBSERVED_FAILING: Final[set[tuple[str, str]]] = set()

#: A monitoring slot of our own. Ids 0, 1, 2 and 5 are reserved for a debugger,
#: coverage, a profiler and the optimiser; 3 and 4 are free for general use, and
#: taking a free one is what keeps `coverage run` and a debugger working while
#: this is installed.
_TOOL_ID: Final = 3
_TOOL_NAME: Final = "lovely-assertions-failing-calls"
_PACKAGE: Final = Expect.__module__.rsplit(".", 1)[0]


def _record_failing_assertion(_code: object, _offset: int) -> None:
    """Note every assertion on the stack when a failure is reported.

    Every assertion on it, not just the one that called ``_fail``: an alias that
    delegates -- ``contains_no_duplicates`` calls ``has_unique_items`` -- is
    invisible to anything that reads the immediate caller only, and reading it
    that way reports every such alias as an uncovered gap.

    Through ``sys.monitoring`` rather than by patching ``_fail``, and that is the
    whole reason this works. A wrapper adds a frame, and the frame it adds is the
    first non-library one, so the machinery that recovers a subject's name from
    the caller's source line would read *the wrapper's* source instead and every
    message test would fail. The monitor observes the same call and changes no
    stack. Events are set on two code objects, so the cost is paid on the failure
    path only.
    """
    here = inspect.currentframe()
    if here is None or here.f_back is None:  # pragma: no cover - CPython always has one
        return
    frame: FrameType | None = here.f_back.f_back  # the caller of `_fail`
    while frame is not None and str(frame.f_globals.get("__name__", "")).startswith(_PACKAGE):
        holder = frame.f_locals.get("self")
        name = frame.f_code.co_name
        if holder is not None and not name.startswith("_"):
            for klass in type(holder).__mro__:
                if name in vars(klass):
                    OBSERVED_FAILING.add((klass.__name__, name))
                    break
        frame = frame.f_back


def pytest_configure(config: pytest.Config) -> None:
    """Watch `_fail` and `_fail_narrowing` for the length of the session.

    The two are read out of the class dictionary rather than as attributes, the
    way ``_ACTIVE_COLLECTOR`` is above and for the same reason: a direct access
    to a protected name across a module boundary is what pyright reports.
    """
    del config
    try:
        sys.monitoring.use_tool_id(_TOOL_ID, _TOOL_NAME)
    except ValueError:  # something else got there first; the report stands down
        return
    for name in ("_fail", "_fail_narrowing"):
        function: Any = vars(Expect)[name]
        sys.monitoring.set_local_events(_TOOL_ID, function.__code__, sys.monitoring.events.PY_START)
    sys.monitoring.register_callback(
        _TOOL_ID, sys.monitoring.events.PY_START, _record_failing_assertion
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Report any assertion the whole run never once showed failing.

    Only on a complete, green run. A subset would report everything it did not
    reach, and a run that already failed has a better message to show first.
    """
    if exitstatus != 0 or session.config.option.keyword or session.config.args != ["tests"]:
        return
    if sys.monitoring.get_tool(_TOOL_ID) != _TOOL_NAME:
        return  # the monitor never installed, so there is nothing to conclude
    uncovered = sorted(
        f"{owner}.{name}"
        for owner, name in _happy_calls.HAPPY_CALLS
        if (owner, name) not in OBSERVED_FAILING and (owner, name) not in CANNOT_FAIL
    )
    if uncovered:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        print(  # noqa: T201
            f"\nthese assertions were never once shown FAILING: {uncovered}\n"
            f"Each has a passing exercise and no failing one, so the branch that "
            f"builds its message is never rendered and it could be neutered to "
            f"`return self` with the suite green. Add a test that fails it, or "
            f"record it in CANNOT_FAIL with the reason it cannot."
        )
    stale = sorted(f"{o}.{n}" for o, n in CANNOT_FAIL if (o, n) in OBSERVED_FAILING)
    if stale:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        print(f"\nCANNOT_FAIL names assertions that were seen failing: {stale}")  # noqa: T201


#: Skip a test whose assertion *is* a measurement, when something is watching.
#:
#: These are not flaky and this is not a concession: a tracer allocates on the
#: path it traces, so under `coverage run` the reading is the instrument reading
#: itself. Only the peak-allocation claims are marked; the retention probes
#: survive untouched, because taking the smallest of three passes absorbs what a
#: tracer adds.
measured = pytest.mark.skipif(
    watching_the_interpreter() is not None,
    reason=f"a measurement cannot be read while {watching_the_interpreter()}",
)
