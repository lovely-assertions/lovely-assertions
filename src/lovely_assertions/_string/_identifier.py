"""Whether the string could be written as a Python name.

``str.isidentifier`` and nothing else: the question has one right answer and the
language ships it. What this adds is the character that failed and where.
"""

from typing import Self

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._string._faults import identifier_fault
from lovely_assertions._string._render import clipped

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class IdentifierAssertions(Expect[str]):
    """The language's own lexical question."""

    __slots__ = ()

    def is_identifier(self, *, because: str = "") -> Self:
        """Assert the string is a valid Python identifier (``str.isidentifier``).

        The opening character and the continuation characters obey different
        rules, and the message says which one was broken: ``"1st"`` cannot
        *start* with ``"1"``, where ``"my-var"`` has a ``"-"`` at index 2.

        It answers the language's lexical question and nothing more, so a keyword
        passes -- ``"class".isidentifier()`` is ``True``. Chain
        ``.and_.is_not_in(keyword.kwlist)`` when a keyword has to be refused too.
        """
        subject = self._subject
        if subject.isidentifier():
            return self
        return self._fail(
            f"to be a valid Python identifier, but {identifier_fault(subject)}", because
        )

    def is_not_identifier(self, *, because: str = "") -> Self:
        """Assert the string is not a valid Python identifier."""
        subject = self._subject
        if not subject.isidentifier():
            return self
        return self._fail(
            f"not to be a valid Python identifier, but {clipped(subject)} is one", because
        )
