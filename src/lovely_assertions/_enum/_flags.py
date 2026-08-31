"""Whether one member's bits are set in another, for flag enumerations only.

The question this family asks is subset containment and never equality: a
member carrying ``R | W`` has the flag ``R``, and "exactly these bits" is what
``is_equal_to`` was already for. What follows from a subset test -- the empty
flag being contained in everything, a composite operand being all-or-nothing --
is spelled out on the methods themselves, because it is read where the operand
is written and not here.

The test is next door, in :mod:`lovely_assertions._enum._membership`, with the
guard that turns a non-flag operand away and the remembered ``enum.Flag`` that
guard needs. That is also what makes this a family apart from the names and the
values: those read ``.name`` and ``.value`` off the member and never need
``enum`` itself, while a bit test cannot be written without the class. So the
one ``enum`` import this package is willing to make is reached from here and
from nowhere else in it.

The precondition is the part no signature carries. ``expect()`` dispatches on
``Enum`` -- one branch, whether or not the member is a flag -- so the subject
binds ``T`` to ``Enum``, and a mixin it inherits binds it the same way: one
bound to ``Flag`` would be rejected by the checkers for not accepting the
subject's parameter, which is the shape of the alternative where a plain member
never sees these assertions at all. It sees them, and is turned away at the
guard with a ``TypeError`` rather than a verdict nothing supports.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._core import Expect
from lovely_assertions._enum._membership import flag_is_present
from lovely_assertions._enum._rendering import rendered
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from enum import Enum

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class FlagAssertions[T: "Enum"](Expect[T]):
    """Subset containment between flag members -- not equality, and not any-of."""

    __slots__ = ()

    # -- flags (enum.Flag and enum.IntFlag only) -----------------------------
    def has_flag(self, other: T, /, *, because: str = "") -> Self:
        """Assert ``other``'s bits are all set in the subject.

        The test is ``other in subject``, which is subset containment rather
        than equality: ``Perm.R | Perm.W`` has the flag ``Perm.R``, and has
        ``Perm.R | Perm.W`` as well.

        Two consequences of that are worth knowing before they surprise
        somebody. The **empty flag is a subset of everything**, so
        ``has_flag(Perm(0))`` passes for every member including ``Perm(0)``
        itself, and asserts nothing; ``Perm(0)`` conversely has no flag but the
        empty one. And a **composite operand is all-or-nothing** --
        ``expect(Perm.R).has_flag(Perm.R | Perm.W)`` fails, because ``W`` is not
        set. "Any of these" is a different claim and gets a different spelling:
        ``satisfies_any(lambda it: it.has_flag(Perm.R), ...)``, one branch per
        flag.

        Raises ``TypeError`` when either side is not an ``enum.Flag`` member, or
        when the two belong to different enumerations. Both are caller bugs (see
        :func:`lovely_assertions._enum._membership.flag_is_present`). The
        operand is typed ``T`` -- the subject's *own* enumeration -- so the
        checkers refuse the cross-enumeration form before it can run; being a
        ``Flag`` at all is the half no signature can state, because ``T`` has
        already been fixed to whatever ``expect()`` was handed, and it is the
        half the guard exists for.
        """
        subject = self._subject
        if flag_is_present(subject, other):
            return self
        return self._fail(f"to have flag {rendered(other)}, but was {rendered(subject)}", because)

    def does_not_have_flag(self, other: T, /, *, because: str = "") -> Self:
        """Assert at least one of ``other``'s bits is not set in the subject.

        The exact complement of :meth:`has_flag`, and it inherits both of that
        method's edges, negated. ``does_not_have_flag(Perm(0))`` can never pass,
        the empty flag being a subset of every member. And a composite operand
        passes as soon as *one* of its bits is missing -- so
        ``expect(Perm.R).does_not_have_flag(Perm.R | Perm.W)`` **passes**, on
        the strength of the absent ``W`` alone. Where "neither of these" is
        meant, one call per flag says it.
        """
        subject = self._subject
        if not flag_is_present(subject, other):
            return self
        return self._fail(
            f"not to have flag {rendered(other)}, but {rendered(subject)} has it", because
        )
