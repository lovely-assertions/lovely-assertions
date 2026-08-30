"""The two registries, and the order they are consulted in.

Scoped formatters live in a ``ContextVar`` and global ones in a list, and that
difference is the whole design: a scope must be able to change how one block
renders without mutating anything a concurrent test can see, while a global
registration is a decision about the whole suite made once at import.

The bound on the global registry is not a performance guard. A registry that
grows without limit is a test that registers inside a loop, and the hundredth
formatter is not a hundredth opinion about rendering -- it is ninety-nine copies
of the same one, consulted in order, on every value in every failure.
"""

from contextvars import ContextVar, Token
from typing import Final

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters._protocol import ValueFormatter, check

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


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
GLOBAL: list[ValueFormatter] = []


#: Formatters belonging to the scopes open on this thread or task, innermost
#: first. A ``ContextVar`` for the reason every other piece of scoped state in the
#: package is one: it has to be isolated per thread and per asyncio task, or a
#: parallel run leaks one test's rendering into another test's message.
SCOPED: ContextVar[tuple[ValueFormatter, ...]] = ContextVar(
    "lovely_assertions.scoped_formatters", default=()
)


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
    check(formatter)
    if any(existing is formatter for existing in GLOBAL):
        message = type(formatter).__name__ + " is already registered"
        raise ValueError(message)
    if len(GLOBAL) >= _MAX_GLOBAL:
        raise ValueError(_TOO_MANY_FORMATTERS)
    GLOBAL.append(formatter)


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
        check(formatter)
    return SCOPED.set((*formatters, *SCOPED.get()))


def pop_formatters(token: FormatterToken, /) -> None:
    """Undo the :func:`push_formatters` call that returned ``token``.

    Tokens are reset innermost first, as any ``ContextVar`` token must be:
    resetting one out of order, twice, or from a different context raises
    ``ValueError``.
    """
    SCOPED.reset(token)
