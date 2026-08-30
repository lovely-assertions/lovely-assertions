"""Claims about every item at once.

Types, absent ``None``, and uniqueness. The last two look like predicates and are
not: ``does_not_contain_none`` is the check people forget after a filter, and
duplicates are a property of the collection rather than of any item in it.
"""

from typing import TYPE_CHECKING, Any, Self, cast

from lovely_assertions._collection._clauses import by_key, describe_key
from lovely_assertions._collection._comparison import first_repeat
from lovely_assertions._collection._element_types import ElementTypeAssertions
from lovely_assertions._collection._render import render_items
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class ScreeningAssertions[E, C: Collection[Any] = Collection[E]](ElementTypeAssertions[E, C]):
    """What every item must, or must not, be."""

    __slots__ = ()

    def contains_items_of_type(self, expected_type: type[object], /, *, because: str = "") -> Self:
        """Assert every item is an instance of ``expected_type`` -- the FluentAssertions spelling.

        An alias of :meth:`all_are_instance_of`, the way
        :meth:`contains_no_duplicates` is one of :meth:`has_unique_items`. The
        name is this library's spelling of FluentAssertions'
        ``ContainItemsAssignableTo<T>``, and that assertion is about *all* the
        items. Reading the name instead as "holds some items of that type" would
        give a call arriving from FluentAssertions a weaker meaning than the one
        it was written with, and an assertion that passes where the original
        fails is the one bug a library of assertions must not have.
        """
        return self.all_are_instance_of(expected_type, because=because)

    def does_not_contain_items_of_type(
        self, unexpected_type: type[object], /, *, because: str = ""
    ) -> Self:
        """Assert no item is an instance of ``unexpected_type``, subclasses included.

        The mirror of :meth:`contains_items_of_type`, and the negation
        FluentAssertions gives ``NotContainItemsAssignableTo<T>``: *not one* item
        may be of that type. It is not "not all of them are" -- that reading would
        pass on a collection holding a single offender, which is exactly the case
        the assertion is written to catch.

        Unlike its mirror this is a declaration of its own rather than an alias:
        there is no ``none_are_instance_of`` for it to delegate to, and inventing
        a second name for one assertion would only give the reader a choice with
        no consequence.
        """
        subject = self._subject
        for index, item in enumerate(subject):
            if isinstance(item, unexpected_type):
                # `isinstance` narrows `item` to the intersection of `E` and the
                # type asked about, which collapses to `object` while `E` is a
                # type parameter. The cast restates what the loop already knows.
                return self._fail(
                    f"not to contain any item of type {unexpected_type.__name__}, but "
                    f"{
                        self._names_type(
                            lambda v: isinstance(v, unexpected_type), (index, cast('E', item))
                        )
                    }",
                    because,
                )
        return self

    def does_not_contain_none(
        self, *, key: "Callable[[E], object] | None" = None, because: str = ""
    ) -> Self:
        """Assert no item is ``None``, or -- with ``key`` -- that no item *yields* one.

        ``key`` moves the question one level in, which is where it usually
        belongs::

            expect(rows).does_not_contain_none(key=lambda row: row.email)

        asks whether any row is missing an address, not whether the list itself
        holds a ``None`` -- a question about a list of dataclasses that could only
        ever be answered "no". The failure names the key, so the reader is not
        left wondering which of the row's fields was empty.

        Iterates rather than asking ``None in subject``: a ``bytes`` subject holds
        integers and refuses the membership test outright with ``TypeError``, and
        ``bytes`` is a collection this library dispatches to a subject of its own.
        Walking also gives the position, which the membership form could never
        report -- and it is the only form ``key`` could take at all.
        """
        subject = self._subject
        for index, item in enumerate(subject):
            if (item if key is None else key(item)) is None:
                if key is None:
                    return self._fail(
                        f"not to contain None, but found one{self._position(index)}:"
                        f" {render_items(subject)}",
                        because,
                    )
                return self._fail(
                    f"not to contain None under {describe_key(key)}, but "
                    f"{self._names(lambda v: key(v) is None, (index, item))} gave one:"
                    f" {render_items(subject)}",
                    because,
                )
        return self

    def has_unique_items(
        self, *, key: "Callable[[E], object] | None" = None, because: str = ""
    ) -> Self:
        """Assert no item appears twice, or -- with ``key`` -- no *key* does.

        Vacuous on a ``set``, which is free to say so, and a real question on
        ``dict.values()`` or on any collection built by hand.

        ``key`` is what makes it a real question on a collection of rows::

            expect(orders).has_unique_items(key=lambda order: order.id)

        Two orders with the same id are almost never the same object and almost
        always the bug being looked for, so uniqueness of the whole row would
        report nothing. The failure names **the key's result** -- the id that came
        round twice -- because that is the value the assertion was about; the
        whole row would bury it.
        """
        subject = self._subject
        repeat = first_repeat(subject, key)
        if repeat is None:
            return self
        value, index = repeat
        return self._fail(
            f"to have unique items{by_key(key)}, but {format_value(value)}"
            f" appeared again{self._position(index)}: {render_items(subject)}",
            because,
        )

    def contains_no_duplicates(
        self, *, key: "Callable[[E], object] | None" = None, because: str = ""
    ) -> Self:
        """Assert no item appears twice -- the FluentAssertions spelling.

        An alias of :meth:`has_unique_items`, ``key`` included. Both names ship
        because each one reads naturally in a different sentence, and neither is
        worth losing.
        """
        return self.has_unique_items(key=key, because=because)
