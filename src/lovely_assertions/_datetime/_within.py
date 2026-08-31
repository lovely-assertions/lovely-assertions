"""The middle of ``is_within(delta).before(other)``.

Two directed continuations, both inclusive at both ends, and the refusal of a
chain nobody finished. A ``WithinDelta`` that is never asked ``.before`` or
``.after`` asserts nothing at all, and an assertion that cannot fail is the one
kind of test worse than a wrong one -- so leaving one unfinished is reported.

The bound is on the subject rather than on ``DateTimeExpect`` itself, so a user's
own subclass comes back out of the chain as the class they put in.
"""

from typing import TYPE_CHECKING, override

from lovely_assertions._datetime._guards import reject_incomparable
from lovely_assertions._datetime._render import distance_note, rendered
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from datetime import datetime, timedelta

    from lovely_assertions._datetime._instant import DateTimeExpect

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

#: Warned about when an ``is_within(...)`` is garbage-collected without either
#: continuation having been called. See :meth:`WithinDelta.__del__`.
_UNFINISHED_CHAIN = (
    "is_within(...) asserted nothing: continue it with .before(...) or .after(...). The delta was "
)


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
            reject_incomparable(subject, other, error)
        if inside:
            return parent
        # Reported through the subject this continuation came from, so the failure
        # carries that subject's name rather than the continuation's.
        return parent._fail(  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
            f"to be within {rendered(self._delta)} before {rendered(other)},"
            f" but was {rendered(subject)}, {distance_note(subject, other)}",
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
            reject_incomparable(subject, other, error)
        if inside:
            return parent
        # Reported through the parent subject, as in `before` above.
        return parent._fail(  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
            f"to be within {rendered(self._delta)} after {rendered(other)},"
            f" but was {rendered(subject)}, {distance_note(subject, other)}",
            because,
        )
