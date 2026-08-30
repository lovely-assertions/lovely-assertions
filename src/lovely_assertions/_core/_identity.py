"""What ``is`` says, kept apart from what ``==`` says.

Two seams a reader confuses with each other, which is exactly why they are not
in the same file. An identity failure and an equality failure look alike in the
message and mean entirely different things about the bug.
"""

from typing import Self

from lovely_assertions._core._base import ExpectBase
from lovely_assertions._diff import render_operand
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class IdentityAssertions[T](ExpectBase[T]):
    """The assertions of the ``identity`` seam."""

    __slots__ = ()

    def is_same_as(self, expected: object, /, *, because: str = "") -> Self:
        """Assert ``subject is expected`` -- the same object, not merely an equal one.

        Use :meth:`is_equal_to` when equality is what you mean. Identity of small
        integers and short strings is an interpreter detail rather than a promise,
        so asserting it on them tests the interpreter and not the code.
        """
        if self._subject is expected:
            return self
        return self._fail(
            f"to be the same object as {render_operand(expected)},"
            f" but was {render_operand(self._subject)}",
            because,
        )

    def is_not_same_as(self, unexpected: object, /, *, because: str = "") -> Self:
        """Assert ``subject is not unexpected``.

        The complement of :meth:`is_same_as`. Two equal but distinct objects pass:
        this is about identity, so a copy is not the original.
        """
        if self._subject is not unexpected:
            return self
        return self._fail(f"not to be the same object as {render_operand(unexpected)}", because)
