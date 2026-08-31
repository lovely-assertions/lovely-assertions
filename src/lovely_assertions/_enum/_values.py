"""What a member holds, which is not the same question as what it is.

The value is the payload -- the integer a protocol agreed on, the string in a
column -- and every assertion here compares that payload with ``==`` and nothing
else. Two members of unrelated enumerations both carrying ``1`` therefore have
the same value while staying unequal, and both answers are right: ``is_equal_to``
claims the member, these claim only what is inside it. A test that means the
enumeration to be part of the claim has ``is_equal_to`` to say so; one reading a
payload back out of a serialised form should not have to.

:meth:`EnumExpect.has_value` types its operand ``object`` because of that rather
than in spite of it. An enumeration stores whatever it likes and ``==`` accepts
whatever it is handed, so a parameter tied to the subject would turn down the
comparisons the family exists to make. What follows is that genuinely arbitrary
values reach the failure message, which is why an operand goes into one through
the bounded rendering rather than straight to ``repr``: an assertion must not
blow up inside the message reporting its own verdict.

NaN is the case worth reading before writing one of these. It is unequal to
itself, so :meth:`EnumExpect.has_value` can never match one and
:meth:`EnumExpect.does_not_have_value` always passes against one -- correct, and
unreadable from a failure that prints ``nan`` on both sides and so reads as a
bug in the library. The note that explains it is keyed on the *operand*, because
that is the side that makes the two renderings agree; a NaN held by the subject
alone leaves a message that already says something.

The name is the other half, and this file never reads it: the two families ask
about one member and share nothing but the rendering their messages are written
with.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._core import Expect
from lovely_assertions._enum._rendering import nan_value_note, rendered
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from enum import Enum

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class ValueAssertions[T: "Enum"](Expect[T]):
    """What a member holds -- never which member it is."""

    __slots__ = ()

    # -- values -------------------------------------------------------------
    def has_value(self, value: object, /, *, because: str = "") -> Self:
        """Assert the member's ``value`` equals ``value``.

        The comparison is ``==`` on the *value*, not on the member, so an
        ``IntEnum`` and a plain ``Enum`` holding ``1`` both have the value
        ``1``. A NaN value can never match, itself included, and a failure
        with ``nan`` on both sides carries a note saying why, rather than
        reading as a bug in the library.
        """
        subject = self._subject
        if subject.value == value:
            return self
        return self._fail(
            f"to have value {rendered(value)}, but {rendered(subject)} has value "
            f"{rendered(subject.value)}{nan_value_note(value)}",
            because,
        )

    def does_not_have_value(self, value: object, /, *, because: str = "") -> Self:
        """Assert the member's ``value`` differs from ``value``.

        The exact complement of :meth:`has_value`, so a NaN passes it: a NaN
        value is not equal to the NaN it was compared against.
        """
        subject = self._subject
        if subject.value != value:
            return self
        return self._fail(
            f"not to have value {rendered(value)}, but {rendered(subject)} has it", because
        )

    def has_same_value_as(self, other: "Enum", /, *, because: str = "") -> Self:
        """Assert the member's ``value`` equals ``other``'s.

        Across enumerations too, and that is the decision: ``Colour.RED`` and
        ``Priority.LOW`` both carrying ``1`` **do** have the same value, because
        the assertion is named after the values and that is what the values are.
        The two members are still not equal -- ``is_equal_to`` is false for
        them, as it should be -- and the pair of answers is not a contradiction
        but the distinction the two assertions exist to draw. Where the
        enumeration is meant to be part of the claim, ``is_equal_to`` is the one
        that says so.
        """
        subject = self._subject
        if subject.value == other.value:
            return self
        return self._fail(
            f"to have the same value as {rendered(other)}, but had value "
            f"{rendered(subject.value)} rather than {rendered(other.value)}"
            f"{nan_value_note(other.value)}",
            because,
        )
