"""Soft assertions: named, nested, discardable.

The seam lives in ``_fail``, the one funnel every assertion in the library already
goes through; putting it anywhere else would mean threading a scope through each
assertion by hand. The state is per-scope, held in a ``ContextVar`` rather than a
global, which is what makes it safe under parallel test runners -- the Python
equivalent of the ``AssertionChain`` FluentAssertions injects.
"""

import asyncio
import contextlib
import contextvars
import gc
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, cast

import pytest

from lovely_assertions import AssertionFailure, ValueFormatter, expect, soft_assertions

if TYPE_CHECKING:
    from collections.abc import Iterator
    from contextvars import ContextVar


def _active_collector() -> object | None:
    """The collector failures are being routed to, or ``None`` for raising.

    Read out of the module namespace by name, the way ``tests/test_happy_path.py``
    reaches the same private: a direct attribute access across modules is what
    pyright reports, and the point here is the value, not the spelling.
    """
    from lovely_assertions import _core

    variable: ContextVar[object | None] = vars(_core)["_ACTIVE_COLLECTOR"]
    return variable.get()


def test_a_passing_block_raises_nothing() -> None:
    with soft_assertions():
        expect(1).is_equal_to(1)
        expect("x").is_equal_to("x")


def test_failures_aggregate_instead_of_stopping_at_the_first() -> None:
    with pytest.raises(AssertionFailure) as caught, soft_assertions():
        first = 1
        second = 2
        expect(first).is_equal_to(9)
        expect(second).is_equal_to(9)
    message = str(caught.value)
    assert "2 assertions failed:" in message
    assert "Expected first to equal 9, but was 1." in message
    assert "Expected second to equal 9, but was 2." in message


def test_a_single_failure_is_phrased_in_the_singular() -> None:
    with pytest.raises(AssertionFailure) as caught, soft_assertions():
        first = 1
        expect(first).is_equal_to(9)
    assert "1 assertion failed:" in str(caught.value)


def test_assertions_keep_chaining_after_a_failure() -> None:
    """``_fail`` returns ``Self`` so a soft block does not stop at the first miss."""
    with pytest.raises(AssertionFailure) as caught, soft_assertions():
        value = 1
        expect(value).is_equal_to(9).is_equal_to(8)
    message = str(caught.value)
    assert "2 assertions failed:" in message
    assert "but was 1" in message


def test_scope_name_prefixes_the_subject() -> None:
    with pytest.raises(AssertionFailure) as caught, soft_assertions("Test1"):
        balance = 1
        expect(balance).is_equal_to(9)
    assert "Expected Test1/balance to equal 9, but was 1." in str(caught.value)


def test_nested_scope_names_compose_into_a_path() -> None:
    with (
        pytest.raises(AssertionFailure) as caught,
        soft_assertions("Test1"),
        soft_assertions("Test2"),
    ):
        items = [1]
        expect(items).is_equal_to([])
    assert "Expected Test1/Test2/items to equal []" in str(caught.value)


def test_anonymous_scopes_do_not_appear_in_the_path() -> None:
    with pytest.raises(AssertionFailure) as caught, soft_assertions("Test1"), soft_assertions():
        balance = 1
        expect(balance).is_equal_to(9)
    assert "Expected Test1/balance to equal 9, but was 1." in str(caught.value)


def test_inner_failures_bubble_up_to_the_outer_scope() -> None:
    """Only the outermost scope raises; otherwise nesting would defeat aggregation."""
    with pytest.raises(AssertionFailure) as caught, soft_assertions("Outer"):
        outer_value = 1
        expect(outer_value).is_equal_to(9)
        with soft_assertions("Inner"):
            inner_value = 2
            expect(inner_value).is_equal_to(9)
    message = str(caught.value)
    assert "2 assertions failed:" in message
    assert "Expected Outer/outer_value to equal 9" in message
    assert "Expected Outer/Inner/inner_value to equal 9" in message


def test_leaving_a_scope_restores_hard_failures() -> None:
    with soft_assertions():
        expect(1).is_equal_to(1)
    with pytest.raises(AssertionFailure):
        expect(1).is_equal_to(2)


def test_discard_returns_messages_without_raising() -> None:
    with soft_assertions() as scope:
        balance = 1
        expect(balance).is_equal_to(9)
        collected = scope.discard()
    assert collected == ["Expected balance to equal 9, but was 1."]


