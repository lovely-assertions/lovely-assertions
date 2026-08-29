"""Dates, times and durations.

``_ordered.py`` explains why these are not routed to :class:`OrderedExpect`: a
date is orderable and is not a number, so ``is_positive`` and ``is_zero`` mean
nothing for it, and a value on a calendar wants a vocabulary of its own --
``is_before``/``is_after`` rather than ``is_less_than``/``is_greater_than``.
``expect(deadline).is_before(now)`` is the whole reason the subject exists.

**The stdlib's own Liskov wart.** ``datetime`` subclasses ``date``, so the type
system cannot stop a ``datetime`` operand reaching a ``date`` subject -- and
comparing the two raises ``TypeError`` in CPython. The same is true of a naive
datetime against an aware one, which is the most common way a real suite crashes
on dates. Both are caught here and reported as what they are: a bare
``TypeError: can't compare offset-naive and offset-aware datetimes`` surfacing
from inside an assertion library reads like the library broke, when in fact it
*is* the finding.

The subject is generic over the concrete date type, so a ``date`` subject takes
``date`` bounds and a ``datetime`` subject takes ``datetime`` bounds -- the
checker refuses statically what the runtime would only discover as a crash.

**Both crashes stay ``TypeError``; neither becomes an assertion failure.** The
rule is the one ``_ordered.py`` applies to a ``Decimal`` NaN: when two values
cannot be compared at all, there is no verdict to report. "Passed" is untrue and
"failed" is worse -- it would blame the subject for a mistake in the test, and a
runner would present it as a finding about production code. So the comparison is
re-raised as a ``TypeError`` that says *which* side is naive and which is aware,
or which is a date and which a datetime, and what both of them were. The
exception type is the same one CPython raised, so a suite that already catches
``TypeError`` keeps working; only the message improves. Where nothing here can
explain the refusal -- a user's own ``__lt__`` saying no for its own reasons --
the original exception is re-raised untouched rather than dressed up as a date
problem it is not.

**A component no calendar has, and a tolerance no pair of values could satisfy,
are ``ValueError``.** ``has_month(13)`` and ``is_close_to(x, within=-1 day)``
could never pass whatever the subject is, which makes them the same kind of
mistake as ``_ordered._reject_unusable_range``'s inverted bounds: a bug in the
test, raised where it was written. A tolerance of *zero* is kept, because it
describes exactly one acceptable value rather than none -- the same reason
``is_between(x, x)`` is legal where ``is_strictly_between(x, x)`` is not.

**Nothing here imports ``datetime``.** The classes are needed for typing and
never at runtime, so they arrive under ``TYPE_CHECKING`` and the module costs an
importing program nothing. ``_subjects.py`` finds the real types through
``sys.modules`` when it has a value to dispatch, on the same argument that
governs ``Decimal``: a program holding a ``datetime`` has already imported one.
Every assertion therefore works through methods on the value it was handed, and
the two facts this module needs about ``datetime`` that no method exposes -- the
calendar's year bounds, and the names of the days -- are written down as
constants rather than imported.
"""

from typing import TYPE_CHECKING, NoReturn, Self, cast, override

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value

if TYPE_CHECKING:
    from datetime import date, datetime, time, timedelta, tzinfo

    from lovely_assertions._ordered import Ordered

#: The value types again, this time as PEP 695 aliases, for the four class
#: statements below whose *base* names one of them.
#:
#: A base is evaluated when the class is created, so it cannot be a name only
#: the checkers can see. A string is the obvious escape and it is not free: on
#: CPython 3.14, subscripting a generic with a string builds a ``ForwardRef``,
#: and building one imports ``annotationlib``, which pulls in ``ast`` and
#: ``enum`` -- three modules that would then load for every program that merely
#: says ``import lovely_assertions``, and invisible on 3.13 where a
#: ``ForwardRef`` costs nothing.
#:
#: A PEP 695 alias is lazily evaluated in the one way that matters here: the
#: object exists without its right-hand side being resolved, so the alias can
#: name a type from a module this library refuses to import, and a checker still
#: reads through it to ``DateExpect[datetime]``. A bound -- ``[T: "date"]`` -- is
#: lazy already and stays a string; only a base needs this.
type _DateTime = datetime
type _Time = time
type _TimeDelta = timedelta

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = [
    "DateExpect",
    "DateTimeExpect",
    "TimeDeltaExpect",
    "TimeExpect",
    "WithinDelta",
    "rendered",
]

#: The years the proleptic Gregorian calendar ``datetime`` implements admits --
#: ``datetime.MINYEAR`` and ``datetime.MAXYEAR``, written out because importing
#: them would put the ``datetime`` module on the bill of every program that
#: imports this library. They are fixed by the stdlib, not configuration.
_MIN_YEAR = 1
_MAX_YEAR = 9999

