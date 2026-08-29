"""How a value is rendered inside a failure message.

``repr`` is the right default and a poor one for domain objects: a message that
reads ``<myapp.orders.Order object at 0x10f3a2d90>`` gives the reader a memory
address in place of the thing they are trying to understand. FluentAssertions
answers that with registerable formatters, and this is the port.

Two registries, consulted in one order. **Scoped** formatters come first,
innermost scope outwards; then the **global** ones, in registration order; then
``repr``. The first formatter whose ``can_handle`` claims the value wins. Scoped
goes in front because that is the entire point of scoping: a block that needs a
different rendering must be able to get one without mutating configuration every
other test shares.

Three rules shape everything here.

**Nothing runs for a passing assertion.** :func:`format_value` is called from a
failure branch and from nowhere else, so it may read a ``ContextVar``, allocate
and format freely -- and a passing assertion pays for none of it.

**It never raises.** Formatters are user code, and user code has bugs. One that
throws is skipped exactly as if it had declined; a value nothing claims falls
back to ``repr``; a value whose ``repr`` also throws is named by its type.
Turning somebody's failing test into an error raised inside the assertion
library is the worst outcome available, and every rendering helper in the
library takes the same line.

**It formats with concatenation, never f-strings.** An f-string is evaluated
where it is written, so the library confines them to arguments of ``_fail`` --
the one call reached only once a failure is certain -- and a module with no
``_fail`` in it therefore has no f-strings at all. This is one of those modules;
``_diff.py`` is another.
"""

from collections.abc import Iterable, Sized
from contextvars import ContextVar, Token
from typing import Final, Protocol, cast, runtime_checkable

from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = [
    "FormatterToken",
    "IterableFormatter",
    "ObjectFormatter",
    "ValueFormatter",
    "format_value",
    "pop_formatters",
    "push_formatters",
    "register_formatter",
]

#: Items an :class:`IterableFormatter` shows before it truncates. Deliberately the
#: same as the default ``FormattingOptions.max_items``: two different caps on two
#: messages about the same collection would only make the reader wonder which one
#: was lying.
_MAX_ITEMS: Final = 10

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

#: Stands in for an attribute that is missing, or whose property raised.
_UNREADABLE: Final = "<unreadable>"

#: Last resort: the value's ``repr`` raised and its type would not even give up
#: its name.
_UNRENDERABLE: Final = "<unrenderable value>"


@runtime_checkable
class ValueFormatter(Protocol):
    """Renders a value into the text of a failure message.

    Structural, so nothing has to inherit from it: an object with these two
    methods is a formatter. ``can_handle`` decides, ``format`` renders, and
    neither is asked anything on the happy path.
    """

    __slots__ = ()

    def can_handle(self, value: object, /) -> bool:
        """Whether this formatter claims ``value``."""
        ...

    def format(self, value: object, /) -> str:
        """Render ``value`` for a failure message."""
        ...


#: The handle :func:`push_formatters` returns and :func:`pop_formatters` takes.
#: Named so that a caller holding one -- ``SoftScope`` -- can annotate its field
#: without importing ``contextvars`` or knowing what is in the ``ContextVar``.
type FormatterToken = Token[tuple[ValueFormatter, ...]]

#: Global formatters the registry will hold before it refuses more.
#:
#: This is the one piece of state in the package an ordinary public call can grow
#: without bound, and the growth is not free: every registration lengthens the
#: list :func:`format_value` walks for *every value in every failure message*, and
#: keeps the formatter and whatever it closes over alive for the process.
#:
#: :func:`register_formatter` already refuses the same formatter *object* twice,
#: which catches a module imported twice. It cannot catch a fixture that builds a
#: fresh ``ObjectFormatter(Order, "id")`` per test, because two instances
#: configured alike are genuinely two objects -- and that is the shape worth a
#: hard cap. The cap sits far past any real configuration, so reaching it means
#: registration is running per test rather than once, and the error says so.
_MAX_GLOBAL: Final = 64

_TOO_MANY_FORMATTERS: Final = (
    "more than 64 global formatters are registered, which means registration is "
    "running per test rather than once at import. Every one of them is asked about "
    "every value in every failure message, and none of them is ever released. "
    "Register at import -- in a conftest module body -- or use `formatting()` / "
    "`soft_assertions(formatters=...)` for a rendering that belongs to one block"
)

#: Globally registered formatters, in registration order. Appended to by
#: :func:`register_formatter` and never otherwise mutated; meant to be written
#: once, at import, rather than edited per test.
_GLOBAL: list[ValueFormatter] = []

#: Formatters belonging to the scopes open on this thread or task, innermost
#: first. A ``ContextVar`` for the reason every other piece of scoped state in the
#: package is one: it has to be isolated per thread and per asyncio task, or a
#: parallel run leaks one test's rendering into another test's message.
_SCOPED: ContextVar[tuple[ValueFormatter, ...]] = ContextVar(
    "lovely_assertions.scoped_formatters", default=()
)

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
    scoped = _SCOPED.get()
    if not scoped and not _GLOBAL:
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
    for formatter in _GLOBAL:
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


