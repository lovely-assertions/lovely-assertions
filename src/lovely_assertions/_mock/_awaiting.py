"""Whether the coroutines the mock handed back were ever awaited.

An ``AsyncMock`` records two things, and the test usually means the second.
*Calling* it appends to ``call_args_list`` and hands back a coroutine; *awaiting*
that coroutine is what runs the body and appends to ``await_args_list``. Code
that builds a coroutine and drops it -- a missing ``await``, a task nobody
gathered, a ``TaskGroup`` that exited before the work started -- leaves the first
list full and the second empty.

Every assertion on the call side passes in that state, here and in
``unittest.mock`` both::

    fetch = AsyncMock()
    fetch("/users")                               # no await
    expect(fetch).was_called_once_with("/users")  # passes

That is not wrong -- it *was* called -- but it is not what the test meant, and
nothing in the call-side catalogue can say so. This file is the other half: the
same questions, asked of ``await_args_list``.

**The messages carry the distinction the call side cannot.** "It was never
called" and "it was called once with ('/users') and never awaited" are two
different bugs -- a wiring mistake and a missing ``await`` -- and one of them
names the line to go and fix. ``unittest.mock`` reports both as ``Awaited 0
times``, mentioning neither that the mock was called nor what it was called
with. Telling those two apart is the whole reason this file exists.

The arguments an await was made with go through the same matching, the same
difference engine and the same notes as the call side, with ``"await"`` passed
where the call side passes ``"call"``. One wording rule, one set of helpers: an
assertion here cannot drift into describing a difference differently from its
twin next door.
"""

from typing import TYPE_CHECKING, Any, Self, cast

from lovely_assertions._core import Found
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._mock._base import MockBase
from lovely_assertions._mock._call_matching import matches_call
from lovely_assertions._mock._differences import (
    describe_call_difference,
    earlier_matches_note,
    nearest_note,
    which_matched,
)
from lovely_assertions._mock._rendering import (
    last_clause,
    numbered,
    render_call,
    render_calls,
    render_options,
    wanted,
)
from lovely_assertions._sequence import SequenceExpect
from lovely_assertions._text import count_of

