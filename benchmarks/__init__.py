"""Performance guard-rails for lovely-assertions.

Run with ``uv run python -m benchmarks``.

Performance is not what this library is for: the goal is no waste on the hot
path, not a race for microseconds. These numbers exist to catch the first kind of
problem, and the difference matters. Removing a ten-fold cost that bought nothing
is worth doing; shaving a hundred nanoseconds off a dispatch that already costs
less than the test around it is not.

The suite is deliberately not part of ``pytest``. Timings vary with the machine,
and a wall-clock assertion in CI is a flaky test wearing a useful disguise. What
*is* asserted lives in ``tests/test_performance_invariants.py``: the claims that
hold regardless of how fast the machine is.

**Three measurements, three different bugs.** They are not three ways of saying
the same thing, and each one is blind to what the other two are for.

:func:`peak_bytes_allocated` counts the high-water mark *within* a single call --
a *transient*, something built and thrown away. It is the one that can check the
claim that a passing assertion allocates nothing: an f-string evaluated on the
happy path and discarded is net-zero by the time a loop ends, so a before/after
count of anything cannot see it.

:func:`bytes_retained` counts the traced bytes still held when the calls are over
-- a *leak*, in the units a leak is actually measured in.

:func:`blocks_allocated` counts the *number of live blocks* still held. It is the
coarsest of the three and it is kept for one reason: it is the only one that does
not need ``tracemalloc``, so it says what a leak costs in objects rather than in
bytes, which is the number that matters for a per-call allocation. It is blind to
any leak that does not create a new object -- see its own docstring.

None of that is a hypothesis. ``test_the_three_measurements_see_three_different_bugs``
plants a discarded f-string and a growing registry and pins all six answers.

:func:`measuring_peaks` is the fourth name here and not a fourth measurement: it
is :func:`peak_bytes_allocated`'s reading with the session opened once instead of
per call, for the caller with a whole sweep of callbacks to read rather than one.
"""

import gc
import sys
import tracemalloc
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Final

__all__ = [
    "blocks_allocated",
    "bytes_retained",
    "measuring_peaks",
    "peak_bytes_allocated",
    "watching_the_interpreter",
]

#: Enough repetitions that a single stray allocation per call is unmistakable,
#: few enough that the invariant test stays instant.
CALLS: Final = 20_000

#: Far fewer, because :func:`peak_bytes_allocated` does not need repetition to
#: build a signal: it reads an exact high-water mark on every single call, and one
#: call would in principle do. The repetitions are there to catch an allocation
#: that happens only *sometimes* -- a cache that refills, a branch taken on every
#: fourth call -- not to accumulate anything. ``tracemalloc`` costs roughly a
#: microsecond per traced allocation, so this stays small on purpose.
PEAK_CALLS: Final = 500

#: Calls made before measuring anything, and discarded. The first call through an
#: assertion is not representative: it populates ``_LAZY_ANSWERS`` in the dispatch
#: table, the ``re`` module's pattern cache, and the negative-result caches inside
#: every ABC an ``isinstance`` touches. Measuring those would report a one-off
#: setup cost as a per-call one.
WARMUP_CALLS: Final = 200

#: Independent readings of a retention count, of which the *smallest* is kept.
#:
#: The noise here is one-sided, the way it is in the allocation sweep that reads
#: this module: a block freed between the two ``gc.collect()`` calls lowers the
#: ``before`` total and so *inflates* the reading, while nothing deflates it. The
#: minimum is therefore the honest statistic, not a convenience.
#:
#: The reading that has to be steady is the no-op baseline, because every call
#: site compares against it. On CPython 3.14 a single reading of it is not:
#: ``blocks_allocated(lambda: None)`` answers differently in isolation and inside
#: a full pytest session, and one high reading of the baseline turns every
#: comparison against it into a failure that says nothing about the callback.
#:
#: A real leak survives this untouched, which is the property that matters: it
#: grows with ``calls``, so every pass reads it and the minimum is still far above
#: the baseline. See ``test_the_three_measurements_see_three_different_bugs``.
RETENTION_PASSES: Final = 3


def watching_the_interpreter() -> str | None:
    """What is instrumenting execution right now, or ``None`` when nothing is.

    A tracer allocates on the path it is tracing, which is the path these
    functions measure. Under ``coverage run -m pytest`` every reading here is the
    instrument reading the instrument, and each one comes back above its baseline
    for a reason that is not a regression -- so a caller that finds a name here
    has to skip rather than report, and a coverage number costs a run that
    measures nothing.

    Both mechanisms, because ``coverage`` uses whichever the interpreter offers:
    ``sys.monitoring`` on 3.12 and later, ``sys.settrace`` before that and under
    ``--timid``.
    """
    if sys.gettrace() is not None:
        return "sys.settrace is active"
    watcher = sys.monitoring.get_tool(sys.monitoring.COVERAGE_ID)
    if watcher is not None:
        return watcher + " is monitoring execution"
    return None