def register_formatter(formatter: ValueFormatter, /) -> None:
    """Register ``formatter`` for every failure message from here on.

        >>> register_formatter(ObjectFormatter(Order, "id", "total"))  # doctest: +SKIP

    Consulted after any scoped formatter and before ``repr``, in registration
    order, so **the first registration wins and a later one does not displace
    it**. Overriding a rendering is what the scoped registry is for; a global
    registration that quietly took precedence over an earlier one would make a
    message depend on which module happened to be imported first.

    Write once, at import -- in a ``conftest`` module body -- and never per test.
    Global assertion state that each test edits stops being safe the moment the
    suite runs in parallel, which is also why the number of global registrations
    is capped rather than unbounded.

    Raises ``ValueError`` for the *same formatter object* registered twice -- the
    only way that happens is configuration running per test rather than once -- and
    again once the cap is reached. Two different instances of one class are not a
    duplicate: ``ObjectFormatter(Order, "id")`` and ``ObjectFormatter(Customer,
    "name")`` are two formatters. That is why the check is on identity, where
    ``register`` refuses a repeated *type*: there the type is the lookup key, and
    here nothing is -- a formatter claims values by predicate.

    Raises ``TypeError`` for an object that is not a formatter. The check has to
    happen here: :func:`format_value` treats a broken formatter as one that
    declined, so a misspelled method would otherwise never be reported at all --
    the messages would simply, silently, stay as they were.
    """
    _check(formatter)
    if any(existing is formatter for existing in _GLOBAL):
        message = type(formatter).__name__ + " is already registered"
        raise ValueError(message)
    if len(_GLOBAL) >= _MAX_GLOBAL:
        raise ValueError(_TOO_MANY_FORMATTERS)
    _GLOBAL.append(formatter)


def push_formatters(formatters: tuple[ValueFormatter, ...], /) -> FormatterToken:
    """Give ``formatters`` precedence in the current context.

    Used by :class:`SoftScope` to scope formatters to a block. They go **in front
    of** everything already in play, which is what lets a block override a global
    formatter, and what makes the innermost of two nested scopes win; within one
    call they are consulted left to right.

    The scoping is per context, not per process: one thread's or one task's
    formatters never reach another's messages. Returns the token that undoes the
    push, so pair every call with :func:`pop_formatters` on it, in a ``finally``.

    Raises ``TypeError`` if any member is not a formatter. Every member is checked
    before any of them is installed, so a bad argument cannot leave half a scope
    behind.
    """
    for formatter in formatters:
        _check(formatter)
    return _SCOPED.set((*formatters, *_SCOPED.get()))


def pop_formatters(token: FormatterToken, /) -> None:
    """Undo the :func:`push_formatters` call that returned ``token``.

    Tokens are reset innermost first, as any ``ContextVar`` token must be:
    resetting one out of order, twice, or from a different context raises
    ``ValueError``.
    """
    _SCOPED.reset(token)


def _check(formatter: object, /) -> None:
    """Refuse an object that cannot work as a formatter.

    Takes ``object`` rather than ``ValueFormatter`` so the check means something:
    against the declared type it would be a tautology, and the callers are
    exactly where a caller's declaration might be wrong.

    ``isinstance`` against a protocol asks only whether the two *names* exist, so
    it accepts ``can_handle = True``. Callability is checked as well, because the
    consequence of letting that through is invisible: the ``TypeError`` from
    calling a bool would reach :func:`_apply`, which reads it as a decline, and
    the formatter would then silently render nothing for the life of the process.
    """
    if isinstance(formatter, ValueFormatter) and _callable_members(formatter):
        return
    message = (
        type(formatter).__name__
        + " is not a value formatter: it needs can_handle(value) and format(value)"
    )
    raise TypeError(message)


def _callable_members(formatter: object, /) -> bool:
    """Whether both formatter members are callable, not merely present."""
    return callable(getattr(formatter, "can_handle", None)) and callable(
        getattr(formatter, "format", None)
    )


def _check_class(candidate: object, owner: str, /) -> None:
    """Refuse something ``isinstance`` could not use as a class.

    Same reasoning as :func:`_check`, one level down. ``isinstance(value, "list")``
    raises ``TypeError``, :func:`_apply` reads that as a decline, and a formatter
    built on a string instead of a class then turns down every value there is
    without ever saying why. Worse, it is data-dependent -- ``isinstance`` walks a
    tuple left to right, so ``IterableFormatter(list, "tuple")`` works until the
    day it is handed something that is not a list. A mistake whose only symptom is
    *messages that did not change* has to be reported where it was made.
    """
    if isinstance(candidate, type):
        return
    message = owner + " needs a class to claim, not " + type(candidate).__name__
    raise TypeError(message)


def _check_name(candidate: object, /) -> None:
    """Refuse an attribute name that is not a string, for the reason above."""
    if isinstance(candidate, str):
        return
    message = "ObjectFormatter needs attribute names, not " + type(candidate).__name__
    raise TypeError(message)


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
            _check_class(claimed, "IterableFormatter")
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
        _check_class(subject_type, "ObjectFormatter")
        for name in attributes:
            _check_name(name)
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