def test_discard_empties_the_scope() -> None:
    """Nothing left to aggregate means nothing raised on the way out."""
    with soft_assertions() as scope:
        balance = 1
        expect(balance).is_equal_to(9)
        scope.discard()
        assert scope.discard() == []


def test_discard_on_a_clean_scope_returns_empty() -> None:
    with soft_assertions() as scope:
        expect(1).is_equal_to(1)
        assert scope.discard() == []


def test_a_non_assertion_exception_propagates_untouched() -> None:
    with pytest.raises(ZeroDivisionError), soft_assertions():
        value = 1
        expect(value).is_equal_to(9)
        _ = 1 / 0


def test_a_real_error_is_not_masked_by_collected_failures() -> None:
    """The programming error is the more urgent signal; do not bury it."""
    with pytest.raises(ValueError, match="boom"), soft_assertions():
        value = 1
        expect(value).is_equal_to(9)
        raise ValueError("boom")


def test_scope_exposes_its_name() -> None:
    with soft_assertions("Test1") as scope:
        assert scope.name == "Test1"
    with soft_assertions() as anonymous:
        assert anonymous.name is None


def test_scopes_are_isolated_between_threads() -> None:
    """ContextVar, not global state: a scope in one thread must not catch another's."""

    def soft_worker() -> int:
        with soft_assertions() as scope:
            expect(1).is_equal_to(2)
            return len(scope.discard())

    def hard_worker() -> bool:
        try:
            expect(1).is_equal_to(2)
        except AssertionFailure:
            return True
        return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        soft_results = [pool.submit(soft_worker) for _ in range(4)]
        hard_results = [pool.submit(hard_worker) for _ in range(4)]
        assert [future.result() for future in soft_results] == [1, 1, 1, 1]
        assert all(future.result() for future in hard_results)


def test_scopes_are_isolated_between_concurrent_tasks() -> None:
    """Same guarantee under asyncio, where tasks copy the context."""

    async def soft_task() -> int:
        with soft_assertions() as scope:
            expect(1).is_equal_to(2)
            await asyncio.sleep(0)
            return len(scope.discard())

    async def hard_task() -> bool:
        await asyncio.sleep(0)
        try:
            expect(1).is_equal_to(2)
        except AssertionFailure:
            return True
        return False

    async def main() -> list[object]:
        return list(await asyncio.gather(soft_task(), hard_task(), soft_task()))

    assert asyncio.run(main()) == [1, True, 1]


# ---------------------------------------------------------------------------
# The routing always comes back
#
# A collector left active is the worst failure this library has: it does not
# raise, it *stops* raising. Every failing assertion in that thread from then on
# is filed into a sink nobody reads, so under a test runner a whole file goes
# green without asserting anything. Every test below therefore ends the same two
# ways -- the ContextVar is back to `None`, and a genuinely failing assertion
# genuinely fails.
# ---------------------------------------------------------------------------
def _routing_still_raises() -> bool:
    """Whether a failing assertion still fails, which is what a leak silences."""
    try:
        expect(1).is_equal_to(2)
    except AssertionFailure:
        return True
    return False


def test_re_entering_a_live_scope_is_refused_rather_than_leaked() -> None:
    """Re-entering one scope object would leak the routing, so it is refused outright.

    A scope holds a single reset token. Entering the same object twice would
    overwrite that token, the outer ``__exit__`` would find nothing to reset, and
    the collector would stay active for the rest of the thread -- which is this
    library silently ceasing to report anything.
    """
    scope = soft_assertions("outer")
    with pytest.raises(RuntimeError, match="not reentrant"), scope, scope:
        pass  # pragma: no cover -- the second `with` never opens
    assert _active_collector() is None
    assert _routing_still_raises()


def test_a_refused_re_entry_leaves_the_scope_it_was_refused_in_intact() -> None:
    """``__enter__`` refuses before it touches anything, so the open block goes on."""
    scope = soft_assertions("ledger")
    with scope:
        with pytest.raises(RuntimeError, match="already open"):
            scope.__enter__()  # `with scope` again, spelled out
        balance = 1
        expect(balance).is_equal_to(9)
        collected = scope.discard()
    assert collected == ["Expected ledger/balance to equal 9, but was 1."]
    assert _active_collector() is None


