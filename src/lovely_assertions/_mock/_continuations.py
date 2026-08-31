"""The recorded calls as subjects, and the attributes a mock carries.

Handing the call list to the sequence subject rather than restating its
catalogue: a caller who wants to assert about the order of calls wants the
assertions they already know.
"""

from typing import TYPE_CHECKING, Any, Self, cast

from lovely_assertions._core import Found
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._mock._base import MockBase
from lovely_assertions._sequence import SequenceExpect

if TYPE_CHECKING:
    from collections.abc import Sequence


#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class ContinuationAssertions(MockBase):
    """The recorded calls, as subjects of their own."""

    __slots__ = ()

    @property
    def calls(self) -> "SequenceExpect[Any]":
        """The recorded calls, as a sequence subject.

            expect(fetch).calls.has_length(2)
            expect(fetch).calls.contains_in_order(call("/a"), call("/b"))

        A property rather than a method because it makes no claim and cannot
        fail: a mock that was never called has an empty list of calls, which is
        an answer rather than a failure. :meth:`last_call` is a method for the
        opposite reason.

        The elements are ``unittest.mock`` ``call`` objects, kept as they were
        recorded rather than converted into something friendlier. Three reasons.
        ``call(...)`` is the vocabulary every mock user already writes, and it
        compares the way they expect -- ``call(1) == ((1,), {})``. Its ``repr``
        is the call that produced it, so a failure message can be pasted back
        into a test. And handing back the mock's own list is what makes
        ``contains_in_order`` a better ``assert_has_calls`` rather than a second,
        subtly different one.

        A name given with ``described_as`` or ``expect(..., name=...)`` carries
        over, exactly as it does through ``extracting``.
        """
        recorded: Sequence[Any] = self._subject.call_args_list
        derived: SequenceExpect[Any] = SequenceExpect(recorded)
        return self._carrying_name(derived)

    def last_call(self, *, because: str = "") -> "Found[Self, Any]":
        """Assert the mock was called, and continue on its most recent call.

            expect(fetch).last_call().which.subject.args

        A method rather than a property, unlike :attr:`calls`: this one asserts
        something -- that there *is* a last call -- and every assertion in the
        library takes a ``because``, which a property cannot.

        ``.which`` descends into the call itself, ``.and_`` goes back to the mock.
        The found value is the recorded ``call`` object, so ``.which.subject.args``
        and ``.which.subject.kwargs`` are its two halves.
        """
        recorded: Sequence[Any] = self._subject.call_args_list
        if recorded:
            found: Any = recorded[-1]
            return Found(self, found)
        return cast(
            "Found[Self, Any]",
            self._fail_narrowing(f"to have been called, but {self._how_it_was_called()}", because),
        )


class InternalAssertions(MockBase):
    """The attributes a mock carries about itself."""

    __slots__ = ()
