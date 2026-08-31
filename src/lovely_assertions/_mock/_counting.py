"""How many times the mock was called.

Counting is the cheapest question and the one most tests actually mean, so it is
answered without touching the arguments at all. ``once`` and ``twice`` read
better than a number and are the same claim.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._mock._base import MockBase
from lovely_assertions._text import count_of

if TYPE_CHECKING:
    from lovely_assertions._occurrence import Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class CountingAssertions(MockBase):
    """How many times the mock was called."""

    __slots__ = ()

    def was_called(self, *, because: str = "") -> Self:
        """Assert the mock was called at least once."""
        if self._subject.call_args_list:
            return self
        return self._fail(f"to have been called, but {self._how_it_was_called()}", because)

    def was_not_called(self, *, because: str = "") -> Self:
        """Assert the mock was never called.

        The failure lists the calls, which is the half ``assert_not_called``
        leaves out: knowing that something was called three times is no use
        without knowing what it was called with.
        """
        if not self._subject.call_args_list:
            return self
        return self._fail(f"not to have been called, but {self._how_it_was_called()}", because)

    def was_called_once(self, *, because: str = "") -> Self:
        """Assert the mock was called exactly once, whatever the arguments."""
        if len(self._subject.call_args_list) == 1:
            return self
        return self._fail(f"to have been called once, but {self._how_it_was_called()}", because)

    def has_call_count(self, expected: "int | Occurrence", /, *, because: str = "") -> Self:
        """Assert how many times the mock was called.

        Takes a plain count or an occurrence constraint, so both of these read as
        what they mean::

            expect(fetch).has_call_count(3)
            expect(fetch).has_call_count(at_least(2))

        ``has_call_count(3)`` and ``has_call_count(exactly(3))`` are the same
        assertion and produce the same message; the constraint is what buys
        "at least", "at most" and the rest without a method each.

        The count is the mock's *own* calls. Calls that went to its children are
        recorded on the parent's ``mock_calls`` and are not counted here.
        """
        count = len(self._subject.call_args_list)
        if isinstance(expected, int):
            if count == expected:
                return self
            return self._fail(
                f"to have been called exactly {count_of(expected, 'time')},"
                f" but {self._how_it_was_called()}",
                because,
            )
        if expected.allows(count):
            return self
        return self._fail(
            f"to have been called {expected.describe()}, but {self._how_it_was_called()}",
            because,
        )