def blocks_allocated(
    callback: Callable[[], object], /, calls: int = CALLS, warmup: int = WARMUP_CALLS
) -> int:
    """Net memory *blocks* the interpreter holds after ``calls`` invocations.

    This is *retention*, and only retention. A call that allocates an object and
    drops it again before returning reads as zero here, because by the time the
    loop ends the block is back on the free list -- see
    :func:`peak_bytes_allocated` for the measurement that does see it.

    **Read the word blocks literally, because the gap is wide.** This counts
    objects, not bytes, and a great many leaks do not create an object. A registry
    that appends the subject to a module-level list holds a reference to something
    that already existed: the list's pointer array is reallocated in place and
    stays one block, so twenty thousand leaked references read as *exactly the
    no-op baseline*. So does a debug log that extends a ``bytearray``. Both are
    genuine unbounded leaks and both are invisible here. That is what
    :func:`bytes_retained` is for, and why the retention claim is asserted with
    both. What this one is still the right instrument for is the leak that does
    build something -- a ``Found`` kept alive, a memo of freshly formatted strings
    -- because one block per call is a plainer statement of the fault than the
    bytes it happens to occupy, and because it needs no tracer to say it.

    The warmup is not decoration. Measured cold, ``expect(PurePosixPath(...))
    .has_name("x")`` sits a few blocks above the no-op baseline and lands exactly
    on it once warm -- not a leak but ``pathlib`` filling its lazily-computed
    ``_tail`` on first access, a fixed cost that does not grow with ``calls`` and
    that this function has no way to tell apart from a real one. Reporting a
    one-off cache fill as a leak is a false positive in a performance test, which
    is the failure that teaches people to press rerun.

    Lives here rather than in the test that uses it because measurement is this
    package's job, and because a benchmark importing from ``tests`` is a
    dependency pointing the wrong way.
    """
    for _ in range(warmup):
        callback()
    readings: list[int] = []
    for _ in range(RETENTION_PASSES):
        gc.collect()
        before = sys.getallocatedblocks()
        for _ in range(calls):
            callback()
        gc.collect()
        readings.append(sys.getallocatedblocks() - before)
    return min(readings)


def bytes_retained(
    callback: Callable[[], object], /, calls: int = CALLS, warmup: int = WARMUP_CALLS
) -> int:
    """Net traced bytes the interpreter still holds after ``calls`` invocations.

    The same question as :func:`blocks_allocated` asked in the units a leak is
    actually measured in, and the reason it is asked twice is that the block count
    misses the most ordinary shape the bug takes. A list of every subject asserted
    on grows by a pointer per call and by no blocks at all; here it reads as a
    byte count that climbs with ``calls``, orders of magnitude above the baseline.
    ``test_the_three_measurements_see_three_different_bugs`` pins both halves of
    that sentence.

    The baseline is not quite zero, and that offset is not a rounding:
    ``get_traced_memory()`` returns a tuple, and the one built for the opening
    reading is itself traced. It is the same handful of bytes on every run and on
    every callback, so it cancels against a baseline measured the same way --
    which is how every caller here uses it. Subtracting a constant that was
    measured rather than assumed would be the more fragile choice.

    ``gc.collect()`` runs on both sides, so a cycle waiting to be collected is not
    reported as a leak. The collector is left *enabled* during the loop, unlike
    :func:`peak_bytes_allocated`: a collection landing mid-loop can only make this
    number smaller, never larger, so it cannot invent a failure.

    **What it does not see.** Whatever ``tracemalloc`` does not see: memory the C
    allocator hands back from a free list is not traced, and neither is anything
    allocated before the tracer started. And it is still a *net* figure -- a call
    that leaks one object and frees another of the same size reads as zero.
    """
    if tracemalloc.is_tracing():
        message = (
            "tracemalloc is already tracing; bytes_retained would stop it "
            "underneath its owner. Run without -X tracemalloc."
        )
        raise RuntimeError(message)
    for _ in range(warmup):
        callback()
    gc.collect()
    tracemalloc.start(1)
    try:
        before = tracemalloc.get_traced_memory()[0]
        for _ in range(calls):
            callback()
        gc.collect()
        after = tracemalloc.get_traced_memory()[0]
    finally:
        tracemalloc.stop()
    return after - before


