"""Opening a warning capture, which is what a reader writes.

Separate from the handle it builds, for the reason the exception family separates
the two: this decides what will be captured and what will be put back, and the
handle answers what was.
"""

from typing import TYPE_CHECKING

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._warnings._caught import CaughtWarnings

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from lovely_assertions._occurrence import Occurrence
    from lovely_assertions._warnings._subject import WarnedExpect

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def expect_warns[W: Warning](
    category: type[W], /, *, occurrences: "Occurrence | None" = None, because: str = ""
) -> "AbstractContextManager[WarnedExpect[W]]":
    """Assert that the block issues a warning of ``category``; continue on the warnings.

        with expect_warns(DeprecationWarning) as warned:
            legacy()
        warned.with_message_containing("use parse_iso instead")

    The primary form, because it sits where ``pytest.warns`` sits: the code under
    test stays a statement instead of being folded into a lambda. What it does
    that ``pytest.warns`` does not is listed in the module docstring, at the top
    of this file, along with the cases where ``pytest.warns`` is the better
    answer.

    A subclass of ``category`` counts. ``expect_warns(Warning)`` is how "any
    warning at all" is spelled -- there is no default, for the reason
    ``expect_raises`` has none: an assertion whose subject is implicit is an
    assertion whose failure message has nothing to name.

    ``occurrences`` takes a count constraint -- ``occurrences=exactly(2)``,
    ``at_least(1)``, ``at_most(3)`` -- and counts only warnings of ``category``.
    Without it the assertion means "at least one".

    Inside the block there are no warnings yet, so ``warned.subject`` raises a
    ``RuntimeError`` that says so. The declared return type is a plain context
    manager over :class:`WarnedExpect`, which is what the ``as`` binding needs; the
    handle's own class is an implementation detail.
    """
    return CaughtWarnings(category, occurrences, because)
