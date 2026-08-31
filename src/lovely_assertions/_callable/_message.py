"""What ``str(exception)`` says.

The assertion people reach for first and the one most likely to be brittle, so
the catalogue offers containment and pattern forms rather than only equality --
an exception message is prose, and pinning all of it pins the wording.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._callable._rendering import rendered
from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._text import pattern_text, regex_matcher

if TYPE_CHECKING:
    import re

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class MessageAssertions[E: BaseException](Expect[E]):
    """What ``str(exception)`` says."""

    __slots__ = ()

    def with_message(self, pattern: "str | re.Pattern[str]", /, *, because: str = "") -> Self:
        """Assert the exception's message matches the regular expression ``pattern``.

        A ``re.search``, not a full match, exactly as ``StringExpect.matches``:
        ``with_message("invalid")`` passes for ``"invalid literal for int()"``.
        Anchor the pattern yourself when the whole message is meant. The message
        is ``str(exception)``, which is what a traceback prints -- not
        ``args[0]``, which is only sometimes the same thing.
        """
        message = str(self._subject)
        if regex_matcher(pattern).search(message) is not None:
            return self
        return self._fail(
            f"to have a message matching {rendered(pattern_text(pattern))},"
            f" but the message was {rendered(message)}",
            because,
        )

    def with_message_containing(self, text: str, /, *, because: str = "") -> Self:
        """Assert the exception's message contains ``text`` -- a plain substring, no regex.

        The message is ``str(exception)``, as in :meth:`with_message`; reach for
        that one when the expectation is a regular expression rather than a
        literal fragment, and for this one when the fragment contains characters a
        pattern would give meaning to. The failure quotes the whole message it
        searched, elided if it is very long.
        """
        message = str(self._subject)
        if text in message:
            return self
        return self._fail(
            f"to have a message containing {rendered(text)},"
            f" but the message was {rendered(message)}",
            because,
        )
