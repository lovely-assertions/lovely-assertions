"""Opening the block, which is the form most of this family is used in.

Separate from the handle it builds because it is what a reader writes, and
because the two answer different questions: this one decides what will be caught,
the handle answers what was.
"""

from typing import TYPE_CHECKING

from lovely_assertions._callable._block import CaughtExpect
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from lovely_assertions._callable._raised import RaisedExpect

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def expect_raises[E: BaseException](
    exception_type: type[E], /, *, because: str = ""
) -> "AbstractContextManager[RaisedExpect[E]]":
    """Assert that the block raises ``exception_type``; continue on the exception.

        with expect_raises(ValueError) as caught:
            parse("x")
        caught.with_message_containing("invalid")

    The primary form, because it sits where ``pytest.raises`` sits: the code
    under test stays a statement instead of being folded into a lambda. It
    differs from ``pytest.raises`` on the wrong-type case, which it reports as
    the assertion failure it is, with the real exception attached as the cause,
    rather than letting it pass for whatever the runner makes of it.

    Inside the block there is no exception yet, so ``caught.subject`` raises a
    ``RuntimeError`` that says so. The declared return type is a plain context
    manager over :class:`RaisedExpect`, which is what the ``as`` binding needs;
    the handle's own class is an implementation detail.
    """
    return CaughtExpect(exception_type, because)