#: The remaining calendar and clock components, as ``low, high`` pairs. ``day``
#: is bounded by the longest month rather than by the subject's own month: day 31
#: of a February is a claim that *fails*, where day 32 is a claim nobody could
#: ever make.
_MONTHS = (1, 12)
_DAYS = (1, 31)
_HOURS = (0, 23)
_MINUTES = (0, 59)
#: 59, not 60: ``datetime`` has no leap seconds, so there is no 23:59:60.
_SECONDS = (0, 59)
_MICROSECONDS = (0, 999999)

#: ``date.weekday()`` numbers Monday 0 through Sunday 6, so the weekend starts
#: here. Named rather than spelled ``>= 5`` at three call sites.
_SATURDAY = 5

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

#: The kinds this module can name, most specific first: a ``datetime``'s MRO
#: contains ``date`` as well, and answering "date" for one would describe the
#: wrong half of the mismatch being explained.
_KINDS = ("datetime", "date", "time", "timedelta")

#: Appended when the two sides of a refused comparison are a ``date`` and a
#: ``datetime``. Without it the reader is left wondering why the checker let the
#: call through -- and the answer is that no checker could have.
_LISKOV_NOTE = "; datetime subclasses date, so no type checker can refuse the mix"

#: The letters :func:`_with_article` reads as taking "an". See its docstring for
#: what a letter cannot decide.
_VOWEL_LETTERS = "AEIOUaeiou"

#: Warned about when an ``is_within(...)`` is garbage-collected without either
#: continuation having been called. See :meth:`WithinDelta.__del__`.
_UNFINISHED_CHAIN = (
    "is_within(...) asserted nothing: continue it with .before(...) or .after(...). The delta was "
)


def _signed_duration(span: "timedelta", /) -> str:
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
        return _signed_duration(cast("timedelta", value))
    return text


# ---------------------------------------------------------------------------
# The two crashes, explained (see the module docstring for why they stay
# TypeErrors). Everything below here runs on a failure or an error path only.
# ---------------------------------------------------------------------------
def _awareness(value: object, /) -> str | None:
    """``"aware"``, ``"naive"``, or ``None`` for a value that has no clock at all.

    A ``date`` has no ``utcoffset``, and a ``datetime`` or ``time`` whose
    ``tzinfo`` answers ``None`` is naive despite carrying one -- which is the
    same rule :meth:`_ClockExpect.is_aware` applies, asked here by duck test so
    that no ``datetime`` import is needed to ask it.
    """
    utcoffset = getattr(value, "utcoffset", None)
    if utcoffset is None:
        return None
    return "aware" if utcoffset() is not None else "naive"


def _kind(value: object, /) -> str:
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


def _with_article(kind: str, /) -> str:
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


def _reject_incomparable(left: object, right: object, error: TypeError, /) -> NoReturn:
    """Re-raise a comparison CPython refused, saying why. Error path only.

    Two causes are recognised, and both name which side is which and what it
    was, because "can't compare offset-naive and offset-aware datetimes" tells a
    reader everything except the thing they need. Anything else propagates
    unchanged: a ``TypeError`` from a user's own comparison is not this module's
    to reinterpret.
    """
    left_kind = _kind(left)
    right_kind = _kind(right)
    if left_kind != right_kind:
        note = _LISKOV_NOTE if {left_kind, right_kind} == {"date", "datetime"} else ""
        raise TypeError(
            "can't compare "
            + _with_article(left_kind)
            + " with "
            + _with_article(right_kind)
            + ": "
            + rendered(left)
            + " is "
            + _with_article(left_kind)
            + " and "
            + rendered(right)
            + " is "
            + _with_article(right_kind)
            + note
        ) from error
    left_zone = _awareness(left)
    right_zone = _awareness(right)
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


def _offending_bound(subject: object, low: "Ordered", high: "Ordered", /) -> "Ordered":
    """Which of a range's two bounds the comparison refused. Error path only.

    ``low <= subject <= high`` reports one ``TypeError`` for two comparisons, and
    a message that named the wrong bound would send the reader to the wrong line.
    """
    try:
        _ = low <= subject
    except TypeError:
        return low
    return high


def _reject_unusable_range(low: "Ordered", high: "Ordered", /) -> None:
    """Raise for bounds that describe no range at all -- ``_ordered.py``'s rule.

    Checked before the subject is looked at, on purpose: bounds no value could
    satisfy are a bug in the test, and a subject that happened to fail would hide
    it behind a message blaming the value. Two bounds that cannot be compared
    with each other -- one naive and one aware, say -- are the same kind of
    mistake and are reported the same way.
    """
    try:
        inverted = low > high
    except TypeError as error:
        _reject_incomparable(low, high, error)
    if inverted:
        raise ValueError(
            "range is inverted: low " + rendered(low) + " exceeds high " + rendered(high)
        )


