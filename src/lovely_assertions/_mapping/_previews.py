"""What a mapping looks like inside a message, capped and in a stable order.

A mapping of two hundred keys cannot go in a failure message, and a mapping of
three should go in whole. Everything here is bounded by the scope the reader is
in and says what it left out.

The did-you-mean clause is the one worth having: a missing key is usually a typo,
and naming the nearest key present turns a failure into a fix.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Final

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Sized

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Stands in for "no such key", so a lookup and the miss it may report are one
#: operation rather than a ``__contains__`` followed by a ``__getitem__``.
MISSING: Final[object] = object()


def preview(values: "Collection[object]", /) -> str:
    """Render ``values`` as a list, capped at ``current_formatting().max_items``.

    Failure path only -- which is what lets the cap be read from a ``ContextVar``
    at all, since a passing assertion must not touch one. Uses concatenation
    rather than an f-string on purpose: a message is assembled in exactly one
    place, inside ``_fail``, and a helper called from an argument list would
    format eagerly, on the passing path as well as the failing one.
    """
    limit = current_formatting().max_items
    total = len(values)
    if total <= limit:
        return "[" + ", ".join(format_value(value) for value in values) + "]"
    shown: list[str] = []
    for value in values:
        if len(shown) == limit:
            break
        shown.append(format_value(value))
    return "[" + ", ".join(shown) + ", ... " + str(total - limit) + " more]"


def preview_entries[EK, EV](entries: Mapping[EK, EV], /) -> str:
    """Render ``entries`` as a mapping, capped at ``current_formatting().max_items``.

    Failure path only. ``contains_entries`` echoes what it was asked for, and a
    caller who passed a hundred pairs must not have them pasted back at them --
    unless they asked for that, which is what a ``formatting`` block is.
    """
    limit = current_formatting().max_items
    total = len(entries)
    shown: list[str] = []
    for key, value in entries.items():
        if len(shown) == limit:
            return "{" + ", ".join(shown) + ", ... " + str(total - limit) + " more}"
        shown.append(format_value(key) + ": " + format_value(value))
    return "{" + ", ".join(shown) + "}"


def entry_count(count: int, /) -> str:
    """``"1 entry"`` or ``"4 entries"``. Failure path only."""
    if count == 1:
        return "1 entry"
    return str(count) + " entries"


def did_you_mean(key: object, candidates: "Iterable[object]", /) -> str:
    """A parenthesised suggestion when a string key misses by a near-spelling.

    Returns ``""`` when nothing is close enough, and for non-string keys: a
    "did you mean" between values that were never spelled out is noise. When it
    does fire it is the single most useful thing the message can carry, which is
    why the cost of importing ``difflib`` is worth paying -- here, in the failure
    branch, and nowhere else.
    """
    if not isinstance(key, str):
        return ""
    import difflib  # noqa: PLC0415  (importing this package must not import difflib)

    names = [candidate for candidate in candidates if isinstance(candidate, str)]
    close = difflib.get_close_matches(key, names, n=1)
    if not close:
        return ""
    return " (did you mean " + repr(close[0]) + "?)"


def entry_diff[EK, EV](subject: Mapping[EK, EV], entries: Mapping[EK, EV], /) -> str:
    """Say which of ``entries`` are absent and which hold something else.

    Failure path only. The two are different bugs -- a key never written, and a
    key written with the wrong value -- so they get separate clauses instead of
    one "did not contain" the reader has to investigate.
    """
    missing: list[EK] = []
    differing: list[str] = []
    for key, value in entries.items():
        actual = subject.get(key, MISSING)
        if actual is MISSING:
            missing.append(key)
        elif not (actual is value or actual == value):
            differing.append(
                format_value(key)
                + " held "
                + format_value(actual)
                + " instead of "
                + format_value(value)
            )
    clauses: list[str] = []
    if missing:
        clauses.append("was missing " + preview(missing))
    if differing:
        limit = current_formatting().max_items
        shown = differing[:limit]
        if len(differing) > limit:
            shown.append("... " + str(len(differing) - limit) + " more")
        clauses.append(", ".join(shown))
    return " and ".join(clauses)


def render_or_none(subject: "Mapping[Any, Any] | None", /) -> str:
    """Render a mapping, or ``None`` for a subject that turned out to be missing.

    Failure path only. Declared as an optional parameter for the reason
    :func:`is_none_or_empty` is: the subject type excludes ``None``, so the
    comparison would be flagged as unreachable if it were written inline.
    """
    if subject is None:
        return "None"
    return preview_entries(subject)


def is_none_or_empty(subject: "Sized | None", /) -> bool:
    """Whether the subject is missing entirely or simply holds nothing.

    Runs on the happy path. Declared as an optional parameter so the ``None``
    branch is honest to both checkers: ``MappingExpect``'s subject type excludes
    ``None``, and a comparison against it inside the method would be flagged as
    unreachable. ``_collection`` carries the twin of this for the same reason.
    """
    return subject is None or len(subject) == 0


#: Guard for the variadic assertions. A call with nothing to look for either
#: passes whatever the subject is -- a test that asserts nothing -- or could never
#: pass at all. Both are bugs in the test rather than findings about the subject,
#: so they are raised, not reported. The variadics on
#: :class:`~lovely_assertions._string.StringExpect` raise for the same reason.
NEEDS_VALUES = "at least one value to look for is required"
