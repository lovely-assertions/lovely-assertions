"""Assertions for ``bool``.

The shortest catalogue in the library, and the only one where the value in a
failure message tells the reader nothing new: there are two of them, and the
assertion already named the one it wanted. So the effort goes elsewhere.
``implies`` can fail exactly one way -- the subject held and the consequent did
not -- and its message spells both sides out rather than leaving the reader to
recall the truth table.

The four value checks are identity, not truthiness: ``is_true`` asks for ``True``
itself, never for something merely truthy. ``expect()`` routes only an exact
``bool`` here, so the distinction stays invisible in normal use; it surfaces when
a subject is built by hand around a ``1`` or a NumPy scalar, and there the strict
reading reports the bug instead of hiding it. ``implies`` is the one method that
must read the subject for *truth* rather than for identity -- an implication is
defined over truth values -- so it reports the value it actually saw instead of
asserting that it was ``True``.
"""

from typing import Self

from lovely_assertions import _engine
from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["BoolExpect"]


class BoolExpect(Expect[bool]):
    """The subject ``expect()`` hands back for a ``bool``.

    Adds the two value checks, their negations and :meth:`implies` to the generic
    catalogue; ``is_equal_to``, ``is_not_equal_to`` and the rest are inherited
    from :class:`Expect`. Every method returns the subject, so calls chain.
    """

    __slots__ = ()

    # -- the two values ----------------------------------------------------
    def is_true(self, *, because: str = "") -> Self:
        """Assert the subject is ``True``.

        Identity, not truthiness: a subject that is merely truthy -- a ``1``, a
        non-empty string, a NumPy scalar -- fails, and the failure prints what was
        actually there. Returns the subject, so the call chains. For a plain
        ``bool`` this and :meth:`is_not_false` make the same claim; reach for this
        one to state what the value is.
        """
        if self._subject is True:
            return self
        return self._fail(f"to be True, but was {_engine.render_operand(self._subject)}", because)

    def is_false(self, *, because: str = "") -> Self:
        """Assert the subject is ``False``.

        Identity, not falsiness: a ``0``, a ``None`` or an empty container -- which
        reaches here only through a hand-built subject -- fails rather than passing
        quietly. Returns the subject, so the call chains. For a plain ``bool`` this
        and :meth:`is_not_true` make the same claim; reach for this one to state
        what the value is.
        """
        if self._subject is False:
            return self
        return self._fail(f"to be False, but was {_engine.render_operand(self._subject)}", because)

    def is_not_true(self, *, because: str = "") -> Self:
        """Assert the subject is not ``True``.

        For a plain ``bool`` this is :meth:`is_false` wearing another name, and
        both are kept because they read differently at the call site: one states
        what the value is, the other what it must not have become -- the shape a
        "the flag was never set" check wants. It is also where FluentAssertions'
        ``NotBeTrue`` lands, where the distinction is real because a nullable
        ``bool?`` can be neither. A Python ``bool | None`` falls back to the
        generic subject rather than reaching this class, so that case does not
        survive the trip -- but the name it is looked up under does. Returns the
        subject, so the call chains.
        """
        if self._subject is not True:
            return self
        return self._fail("not to be True, but it was", because)

    def is_not_false(self, *, because: str = "") -> Self:
        """Assert the subject is not ``False``.

        The mirror of :meth:`is_not_true`. For a plain ``bool`` it makes the same
        claim as :meth:`is_true`, under a name that reads as "it must not have been
        switched off". Returns the subject, so the call chains.
        """
        if self._subject is not False:
            return self
        return self._fail("not to be False, but it was", because)

    # -- logic -------------------------------------------------------------
    def implies(self, consequent: bool, /, *, because: str = "") -> Self:
        """Assert the material implication ``subject -> consequent``.

        It holds unless the subject is true and ``consequent`` is not, so three
        of the four rows pass -- including both rows where the subject is false,
        which is the part that surprises people reading a failure.

        ``consequent`` is a value, not a callable: it is evaluated by the caller
        before the assertion runs, so this asserts a relationship between two
        booleans already in hand rather than deferring one of them.

        Both sides are reported as they were found. The failing row is always
        "the subject held", but *what* held is worth printing: a subject that
        reached here as a ``1`` or a ``"yes"`` is a finding, and a message that
        answered ``True`` for all three would hide it.

        This is the one method here that reads the subject for truth rather than
        for identity, since an implication is defined over truth values. Returns
        the subject, so the call chains.
        """
        if not self._subject or consequent:
            return self
        return self._fail(
            f"to imply the consequent, but was {_engine.render_operand(self._subject)} "
            f"while the consequent was {_engine.render_operand(consequent)}",
            because,
        )
