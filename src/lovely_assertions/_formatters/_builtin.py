"""The two formatters the library ships, and what they are for.

Neither is registered by default. They exist because the two shapes a reader
most often wants rendered differently -- a long container, and an object whose
``repr`` is an address -- take the same two arguments every time, and writing
that pair out per project is a tax on the feature rather than a use of it.

Both are bounded by the same scope every other rendering obeys, and both name
what they left out rather than dropping it silently.
"""

from collections.abc import Iterable, Sized
from typing import Final, cast

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters._protocol import check_class, check_name
from lovely_assertions._formatters._render import format_value

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Items an :class:`IterableFormatter` shows before it truncates. Deliberately the
#: same as the default ``FormattingOptions.max_items``: two different caps on two
#: messages about the same collection would only make the reader wonder which one
#: was lying.
_MAX_ITEMS: Final = 10


#: Stands in for an attribute that is missing, or whose property raised.
_UNREADABLE: Final = "<unreadable>"


class IterableFormatter:
    """Renders an iterable as ``Type[item, item, ... (3 more)]``.

    The port of FluentAssertions' ``EnumerableValueFormatter``, and one half of
    what makes the registry worth having: a domain collection reads as its
    contents rather than as an address.

        >>> IterableFormatter(OrderBook, max_items=3)  # doctest: +SKIP

    Takes one or more types to claim, and ``max_items``, the number of items shown
    before the rendering is truncated. Raises ``ValueError`` for no types at all or
    a ``max_items`` below one, and ``TypeError`` for an argument that is not a
    class -- at construction, where the mistake is, rather than in a later message.

    It claims the types it is given, not every iterable there is. A formatter
    that claimed everything would sit in front of the whole registry, and ``repr``
    is the right rendering for a list of integers. It also declines a value of a
    claimed type that turns out not to be iterable, rather than raising and being
    caught by the safety net -- a formatter that knows it cannot help should say
    so.

    Items are rendered through :func:`format_value`, so a nested type with its own
    formatter renders through that one, and the re-entry depth bound applies.

    Truncation counts what it left out when counting is free. An iterator has no
    length, and draining it to produce a number would consume the very object the
    reader is being shown, so those say ``(more)`` without a figure.
    """

    __slots__ = ("_max_items", "_types")

    def __init__(self, *types: type, max_items: int = _MAX_ITEMS) -> None:
        if not types:
            message = "IterableFormatter needs at least one type to claim"
            raise ValueError(message)
        if max_items < 1:
            message = "max_items must be at least 1"
            raise ValueError(message)
        for claimed in types:
            check_class(claimed, "IterableFormatter")
        self._types: tuple[type, ...] = types
        self._max_items: int = max_items

    def can_handle(self, value: object, /) -> bool:
        """Whether ``value`` is one of the claimed types *and* is iterable.

        Both halves, because a claimed type that turns out not to be iterable is
        one this formatter cannot render, and saying so here is cheaper and
        clearer than raising into the registry's safety net.
        """
        return isinstance(value, self._types) and isinstance(value, Iterable)

    def format(self, value: object, /) -> str:
        """Render as ``Type[item, item, ... (3 more)]``, items through the registry."""
        shown: list[str] = []
        truncated = False
        for item in cast("Iterable[object]", value):
            if len(shown) == self._max_items:
                truncated = True
                break
            shown.append(format_value(item))
        opened = type(value).__name__ + "[" + ", ".join(shown)
        if not truncated:
            return opened + "]"
        return opened + ", ... (" + _left_out(value, self._max_items) + ")]"


def _left_out(value: object, shown: int, /) -> str:
    """How many items a truncated rendering did not show.

    The count is a suffix on a rendering that has already succeeded, so it is
    guarded separately: a ``__len__`` that throws or lies costs the reader the
    figure, never the items that came out right. Letting it escape would hand the
    whole thing to :func:`_apply`, which would throw away a perfectly good
    ``Feed[1, 2, ...`` and print an address instead.
    """
    try:
        remaining = len(value) - shown if isinstance(value, Sized) else 0
    except Exception:
        return "more"
    if remaining > 0:
        return str(remaining) + " more"
    return "more"


class ObjectFormatter:
    """Renders an object through chosen attributes: ``Order(id=7, total=42)``.

    The port of FluentAssertions' ``DefaultValueFormatter``, and the direct answer
    to ``<myapp.orders.Order object at 0x10f3a2d90>``.

        >>> ObjectFormatter(Order, "id", "total")  # doctest: +SKIP

    At least one attribute name is required, and omitting them is a ``ValueError``:
    ``ObjectFormatter(Order)`` would render ``Order()``, which is less than
    ``repr`` already gives you. A subject that is not a class, or a name that is
    not a string, is a ``TypeError``. Both are reported at construction rather than
    in every later message.

    Subclasses are claimed too, where ``register`` keys on the exact type. The two
    differ because the registries do: there the type is a dictionary key and a
    subclass may want an entirely different subject, while here the registry is an
    ordered list, so a formatter registered for the subclass simply wins -- and a
    parent's attributes are usually the right rendering for a subclass. The heading
    names the *runtime* type, so a subclass still says which one it is.

    An attribute that is missing, or whose property raises, renders as
    ``<unreadable>`` rather than sinking the whole rendering. A half-built object
    is exactly what a failing test tends to be holding, and
    ``Order(id=7, total=<unreadable>)`` says more than the address does.

    Values are rendered through :func:`format_value`, so an attribute holding
    another formatted type renders through its formatter.
    """

    __slots__ = ("_attributes", "_type")

    def __init__(self, subject_type: type, /, *attributes: str) -> None:
        if not attributes:
            message = "ObjectFormatter needs at least one attribute name to show"
            raise ValueError(message)
        check_class(subject_type, "ObjectFormatter")
        for name in attributes:
            check_name(name)
        self._type: type = subject_type
        self._attributes: tuple[str, ...] = attributes

    def can_handle(self, value: object, /) -> bool:
        """Whether ``value`` is the claimed type or a subclass of it."""
        return isinstance(value, self._type)

    def format(self, value: object, /) -> str:
        """Render as ``Type(name=value, ...)``, heading the *runtime* type."""
        parts = [name + "=" + _read(value, name) for name in self._attributes]
        return type(value).__name__ + "(" + ", ".join(parts) + ")"


def _read(value: object, name: str, /) -> str:
    """One attribute, rendered, or :data:`_UNREADABLE` if it would not come out."""
    try:
        attribute = getattr(value, name)
    except Exception:
        return _UNREADABLE
    return format_value(attribute)
