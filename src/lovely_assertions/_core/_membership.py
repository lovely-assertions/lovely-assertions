"""Whether the subject is among some alternatives.

Given inline, or given as a container that answers ``__contains__`` itself. The
two read alike and fail differently, so both say which form they were asked in.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value

if TYPE_CHECKING:
    from collections.abc import Container
from lovely_assertions._core._base import ExpectBase

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
from lovely_assertions._diff import render_operand

__tracebackhide__ = hide_internal_frames


#: Guard for the variadic assertions. A call with nothing to look for either
#: passes whatever the subject is -- a test that asserts nothing -- or could never
#: pass at all. Both are bugs in the test rather than findings about the subject,
#: so they are raised as a ``ValueError``, not collected as a failure.
_NEEDS_VALUES = "at least one value to look for is required"


class MembershipAssertions[T](ExpectBase[T]):
    """The assertions of the ``membership`` seam."""

    __slots__ = ()

    def is_one_of(self, *options: object, because: str = "") -> Self:
        """Assert the subject equals one of ``options``.

        Equality decides, so the options need be neither hashable nor of one
        type. Raises :class:`ValueError` when no option is given, since a call
        with nothing to look for could never pass. Reach for :meth:`is_in` when
        the alternatives are already a container rather than a literal list.
        """
        if not options:
            raise ValueError(_NEEDS_VALUES)
        if self._subject in options:
            return self
        return self._fail(
            "to be one of ("
            + ", ".join(format_value(option) for option in options)
            + ("," if len(options) == 1 else "")
            + f"), but was {render_operand(self._subject)}",
            because,
        )

    def is_in(self, container: "Container[object]", /, *, because: str = "") -> Self:
        """Assert the subject is contained in ``container``.

        The container's ``__contains__`` decides, which is worth remembering for
        the types that answer it their own way: a ``str`` matches substrings, and
        a ``range`` answers arithmetically without materialising anything. Use
        :meth:`is_one_of` to give the alternatives inline instead.
        """
        if self._subject in container:
            return self
        return self._fail(
            f"to be in {render_operand(container)}, but was {render_operand(self._subject)}",
            because,
        )

    def is_not_in(self, container: "Container[object]", /, *, because: str = "") -> Self:
        """Assert the subject is not contained in ``container``.

        The complement of :meth:`is_in`, asking the same ``__contains__``.
        """
        if self._subject not in container:
            return self
        return self._fail(
            f"not to be in {render_operand(container)}, but was {render_operand(self._subject)}",
            because,
        )