def _reject_impossible_component(label: str, value: int, bounds: tuple[int, int], /) -> None:
    """Raise ``ValueError`` for a calendar component no date could carry.

    ``has_month(13)`` is not a claim a subject can disprove; it is a claim the
    calendar has no room for, so it is a bug in the test rather than a finding --
    the same line ``_reject_unusable_range`` takes on an inverted range. Note
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


def _reject_negative_span(label: str, span: "timedelta", /) -> None:
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


def _zone_of(value: object, /) -> "tzinfo | None":
    """The value's own timezone, or ``None`` when it is naive.

    Naive by the same rule as :meth:`_ClockExpect.is_aware`: a ``tzinfo`` whose
    ``utcoffset`` answers ``None`` is not a timezone, and handing it to
    ``datetime.now`` would be asking for the current moment somewhere that
    declines to say where it is.
    """
    utcoffset = getattr(value, "utcoffset", None)
    if utcoffset is None or utcoffset() is None:
        return None
    return cast("tzinfo | None", getattr(value, "tzinfo", None))


def _now_like[D: "date"](value: D, /) -> D:
    """The current moment, in the same shape and timezone as ``value``.

    Built from the subject's own type, so a ``date`` gets a date, a ``datetime``
    gets a datetime, and a subclass of either gets one of itself -- and no
    ``datetime`` import is needed to produce any of them.

    Matching the *awareness* is the part that matters: a naive "now" compared
    against an aware subject is precisely the crash this module exists to
    explain, reintroduced inside the assertion meant to prevent it.
    """
    kind = type(value)
    now = getattr(kind, "now", None)
    if now is None:
        return kind.today()
    return cast("D", now(_zone_of(value)))


def _day_name(value: "date", /) -> str:
    """Name the subject's day of the week. Failure path only."""
    return _DAY_NAMES[value.weekday()]


def _not_utc_reason(subject: "datetime", /) -> str:
    """Say why a datetime is not UTC. Failure path only."""
    offset = subject.utcoffset()
    if offset is None:
        return "is naive"
    return "is offset " + rendered(offset) + " from UTC"


def _timezone_of(subject: "datetime", /) -> str:
    """Name the subject's timezone for a failure message. Failure path only.

    ``None`` is what ``tzinfo`` holds and not what the reader is asking about, so
    it is spelled out rather than printed.
    """
    zone = subject.tzinfo
    if zone is None:
        return "no timezone at all"
    return rendered(zone)


def _same_offset_note(subject: "datetime", zone: "tzinfo", /) -> str:
    """Flag the confusing half of a :meth:`DateTimeExpect.has_timezone` failure.

    Failure path only. Two ``tzinfo`` objects that agree on the offset and still
    compare unequal -- ``timezone.utc`` against ``ZoneInfo("UTC")``, most often --
    produce a message where both sides look identical unless it is said out loud.
    """
    offset = subject.utcoffset()
    if offset is not None and offset == zone.utcoffset(subject):
        return " (the two agree on the offset and are still not the same timezone)"
    return ""


def _distance_note(subject: "datetime", other: "datetime", /) -> str:
    """How far the subject is from ``other``, and on which side. Failure path only.

    The two moments being equal needs no third branch: both continuations of the
    difference chain are inclusive, so a subject sitting exactly on ``other``
    passed and never reached a message.
    """
    if subject < other:
        return rendered(other - subject) + " before it"
    return rendered(subject - other) + " after it"


