"""Report per-call cost, allocation behaviour and import time.

Everything here is printed and nothing is asserted: a wall-clock number varies
with the machine it was read on, so holding a test to one buys a flake rather
than a guard-rail. The claims that survive a change of machine are asserted in
``tests/test_performance_invariants.py`` instead.
"""

import statistics
import subprocess
import sys
import timeit
from typing import TYPE_CHECKING, Final

from benchmarks import blocks_allocated, bytes_retained, peak_bytes_allocated
from lovely_assertions import expect

if TYPE_CHECKING:
    from collections.abc import Callable

#: Enough iterations that the timer's own resolution disappears, few enough that
#: the whole report finishes in a few seconds.
_CALLS: Final = 200_000
#: Independent timing runs, of which the fastest is kept: a slower one only ever
#: means the machine was busy with something else.
_REPEATS: Final = 5


def _ns(statement: str, setup: str = "") -> float:
    """Nanoseconds per call, taking the best run.

    The minimum, not the mean: a slower run only ever means the machine was doing
    something else, so the fastest observed run is the least noisy estimate of
    what the code actually costs.
    """
    namespace: dict[str, object] = {"expect": expect}
    best = min(
        timeit.repeat(statement, setup=setup, number=_CALLS, repeat=_REPEATS, globals=namespace)
    )
    return best / _CALLS * 1e9


def _row(label: str, statement: str, setup: str = "", *, baseline: float | None = None) -> float:
    cost = _ns(statement, setup)
    suffix = "" if baseline is None else f"   ({cost / baseline:.0f}x bare assert)"
    print(f"  {label:<44} {cost:8.1f} ns{suffix}")
    return cost


def _report_calls() -> None:
    print(f"Per-call cost (best of {_REPEATS} x {_CALLS:,})")
    print("-" * 72)
    baseline = _row("assert value == 3", "assert value == 3", "value = 3")
    print()
    print("  A whole assertion, wrapper included:")
    _row(
        "expect(value).is_equal_to(3)",
        "expect(value).is_equal_to(3)",
        "value = 3",
        baseline=baseline,
    )
    _row(
        "expect(text).starts_with('he')",
        "expect(text).starts_with('he')",
        "text = 'hello'",
        baseline=baseline,
    )
    _row(
        "expect(items).contains(2)",
        "expect(items).contains(2)",
        "items = [1, 2, 3]",
        baseline=baseline,
    )
    print()
    print("  The assertion alone, on a subject already built:")
    _row("is_equal_to", "subject.is_equal_to(3)", "subject = expect(3)")
    _row("is_positive", "subject.is_positive()", "subject = expect(5)")
    _row("starts_with", "subject.starts_with('he')", "subject = expect('hello')")
    _row("contains", "subject.contains(2)", "subject = expect([1, 2, 3])")
    print()
    print("  Dispatch alone -- where the wrapper's cost actually is:")
    _row("expect(3)          exact-type table", "expect(3)")
    _row("expect([1, 2, 3])  exact-type table", "expect(items)", "items = [1, 2, 3]")
    _row("expect({'a': 1})   exact-type table", "expect(rows)", "rows = {'a': 1}")
    _row("expect(object())   full issubclass chain", "expect(value)", "value = object()")


def _report_allocation() -> None:
    """All three measurements side by side, because they answer different questions.

    ``blocks`` is how many objects are still held when the calls are over;
    ``retained`` is how many bytes are; ``peak`` is the most one call ever held at
    once. The last two rows are anti-patterns on purpose, and each one reads as
    nothing in two of the three columns -- a discarded message is net-zero by the
    time anything is counted, and a registry of references creates no object of
    its own. A column that stayed silent for one of them is a column that would
    stay silent for the same bug in the library. The report shows that difference
    rather than asserting it; ``tests/test_performance_invariants.py`` asserts it.
    """
    print()
    print("Allocation on a passing assertion (none is the contract)")
    print("-" * 72)
    subject = expect(3)
    numeric = expect(5)
    registry: list[object] = []

    def discards_a_message() -> object:
        _ = f"to equal {3!r}, but was {subject.subject!r}"
        return subject.is_equal_to(3)

    def keeps_a_registry() -> object:
        registry.append(subject.subject)
        return subject.is_equal_to(3)

    rows: list[tuple[str, Callable[[], object]]] = [
        ("no-op baseline", lambda: None),
        ("is_equal_to", lambda: subject.is_equal_to(3)),
        ("is_positive", numeric.is_positive),
        ("is_equal_to + a discarded f-string", discards_a_message),
        ("is_equal_to + a registry of subjects", keeps_a_registry),
    ]
    print(f"  {'':<38} {'blocks':>9} {'retained':>12} {'peak in one call':>18}")
    for label, callback in rows:
        blocks = blocks_allocated(callback)
        held = bytes_retained(callback)
        peak = peak_bytes_allocated(callback)
        print(f"  {label:<38} {blocks:+8d} {held:+11d} B {peak:11d} bytes")


def _report_import() -> None:
    print()
    print("Import time (a few milliseconds is the contract)")
    print("-" * 72)
    timings: list[float] = []
    for _ in range(10):
        result = subprocess.run(
            [sys.executable, "-X", "importtime", "-c", "import lovely_assertions"],
            capture_output=True,
            text=True,
            check=True,
        )
        rows = [
            line
            for line in result.stderr.splitlines()
            if line.rstrip().endswith("lovely_assertions")
        ]
        if rows:
            timings.append(int(rows[-1].split("|")[1].strip()) / 1000)
    median = statistics.median(timings)
    print(f"  {'import lovely_assertions':<44} {median:8.2f} ms (median of 10)")


def main() -> None:
    _report_calls()
    _report_allocation()
    _report_import()


if __name__ == "__main__":
    main()
