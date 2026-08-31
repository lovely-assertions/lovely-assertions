"""How a collection appears inside a failure message.

Three rules, and the third is the one people get wrong. A message shows the items
in the order the *caller* would expect to see them, not iteration order; it names
what it left out rather than dropping it; and it puts the brackets back, because
``[1, 2]`` and ``(1, 2)`` are different values and a reader comparing two lines
needs to see which is which.
"""

from typing import TYPE_CHECKING

from lovely_assertions import _engine
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting
from lovely_assertions._text import clipped

if TYPE_CHECKING:
    from collections.abc import Collection

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


# ---------------------------------------------------------------------------
# Rendering helpers -- failure path only.
#
# None of them may use an f-string: an f-string is a message, and a message is
# built in exactly one place, inside `_fail`. They concatenate and join instead,
# so that a helper reached from an argument list cannot format eagerly.
# ---------------------------------------------------------------------------
#: Brackets per container kind, so a tuple still looks like a tuple and a set
#: like a set even though the items are rendered one at a time.
_BRACKETS: dict[type[object], tuple[str, str]] = {
    list: ("[", "]"),
    tuple: ("(", ")"),
    set: ("{", "}"),
    frozenset: ("frozenset({", "})"),
}


#: How an *empty* container of each kind reads. Python renders these itself and
#: they are worth copying: a set has no empty literal, so composing the brackets
#: above would print `{}`, which is a dict.
_EMPTY_RENDERING: dict[type[object], str] = {
    list: "[]",
    tuple: "()",
    set: "set()",
    frozenset: "frozenset()",
}


def in_message_order[T](items: "Collection[T]", /) -> "Collection[T]":
    """The order a failure message reads ``items`` in. Failure path only.

    A set has no order of its own, and CPython walks one in hash order, which is
    randomised per process. Left alone, two runs of the same failing assertion
    name a different item and -- once the listing is cut to its bound -- hide a
    different part of the collection, so a reader who runs it a second time to
    look closer is shown different evidence. Sorting where there was no order to
    lose makes the message the same every time.

    A sequence keeps the order it arrived in, because there the order *is* the
    finding: which item sits where is what the message is about.
    """
    if isinstance(items, set | frozenset):
        return _engine.stable_order(list(items))
    return items


def render_items(items: "Collection[object]", /) -> str:
    """Render a collection for a failure message, truncating a long one.

    Items are rendered one at a time rather than through the collection's own
    ``repr``, because a container's ``repr`` calls each item's ``__repr__``
    directly and a registered formatter would never be consulted -- which would
    make formatters useless for exactly the case they are wanted in,
    ``expect(orders).contains(order)``. The brackets are restored from the
    container's type so the rendering still reads as what it is.

    Past ``current_formatting().max_items`` the listing is cut and says how many
    it left out. That bound is read here rather than baked in, so a
    ``formatting(max_items=...)`` block changes what every collection message in
    the library prints -- this function renders them all, the sequence subject
    included. The read is safe because nothing calls this except a message being
    built: **failure path only**, so a passing assertion never touches the
    ContextVar behind it.
    """
    total = len(items)
    if total == 0:
        return _EMPTY_RENDERING.get(type(items), "[]")
    options = current_formatting()
    limit = options.max_items
    opening, closing = _BRACKETS.get(type(items), ("[", "]"))
    shown: list[str] = []
    for item in in_message_order(items):
        if len(shown) == limit:
            break
        # Each item, not just how many of them. Bounding the count alone leaves
        # the message as large as the values in it -- ten items whose renderings
        # run to fifty thousand characters each is half a megabyte of message,
        # which is the thing this bound exists to prevent.
        shown.append(clipped(format_value(item), options.max_chars))
    body = ", ".join(shown)
    if total <= limit:
        if total == 1 and opening == "(":
            return "(" + body + ",)"
        return opening + body + closing
    return "[" + body + ", ... (" + str(total - limit) + " more)]"


def render_or_none(subject: "Collection[object] | None", /) -> str:
    """Render a collection, or ``None`` for a subject that turned out to be missing.

    Declared as an optional parameter for the reason ``is_none_or_empty`` is:
    the subject type excludes ``None``, so the comparison would be flagged as
    unreachable if it were written inside the assertion.
    """
    if subject is None:
        return "None"
    return render_items(subject)
