"""The mock subjects, assembled from one seam per question asked of a mock.

How often it was called, with what, the recorded calls as a subject of their own,
and the internals a reader sometimes has to reach for. Four questions, and the
order is the order people ask them in.

Two subjects rather than one, because an ``AsyncMock`` answers a question a
``Mock`` cannot. :class:`AsyncMockExpect` extends the whole call-side catalogue
with the await-side one, and a plain ``Mock`` is never handed it -- asking a
synchronous mock whether it was awaited is a question about a list it does not
keep, and offering the method anyway would be the same mistake as offering
``is_positive`` on a string.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._mock._arguments import ArgumentAssertions
from lovely_assertions._mock._awaiting import AwaitAssertions
from lovely_assertions._mock._base import MockBase
from lovely_assertions._mock._continuations import ContinuationAssertions, InternalAssertions
from lovely_assertions._mock._counting import CountingAssertions

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class MockExpect(
    CountingAssertions,
    ArgumentAssertions,
    ContinuationAssertions,
    InternalAssertions,
    MockBase,
):
    """Assertions about how a mock was called.

    The subject is a mock, and its type is ``Any``: a mock stands in for
    something, and pinning it to a class would be a claim about the thing it
    stands in for rather than about the mock. Everything on
    :class:`~lovely_assertions.Expect` still applies, so ``.subject`` hands the
    mock back and ``satisfies`` runs an inspection over it.

    The catalogue is deliberately the ``unittest.mock`` one, renamed to read as an
    expectation rather than as a command::

        assert_called()            -> was_called()
        assert_not_called()        -> was_not_called()
        assert_called_once()       -> was_called_once()
        assert_called_with(...)    -> was_called_with(...)
        assert_called_once_with()  -> was_called_once_with(...)
        assert_any_call(...)       -> was_ever_called_with(...)
        (nothing)                  -> was_never_called_with(...)
        call_count == n            -> has_call_count(n)
        assert_has_calls([...])    -> calls.contains_in_order(...)

    Two of those rows are worth a second look. ``was_never_called_with`` has no
    counterpart in ``unittest.mock`` at all, and it is the assertion a test
    actually wants when it is guarding against a call that must not happen.
    ``assert_has_calls`` is not reimplemented because :attr:`calls` already hands
    the whole ordered catalogue of
    :class:`~lovely_assertions.SequenceExpect` to the recorded calls, with
    messages that name the position where the expected order broke.
    """

    __slots__ = ()


class AsyncMockExpect(AwaitAssertions, MockExpect):
    """Assertions about how an async mock was called and awaited.

    Everything :class:`MockExpect` offers, plus the await side: ``was_awaited``,
    ``was_awaited_once_with``, ``has_await_count``, :attr:`~AwaitAssertions.awaits`
    and the rest. ``expect()`` builds this one for any mock that records awaits --
    an ``AsyncMock``, a ``Mock(spec=some_async_function)``, or the async members
    of an autospecced class -- and :class:`MockExpect` for every other mock.

    **Why the await catalogue is a separate subject rather than nine more methods
    on** :class:`MockExpect`. A synchronous ``Mock`` keeps no ``await_args_list``,
    so those nine assertions have nothing to read; a mock answers every attribute,
    though, so reading it anyway would compare against a child mock standing in
    for a list and pass. Guarding each of them at runtime would fix the passing
    and leave the catalogue advertising nine assertions the subject cannot
    answer. Splitting the subject is what makes the offer honest -- and it is the
    same rule the rest of the library follows, where a ``str`` subject has no
    ``is_positive``.

    A checker cannot see that split through ``expect()``: typeshed gives a mock an
    ``Any`` in its MRO, so a mock is statically assignable to everything and no
    overload can reach it. ``expect(fetch, as_=AsyncMockExpect)`` is the typed
    route, and it is where the distinction becomes something a checker enforces.
    """

    __slots__ = ()