def test_a_scope_object_can_be_opened_again_once_it_has_closed() -> None:
    """Re-*use* is not re-*entry*: a closed scope has nothing left to alias."""
    scope = soft_assertions("run")
    for _ in range(2):
        with scope:
            balance = 1
            expect(balance).is_equal_to(9)
            assert scope.discard() == ["Expected run/balance to equal 9, but was 1."]
    assert _active_collector() is None


def test_a_new_block_does_not_report_what_the_last_one_held_back() -> None:
    """A body that raises keeps its failures; the next block must not inherit them.

    They stay readable through ``discard()`` until the scope is opened again --
    reporting them under the next block would attribute a finding to code that
    never ran.
    """
    scope = soft_assertions("sync")
    with pytest.raises(ValueError, match="boom"), scope:
        balance = 1
        expect(balance).is_equal_to(9)
        raise ValueError("boom")
    assert scope.discard() == ["Expected sync/balance to equal 9, but was 1."]

    other = soft_assertions("sync")
    with pytest.raises(ValueError, match="boom"), other:
        balance = 1
        expect(balance).is_equal_to(9)
        raise ValueError("boom")
    with other:  # nothing wrong in *this* block, so nothing is raised on the way out
        expect(1).is_equal_to(1)
    assert _active_collector() is None


def test_a_body_that_raises_still_puts_the_routing_back() -> None:
    with pytest.raises(ValueError, match="boom"), soft_assertions("aborted"):
        expect(1).is_equal_to(2)
        raise ValueError("boom")
    assert _active_collector() is None
    assert _routing_still_raises()


def test_a_refused_formatter_does_not_leave_the_routing_on() -> None:
    """``__enter__`` can still fail, and a failed ``__enter__`` gets no ``__exit__``.

    Pushing formatters refuses an object that is not one, so it has to happen
    *before* the routing switch: otherwise the refusal leaves the collector
    active with nothing scheduled to turn it off.
    """
    formatters = cast("tuple[ValueFormatter, ...]", (object(),))
    with (
        pytest.raises(TypeError, match="not a value formatter"),
        soft_assertions("bad", formatters=formatters),
    ):
        pass  # pragma: no cover -- the block never opens
    assert _active_collector() is None
    assert _routing_still_raises()


def test_a_generator_abandoned_inside_a_scope_leaves_no_routing_behind() -> None:
    """Collecting a suspended generator throws ``GeneratorExit`` in at the yield.

    That runs ``__exit__`` with an exception in flight, which is exactly the path
    that must restore the routing and raise nothing -- a scope raising its
    aggregate during garbage collection would report a finding at a point in the
    program that has nothing to do with it.
    """

    def rows() -> "Iterator[int]":
        with soft_assertions("stream") as scope:
            expect(1).is_equal_to(2)
            yield 1
            _ = scope.discard()  # pragma: no cover -- never resumed

    stream = rows()
    assert next(stream) == 1
    assert _active_collector() is not None
    del stream
    gc.collect()
    assert _active_collector() is None
    assert _routing_still_raises()


def test_leaving_a_scope_in_another_task_is_refused_rather_than_leaked() -> None:
    """A token belongs to the context that made it; ``reset`` says so obscurely.

    ``ContextVar.reset`` raises ``ValueError: ... created in a different
    Context``, which names neither the scope nor the mistake. The scope names
    both, and leaves the context it was left in alone rather than switching off a
    scope it never opened.
    """

    async def main() -> str:
        scope = soft_assertions("crosser")

        async def open_it() -> None:
            scope.__enter__()  # a `with` cannot span two tasks

        async def leave_it() -> str:
            try:
                scope.__exit__(None, None, None)
            except RuntimeError as refused:
                return str(refused)
            return ""  # pragma: no cover -- the refusal is the assertion

        await asyncio.create_task(open_it())
        return await asyncio.create_task(leave_it())

    assert "different thread or task" in asyncio.run(main())
    assert _active_collector() is None
    assert _routing_still_raises()


def test_leaving_scopes_out_of_order_switches_the_routing_off() -> None:
    """Unreachable from a ``with`` statement, and unrecoverable once done.

    The outer scope's token restores what was active when *it* opened, which
    would resurrect a collector the inner scope has already ended. There is no
    right answer left, so the routing goes off: an assertion that raises when it
    should have been collected is loud, and one collected into a dead scope is
    silent.
    """
    outer = soft_assertions("outer")
    inner = soft_assertions("inner")
    outer.__enter__()
    inner.__enter__()
    with pytest.raises(RuntimeError, match="out of order"):
        outer.__exit__(None, None, None)
    assert _active_collector() is None
    with pytest.raises(RuntimeError, match="out of order"):
        inner.__exit__(None, None, None)
    assert _active_collector() is None
    assert _routing_still_raises()


