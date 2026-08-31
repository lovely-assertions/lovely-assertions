"""What comparing two members actually means, once they have been selected.

Each option here changes the answer for a pair the selection rules have already
let through: whether a sequence's order is part of its content, what a chosen type
is compared with instead of member by member, how far down the walk goes before it
falls back to ``==``, and whether an enum member is its name or its value.

They are the settings a surprising *verdict* is explained by, where the selection
options explain a member the reader expected to be told about and was not. That is
the seam these two files are cut along.

Where a method takes an argument, a bad one is refused at the call rather than at
the first pair it would have decided. Once the walk is under way a comparator the
engine cannot use is indistinguishable from a difference in the values, and the
report would blame the graphs for a mistake in the configuration.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._equivalence._options._selection import SelectingOptions
from lovely_assertions._equivalence._validation import (
    require_callable,
    require_class,
    require_depth,
)
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Callable

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class BehaviourOptions(SelectingOptions):
    """The builder methods that decide what comparing a selected member means.

    The last link before :class:`Equivalency`, which is why the concrete class
    names one base and still inherits every option: the chain is single
    inheritance the whole way down, and each method returns ``Self`` over a copy
    of the caller's own class, so a chain that crosses both groups of methods
    still has the whole catalogue at the end of it.

    It extends :class:`SelectingOptions` rather than standing beside it because
    nothing needs the two to be independent. Neither group calls into the other,
    and stacking them keeps a single ancestry for a checker and a reader to
    follow.
    """

    __slots__ = ()

    # -- ordering -----------------------------------------------------------
    def ignoring_order(self) -> Self:
        """Compare sequences as bags: same items, any order.

            >>> equivalency().ignoring_order()
            equivalency().ignoring_order()

        Off by default, which is where this library parts company with
        FluentAssertions. C# has no cheap set literal, so ignoring order was the
        kinder default there; Python has ``set``, a ``list`` is ordered by
        definition, and a default under which ``[1, 2]`` matches ``[2, 1]``
        produces tests that pass when they should not.

        An index stops meaning anything here, so ``excluding_path("items[0]")``
        does not reach the items of a sequence whose order is ignored: there is no
        item the path names. Excluding the sequence itself still works, and so
        does ``excluding`` a field name inside the items -- both of those name
        something that survives the reordering.

        It is also the expensive option. Items that are simply equal are paired
        off by equality -- through a hash where there is one, by linear scan where
        there is not -- but whatever is left has to be matched by *comparing* each
        candidate against each remaining item, which is quadratic in full recursive
        comparisons. :data:`_MAX_MATCHING` and :data:`_MAX_SCANNING` bound the two
        halves across the whole comparison, and a comparison that exceeds either
        raises :class:`ValueError` rather than reporting a pairing it did not
        finish. Roughly: three hundred items on each side that nothing pairs by
        equality, or a few thousand unhashable ones, at which point comparing them
        in order is the cheaper question to ask.
        """
        return self._but("ignore_order", True)

    # -- semantics ----------------------------------------------------------
    def using[C](self, kind: type[C], comparator: "Callable[[C, C], bool]") -> Self:
        """Compare values of ``kind`` with ``comparator`` instead of structurally.

            >>> equivalency().using(float, close_within(0.001))
            equivalency().using(float, close_within)

        This is the vehicle for tolerance -- see :func:`close_within` -- and for
        any type whose members are not the thing being compared. The comparator is
        consulted wherever both sides of a pair are instances of ``kind``, at any
        depth.

        Registrations are consulted **last first**, so a later call narrows an
        earlier one rather than being shadowed by it: ``using(object, ...)``
        followed by ``using(float, ...)`` gives floats the second comparator and
        everything else the first.

        A comparator that raises is not a crash. The pair it could not handle is
        reported as a difference naming the exception, which is the finding: a
        comparator for ``datetime`` handed a ``date`` is a configuration mistake,
        and it should read as one.

        Returns a new configuration; this one is unchanged. A ``kind`` that is not
        a class, or a ``comparator`` that is not callable, raises
        :class:`TypeError` here rather than at the first pair it would have
        decided, where it would have looked like a difference in the values.
        """
        require_class(kind, "using")
        require_callable(comparator, "using")
        return self._but("comparators", (*self.comparators, (kind, comparator)))

    def with_max_depth(self, depth: int) -> Self:
        """Descend at most ``depth`` levels of structure.

            >>> equivalency().with_max_depth(3)
            equivalency().with_max_depth(3)

        At the bound the walk stops descending and compares with ``==`` instead,
        and says so in the message when that comparison fails. ``0`` is legal and
        means "compare the two values, do not take them apart" -- the same reading
        ``FormattingOptions.max_depth`` gives it.

        Returns a new configuration; this one is unchanged. A non-integer raises
        :class:`TypeError` and a negative depth raises :class:`ValueError`.
        """
        return self._but("max_depth", require_depth(depth))

    def comparing_enums_by_name(self) -> Self:
        """Compare two enum members by their name rather than by their value.

            >>> equivalency().comparing_enums_by_name()
            equivalency().comparing_enums_by_name()

        The case this exists for is two enums that mean the same thing and are
        numbered differently -- one from a wire protocol, one from the domain
        model. Members of *different* enum classes therefore compare equivalent
        when their names match, which is the whole point and worth knowing.

        It cuts the other way too. Two ``IntEnum`` members that share a value under
        different names are equal to Python and are not equivalent here, because
        asking for name semantics is asking for the value to stop deciding. That
        makes this and :meth:`using` -- which is only ever as strict as the
        comparator it is handed -- the two options that can be **narrower** than
        ``==``; every other one widens.
        """
        return self._but("enums_by_name", True)
