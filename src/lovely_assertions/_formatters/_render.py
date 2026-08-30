"""Asking a formatter, without ever letting it break the message.

A formatter is somebody else's code, running inside a failure that is already
being reported. Anything it raises is caught and the value falls back to
``repr``; anything ``repr`` raises falls back again to a note naming the type.
There is no path out of here that does not return a string.

The in-progress marker is the subtler half. A formatter that renders its value by
formatting the value's own members re-enters this module, and a value that holds
itself would otherwise recurse until the stack gives out -- inside an assertion
that was only ever trying to say two numbers differ.
"""

from contextvars import ContextVar
from typing import Final, cast

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import _registry
from lovely_assertions._formatters._protocol import ValueFormatter

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Levels of nesting :func:`format_value` re-enters before it renders ``...``.
#: Recursion here runs through user code -- a container's formatter rendering its
#: items -- so the bound is what keeps a deeply nested structure from turning a
#: failure message into a stack overflow, and what keeps the message readable.
_MAX_DEPTH: Final = 4


#: Stands in for a value that is already being rendered further up the stack.
#: ``repr`` writes ``[...]`` for the same situation; this says which situation.
_CIRCULAR: Final = "<circular reference>"


#: Stands in for structure below :data:`_MAX_DEPTH`.
_ELLIPSIS: Final = "..."


#: Last resort: the value's ``repr`` raised and its type would not even give up
#: its name.
_UNRENDERABLE: Final = "<unrenderable value>"


#: Identities of the values being rendered right now, outermost first. The cycle
#: guard and the depth bound both read it; it is a ``ContextVar`` rather than a
#: module global for the same isolation reason, and immutable so that two threads
#: sharing the default share nothing that can change.
_RENDERING: ContextVar[tuple[int, ...]] = ContextVar("lovely_assertions.rendering", default=())


def format_value(value: object, /) -> str:
    """Render ``value`` for a failure message.

    **Failure path only**: it reads a ``ContextVar`` and allocates, so a passing
    assertion must never reach it.

    Scoped formatters first, innermost scope outwards, then the global ones in
    registration order, then ``repr``. First claim wins.

        >>> format_value([1, 2])
        '[1, 2]'

    Never raises, and always returns a ``str``. A formatter that throws is skipped
    as though it had declined, and a value that nothing can render -- ``repr``
    included -- is described by its type instead.

    A formatter renders a container's parts by calling back into here, so nesting
    is bounded: a value already being rendered further up the stack renders as
    ``<circular reference>``, and structure below a fixed re-entry depth renders as
    ``...``.
    """
    scoped = _registry.SCOPED.get()
    if not scoped and not _registry.GLOBAL:
        # Nothing registered anywhere, which is the state of a library nobody has
        # configured: no formatter to ask, and so no recursion to guard against.
        return _fallback(value)
    return _formatted(value, scoped)


def _formatted(value: object, scoped: tuple[ValueFormatter, ...], /) -> str:
    """:func:`format_value` once there is at least one formatter to ask.

    A formatter may render its parts through :func:`format_value` again -- that
    is how a list of orders gets the order formatter -- so the value is marked as
    in progress around the *rendering*. A structure that contains itself would
    otherwise recurse until the interpreter stopped it, in the middle of reporting
    somebody else's failure.

    The marker goes around the rendering and not around the whole loop, because
    recursion is only possible through a formatter that *claims* the value, and
    almost nothing claims almost anything. Marking every value instead would pay a
    ``ContextVar`` set and reset to guard a recursion that cannot happen. The two
    registries are walked in place rather than concatenated for the same reason:
    joining them allocates a fresh tuple for every value in every message, and
    this is the path every message in the library goes through.
    """
    active = _RENDERING.get()
    marker = id(value)
    if marker in active:
        return _CIRCULAR
    if len(active) >= _MAX_DEPTH:
        return _ELLIPSIS
    for formatter in scoped:
        rendered = _apply(formatter, value, active, marker)
        if rendered is not None:
            return rendered
    for formatter in _registry.GLOBAL:
        rendered = _apply(formatter, value, active, marker)
        if rendered is not None:
            return rendered
    return _fallback(value)


def _apply(
    formatter: ValueFormatter, value: object, active: tuple[int, ...], marker: int, /
) -> str | None:
    """Ask one formatter for a rendering; ``None`` means it did not produce one.

    A formatter that raises is treated exactly as one that declined. So is one
    that returns something other than a string: coercing it with ``str()`` would
    produce a plausible-looking rendering that is a lie, where falling through
    produces an honest ``repr``.

    The in-progress marker is set here, around the one call that can recurse.
    ``can_handle`` is outside it: a predicate that rendered the value it is being
    asked about would be a strange thing to write, and it is guarded anyway --
    a runaway raises ``RecursionError``, which this treats as a decline.
    """
    try:
        if not formatter.can_handle(value):
            return None
        token = _RENDERING.set((*active, marker))
        try:
            # Widened on purpose: the `-> str` on `format` is a promise a caller
            # can break, and this function exists for the case where it is broken.
            # Without the cast the check below reads as redundant to a type
            # checker, which is precisely the assumption being tested.
            rendered = cast("object", formatter.format(value))
        finally:
            # Restored even when a formatter blew up mid-render: a leaked marker
            # would make every later message claim a circular reference.
            _RENDERING.reset(token)
    except Exception:
        return None
    if isinstance(rendered, str):
        return rendered
    return None


def _fallback(value: object, /) -> str:
    """``repr``, and a description of the type when even that fails."""
    try:
        return repr(value)
    except Exception:
        return _unrenderable(value)


def _unrenderable(value: object, /) -> str:
    """Name a value whose ``repr`` raised.

    The second guard is not paranoia dressed up: reading ``__name__`` goes
    through the metaclass, and a class with a hostile ``__getattribute__`` makes
    even that raise. Whatever happens, this function returns a string.
    """
    try:
        return "<" + type(value).__name__ + " with an unusable __repr__>"
    except Exception:
        return _UNRENDERABLE