def test_leaving_a_scope_that_was_never_opened_is_refused() -> None:
    scope = soft_assertions("unopened")
    with pytest.raises(RuntimeError, match="not open"):
        scope.__exit__(None, None, None)


def test_leaving_a_scope_twice_is_refused() -> None:
    """The second exit has a spent token, and a spent token must never be reset."""
    scope = soft_assertions("once")
    with scope:
        expect(1).is_equal_to(1)
    with pytest.raises(RuntimeError, match="not open"):
        scope.__exit__(None, None, None)
    assert _active_collector() is None


def test_leaving_an_unopened_scope_does_not_disturb_an_open_one() -> None:
    """The refusal is not allowed to be a second leak: it touches no routing."""
    unopened = soft_assertions("unopened")
    with soft_assertions("live") as live:
        with pytest.raises(RuntimeError, match="not open"):
            unopened.__exit__(None, None, None)
        balance = 1
        expect(balance).is_equal_to(9)
        collected = live.discard()
    assert collected == ["Expected live/balance to equal 9, but was 1."]
    assert _active_collector() is None


def test_an_inner_scope_that_raises_leaves_both_scopes_routed_back() -> None:
    """Two different scopes, the inner one aborted: neither may stay active."""
    with pytest.raises(ValueError, match="inner boom"), soft_assertions("outer") as outer:
        expect(1).is_equal_to(2)
        with soft_assertions("inner"):
            expect(3).is_equal_to(4)
            raise ValueError("inner boom")
    assert _active_collector() is None
    assert _routing_still_raises()
    # The outer scope kept what it had collected before the error, and reported
    # nothing: the error is the more urgent signal.
    assert outer.discard() == ["Expected outer/1 to equal 2, but was 1."]


def test_discard_is_safe_outside_a_block_and_twice_over() -> None:
    scope = soft_assertions("never opened")
    assert scope.discard() == []
    assert scope.discard() == []
    assert _active_collector() is None


def test_a_scope_can_be_opened_again_after_a_discard() -> None:
    scope = soft_assertions("retry")
    with scope:
        expect(1).is_equal_to(2)
        _ = scope.discard()
    with pytest.raises(AssertionFailure, match="1 assertion failed"), scope:
        expect(1).is_equal_to(2)
    assert _active_collector() is None


def test_two_threads_hold_open_scopes_at_the_same_time() -> None:
    """Interleaved, not merely sequential: both are open before either collects."""
    both_open = threading.Barrier(2, timeout=5)

    def worker(marker: int) -> list[str]:
        with soft_assertions() as scope:
            both_open.wait()
            value = marker
            expect(value).is_equal_to(-1)
            return scope.discard()

    with ThreadPoolExecutor(max_workers=2) as pool:
        # Submitted before either is waited on: `.result()` on the first would
        # block until it finished, and the barrier would never be reached.
        running = [pool.submit(worker, 1), pool.submit(worker, 2)]
        collected = [future.result() for future in running]
    assert sorted(message for messages in collected for message in messages) == [
        "Expected value to equal -1, but was 1.",
        "Expected value to equal -1, but was 2.",
    ]
    assert _active_collector() is None


def test_leaving_a_scope_inside_a_task_opened_outside_it_is_refused() -> None:
    """The other half of the cross-context mistake, and the half that hides.

    A task created inside an open scope inherits a *copy* of the context, so the
    scope's own collector is the active one in there -- while the token still
    belongs to the context that made it. Deciding by "is the active collector
    mine?" therefore takes the ordinary path and hands ``ContextVar.reset`` a
    foreign token, which answers with the raw ``ValueError`` the scope exists to
    replace. Only ``reset`` itself can tell the two apart.
    """

    async def main() -> str:
        scope = soft_assertions("crosser")
        scope.__enter__()  # opened in *this* task's context
        assert _active_collector() is not None

        async def leave_it() -> str:
            # Inherited the context above, so the collector is visible here too.
            assert _active_collector() is not None
            try:
                scope.__exit__(None, None, None)
            except RuntimeError as refused:
                return str(refused)
            return ""  # pragma: no cover -- the refusal is the assertion

        return await asyncio.create_task(leave_it())

    assert "different thread or task" in asyncio.run(main())
    assert _active_collector() is None
    assert _routing_still_raises()


