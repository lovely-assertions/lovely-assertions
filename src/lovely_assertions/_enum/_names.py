"""The label a member carries, asked without reference to what it holds.

A member has two halves a test can name it by, and this family takes the one the
author typed: ``Colour.RED`` is named ``"RED"`` whatever sits behind it. That is
the half that survives a boundary -- a value is the wire format's choice and
changes when the wire does, while the name is the domain's word for the case --
which is why :meth:`EnumExpect.has_same_name_as` takes a member of any
enumeration rather than only of the subject's own.

The name is always the *canonical* spelling, and knowing that is what makes a
failure here readable. An alias is a second spelling of one member rather than a
member of its own, so ``Colour.CRIMSON`` written against the same value answers
to ``"RED"``, and a failure about it names ``Colour.RED`` -- the object the
assertion was actually handed. Flag members strain the idea further: a
combination carries a compound name, and the empty flag carries ``None``, which
no ``str`` argument can match.

The value is the other half, and this file never reads it. Keeping the two apart
is what lets a failure be about one thing; a name mismatch that also printed
values would leave the reader working out which half the assertion meant.
Nothing here imports ``enum`` either -- the annotation is quoted under
``TYPE_CHECKING`` and every check reads ``.name`` off the member it was given --
so only the flag family pays for the real class.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._core import Expect
from lovely_assertions._enum._rendering import rendered
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from enum import Enum

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class NameAssertions[T: "Enum"](Expect[T]):
    """Which name a member answers to -- never what it holds."""

    __slots__ = ()

    # -- names --------------------------------------------------------------
    def has_name(self, name: str, /, *, because: str = "") -> Self:
        """Assert the member is the one called ``name``."""
        subject = self._subject
        if subject.name == name:
            return self
        return self._fail(
            f"to be named {name!r}, but {rendered(subject)} is named {subject.name!r}", because
        )

    def does_not_have_name(self, name: str, /, *, because: str = "") -> Self:
        """Assert the member is not the one called ``name``.

        An alias passes for its own spelling: ``Colour.CRIMSON`` is
        ``Colour.RED``, so it *does not* have the name ``"CRIMSON"``.
        """
        subject = self._subject
        if subject.name != name:
            return self
        return self._fail(f"not to be named {name!r}, but {rendered(subject)} is", because)

    def has_same_name_as(self, other: "Enum", /, *, because: str = "") -> Self:
        """Assert the member's name equals ``other``'s.

        The operand is any enum member, deliberately: comparing two
        enumerations by name is what this assertion is *for* -- the domain's
        ``Status.ACTIVE`` against the wire protocol's ``WireStatus.ACTIVE`` --
        and requiring the same class would leave it saying only what
        ``is_equal_to`` already says. ``comparing_enums_by_name()`` on
        :meth:`~lovely_assertions.Expect.is_equivalent_to` is the same idea for
        a whole object graph.
        """
        subject = self._subject
        if subject.name == other.name:
            return self
        return self._fail(
            f"to have the same name as {rendered(other)}, "
            f"but was named {subject.name!r} rather than {other.name!r}",
            because,
        )
