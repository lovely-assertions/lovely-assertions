"""The mock subject, assembled from one seam per question asked of a mock.

How often it was called, with what, the recorded calls as a subject of their own,
and the internals a reader sometimes has to reach for. Four questions, and the
order is the order people ask them in.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._mock._arguments import ArgumentAssertions
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