def test_a_foreign_scope_with_formatters_is_refused_without_a_second_error() -> None:
    """Scoped formatters are context-local too, so their token is just as foreign.

    Popping it would raise the same ``ValueError`` the collector's reset just
    refused to let through, replacing the refusal that names the mistake with one
    that names a ``Token``. That context keeps its own formatters.
    """

    class Shouty:
        def can_handle(self, value: object) -> bool:
            return isinstance(value, str)

        def format(self, value: object) -> str:
            return str(value).upper()  # pragma: no cover -- never rendered

    formatters: tuple[ValueFormatter, ...] = (Shouty(),)

    async def main() -> str:
        scope = soft_assertions("crosser", formatters=formatters)
        scope.__enter__()

        async def leave_it() -> str:
            try:
                scope.__exit__(None, None, None)
            except RuntimeError as refused:
                return str(refused)
            return ""  # pragma: no cover -- the refusal is the assertion

        return await asyncio.create_task(leave_it())

    assert "different thread or task" in asyncio.run(main())
    assert _active_collector() is None


def test_a_foreign_scope_leaves_the_routing_of_the_context_refusing_it_alone() -> None:
    """The refusal must not become the leak in the other direction.

    Switching the routing off here would end a scope this one never opened --
    the live block below is somebody else's, and it goes on collecting.
    """

    async def main() -> list[str]:
        stray = soft_assertions("stray")

        async def open_it() -> None:
            stray.__enter__()

        await asyncio.create_task(open_it())
        with soft_assertions("live") as live:
            with pytest.raises(RuntimeError, match="different thread or task"):
                stray.__exit__(None, None, None)
            balance = 1
            expect(balance).is_equal_to(9)
            return live.discard()

    assert asyncio.run(main()) == ["Expected live/balance to equal 9, but was 1."]
    assert _active_collector() is None


def test_a_misuse_is_never_reported_over_an_exception_already_in_flight() -> None:
    """The routing is repaired either way; the *report* waits.

    ``__exit__`` sees the exception that is unwinding the block. Raising a
    complaint about the scope there would replace the error the reader needs with
    a note about the plumbing -- and during garbage collection, where a
    ``GeneratorExit`` arrives, it would surface at a point in the program that has
    nothing to do with it.
    """
    scope = soft_assertions("never opened")
    scope.__exit__(ValueError, ValueError("boom"), None)  # the misuse is swallowed
    with pytest.raises(RuntimeError, match="not open"):
        scope.__exit__(None, None, None)  # and reported when nothing is in flight
    assert _active_collector() is None


# ---------------------------------------------------------------------------
# An error inside the block: neither buried nor thrown away
# ---------------------------------------------------------------------------
def test_an_error_inside_the_block_still_propagates_unchanged() -> None:
    """One half of the bargain, pinned so it cannot be traded away for the other.

    A real error is the more urgent signal, so the scope does not replace it with
    an aggregate of the failures collected before it. Whatever the block raised
    is what leaves the block.
    """
    with pytest.raises(ValueError, match="the fixture blew up") as caught, soft_assertions():
        expect(1).is_equal_to(2)
        message = "the fixture blew up"
        raise ValueError(message)
    assert type(caught.value) is ValueError
    assert caught.value.__cause__ is None


def test_the_failures_collected_before_an_error_arrive_as_notes() -> None:
    """The other half. Silence here is how a block that found several reports none.

    The scope exists to report every failure. An exception cutting the block short
    must not take them with it, or the reader is shown one unrelated error and no
    sign that assertions had already failed before it.

    PEP 678 notes are exactly this: attached under the exception the reader is
    already being shown, changing nothing about which one propagates. CPython's
    own traceback renderer prints them, and so does pytest.
    """
    with pytest.raises(ValueError, match="the fixture blew up") as caught, soft_assertions():
        expect(1).is_equal_to(2)
        expect("ada").is_equal_to("bob")
        message = "the fixture blew up"
        raise ValueError(message)

    notes = getattr(caught.value, "__notes__", [])
    assert notes[0] == "2 assertions had already failed in this scope:"
    assert notes[1] == "  (1) Expected 1 to equal 2, but was 1."
    # The name is the source text as the caller wrote it, double quotes included.
    assert notes[2] == "  (2) Expected \"ada\" to equal 'bob', but was 'ada'."


