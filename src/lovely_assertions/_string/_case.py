"""Case, and the answer the three of them share.

A string with no cased characters at all is neither upper nor lower, and saying
so is the whole difference between a useful failure and ``False``. Title case is
the fussy one: Python's rule is about runs, not words, and the failure names the
character where the run went wrong.
"""

from typing import Self

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._string._faults import (
    class_fault,
    is_uncased,
    stays_lower,
    stays_upper,
    title_fault,
)
from lovely_assertions._string._render import clipped

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class CaseAssertions(Expect[str]):
    """Upper, lower and title case."""

    __slots__ = ()

    def is_upper(self, *, because: str = "") -> Self:
        """Assert every cased character in the string is upper case.

        ``str.isupper`` is the test, so a string with no cased characters at all
        -- ``"123"``, ``""`` -- is neither upper nor lower and fails both this
        and :meth:`is_lower`. That failure gets its own message: a reader shown
        ``but was '123'`` would reasonably conclude the assertion was broken.

        Any other failure names the character that caused it and where it sits,
        the way the character-class family does. ``but 'Abc' has 'b' at index 1``
        beats ``but was 'Abc'`` on anything longer than three characters.
        """
        subject = self._subject
        if subject.isupper():
            return self
        if is_uncased(subject):
            return self._fail(
                f"to be upper case, but {clipped(subject)} has no cased characters", because
            )
        return self._fail(f"to be upper case, but {class_fault(subject, stays_upper)}", because)

    def is_not_upper(self, *, because: str = "") -> Self:
        """Assert the string is not entirely upper case."""
        subject = self._subject
        if not subject.isupper():
            return self
        return self._fail(f"not to be upper case, but was {clipped(subject)}", because)

    def is_lower(self, *, because: str = "") -> Self:
        """Assert every cased character in the string is lower case.

        The mirror of :meth:`is_upper`, uncased strings included.
        """
        subject = self._subject
        if subject.islower():
            return self
        if is_uncased(subject):
            return self._fail(
                f"to be lower case, but {clipped(subject)} has no cased characters", because
            )
        return self._fail(f"to be lower case, but {class_fault(subject, stays_lower)}", because)

    def is_not_lower(self, *, because: str = "") -> Self:
        """Assert the string is not entirely lower case."""
        subject = self._subject
        if not subject.islower():
            return self
        return self._fail(f"not to be lower case, but was {clipped(subject)}", because)

    def is_title(self, *, because: str = "") -> Self:
        """Assert the string is title case (``str.istitle``).

        Title case is a rule about words rather than about characters: an
        upper-case character may only follow an uncased one and a lower-case
        character may only follow a cased one, so ``"Hello World"`` passes while
        both ``"hello World"`` and ``"HELLO"`` fail. The message names the
        character that broke the rule and which half of it went.

        A string with no cased characters at all is not title case either -- the
        same trap :meth:`is_upper` documents, and it gets the same message.
        """
        subject = self._subject
        if subject.istitle():
            return self
        return self._fail(f"to be title case, but {title_fault(subject)}", because)

    def is_not_title(self, *, because: str = "") -> Self:
        """Assert the string is not title case.

        True of the empty string, which ``str.istitle`` rejects for want of a
        cased character.
        """
        subject = self._subject
        if not subject.istitle():
            return self
        return self._fail(f"not to be title case, but {clipped(subject)} is", because)
