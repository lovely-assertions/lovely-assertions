"""How a moment, a duration and every note about one are spelled.

ISO where a reader expects ISO, and words where a number would be worse: a
duration of ``-1 day, 82800`` is what ``timedelta`` prints and not what anybody
means, so it is signed and spelled out.

Failure path only, all of it. A passing temporal assertion is a comparison
between two values that already exist.
"""

from typing import TYPE_CHECKING, cast

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value

if TYPE_CHECKING:
    from datetime import date, datetime, timedelta, tzinfo

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: The kinds this module can name, most specific first: a ``datetime``'s MRO
#: contains ``date`` as well, and answering "date" for one would describe the
#: wrong half of the mismatch being explained.
_KINDS = ("datetime", "date", "time", "timedelta")


#: The letters :func:`with_article` reads as taking "an". See its docstring for
#: what a letter cannot decide.
_VOWEL_LETTERS = "AEIOUaeiou"


#: The days of the week, in ``weekday()`` order. ``calendar.day_name`` is the
#: obvious source and is wrong twice over: it would cost an import this module
#: refuses, and it is locale-dependent, where a failure message is English by
#: rule. Failure path only.
_DAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def signed_duration(span: "timedelta", /) -> str:
    """Render a duration, backwards ones included. Failure path only.

    ``str(timedelta(seconds=-5))`` is ``'-1 day, 23:59:55'``. That is the
    normalised form -- only ``days`` carries the sign -- and it is not what
    anybody means by "five seconds backwards"; a reader meeting it in a failure
    message stops to do subtraction. A negative duration is therefore printed as
    the negation of its magnitude, so it reads ``-0:00:05`` and says what it is
    at a glance. Positive durations are untouched.
    """
    if span.days < 0:
        return "-" + str(-span)
    return str(span)


def rendered(value: object, /) -> str:
    """Render a date-like value for a failure message. Failure path only.

    Goes through the formatter registry first, so a domain wrapper reads as
    itself. Where the registry has no opinion, the ISO spelling replaces the
    stdlib ``repr`` -- ``datetime.datetime(2020, 1, 1, 0, 0)`` is noise beside
    ``2020-01-01T00:00:00``, which every reader already parses. Asked by duck
    test rather than ``isinstance`` so that this module keeps costing an
    importing program nothing.
    """
    text = format_value(value)
    if text != repr(value):
        return text
    isoformat = getattr(value, "isoformat", None)
    if isoformat is not None:
        return str(isoformat())
    if hasattr(value, "total_seconds"):
        return signed_duration(cast("timedelta", value))
    return text


# ---------------------------------------------------------------------------
# The two crashes, explained (see the module docstring for why they stay
# TypeErrors). Everything below here runs on a failure or an error path only.
# ---------------------------------------------------------------------------
def awareness(value: object, /) -> str | None:
    """``"aware"``, ``"naive"``, or ``None`` for a value that has no clock at all.

    A ``date`` has no ``utcoffset``, and a ``datetime`` or ``time`` whose
    ``tzinfo`` answers ``None`` is naive despite carrying one -- which is the
    same rule :meth:`ClockExpect.is_aware` applies, asked here by duck test so
    that no ``datetime`` import is needed to ask it.
    """
    utcoffset = getattr(value, "utcoffset", None)
    if utcoffset is None:
        return None
    return "aware" if utcoffset() is not None else "naive"


def kind_name(value: object, /) -> str:
    """Name a value's date-like kind from its MRO. Failure path only.

    ``isinstance`` would be the direct spelling and would need the real classes;
    the names in the MRO answer the same question and a subclass of ``date`` --
    which people do write -- still reports as a date.
    """
    names = {cls.__name__ for cls in type(value).__mro__}
    for candidate in _KINDS:
        if candidate in names:
            return candidate
    return type(value).__name__


def with_article(kind: str, /) -> str:
    """``kind`` with the article it takes -- "a date", "an Instant". Error path only.

    A spelling heuristic, and it can only ever be one: English picks the article
    by sound, so a class named ``Hour`` reads "a Hour" here where a speaker says
    "an hour", and one named ``Unicorn`` reads "an Unicorn" where a speaker says
    "a unicorn". The four kinds named above all begin with a consonant, so the
    guess is only ever made about a caller's own class name, where being right
    about the common shapes beats being wrong about every one of them.
    """
    if kind[:1] in _VOWEL_LETTERS:
        return "an " + kind
    return "a " + kind


def day_name(value: "date", /) -> str:
    """Name the subject's day of the week. Failure path only."""
    return _DAY_NAMES[value.weekday()]


def not_utc_reason(subject: "datetime", /) -> str:
    """Say why a datetime is not UTC. Failure path only."""
    offset = subject.utcoffset()
    if offset is None:
        return "is naive"
    return "is offset " + rendered(offset) + " from UTC"


def timezone_of(subject: "datetime", /) -> str:
    """Name the subject's timezone for a failure message. Failure path only.

    ``None`` is what ``tzinfo`` holds and not what the reader is asking about, so
    it is spelled out rather than printed.
    """
    zone = subject.tzinfo
    if zone is None:
        return "no timezone at all"
    return rendered(zone)


def same_offset_note(subject: "datetime", zone: "tzinfo", /) -> str:
    """Flag the confusing half of a :meth:`DateTimeExpect.has_timezone` failure.

    Failure path only. Two ``tzinfo`` objects that agree on the offset and still
    compare unequal -- ``timezone.utc`` against ``ZoneInfo("UTC")``, most often --
    produce a message where both sides look identical unless it is said out loud.
    """
    offset = subject.utcoffset()
    if offset is not None and offset == zone.utcoffset(subject):
        return " (the two agree on the offset and are still not the same timezone)"
    return ""


def distance_note(subject: "datetime", other: "datetime", /) -> str:
    """How far the subject is from ``other``, and on which side. Failure path only.

    The two moments being equal needs no third branch: both continuations of the
    difference chain are inclusive, so a subject sitting exactly on ``other``
    passed and never reached a message.
    """
    if subject < other:
        return rendered(other - subject) + " before it"
    return rendered(subject - other) + " after it"
