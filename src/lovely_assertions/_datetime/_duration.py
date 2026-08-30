"""A length of time, which is not a moment and does not compare like one.

Its own subject rather than a numeric one, because the vocabulary is different:
a duration is longer or shorter, not greater or less, and a failure that says
"greater than 0:05:00" is a failure the reader has to translate.

Signed throughout. A negative duration is a real value with a real meaning, and
the assertions that would be nonsense on one say so rather than answering.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._core import Expect
from lovely_assertions._datetime._guards import reject_negative_span, reject_unusable_range
from lovely_assertions._datetime._lazy import TimeDeltaValue
from lovely_assertions._datetime._render import rendered
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from datetime import timedelta

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class TimeDeltaExpect(Expect[TimeDeltaValue]):
    """Assertions for a duration.

    A duration is signed, so it keeps ``is_positive`` and its neighbours where a
    date cannot have them, and takes duration vocabulary -- ``is_longer_than``
    rather than ``is_greater_than`` -- for the same reason a date takes
    ``is_before``.

    "Longer" and "shorter" are the *signed* comparisons, not comparisons of
    magnitude: ``timedelta(days=-2)`` is shorter than ``timedelta(0)``, which is
    what ``<`` says and what a duration that can run backwards has to mean.
    ``expect(abs(span))`` is how to ask about magnitude.
    """

    __slots__ = ()

    def is_longer_than(self, other: "timedelta", /, *, because: str = "") -> Self:
        """Assert the subject is a longer duration than ``other``."""
        if self._subject > other:
            return self
        return self._fail(
            f"to be longer than {rendered(other)}, but was {rendered(self._subject)}", because
        )

    def is_shorter_than(self, other: "timedelta", /, *, because: str = "") -> Self:
        """Assert the subject is a shorter duration than ``other``."""
        if self._subject < other:
            return self
        return self._fail(
            f"to be shorter than {rendered(other)}, but was {rendered(self._subject)}", because
        )

    def is_at_least(self, other: "timedelta", /, *, because: str = "") -> Self:
        """Assert the subject is ``other`` or longer."""
        if self._subject >= other:
            return self
        return self._fail(
            f"to be at least {rendered(other)}, but was {rendered(self._subject)}", because
        )

    def is_at_most(self, other: "timedelta", /, *, because: str = "") -> Self:
        """Assert the subject is ``other`` or shorter."""
        if self._subject <= other:
            return self
        return self._fail(
            f"to be at most {rendered(other)}, but was {rendered(self._subject)}", because
        )

    def is_between(self, low: "timedelta", high: "timedelta", /, *, because: str = "") -> Self:
        """Assert ``low <= subject <= high``, both bounds included.

        An inverted range raises ``ValueError``: no duration could satisfy it.
        """
        reject_unusable_range(low, high)
        if low <= self._subject <= high:
            return self
        return self._fail(
            f"to be between {rendered(low)} and {rendered(high)} inclusive, "
            f"but was {rendered(self._subject)}",
            because,
        )

    def is_not_between(self, low: "timedelta", high: "timedelta", /, *, because: str = "") -> Self:
        """Assert the subject falls outside ``low..high``, bounds included."""
        reject_unusable_range(low, high)
        if not low <= self._subject <= high:
            return self
        return self._fail(
            f"not to be between {rendered(low)} and {rendered(high)} inclusive, "
            f"but was {rendered(self._subject)}",
            because,
        )

    def is_positive(self, *, because: str = "") -> Self:
        """Assert the duration runs forwards. Zero is not positive."""
        # A `timedelta` is falsy exactly when it is zero, and only `days` carries
        # the sign once it is normalised (see `reject_negative_span`). Together
        # they answer the sign question without a zero `timedelta` to ask it of.
        if self._subject and self._subject.days >= 0:
            return self
        return self._fail(f"to be a positive duration, but was {rendered(self._subject)}", because)

    def is_negative(self, *, because: str = "") -> Self:
        """Assert the duration runs backwards. Zero is not negative."""
        if self._subject.days < 0:
            return self
        return self._fail(f"to be a negative duration, but was {rendered(self._subject)}", because)

    def is_zero(self, *, because: str = "") -> Self:
        """Assert the duration is exactly zero."""
        if not self._subject:
            return self
        return self._fail(f"to be zero, but was {rendered(self._subject)}", because)

    def is_not_zero(self, *, because: str = "") -> Self:
        """Assert the duration is not zero -- :meth:`is_zero`'s complement."""
        if self._subject:
            return self
        return self._fail("not to be zero, but it was", because)

    def is_close_to(self, other: "timedelta", /, *, within: "timedelta", because: str = "") -> Self:
        """Assert the subject is no more than ``within`` away from ``other``.

        Absolute and therefore symmetric, exactly as
        :meth:`DateTimeExpect.is_close_to` is. A negative ``within`` raises
        ``ValueError``; zero means exact equality.
        """
        reject_negative_span("within", within)
        if abs(self._subject - other) <= within:
            return self
        return self._fail(
            f"to be within {rendered(within)} of {rendered(other)},"
            f" but was {rendered(self._subject)},"
            f" {rendered(abs(self._subject - other))} away",
            because,
        )

    def is_not_close_to(
        self, other: "timedelta", /, *, within: "timedelta", because: str = ""
    ) -> Self:
        """Assert the subject is more than ``within`` away from ``other``."""
        reject_negative_span("within", within)
        if abs(self._subject - other) > within:
            return self
        return self._fail(
            f"not to be within {rendered(within)} of {rendered(other)},"
            f" but was {rendered(self._subject)},"
            f" only {rendered(abs(self._subject - other))} away",
            because,
        )

    def has_total_seconds(self, expected: float, /, *, because: str = "") -> Self:
        """Assert ``subject.total_seconds()`` equals ``expected``.

        Exact float equality, as every ``has_*`` in this module is exact: it
        states a component, and a component that is nearly right is wrong.
        ``total_seconds()`` is a float, so a value that cannot be written exactly
        in binary will not compare equal to the one you typed --
        ``timedelta(seconds=0.1).total_seconds() == 0.1`` happens to hold, and
        arithmetic that produced the duration may well not. Reach for
        :meth:`is_close_to` when a tolerance is what was meant.
        """
        if self._subject.total_seconds() == expected:
            return self
        return self._fail(
            f"to have total seconds {rendered(expected)},"
            f" but had {rendered(self._subject.total_seconds())} ({rendered(self._subject)})",
            because,
        )
