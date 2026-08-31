"""``bool(subject)``, and naming which kind of falsy applies.

Python has several unrelated ways to be falsy -- empty, zero, ``None``, a
``__bool__`` that says no -- and a message that only says "was falsy" leaves the
reader to work out which. Saying which one is the difference between a failure
they can act on and one they have to reproduce.
"""

from typing import Self

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
from lovely_assertions import _engine
from lovely_assertions._core._base import ExpectBase
from lovely_assertions._exceptions import hide_internal_frames

__tracebackhide__ = hide_internal_frames


def _why_falsy(value: object, /) -> str:
    """Name the *kind* of falsy. Failure path only.

    A container says it is empty, a builtin shows its value, and anything else
    names the method that said no -- because a domain type's ``repr`` is an
    address, which explains nothing.
    """
    if value is None:
        return "it is None"
    kind = type(value)
    if hasattr(kind, "__len__"):
        return "it is an empty " + kind.__name__
    if kind.__module__ == "builtins":
        return "it is " + _engine.render_operand(value)
    return kind.__name__ + ".__bool__ returned False"


class TruthinessAssertions[T](ExpectBase[T]):
    """The assertions of the ``truthiness`` seam."""

    __slots__ = ()

    def is_truthy(self, *, because: str = "") -> Self:
        """Assert ``bool(subject)`` is true.

        Worth having over ``matches(bool)`` because Python is falsy in several
        unrelated ways and which one applies is the entire content of the failure:
        ``None``, a zero, an empty container, or a ``__bool__`` that said no.
        ``matches`` could only report that a predicate returned False.
        """
        if self._subject:
            return self
        return self._fail(f"to be truthy, but {_why_falsy(self._subject)}", because)

    def is_falsy(self, *, because: str = "") -> Self:
        """Assert ``bool(subject)`` is false.

        ``None``, a zero, an empty container and a ``__bool__`` that returned
        False all pass, so this says less than the assertion for the case you
        actually mean -- :meth:`is_none` where the value should be missing, an
        emptiness assertion where it is a container. :meth:`is_truthy` is the
        complement.
        """
        if not self._subject:
            return self
        return self._fail(f"to be falsy, but was {_engine.render_operand(self._subject)}", because)
