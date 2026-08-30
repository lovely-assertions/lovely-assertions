"""``None``, and the narrowing primitive the library's second claim rests on.

``expect(raw).is_not_none().subject`` is a ``str`` to both checkers, not an
``object``. That is one of the three things this library claims, and it is this
one method: the wrapper handed back is the same object, so the assertion stays
free, and the static widening is sound because ``self`` really is an
``Expect[S]`` once ``None`` is excluded.
"""

from typing import TYPE_CHECKING, Self, cast

from lovely_assertions._diff import render_operand
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from lovely_assertions._core import Expect
from lovely_assertions._core._base import ExpectBase

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class NullabilityAssertions[T](ExpectBase[T]):
    """The assertions of the ``None`` seam."""

    __slots__ = ()

    def is_none(self, *, because: str = "") -> Self:
        """Assert the subject is ``None``.

        Identity against ``None``, never ``== None``, so a type with a permissive
        ``__eq__`` cannot talk its way past. :meth:`is_not_none` is the
        complement, and it narrows the static type as well.
        """
        if self._subject is None:
            return self
        return self._fail(f"to be None, but was {render_operand(self._subject)}", because)

    def is_not_none[S](
        self: "NullabilityAssertions[S | None]", *, because: str = ""
    ) -> "Expect[S]":
        """Assert the subject is not ``None``, and hand back a subject typed without it.

        This is the narrowing primitive. It returns ``self``: the wrapper it
        hands back is the same object, so the assertion stays free, and the
        static widening is sound because ``self`` really is an ``Expect[S]`` once
        ``None`` is excluded.

        The re-typing lands on the **returned** subject, not on the caller's
        variable -- a ``TypeIs`` can only narrow a function's first positional
        argument, and ``expect()`` has captured the subject inside a wrapper.
        Re-bind to use it::

            name = expect(raw).is_not_none().subject   # str, guaranteed

        Note the deliberate omission: this does *not* re-specialise to
        ``StringExpect`` and friends. It could, statically -- but a user's own
        ``class Mine(Expect[str])`` would match that overload too and be handed
        back mislabelled. A sound widening beats a convenient lie.
        """
        if self._subject is not None:
            # Sound: `None` has just been excluded, so this same object *is* an
            # `Expect[S]`. The cast states what the checker cannot derive.
            return cast("Expect[S]", self)
        return cast("Expect[S]", self._fail_narrowing("not to be None, but it was", because))