def test_one_collected_failure_is_phrased_in_the_singular() -> None:
    """ "1 assertions" reads as a message nobody looked at."""
    with pytest.raises(RuntimeError) as caught, soft_assertions():
        expect(1).is_equal_to(2)
        message = "boom"
        raise RuntimeError(message)
    assert caught.value.__notes__[0] == "1 assertion had already failed in this scope:"


def test_a_detail_block_is_kept_with_the_failure_it_belongs_to() -> None:
    """A diff under a failure is part of that failure, and is indented under it."""
    with pytest.raises(ValueError, match="boom") as caught, soft_assertions():
        expect({"a": 1}).is_equal_to({"a": 2})
        message = "boom"
        raise ValueError(message)
    notes = caught.value.__notes__
    assert notes[1].startswith("  (1) Expected ")
    assert notes[2] == "        values differ at key 'a': 1 instead of 2"


def test_an_error_with_nothing_collected_gets_no_notes() -> None:
    """Nothing to say, so nothing is said."""
    with pytest.raises(ValueError, match="boom") as caught, soft_assertions():
        message = "boom"
        raise ValueError(message)
    assert not getattr(caught.value, "__notes__", [])


def test_an_assertion_whose_own_operator_raises_keeps_the_report() -> None:
    """An exception out of the subject's own ``__eq__`` is not the library's to keep.

    ``expect(3).is_equal_to(hostile)`` runs the caller's ``__eq__``, and a
    ``__eq__`` that raises is their bug, so it propagates -- exactly as a bare
    ``assert 3 == hostile`` would. What must not go with it is the two findings
    the block had already made.
    """

    class Hostile:  # noqa: PLW1641  (defining __eq__ without __hash__ is the point)
        __slots__ = ()

        def __eq__(self, other: object) -> bool:
            message = "eq exploded"
            raise RuntimeError(message)

    with pytest.raises(RuntimeError, match="eq exploded") as caught, soft_assertions():
        expect(1).is_equal_to(2)
        expect(3).is_equal_to(Hostile())

    assert caught.value.__notes__[0].startswith("1 assertion had already failed")


# ---------------------------------------------------------------------------
# A context that outlived the block
# ---------------------------------------------------------------------------
def test_a_task_that_outlives_the_block_raises_rather_than_reporting_nowhere() -> None:
    """The worst thing a test library can do is stop reporting without stopping.

    ``asyncio.create_task`` copies the context, and a copy holds *the same*
    collector object. Nothing can reset a ``ContextVar`` in somebody else's
    context, so a task started inside an open block and awaited after it closes
    would file its failing assertion into a list nobody will ever read, and the
    runner would print ``passed``.

    The routing in that copied context cannot be reached, but the collector itself
    can say it is closed. The failure then raises where it happens, which is loud
    and right: it is real, and there is no report left for it to join.
    """

    async def check() -> None:
        await asyncio.sleep(0)
        expect(1).is_equal_to(2)

    async def main() -> None:
        task: asyncio.Task[None] | None = None
        with contextlib.suppress(AssertionFailure), soft_assertions():
            task = asyncio.create_task(check())
        assert task is not None
        await task

    with pytest.raises(AssertionFailure, match="to equal 2, but was 1"):
        asyncio.run(main())


def test_a_thread_holding_a_copied_context_raises_too() -> None:
    """The same hole through the other door a copied context comes from."""
    outcome: list[str] = []

    def work() -> None:
        try:
            expect(1).is_equal_to(2)
        except AssertionFailure:
            outcome.append("raised")
        else:
            outcome.append("collected in silence")

    workers: list[threading.Thread] = []
    with contextlib.suppress(AssertionFailure), soft_assertions():
        captured = contextvars.copy_context()
        workers.append(threading.Thread(target=lambda: captured.run(work)))

    workers[0].start()
    workers[0].join()
    assert outcome == ["raised"]


def test_a_reopened_scope_collects_again() -> None:
    """Closing is per block, not per scope object: a scope is reusable."""
    scope = soft_assertions("re")
    with pytest.raises(AssertionFailure), scope:
        expect(1).is_equal_to(9)
    with pytest.raises(AssertionFailure, match="re/") as caught, scope:
        expect(2).is_equal_to(9)
        expect(3).is_equal_to(9)
    assert "2 assertions failed" in str(caught.value)
