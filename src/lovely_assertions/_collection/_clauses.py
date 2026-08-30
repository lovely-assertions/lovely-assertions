"""The subset of a collection a message names, and the words for it.

Failure path only. Each of these turns "the assertion said no" into "these three
items are why", which is the difference between a reader re-running the test with
a print statement and a reader fixing the bug.

Built by concatenation rather than by f-string, like everything else that a
passing assertion must not pay for.
"""

from typing import TYPE_CHECKING, Any

from lovely_assertions._collection._hashing import searchable
from lovely_assertions._collection._render import in_message_order, render_items
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._text import count_of

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def offender[T](
    items: "Collection[T]", offends: "Callable[[T], bool]", found: "tuple[int, T]", /
) -> "tuple[int, T]":
    """The item a message should name, and where it sits. Failure path only.

    The scan that decided the verdict stopped at whatever the container handed
    over first, and for a set that is an order which changes between runs. This
    re-finds the offender in the order the message will *list* the items in, so
    the item the sentence accuses is the one the reader meets first in the
    listing beside it. Over a sequence the two orders are the same, and this
    gives back exactly what the scan already found.

    ``found`` is that result, returned unchanged if the second pass disagrees:
    the test for an offence is often the caller's own predicate, which is under
    no obligation to answer the same way twice, and naming the item the scan
    stopped on beats raising out of a half-built failure message.
    """
    for index, item in enumerate(in_message_order(items)):
        if offends(item):
            return index, item
    return found


def items_outside(items: "Collection[object]", container: "Collection[object]", /) -> list[object]:
    """The items that are not in ``container``. Failure path only.

    Through :func:`searchable` for the reason :func:`none_outside` is. This one
    runs only once an assertion has already failed, so its *allocation* is free --
    but its cost is not, and it is a half a reader really does wait on: the scan
    that decided the verdict stopped at the first item outside, and this walks
    every one of them. Over two long collections that second pass is most of what
    a failing set relation takes, which is why it too goes through the hash table
    rather than falling back to a quadratic scan.
    """
    holder = searchable(items, container)
    return [item for item in items if item not in holder]


def items_inside(items: "Collection[object]", container: "Collection[object]", /) -> list[object]:
    """The items that are in ``container``. Failure path only."""
    holder = searchable(items, container)
    return [item for item in items if item in holder]


def rejected_by(items: "Collection[Any]", predicate: "Callable[[Any], bool]", /) -> list[object]:
    """Every item the predicate turned down.

    Re-runs the predicate over the whole collection, which is fine: this is the
    failure path, and the alternative -- collecting rejects as we go -- would
    make every *passing* call allocate a list it throws away.
    """
    return [item for item in items if not predicate(item)]


def accepted_by(items: "Collection[Any]", predicate: "Callable[[Any], bool]", /) -> list[object]:
    """Every item the predicate accepted. The mirror of :func:`rejected_by`."""
    return [item for item in items if predicate(item)]


def nothing_matched(items: "Collection[object]", /) -> str:
    """The ``but ...`` half of a message for a predicate not one item satisfied.

    "no item matched" is no use on a five-hundred-row collection: it does not say
    whether five hundred items were checked or none were. So this reports the
    number actually examined and shows a bounded sample of them, and treats the
    empty collection as the separate finding it is -- "checked 0 items" in front
    of ``[]`` reads like a bug in the library.
    """
    total = len(items)
    if total == 0:
        return "but it was empty"
    return "but checked " + count_of(total, "item") + " and none matched: " + render_items(items)


def and_the_others(items: "Collection[Any]", predicate: "Callable[[Any], bool]", /) -> str:
    """The ``(and so did N other items)`` tail, or ``""`` when the match was alone.

    One stray row and a systemic problem are different findings. Counting the
    rest costs a second pass over the collection, which is free here: nothing
    calls this unless an assertion has already failed.
    """
    others = sum(1 for item in items if predicate(item)) - 1
    if others <= 0:
        return ""
    return " (and so did " + count_of(others, "other item") + ")"


def describe_key(key: "Callable[[Any], object]", /) -> str:
    """Name a ``key=`` function for a failure message. Failure path only.

    ``describe_predicate`` in ``_core`` applies the same rule and would be the
    obvious call, except for its fallback: an anonymous *key* is not "the
    predicate", and a message that calls it one sends the reader looking for a
    predicate that is not in the call. The shared half is a single ``getattr``;
    the noun is the whole difference, and it is the part that gets read.
    """
    name = getattr(key, "__name__", None)
    if isinstance(name, str) and name != "<lambda>":
        return name
    return "the key"


def by_key(key: "Callable[[Any], object] | None", /) -> str:
    """The `` by <key>`` clause a keyed uniqueness failure carries, or ``""``."""
    if key is None:
        return ""
    return " by " + describe_key(key)


#: Guard for the variadic assertions. A call with nothing to look for either
#: passes whatever the subject is -- a test that asserts nothing -- or could never
#: pass at all. Both are bugs in the test rather than findings about the subject,
#: so they are raised, not reported. The variadics on
#: :class:`~lovely_assertions._string.StringExpect` raise for the same reason.
NEEDS_VALUES = "at least one value to look for is required"
