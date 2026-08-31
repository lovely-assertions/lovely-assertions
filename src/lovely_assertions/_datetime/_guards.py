"""Comparisons Python refuses, and claims no moment could satisfy.

Two kinds of caller mistake, kept apart because they fail differently. Comparing
an aware moment with a naive one raises inside CPython with a message that names
neither side; re-raised here it says which is which. A range whose end precedes
its start, or a month of 13, is a claim about nothing -- raised where it was
written rather than reported as though the subject were at fault.

Neither is a failed assertion, and reporting one as though it were would send a
reader looking at the value instead of at the line they wrote.
"""

from typing import TYPE_CHECKING, NoReturn

from lovely_assertions._datetime._render import awareness, kind_name, rendered, with_article
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from datetime import timedelta

    from lovely_assertions._ordered import Ordered

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Appended when the two sides of a refused comparison are a ``date`` and a
#: ``datetime``. Without it the reader is left wondering why the checker let the
#: call through -- and the answer is that no checker could have.
_LISKOV_NOTE = "; datetime subclasses date, so no type checker can refuse the mix"


def reject_incomparable(left: object, right: object, error: TypeError, /) -> NoReturn:
    """Re-raise a comparison CPython refused, saying why. Error path only.

    Two causes are recognised, and both name which side is which and what it
    was, because "can't compare offset-naive and offset-aware datetimes" tells a
    reader everything except the thing they need. Anything else propagates
    unchanged: a ``TypeError`` from a user's own comparison is not this module's
    to reinterpret.
    """
    left_kind = kind_name(left)
    right_kind = kind_name(right)
    if left_kind != right_kind:
        note = _LISKOV_NOTE if {left_kind, right_kind} == {"date", "datetime"} else ""
        raise TypeError(
            "can't compare "
            + with_article(left_kind)
            + " with "
            + with_article(right_kind)
            + ": "
            + rendered(left)
            + " is "
            + with_article(left_kind)
            + " and "
            + rendered(right)
            + " is "
            + with_article(right_kind)
            + note
        ) from error
    left_zone = awareness(left)
    right_zone = awareness(right)
    if left_zone is not None and right_zone is not None and left_zone != right_zone:
        raise TypeError(
            "can't compare a timezone-aware "
            + left_kind
            + " with a naive one: "
            + rendered(left)
            + " is "
            + left_zone
            + " and "
            + rendered(right)
            + " is "
            + right_zone
            + "; give both a timezone, or neither"
        ) from error
    raise error


def offending_bound(subject: object, low: "Ordered", high: "Ordered", /) -> "Ordered":
    """Which of a range's two bounds the comparison refused. Error path only.

    ``low <= subject <= high`` reports one ``TypeError`` for two comparisons, and
    a message that named the wrong bound would send the reader to the wrong line.
    """
    try:
        _ = low <= subject
    except TypeError:
        return low
    return high


def reject_unusable_range(low: "Ordered", high: "Ordered", /) -> None:
    """Raise for bounds that describe no range at all -- ``_ordered``'s rule.

    Checked before the subject is looked at, on purpose: bounds no value could
    satisfy are a bug in the test, and a subject that happened to fail would hide
    it behind a message blaming the value. Two bounds that cannot be compared
    with each other -- one naive and one aware, say -- are the same kind of
    mistake and are reported the same way.
    """
    try:
        inverted = low > high
    except TypeError as error:
        reject_incomparable(low, high, error)
    if inverted:
        raise ValueError(
            "range is inverted: low " + rendered(low) + " exceeds high " + rendered(high)
        )


def reject_impossible_component(label: str, value: int, bounds: tuple[int, int], /) -> None:
    """Raise ``ValueError`` for a calendar component no date could carry.

    ``has_month(13)`` is not a claim a subject can disprove; it is a claim the
    calendar has no room for, so it is a bug in the test rather than a finding --
    the same line ``reject_unusable_range`` takes on an inverted range. Note
    where the line falls: ``has_day(31)`` on a February date is a perfectly
    possible claim that simply fails, and is left alone.
    """
    low, high = bounds
    if low <= value <= high:
        return
    raise ValueError(
        "there is no "
        + label
        + " "
        + str(value)
        + ": it must be between "
        + str(low)
        + " and "
        + str(high)
    )


def reject_negative_span(label: str, span: "timedelta", /) -> None:
    """Raise ``ValueError`` for a tolerance no pair of values could satisfy.

    A negative tolerance describes an empty range, so it is a caller bug rather
    than a failure; zero describes exactly one acceptable value and is kept.

    The sign is read from ``days`` rather than by comparing against a zero
    ``timedelta``, because there is no zero ``timedelta`` to compare against
    without importing the module this one refuses to import. It is exact rather
    than a trick: a ``timedelta`` normalises to ``0 <= seconds < 86400`` and
    ``0 <= microseconds < 1000000``, so the whole duration is negative exactly
    when ``days`` is.
    """
    if span.days < 0:
        raise ValueError(label + " must not be negative, got " + rendered(span))