if TYPE_CHECKING:
    from collections.abc import Sequence

    from lovely_assertions._occurrence import Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class AwaitAssertions(MockBase):
    """Whether the mock was awaited, and with what.

    **Every assertion here reads a length, never a truth.** ``if
    self._subject.await_args_list:`` looks equivalent and is not: point this
    subject at a synchronous mock -- which ``expect()`` never does, but
    ``as_=AsyncMockExpect`` lets a caller do -- and that attribute is a child mock
    rather than a list, so it is truthy and the assertion passes having compared
    nothing. Asking for its length instead refuses the misuse out loud, which is
    what the rest of this package exists to do about silent passes. It costs a
    real list nothing: a truth test on one calls ``__len__`` anyway.
    """

    __slots__ = ()

    def _how_it_was_awaited(self) -> str:
        """The ``but ...`` half of a message about awaits. Failure path only.

        Three states rather than the call side's two, because "never awaited" is
        where the interesting bug lives and it has two quite different causes. A
        mock that was never called at all is a wiring mistake -- the code under
        test took another branch. One that was called and not awaited is a
        missing ``await``, and the calls it *did* record are what point at the
        line to fix, so they are named rather than summarised away.

        One helper for every await-shaped failure, so the assertions in this file
        cannot drift into one account of that fact apiece. No f-string: the
        message is built inside the ``_fail`` call, so a passing assertion
        formats nothing.
        """
        awaited: Sequence[Any] = self._subject.await_args_list
        options = render_options()
        if awaited:
            return (
                "it was awaited "
                + count_of(len(awaited), "time")
                + ": "
                + render_calls(awaited, options)
            )
        recorded: Sequence[Any] = self._subject.call_args_list
        if not recorded:
            return "it was never called"
        if len(recorded) == 1:
            return (
                "it was called once with "
                + render_call(recorded[0], options)
                + " and never awaited"
            )
        return (
            "it was called "
            + count_of(len(recorded), "time")
            + " and never awaited: "
            + render_calls(recorded, options)
        )

    # -- how often it was awaited ------------------------------------------
    def was_awaited(self, *, because: str = "") -> Self:
        """Assert the mock was awaited at least once.

        The assertion ``was_called`` cannot make. A coroutine that was created
        and dropped satisfies every question about calls and none about awaits,
        which is the state this exists to catch.
        """
        if len(self._subject.await_args_list) > 0:
            return self
        return self._fail(f"to have been awaited, but {self._how_it_was_awaited()}", because)

    def was_not_awaited(self, *, because: str = "") -> Self:
        """Assert the mock was never awaited.

        Passes for a mock that was never called at all, since a coroutine that
        was never created was never awaited either. Reach for
        :meth:`~lovely_assertions.MockExpect.was_not_called` where the point is
        that the call itself must not happen; reach for this one where the call
        is allowed and the work behind it is not -- a cache hit that must not
        refetch, a dry run that must build the request and never send it.
        """
        if len(self._subject.await_args_list) == 0:
            return self
        return self._fail(f"not to have been awaited, but {self._how_it_was_awaited()}", because)

    def was_awaited_once(self, *, because: str = "") -> Self:
        """Assert the mock was awaited exactly once, whatever the arguments."""
        if len(self._subject.await_args_list) == 1:
            return self
        return self._fail(f"to have been awaited once, but {self._how_it_was_awaited()}", because)

    def has_await_count(self, expected: "int | Occurrence", /, *, because: str = "") -> Self:
        """Assert how many times the mock was awaited.

        Takes a plain count or an occurrence constraint, exactly as
        :meth:`~lovely_assertions.MockExpect.has_call_count` does::

            expect(fetch).has_await_count(3)
            expect(fetch).has_await_count(at_least(2))

        The two numbers can disagree, and that they can is the point: a mock
        called three times and awaited twice has one coroutine still sitting
        unawaited, and only this assertion sees it.
        """
        count = len(self._subject.await_args_list)
        if isinstance(expected, int):
            if count == expected:
                return self
            return self._fail(
                f"to have been awaited exactly {count_of(expected, 'time')},"
                f" but {self._how_it_was_awaited()}",
                because,
            )
        if expected.allows(count):
            return self
        return self._fail(
            f"to have been awaited {expected.describe()}, but {self._how_it_was_awaited()}",
            because,
        )

    # -- what it was awaited with ------------------------------------------
    def was_awaited_with(self, *args: object, because: str = "", **kwargs: object) -> Self:
        """Assert the **most recent** await was made with these arguments.

        The same rule :meth:`~lovely_assertions.MockExpect.was_called_with`
        follows, and the same trap: earlier awaits are not looked at. When an
        earlier one *did* match, the message names it.

        ``because`` is keyword-only and therefore shadows a keyword argument of
        the same name that the subject may itself have been awaited with; see the
        package docstring for the escape hatch, which is :attr:`awaits`.
        """
        awaited: Sequence[Any] = self._subject.await_args_list
        if awaited and matches_call(awaited[-1], args, kwargs):
            return self
        if not awaited:
            return self._fail(
                f"to have been awaited with {wanted(args, kwargs)},"
                f" but {self._how_it_was_awaited()}",
                because,
            )
        return self._fail(
            f"to have been awaited with {wanted(args, kwargs)},"
            f" but was {last_clause(len(awaited), 'awaited')}"
            f" {render_call(awaited[-1], render_options())}"
            + describe_call_difference(awaited[-1], args, kwargs)
            + earlier_matches_note(awaited, args, kwargs, "await"),
            because,
        )

    def was_awaited_once_with(self, *args: object, because: str = "", **kwargs: object) -> Self:
        """Assert the mock was awaited exactly once, and with these arguments.

        Four different bugs fail this assertion, and each gets its own message:
        it was never called, it was called and never awaited, it was awaited once
        with something else, or it was awaited more than once. The second is the
        one no call-side assertion can reach -- ``was_called_once_with`` passes
        in that state, which is the whole reason this file exists.
        """
        awaited: Sequence[Any] = self._subject.await_args_list
        if len(awaited) == 1 and matches_call(awaited[0], args, kwargs):
            return self
        if not awaited:
            return self._fail(
                f"to have been awaited once with {wanted(args, kwargs)},"
                f" but {self._how_it_was_awaited()}",
                because,
            )
        if len(awaited) == 1:
            return self._fail(
                f"to have been awaited once with {wanted(args, kwargs)},"
                f" but was awaited with {render_call(awaited[0], render_options())}"
                + describe_call_difference(awaited[0], args, kwargs),
                because,
            )
        return self._fail(
            f"to have been awaited once with {wanted(args, kwargs)},"
            f" but {self._how_it_was_awaited()}" + which_matched(awaited, args, kwargs, "await"),
            because,
        )

    def was_ever_awaited_with(self, *args: object, because: str = "", **kwargs: object) -> Self:
        """Assert some await -- any of them -- was made with these arguments.

        The assertion to reach for when the await under test is one of several
        and its position is not the point. The failure picks the nearest recorded
        await to explain, because "none of these four matched" is a fact the
        reader already had.
        """
        awaited: Sequence[Any] = self._subject.await_args_list
        for one in awaited:
            if matches_call(one, args, kwargs):
                return self
        if not awaited:
            return self._fail(
                f"to have been awaited with {wanted(args, kwargs)} at some point,"
                f" but {self._how_it_was_awaited()}",
                because,
            )
        if len(awaited) == 1:
            return self._fail(
                f"to have been awaited with {wanted(args, kwargs)} at some point,"
                f" but its only await was {render_call(awaited[0], render_options())}"
                + describe_call_difference(awaited[0], args, kwargs),
                because,
            )
        return self._fail(
            f"to have been awaited with {wanted(args, kwargs)} at some point,"
            f" but none of its {count_of(len(awaited), 'await')} was:"
            f" {render_calls(awaited, render_options())}"
            + nearest_note(awaited, args, kwargs, "await"),
            because,
        )

    def was_never_awaited_with(self, *args: object, because: str = "", **kwargs: object) -> Self:
        """Assert no await was made with these arguments.

        ``unittest.mock`` has nothing for this on either side. It is the
        assertion a test means when it guards against work that must not happen
        -- and unlike its call-side twin it stays true of code that *builds* the
        forbidden request as long as nothing ever runs it.
        """
        awaited: Sequence[Any] = self._subject.await_args_list
        for one in awaited:
            if matches_call(one, args, kwargs):
                break
        else:
            return self
        # Past the branch, so the list the message needs is built where it is
        # read. Building it first and testing it for emptiness instead would put
        # a comprehension and a list allocation on the branch that *passes*.
        matched = [index for index, one in enumerate(awaited, 1) if matches_call(one, args, kwargs)]
        options = render_options()
        return self._fail(
            f"never to have been awaited with {wanted(args, kwargs)},"
            f" but {numbered(matched, options, 'await')}"
            f" {'was' if len(matched) == 1 else 'were'}:"
            f" {render_calls(awaited, options)}",
            because,
        )

    # -- continuations over awaits -----------------------------------------
    @property
    def awaits(self) -> "SequenceExpect[Any]":
        """The recorded awaits, as a sequence subject.

            expect(fetch).awaits.has_length(2)
            expect(fetch).awaits.contains_in_order(call("/a"), call("/b"))

        A property rather than a method because it makes no claim and cannot
        fail: a mock that was never awaited has an empty list of awaits, which is
        an answer rather than a failure. The same reasoning, and the same
        vocabulary of ``call`` objects, as
        :attr:`~lovely_assertions.MockExpect.calls` -- ``unittest.mock`` records
        an await with the very same type it records a call with, so a test that
        knows one list knows the other.

        A name given with ``described_as`` or ``expect(..., name=...)`` carries
        over, exactly as it does through :attr:`~lovely_assertions.MockExpect.calls`.
        """
        awaited: Sequence[Any] = self._subject.await_args_list
        derived: SequenceExpect[Any] = SequenceExpect(awaited)
        return self._carrying_name(derived)

    def last_await(self, *, because: str = "") -> "Found[Self, Any]":
        """Assert the mock was awaited, and continue on its most recent await.

            expect(fetch).last_await().which.subject.args

        A method rather than a property, unlike :attr:`awaits`: this one asserts
        something -- that there *is* a last await -- and every assertion in the
        library takes a ``because``, which a property cannot.

        ``.which`` descends into the await itself, ``.and_`` goes back to the
        mock. The found value is the recorded ``call`` object, so
        ``.which.subject.args`` and ``.which.subject.kwargs`` are its two halves.
        """
        awaited: Sequence[Any] = self._subject.await_args_list
        if awaited:
            found: Any = awaited[-1]
            return Found(self, found)
        return cast(
            "Found[Self, Any]",
            self._fail_narrowing(
                f"to have been awaited, but {self._how_it_was_awaited()}", because
            ),
        )
