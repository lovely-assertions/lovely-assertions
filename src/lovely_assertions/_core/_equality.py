"""What the subject's own ``__eq__`` says.

The plainest assertion in the library, and the one whose failure carries the most
work: two values that are unequal have somewhere they part company, and finding
it is what separates this from ``assert a == b``.
"""

from typing import Self

from lovely_assertions._core._base import ExpectBase
from lovely_assertions._diff import describe_difference, render_operand
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class EqualityAssertions[T](ExpectBase[T]):
    """The assertions of the ``equality`` seam."""

    __slots__ = ()

    def is_equal_to(self, expected: object, /, *, because: str = "") -> Self:
        """Assert ``subject == expected``.

        The subject's own ``__eq__`` decides, with everything that implies: a NaN
        never equals itself, and a type with a lenient ``__eq__`` passes here
        where :meth:`is_equivalent_to`, which compares members rather than asking
        the type, would not.

        On failure the two reprs are followed by an account of *how* they differ --
        a unified diff for multi-line text, the first offending index for
        sequences, the keys that moved for mappings. That is the whole reason to
        prefer this over a bare ``assert a == b`` on a composite value, and it
        costs nothing until an assertion fails.
        """
        if self._subject == expected:
            return self
        return self._fail(
            f"to equal {render_operand(expected)}, but was {render_operand(self._subject)}"
            f"{describe_difference(self._subject, expected)}",
            because,
        )

    def is_not_equal_to(self, unexpected: object, /, *, because: str = "") -> Self:
        """Assert ``subject != unexpected``.

        Asks ``!=`` rather than negating ``==``, so a type that defines the two
        independently is taken at its word. The complement of :meth:`is_equal_to`,
        and it carries no difference block: there is nothing to explain about two
        values that were supposed to differ and did.
        """
        if self._subject != unexpected:
            return self
        return self._fail(f"not to equal {render_operand(unexpected)}", because)