def peak_bytes_allocated(
    callback: Callable[[], object], /, calls: int = PEAK_CALLS, warmup: int = WARMUP_CALLS
) -> int:
    """The largest number of bytes ``callback`` held at once during any one call.

    The measurement the claim "a passing assertion allocates nothing" actually
    needs. ``tracemalloc.reset_peak()`` sets the peak to the current total; the
    callback then runs; ``get_traced_memory()`` reports how far above that the
    total ever climbed. An f-string built on the happy path and immediately
    discarded raises that high-water mark by the size of the string and lowers it
    again, so the number comes back non-zero even though nothing was retained.

    It is an exact reading, not a sample. On this machine every clean assertion in
    ``tests/test_performance_invariants.py`` returns literally ``0``, the same
    ``0``, on every run -- there is no noise floor to allow for, because the
    counter is incremented by the allocator itself rather than sampled from the
    outside. That is what makes it safe to compare with ``<=`` in CI.

    Two deliberate choices in the loop.

    ``gc`` is off while measuring. A collection landing mid-call frees objects the
    callback did not allocate, which lowers ``current`` and inflates the reported
    peak by however much unrelated garbage happened to be lying around. That is
    precisely the shape of a test that passes on a laptop and fails in CI, so the
    collector is stopped for the duration and restored afterwards.

    ``warmup`` calls run untraced first, for the reason given on
    :data:`WARMUP_CALLS`.

    **What it does not see.** The peak is read relative to the total *after* the
    call, so a call that both allocates transiently and retains something reports
    only the difference between them, and a call that retains more than it
    transiently allocated reports zero. Retention is :func:`bytes_retained`'s and
    :func:`blocks_allocated`'s question, and all three run over the same table for
    that reason. It also cannot see an allocation the C allocator serves without
    telling ``tracemalloc`` -- free-list reuse of small tuples and frames is
    invisible here, which is why a bare ``lambda: None`` reads as ``0`` rather
    than as the cost of a frame.

    ``tracemalloc`` is global and cannot be nested, so an already-running trace is
    refused rather than silently stopped underneath whoever started it.
    """
    if tracemalloc.is_tracing():
        message = (
            "tracemalloc is already tracing; peak_bytes_allocated would stop it "
            "underneath its owner. Run without -X tracemalloc."
        )
        raise RuntimeError(message)
    for _ in range(warmup):
        callback()
    gc.collect()
    collecting = gc.isenabled()
    gc.disable()
    tracemalloc.start(1)
    try:
        return _worst_peak(callback, calls)
    finally:
        tracemalloc.stop()
        if collecting:
            gc.enable()


def _worst_peak(callback: Callable[[], object], calls: int, /) -> int:
    """The loop both peak measurements share, inside an already-open session.

    ``reset_peak()`` sets the peak to the current total; the callback runs; the
    difference between the peak reached and the total left behind is what the
    call held at once and gave back. The maximum over ``calls`` is the answer,
    because an allocation that happens on one call in four is still an
    allocation.
    """
    worst = 0
    for _ in range(calls):
        tracemalloc.reset_peak()
        callback()
        current, peak = tracemalloc.get_traced_memory()
        worst = max(worst, peak - current)
    return worst


@contextmanager
def measuring_peaks(
    calls: int = PEAK_CALLS, warmup: int = WARMUP_CALLS
) -> "Generator[Callable[[Callable[[], object]], int]]":
    """One tracing session for a whole sweep, yielding the reader to use inside it.

    :func:`peak_bytes_allocated` answers one question and pays a fixed price to
    do it: a ``gc.collect()`` on the live heap, whose cost is set by the size of
    that heap and not by how much work the callback does. Over a sweep of
    hundreds of callbacks -- which is what covering every public assertion
    against its own reference comes to -- that setup costs several times the
    measurements themselves. Opening the session once and reading many callbacks
    inside it makes the same sweep cost the work rather than the setup.

    The reading is identical: same ``reset_peak``/``get_traced_memory`` loop, same
    collector-off discipline, same one-frame tracer. Two things differ, and both
    are deliberate.

    *The warmup runs traced.* Whatever it fills -- a pattern cache, an ABC's
    negative-result cache, ``pathlib``'s lazy ``_tail`` -- is allocated inside the
    session and stays allocated, which raises the running total and nothing else:
    every reading is a difference taken after a ``reset_peak()``, so a higher
    floor cancels exactly.

    *The collector stays off for the whole session* rather than for one
    measurement. Nothing here creates unbounded cyclic garbage -- the heaviest
    entry in such a sweep is an exception with a traceback, a few kilobytes over
    its repetitions -- and a caller whose sweep is large enough to care should
    open a session per pass, which is what
    ``tests/test_performance_invariants.py`` does.

    Refused while another trace is running, for the reason
    :func:`peak_bytes_allocated` gives: ``tracemalloc`` is global and stopping it
    underneath its owner is worse than not measuring.
    """
    if tracemalloc.is_tracing():
        message = (
            "tracemalloc is already tracing; measuring_peaks would stop it "
            "underneath its owner. Run without -X tracemalloc."
        )
        raise RuntimeError(message)
    gc.collect()
    collecting = gc.isenabled()
    gc.disable()
    tracemalloc.start(1)

    def read(callback: Callable[[], object], /) -> int:
        for _ in range(warmup):
            callback()
        return _worst_peak(callback, calls)

    try:
        yield read
    finally:
        tracemalloc.stop()
        if collecting:
            gc.enable()
