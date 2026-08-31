"""``.which``, which on this subject is a spelling rather than a step.

Everywhere else in the library a continuation moves to a different value.
Here the exception already *is* the subject, so ``.which`` returns ``self`` --
and it exists anyway, because ``raises(ValueError).which.with_message("x")``
reads the way the assertion is meant to be read and
``raises(ValueError).with_message("x")`` reads like a claim about the call.
"""

from typing import Self

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class ContinuationAssertions[E: BaseException](Expect[E]):
    """The one continuation an exception subject offers."""

    __slots__ = ()

    @property
    # -- continuations ---------------------------------------------------------
    def which(self) -> Self:
        """The exception itself: here a spelling, not a step.

        Elsewhere ``.which`` descends into a value an assertion *found*. ``raises``
        found the exception and made it the subject already, so there is nothing
        to descend into; ``.which`` exists because
        ``raises(ValueError).which.with_message("x")`` is how the assertion reads
        aloud, and it costs a property call that returns ``self``.
        """
        return self