# ---------------------------------------------------------------------------
# The shared halves
# ---------------------------------------------------------------------------
class _TemporalExpect[T: "Ordered"](Expect[T]):
    """Ordering and ranges, for anything on a calendar or a clock.

    Private, and shared rather than written twice, because ``date`` and ``time``
    answer the comparison operators identically and crash on a naive/aware mix
    identically. What separates them -- a date has no hour, a time has no year --
    is what the public subjects add.

    The bound is ``Ordered`` -- ``_ordered.py``'s protocol, reused exactly as its
    own docstring says it is meant to be -- and **not** ``date | time``, which is
    what it looks like it should be and does not work: a type parameter bounded
    by a union has to satisfy the checker for *every* pairing of that union's
    members, so ``subject < other`` would be asked to prove that a ``date``
    compares against a ``time``. It does not, and the code would be rejected for
    a combination no subclass of this class can produce. The public subjects
    below re-bind ``T`` to a single concrete type, so nothing is loosened where
    a caller can see it.
    """

    __slots__ = ()

    def is_before(self, other: T, /, *, because: str = "") -> Self:
        """Assert the subject falls strictly before ``other``.

        ``other`` has to be comparable with the subject: a ``date`` mixed with a
        ``datetime``, or a naive value with an aware one, raises ``TypeError``
        naming both sides rather than reporting a failure the subject did not
        cause. Equal moments fail; :meth:`is_on_or_before` is the inclusive form.
        """
        try:
            ordered = self._subject < other
        except TypeError as error:
            _reject_incomparable(self._subject, other, error)
        if ordered:
            return self
        return self._fail(
            f"to be before {rendered(other)}, but was {rendered(self._subject)}", because
        )

    def is_after(self, other: T, /, *, because: str = "") -> Self:
        """Assert the subject falls strictly after ``other``.

        Equal moments fail; :meth:`is_on_or_after` is the inclusive form. An
        operand that cannot be compared with the subject raises ``TypeError``,
        on the same terms as :meth:`is_before`.
        """
        try:
            ordered = self._subject > other
        except TypeError as error:
            _reject_incomparable(self._subject, other, error)
        if ordered:
            return self
        return self._fail(
            f"to be after {rendered(other)}, but was {rendered(self._subject)}", because
        )

    def is_on_or_before(self, other: T, /, *, because: str = "") -> Self:
        """Assert the subject falls at or before ``other``.

        :meth:`is_before` is the strict form. An operand that cannot be compared
        with the subject raises ``TypeError``.
        """
        try:
            ordered = self._subject <= other
        except TypeError as error:
            _reject_incomparable(self._subject, other, error)
        if ordered:
            return self
        return self._fail(
            f"to be on or before {rendered(other)}, but was {rendered(self._subject)}", because
        )

    def is_on_or_after(self, other: T, /, *, because: str = "") -> Self:
        """Assert the subject falls at or after ``other``.

        :meth:`is_after` is the strict form. An operand that cannot be compared
        with the subject raises ``TypeError``.
        """
        try:
            ordered = self._subject >= other
        except TypeError as error:
            _reject_incomparable(self._subject, other, error)
        if ordered:
            return self
        return self._fail(
            f"to be on or after {rendered(other)}, but was {rendered(self._subject)}", because
        )

    def is_between(self, low: T, high: T, /, *, because: str = "") -> Self:
        """Assert ``low <= subject <= high``, both bounds included.

        Raises ``ValueError`` for an inverted range, and ``TypeError`` for bounds
        that cannot be compared with each other or with the subject.
        """
        _reject_unusable_range(low, high)
        try:
            inside = low <= self._subject <= high
        except TypeError as error:
            _reject_incomparable(self._subject, _offending_bound(self._subject, low, high), error)
        if inside:
            return self
        return self._fail(
            f"to be between {rendered(low)} and {rendered(high)} inclusive, "
            f"but was {rendered(self._subject)}",
            because,
        )

    def is_not_between(self, low: T, high: T, /, *, because: str = "") -> Self:
        """Assert the subject falls outside ``low..high``, bounds included.

        The exact complement of :meth:`is_between`.
        """
        _reject_unusable_range(low, high)
        try:
            inside = low <= self._subject <= high
        except TypeError as error:
            _reject_incomparable(self._subject, _offending_bound(self._subject, low, high), error)
        if not inside:
            return self
        return self._fail(
            f"not to be between {rendered(low)} and {rendered(high)} inclusive, "
            f"but was {rendered(self._subject)}",
            because,
        )

    def is_strictly_between(self, low: T, high: T, /, *, because: str = "") -> Self:
        """Assert ``low < subject < high``, both bounds excluded.

        ``low == high`` raises ``ValueError`` as an inverted range does: the
        exclusive range between a moment and itself is empty, so no subject could
        ever satisfy it.
        """
        _reject_unusable_range(low, high)
        if low == high:
            raise ValueError(
                "exclusive range is empty: low " + rendered(low) + " equals high " + rendered(high)
            )
        try:
            inside = low < self._subject < high
        except TypeError as error:
            _reject_incomparable(self._subject, _offending_bound(self._subject, low, high), error)
        if inside:
            return self
        return self._fail(
            f"to be strictly between {rendered(low)} and {rendered(high)}, "
            f"but was {rendered(self._subject)}",
            because,
        )


