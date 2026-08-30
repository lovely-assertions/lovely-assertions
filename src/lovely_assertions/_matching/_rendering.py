"""The phrase a matcher stands for, bounded and never raising.

A matcher's ``repr`` appears inside a failure message, so it has the same two
obligations every other rendering in this library has: it must say what the
matcher would accept, and it must not become the reason the message failed to
be produced. Every helper here degrades to something printable.
"""

from typing import Any, Final, cast

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._ordered import rendered

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Operands a ``repr`` shows before it truncates. The same ten as
#: ``_formatters._MAX_ITEMS`` and ``_formatting._DEFAULT_MAX_ITEMS``, deliberately:
#: a matcher's rendering sits *inside* a message those two also bound, and two
#: different caps on one line would only make the reader wonder which was lying.
#:
#: It is a constant here rather than a ``current_formatting()`` read, unlike every
#: other bound in a message. ``__repr__`` is not confined to the failure path --
#: anybody may call it, at any time, from a debugger -- and a ``ContextVar`` read
#: is precisely what this library keeps out of anything a passing run can reach.
_MAX_SHOWN: Final = 10


def type_name(kind: type[Any], /) -> str:
    """A class's name for a ``repr``, and something legible when it has none.

    ``__name__`` goes through the metaclass, and a class with a hostile
    ``__getattribute__`` makes even that raise. A ``repr`` that raises during a
    failure message costs the reader the message, so this cannot.
    """
    # Widened on purpose: `type.__name__` is declared `str`, so against that
    # declaration the check below reads as redundant -- and a metaclass is free to
    # hand back anything at all, which is the case this exists for
    # (`_formatters._apply` widens for the same reason).
    try:
        name = cast("object", kind.__name__)
    except Exception:
        return "<unnameable type>"
    return name if isinstance(name, str) else "<unnameable type>"


def predicate_name(predicate: object, /) -> str:
    """Name a predicate for a ``repr``.

    A lambda's ``__name__`` is ``<lambda>``, which tells the reader nothing they
    could act on, so it reads as "a predicate" instead -- the same choice
    ``_core.describe_predicate`` makes, spelled again here rather than imported
    because that one is failure-path machinery and a ``repr`` is not.
    """
    name = getattr(predicate, "__name__", None)
    if isinstance(name, str) and name != "<lambda>":
        return name
    return "a predicate"


def operands(values: tuple[object, ...], /) -> str:
    """Values inside a matcher's ``repr``, bounded the way every other list is.

    Rendered through ``format_value``, so a domain type with a registered
    formatter reads as itself inside a matcher exactly as it does outside one.
    """
    shown = [format_value(value) for value in values[:_MAX_SHOWN]]
    text = ", ".join(shown)
    left_out = len(values) - len(shown)
    if left_out:
        return text + ", ... (" + str(left_out) + " more)"
    return text


def tolerance_phrase(tol: "int | float | None", rel: "int | float | None", /) -> str:
    """The tolerance half of ``close_to``'s ``repr``, or nothing when it defaulted.

    A default tolerance is ``pytest.approx``'s and is not worth a reader's
    attention; one the caller typed is the whole content of the assertion, so it
    is shown in the form they wrote it rather than as the single band the two
    resolve to. ``rendered`` keeps the digits the same as the ones the numeric
    subject prints.
    """
    if tol is None and rel is None:
        return ""
    if rel is None:
        return " ± " + rendered(tol)
    if tol is None:
        return " ± " + rendered(rel) + " relative"
    return " ± " + rendered(tol) + " or " + rendered(rel) + " relative"
