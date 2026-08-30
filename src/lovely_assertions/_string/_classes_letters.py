"""Letters, digits, numerals and the mixture of them.

Four questions Python answers differently and a reader often means one of the
others: ``isdigit`` accepts a superscript two, ``isnumeric`` accepts a fraction,
and ``isdecimal`` accepts neither. Each assertion says which rule it applied.
"""

from typing import Self

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._string._faults import class_fault
from lovely_assertions._string._render import clipped

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class LetterClassAssertions(Expect[str]):
    """What the characters are."""

    __slots__ = ()

    def is_alpha(self, *, because: str = "") -> Self:
        """Assert every character is a letter (``str.isalpha``).

        Letters as Unicode understands them, so ``"héllo"`` and ``"日本語"`` pass.
        The empty string does not: ``"".isalpha()`` is ``False``, and the message
        says as much rather than leaving the reader to work out why nothing is
        not alphabetic.
        """
        subject = self._subject
        if subject.isalpha():
            return self
        return self._fail(
            f"to contain only alphabetic characters, but {class_fault(subject, str.isalpha)}",
            because,
        )

    def is_not_alpha(self, *, because: str = "") -> Self:
        """Assert the string is not made entirely of letters.

        Satisfied by the empty string, which belongs to no character class.
        """
        subject = self._subject
        if not subject.isalpha():
            return self
        return self._fail(
            f"not to contain only alphabetic characters, but {clipped(subject)} does", because
        )

    def is_digit(self, *, because: str = "") -> Self:
        r"""Assert every character is a digit (``str.isdigit``).

        Python has three overlapping tests here and they are not interchangeable.
        ``isdecimal`` is the narrowest: the characters that spell a base-ten
        number, and exactly the ones ``int()`` will read. ``isdigit`` adds the
        digit-like characters that it will not -- ``"²".isdigit()`` is ``True``
        where ``"²".isdecimal()`` is ``False``, and ``int("²")`` raises.
        :meth:`is_numeric` is wider still.

        Two of the three are exposed and this is the middle one. **If what you
        mean is "this parses as an integer", this is not that assertion**: use
        ``matches(r"\A\d+\Z")``, whose ``\d`` is the decimal set, or assert on the
        parsed value. What this one is good for is rejecting the letters and
        punctuation in a code or an id, where ``"²"`` is not the failure anybody
        is hunting.

        An empty string fails, as it does for every class here.
        """
        subject = self._subject
        if subject.isdigit():
            return self
        return self._fail(
            f"to contain only digits, but {class_fault(subject, str.isdigit)}", because
        )

    def is_not_digit(self, *, because: str = "") -> Self:
        """Assert the string is not made entirely of digits."""
        subject = self._subject
        if not subject.isdigit():
            return self
        return self._fail(f"not to contain only digits, but {clipped(subject)} does", because)

    def is_numeric(self, *, because: str = "") -> Self:
        """Assert every character is numeric (``str.isnumeric``).

        The widest of the three tests :meth:`is_digit` sets out: on top of the
        digits it takes the characters that *mean* a number without spelling one,
        so the fraction ``"½"`` and the Roman numeral ``"Ⅷ"`` pass here and fail
        there. Right when the question is "does this text denote a quantity";
        misleading when the question is "will ``int()`` read it".
        """
        subject = self._subject
        if subject.isnumeric():
            return self
        return self._fail(
            f"to contain only numeric characters, but {class_fault(subject, str.isnumeric)}",
            because,
        )

    def is_not_numeric(self, *, because: str = "") -> Self:
        """Assert the string is not made entirely of numeric characters."""
        subject = self._subject
        if not subject.isnumeric():
            return self
        return self._fail(
            f"not to contain only numeric characters, but {clipped(subject)} does", because
        )

    def is_alnum(self, *, because: str = "") -> Self:
        """Assert every character is a letter or a number (``str.isalnum``).

        The union of :meth:`is_alpha`, :meth:`is_digit` and :meth:`is_numeric`,
        so it accepts ``"½"`` as readily as ``"a"``. Note what it does *not*
        accept: the underscore, which makes a Python name non-alphanumeric.
        :meth:`is_identifier` is that test.
        """
        subject = self._subject
        if subject.isalnum():
            return self
        return self._fail(
            f"to contain only letters and numbers, but {class_fault(subject, str.isalnum)}",
            because,
        )

    def is_not_alnum(self, *, because: str = "") -> Self:
        """Assert the string is not made entirely of letters and numbers."""
        subject = self._subject
        if not subject.isalnum():
            return self
        return self._fail(
            f"not to contain only letters and numbers, but {clipped(subject)} does", because
        )