class _ClockExpect[T: "datetime | time"](_TemporalExpect[T]):
    """The time of day, and whether it is anchored to a timezone.

    Private, and shared by :class:`DateTimeExpect` and :class:`TimeExpect`,
    which are the two subjects that have a clock in them. The union bound is
    safe here where it is not on :class:`_TemporalExpect`: these assertions read
    attributes both members of the union have, and never compare one against the
    other.
    """

    __slots__ = ()

    def has_hour(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the subject's hour is ``expected``, on a 24-hour clock."""
        _reject_impossible_component("hour", expected, _HOURS)
        if self._subject.hour == expected:
            return self
        return self._fail(
            f"to have hour {rendered(expected)}, but had {rendered(self._subject.hour)}"
            f" ({rendered(self._subject)})",
            because,
        )

    def has_minute(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the subject's minute is ``expected``."""
        _reject_impossible_component("minute", expected, _MINUTES)
        if self._subject.minute == expected:
            return self
        return self._fail(
            f"to have minute {rendered(expected)}, but had {rendered(self._subject.minute)}"
            f" ({rendered(self._subject)})",
            because,
        )

    def has_second(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the subject's second is ``expected``. ``datetime`` has no leap seconds."""
        _reject_impossible_component("second", expected, _SECONDS)
        if self._subject.second == expected:
            return self
        return self._fail(
            f"to have second {rendered(expected)}, but had {rendered(self._subject.second)}"
            f" ({rendered(self._subject)})",
            because,
        )

    def has_microsecond(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the subject's microsecond is ``expected``."""
        _reject_impossible_component("microsecond", expected, _MICROSECONDS)
        if self._subject.microsecond == expected:
            return self
        return self._fail(
            f"to have microsecond {rendered(expected)},"
            f" but had {rendered(self._subject.microsecond)} ({rendered(self._subject)})",
            because,
        )

    def is_aware(self, *, because: str = "") -> Self:
        """Assert the subject carries a usable timezone.

        A ``tzinfo`` is not enough: one whose ``utcoffset`` answers ``None`` is
        legal, is what ``datetime`` itself treats as naive, and is the reason the
        question is asked of the offset rather than of the attribute.
        """
        if self._subject.utcoffset() is not None:
            return self
        return self._fail(f"to be timezone-aware, but {rendered(self._subject)} is naive", because)

    def is_naive(self, *, because: str = "") -> Self:
        """Assert the subject carries no usable timezone -- :meth:`is_aware`'s complement."""
        offset = self._subject.utcoffset()
        if offset is None:
            return self
        return self._fail(
            f"to be naive, but {rendered(self._subject)} is timezone-aware"
            f" (offset {rendered(offset)})",
            because,
        )


# ---------------------------------------------------------------------------
# The public subjects
# ---------------------------------------------------------------------------
class DateExpect[T: "date"](_TemporalExpect[T]):
    """Assertions for a calendar date.

    :class:`DateTimeExpect` extends this with everything that needs a time of
    day, mirroring ``datetime``'s own inheritance from ``date``.

    The operand of a comparison is ``T`` rather than ``date``, which is what
    buys the static half of the Liskov wart: on a ``DateTimeExpect`` it resolves
    to ``datetime``, so a ``date`` bound is refused by the checker instead of
    crashing at runtime. The other direction cannot be refused by anybody --
    a ``datetime`` *is* a ``date`` -- which is why the runtime half exists.
    """

    __slots__ = ()

    def has_year(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the subject falls in year ``expected``."""
        _reject_impossible_component("year", expected, (_MIN_YEAR, _MAX_YEAR))
        if self._subject.year == expected:
            return self
        return self._fail(
            f"to have year {rendered(expected)}, but had {rendered(self._subject.year)}"
            f" ({rendered(self._subject)})",
            because,
        )

    def has_month(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the subject falls in month ``expected``, January being 1."""
        _reject_impossible_component("month", expected, _MONTHS)
        if self._subject.month == expected:
            return self
        return self._fail(
            f"to have month {rendered(expected)}, but had {rendered(self._subject.month)}"
            f" ({rendered(self._subject)})",
            because,
        )

    def has_day(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the subject falls on day ``expected`` of its month.

        Day 31 of a February is a claim that fails; day 32 is a claim no calendar
        has room for, and raises ``ValueError``.
        """
        _reject_impossible_component("day of the month", expected, _DAYS)
        if self._subject.day == expected:
            return self
        return self._fail(
            f"to have day {rendered(expected)}, but had {rendered(self._subject.day)}"
            f" ({rendered(self._subject)})",
            because,
        )

    def is_weekday(self, *, because: str = "") -> Self:
        """Assert the subject falls Monday through Friday."""
        if self._subject.weekday() < _SATURDAY:
            return self
        return self._fail(
            f"to fall on a weekday, but {rendered(self._subject)} is a {_day_name(self._subject)}",
            because,
        )

    def is_weekend(self, *, because: str = "") -> Self:
        """Assert the subject falls on a Saturday or a Sunday."""
        if self._subject.weekday() >= _SATURDAY:
            return self
        return self._fail(
            f"to fall on a weekend, but {rendered(self._subject)} is a {_day_name(self._subject)}",
            because,
        )

    def is_today(self, *, because: str = "") -> Self:
        """Assert the subject falls on today's calendar date.

        Compared by calendar day rather than by equality, so a ``datetime``
        subject passes at any hour of the day -- ``date`` and ``datetime`` never
        compare equal to each other, and a subject narrowed to a moment would
        otherwise be able to pass only in the microsecond it was created.

        For an aware subject "today" is today *in the subject's own timezone*,
        which is the only reading that does not compare a wall clock against a
        different one.
        """
        now = _now_like(self._subject)
        if self._subject.toordinal() == now.toordinal():
            return self
        return self._fail(
            f"to be today, but was {rendered(self._subject)} and today is {rendered(now)}", because
        )

    def is_in_the_past(self, *, because: str = "") -> Self:
        """Assert the subject is earlier than the moment the assertion runs.

        "Now" is sampled in the subject's own shape and timezone, so an aware
        subject is compared against an aware now and a naive one against a naive
        now. Anything else would raise the very ``TypeError`` this module is here
        to explain. A ``date`` subject is compared by day, so *today* is neither
        past nor future.
        """
        now = _now_like(self._subject)
        if self._subject < now:
            return self
        return self._fail(
            f"to be in the past, but was {rendered(self._subject)} and now is {rendered(now)}",
            because,
        )

    def is_in_the_future(self, *, because: str = "") -> Self:
        """Assert the subject is later than the moment the assertion runs."""
        now = _now_like(self._subject)
        if self._subject > now:
            return self
        return self._fail(
            f"to be in the future, but was {rendered(self._subject)} and now is {rendered(now)}",
            because,
        )


class DateTimeExpect(DateExpect[_DateTime], _ClockExpect[_DateTime]):
    """Assertions for a point in time.

    Everything on :class:`DateExpect` and every clock assertion are here as well,
    so one chain can run from the calendar day down to the timezone.
    """

    __slots__ = ()

    def is_same_date_as(self, other: "datetime", /, *, because: str = "") -> Self:
        """Assert the subject falls on the same calendar day as ``other``.

        Wall clock against wall clock: neither side is converted to a common
        timezone first, because the question "was this the same day?" is asked of
        the calendar each value carries. Two aware moments in different zones can
        therefore be the same instant and different dates, which is a fact about
        calendars rather than a defect here.
        """
        if self._subject.date() == other.date():
            return self
        return self._fail(
            f"to fall on the same date as {rendered(other)}, but was {rendered(self._subject)}",
            because,
        )

    def is_close_to(self, other: "datetime", /, *, within: "timedelta", because: str = "") -> Self:
        """Assert the subject is no more than ``within`` away from ``other``.

        The distance is absolute, so the assertion is symmetric in both senses:
        it does not care which of the two came first, and swapping subject and
        operand cannot change the verdict. A negative ``within`` raises
        ``ValueError``; zero is legal and means exact equality.
        """
        _reject_negative_span("within", within)
        try:
            distance = abs(self._subject - other)
        except TypeError as error:
            _reject_incomparable(self._subject, other, error)
        if distance <= within:
            return self
        return self._fail(
            f"to be within {rendered(within)} of {rendered(other)},"
            f" but was {rendered(self._subject)}, {rendered(distance)} away",
            because,
        )

    def is_not_close_to(
        self, other: "datetime", /, *, within: "timedelta", because: str = ""
    ) -> Self:
        """Assert the subject is more than ``within`` away from ``other``.

        The exact complement of :meth:`is_close_to`.
        """
        _reject_negative_span("within", within)
        try:
            distance = abs(self._subject - other)
        except TypeError as error:
            _reject_incomparable(self._subject, other, error)
        if distance > within:
            return self
        return self._fail(
            f"not to be within {rendered(within)} of {rendered(other)},"
            f" but was {rendered(self._subject)}, only {rendered(distance)} away",
            because,
        )

    def is_utc(self, *, because: str = "") -> Self:
        """Assert the subject is anchored to UTC.

        Decided by offset, not by identity: ``timezone.utc``, ``ZoneInfo("UTC")``
        and ``timezone(timedelta(0))`` are three unequal objects that describe the
        same timezone, and an assertion that could tell them apart would be
        asserting which library built the value rather than what the value means.
        :meth:`has_timezone` is the identity question, for when that is what was
        wanted.
        """
        offset = self._subject.utcoffset()
        # A `timedelta` is falsy exactly when it is zero, which is how the offset
        # is compared against zero without a zero to compare it against.
        if offset is not None and not offset:
            return self
        return self._fail(
            f"to be UTC, but {rendered(self._subject)} {_not_utc_reason(self._subject)}", because
        )

    def has_timezone(self, zone: "tzinfo", /, *, because: str = "") -> Self:
        """Assert the subject carries exactly the timezone ``zone``.

        Equality of ``tzinfo``, deliberately -- :meth:`is_utc` is the offset
        question. Where the two disagree the failure says so, because a message
        whose two halves print the same offset is otherwise unreadable.
        """
        if self._subject.tzinfo == zone:
            return self
        return self._fail(
            f"to have timezone {rendered(zone)}, but {rendered(self._subject)}"
            f" has {_timezone_of(self._subject)}{_same_offset_note(self._subject, zone)}",
            because,
        )

    def is_within(self, delta: "timedelta", /) -> "WithinDelta[Self]":
        """Open a difference chain: ``is_within(delta).before(other)`` or ``.after(other)``.

        The Python spelling of FluentAssertions' ``BeLessThan(ts).Before(x)``.
        The assertion is made by the continuation, not by this call: ``is_within``
        on its own asserts nothing, and says so out loud if it is ever left that
        way (see :meth:`WithinDelta.__del__`).

        A negative ``delta`` raises ``ValueError``; a zero one is legal and
        narrows the chain to exact equality with the continuation's operand.
        Takes no ``because``; the reason belongs to the continuation that does
        the asserting.
        """
        _reject_negative_span("the delta given to is_within", delta)
        return WithinDelta(self, delta)


class WithinDelta[E: DateTimeExpect]:
    """The middle of ``is_within(delta).before(other)``.

    Generic over the subject that opened the chain rather than typed to
    :class:`DateTimeExpect`, so that a user's own subclass comes back out of
    ``.before(...)`` as itself and the chain keeps flowing with its own
    assertions still visible.

    Both continuations are **inclusive at both ends**: ``.before(other)`` holds
    when the subject sits anywhere in ``other - delta .. other``. The direction is
    part of the claim -- a subject *after* ``other`` fails ``.before`` however
    close it is -- because "within five minutes before the deadline" is a
    statement about which side of the deadline the value fell on, and
    :meth:`DateTimeExpect.is_close_to` is the assertion that does not care.

    A failure is reported through the parent's ``_fail`` rather than through one
    of its own, so the message carries the subject's recovered name and lands in
    whatever soft scope the subject belongs to. That is a deliberate reach across
    the two objects, which are one cooperating pair -- the same arrangement
    ``_core.py`` has between a subject and the scope that collects its failures,
    and it is silenced at the two call sites rather than for the file.
    """

    __slots__ = ("_continued", "_delta", "_parent")

    def __init__(self, parent: E, delta: "timedelta", /) -> None:
        self._parent: E = parent
        self._delta: timedelta = delta
        #: Whether a continuation ran. Read by :meth:`__del__` and nowhere else.
        self._continued: bool = False

    @override
    def __repr__(self) -> str:
        return f"WithinDelta({self._delta!r})"

    def __del__(self) -> None:
        """Warn about a chain that was opened and never finished.

        ``expect(t).is_within(delta)`` with no continuation is a test that
        asserts nothing -- the same defect as a variadic assertion called with no
        arguments, which this library raises on. It cannot be raised on *here*,
        because at the moment the call returns it is still a perfectly good half
        of a chain; the mistake only becomes visible when the object dies unused.
        So it is reported the way CPython reports the identical mistake with an
        un-awaited coroutine: a ``RuntimeWarning`` from the finaliser.

        Best-effort by nature. The warning arrives whenever the collector gets
        there, and its stack points at the finaliser rather than at the guilty
        line, so the message carries the delta to identify which chain it was.
        A warning that arrives late still turns a silently-green test red under
        ``-W error``, which is the outcome that matters.
        """
        if self._continued:
            return
        import warnings  # noqa: PLC0415  (imported here, so only an unfinished chain pays)

        warnings.warn(_UNFINISHED_CHAIN + rendered(self._delta), RuntimeWarning, stacklevel=2)

    def before(self, other: "datetime", /, *, because: str = "") -> E:
        """Assert the subject falls at most ``delta`` before ``other``, and not after it."""
        self._continued = True
        parent = self._parent
        subject = parent.subject
        try:
            inside = other - self._delta <= subject <= other
        except OverflowError:
            # `other - delta` falls before `datetime.min`, so there is nothing
            # representable for the subject to fall short of: the range collapses
            # to "at or before `other`" rather than becoming an error about
            # arithmetic the caller never asked to see.
            inside = subject <= other
        except TypeError as error:
            _reject_incomparable(subject, other, error)
        if inside:
            return parent
        # Reported through the subject this continuation came from, so the failure
        # carries that subject's name rather than the continuation's.
        return parent._fail(  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
            f"to be within {rendered(self._delta)} before {rendered(other)},"
            f" but was {rendered(subject)}, {_distance_note(subject, other)}",
            because,
        )

    def after(self, other: "datetime", /, *, because: str = "") -> E:
        """Assert the subject falls at most ``delta`` after ``other``, and not before it."""
        self._continued = True
        parent = self._parent
        subject = parent.subject
        try:
            inside = other <= subject <= other + self._delta
        except OverflowError:
            # `other + delta` falls past `datetime.max`; see `before` above.
            inside = other <= subject
        except TypeError as error:
            _reject_incomparable(subject, other, error)
        if inside:
            return parent
        # Reported through the parent subject, as in `before` above.
        return parent._fail(  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
            f"to be within {rendered(self._delta)} after {rendered(other)},"
            f" but was {rendered(subject)}, {_distance_note(subject, other)}",
            because,
        )


class TimeExpect(_ClockExpect[_Time]):
    """Assertions for a time of day.

    A ``time`` carries a ``tzinfo`` and no date, so it crashes on a naive/aware
    comparison exactly as a ``datetime`` does and is guarded the same way.
    """

    __slots__ = ()

    def is_midnight(self, *, because: str = "") -> Self:
        """Assert the subject is exactly 00:00:00.000000.

        Asked of the wall clock, so an aware midnight is midnight: it is midnight
        *somewhere*, which is what a ``time`` with a timezone means.
        """
        subject = self._subject
        if not (subject.hour or subject.minute or subject.second or subject.microsecond):
            return self
        return self._fail(f"to be midnight, but was {rendered(subject)}", because)


class TimeDeltaExpect(Expect[_TimeDelta]):
    """Assertions for a duration.

    A duration is signed, so it keeps ``is_positive`` and its neighbours where a
    date cannot have them, and takes duration vocabulary -- ``is_longer_than``
    rather than ``is_greater_than`` -- for the same reason a date takes
    ``is_before``.

    "Longer" and "shorter" are the *signed* comparisons, not comparisons of
    magnitude: ``timedelta(days=-2)`` is shorter than ``timedelta(0)``, which is
    what ``<`` says and what a duration that can run backwards has to mean.
    ``expect(abs(span))`` is how to ask about magnitude.
    """

    __slots__ = ()

    def is_longer_than(self, other: "timedelta", /, *, because: str = "") -> Self:
        """Assert the subject is a longer duration than ``other``."""
        if self._subject > other:
            return self
        return self._fail(
            f"to be longer than {rendered(other)}, but was {rendered(self._subject)}", because
        )

    def is_shorter_than(self, other: "timedelta", /, *, because: str = "") -> Self:
        """Assert the subject is a shorter duration than ``other``."""
        if self._subject < other:
            return self
        return self._fail(
            f"to be shorter than {rendered(other)}, but was {rendered(self._subject)}", because
        )

    def is_at_least(self, other: "timedelta", /, *, because: str = "") -> Self:
        """Assert the subject is ``other`` or longer."""
        if self._subject >= other:
            return self
        return self._fail(
            f"to be at least {rendered(other)}, but was {rendered(self._subject)}", because
        )

    def is_at_most(self, other: "timedelta", /, *, because: str = "") -> Self:
        """Assert the subject is ``other`` or shorter."""
        if self._subject <= other:
            return self
        return self._fail(
            f"to be at most {rendered(other)}, but was {rendered(self._subject)}", because
        )

    def is_between(self, low: "timedelta", high: "timedelta", /, *, because: str = "") -> Self:
        """Assert ``low <= subject <= high``, both bounds included.

        An inverted range raises ``ValueError``: no duration could satisfy it.
        """
        _reject_unusable_range(low, high)
        if low <= self._subject <= high:
            return self
        return self._fail(
            f"to be between {rendered(low)} and {rendered(high)} inclusive, "
            f"but was {rendered(self._subject)}",
            because,
        )

    def is_not_between(self, low: "timedelta", high: "timedelta", /, *, because: str = "") -> Self:
        """Assert the subject falls outside ``low..high``, bounds included."""
        _reject_unusable_range(low, high)
        if not low <= self._subject <= high:
            return self
        return self._fail(
            f"not to be between {rendered(low)} and {rendered(high)} inclusive, "
            f"but was {rendered(self._subject)}",
            because,
        )

    def is_positive(self, *, because: str = "") -> Self:
        """Assert the duration runs forwards. Zero is not positive."""
        # A `timedelta` is falsy exactly when it is zero, and only `days` carries
        # the sign once it is normalised (see `_reject_negative_span`). Together
        # they answer the sign question without a zero `timedelta` to ask it of.
        if self._subject and self._subject.days >= 0:
            return self
        return self._fail(f"to be a positive duration, but was {rendered(self._subject)}", because)

    def is_negative(self, *, because: str = "") -> Self:
        """Assert the duration runs backwards. Zero is not negative."""
        if self._subject.days < 0:
            return self
        return self._fail(f"to be a negative duration, but was {rendered(self._subject)}", because)

    def is_zero(self, *, because: str = "") -> Self:
        """Assert the duration is exactly zero."""
        if not self._subject:
            return self
        return self._fail(f"to be zero, but was {rendered(self._subject)}", because)

    def is_not_zero(self, *, because: str = "") -> Self:
        """Assert the duration is not zero -- :meth:`is_zero`'s complement."""
        if self._subject:
            return self
        return self._fail("not to be zero, but it was", because)

    def is_close_to(self, other: "timedelta", /, *, within: "timedelta", because: str = "") -> Self:
        """Assert the subject is no more than ``within`` away from ``other``.

        Absolute and therefore symmetric, exactly as
        :meth:`DateTimeExpect.is_close_to` is. A negative ``within`` raises
        ``ValueError``; zero means exact equality.
        """
        _reject_negative_span("within", within)
        if abs(self._subject - other) <= within:
            return self
        return self._fail(
            f"to be within {rendered(within)} of {rendered(other)},"
            f" but was {rendered(self._subject)},"
            f" {rendered(abs(self._subject - other))} away",
            because,
        )

    def is_not_close_to(
        self, other: "timedelta", /, *, within: "timedelta", because: str = ""
    ) -> Self:
        """Assert the subject is more than ``within`` away from ``other``."""
        _reject_negative_span("within", within)
        if abs(self._subject - other) > within:
            return self
        return self._fail(
            f"not to be within {rendered(within)} of {rendered(other)},"
            f" but was {rendered(self._subject)},"
            f" only {rendered(abs(self._subject - other))} away",
            because,
        )

    def has_total_seconds(self, expected: float, /, *, because: str = "") -> Self:
        """Assert ``subject.total_seconds()`` equals ``expected``.

        Exact float equality, as every ``has_*`` in this module is exact: it
        states a component, and a component that is nearly right is wrong.
        ``total_seconds()`` is a float, so a value that cannot be written exactly
        in binary will not compare equal to the one you typed --
        ``timedelta(seconds=0.1).total_seconds() == 0.1`` happens to hold, and
        arithmetic that produced the duration may well not. Reach for
        :meth:`is_close_to` when a tolerance is what was meant.
        """
        if self._subject.total_seconds() == expected:
            return self
        return self._fail(
            f"to have total seconds {rendered(expected)},"
            f" but had {rendered(self._subject.total_seconds())} ({rendered(self._subject)})",
            because,
        )
