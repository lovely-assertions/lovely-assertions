"""Assertions about the warnings a call issues.

The catalogue this library is measured against is FluentAssertions', and .NET
has no warnings concept at all, so nothing in that catalogue asks for this
family -- a gap no source suggests is a gap nobody notices. Without it a
warning-emitting callable is invisible here: ``raises`` reports "but nothing was
raised (the call returned None)", which is true, unhelpful, and exactly the shape
of answer a library gives when it has not been asked the question.

Two entry forms land on the same subject, as the exception family does. The
**context-manager form** is the primary one, and sits where ``pytest.warns``
sits::

    with expect_warns(DeprecationWarning) as warned:
        legacy()
    warned.with_message_containing("use parse_iso instead")

The **callable form** wraps a thunk, ``expect(legacy).warns(DeprecationWarning)``,
and lives on :class:`~lovely_assertions.CallableExpect` beside ``raises`` --
in ``_callable.py``, so that both forms refuse an ``async def`` through the one
guard rather than through two that can drift.

**Why this exists next to** ``pytest.warns``, stated plainly because the honest
answer is "not for every case". ``pytest.warns`` is one line, is already in the
file, and needs no import. Three things it cannot do:

*It does not show you what was warned.* It tells you the warning you asked for
did not fire, which you already knew, and says nothing about the four that did --
which is the information that ends the investigation. Every failure this module
reports lists the warnings that were issued, each with the file and line the
``stacklevel`` pointed at.

*It cannot be collected.* ``pytest.warns`` raises, so it ends the test at the
first finding. Everything here reports through ``_fail``, so an active
``soft_assertions`` scope gathers a failed warning assertion alongside the rest
and the block runs to the end.

*It cannot count.* ``occurrences=exactly(2)`` and ``occurrences=at_least(1)`` are
the constraints the rest of this library already speaks, and ``pytest.warns`` has
no spelling for either -- a test that cares whether a deprecation fired once or
once per row has to record the warnings and count them by hand.

And one thing ``pytest.warns`` cannot express at all: assert that **nothing**
warned. Without it, that assertion is written out by hand around a
``catch_warnings`` block every time it is wanted.
:meth:`~lovely_assertions.CallableExpect.does_not_warn` is that assertion.

**The subject is a tuple.** ``raises`` narrows to *the* exception, because a call
raises at most one; a call may issue any number of warnings, and an assertion
that silently kept the first would be wrong in the case the user wrote
``occurrences=`` for. So :class:`WarnedExpect` carries every matching warning, in
the order they were issued, and its own assertions ask whether *some* warning
satisfies them -- the same "any of them" that ``RaisedExpect.with_note_matching``
already applies to notes.

That choice pays for itself in the soft-assertion path. When ``expect_raises``
fails inside a soft scope it has no exception to hand back, so ``_CaughtExpect``
substitutes a stand-in for its subject and has to guard the three assertions that
would hand that stand-in to a user's callable. A tuple has a perfectly good empty
value, so :class:`_CaughtWarnings` keeps ``()`` as its subject -- a real value of
the declared type, and one a predicate written for real warnings survives -- and
needs no such guards. The stand-in still appears where it has to: a narrowing
assertion owes the rest of the chain something that goes on absorbing, and ``()``
is not that, so :meth:`_CaughtWarnings._fail_narrowing` hands the stand-in back
exactly as every other subject in the library does.

**Capture is process-wide, and that is CPython's doing, not this library's.**
``warnings.catch_warnings`` swaps the global filter list and the global
``showwarning``, and its own documentation says it is not thread-safe. Two
consequences, both documented rather than papered over: a warning issued by
*another* thread while a block is open is captured by that block and counts
towards its constraint, and two threads capturing at once can restore each
other's filters. A lock here would fix neither, because it would have to be held
across the user's entire block -- arbitrary code, including code that blocks on
the other thread -- so this module does not take one. ``pytest.warns`` has the
same caveat for the same reason. Nesting in *one* thread is fine:
``catch_warnings`` is re-entrant, and it restores what it found rather than a
default.

**The** ``__warningregistry__`` **trap is handled, and not by us.** A warning
already issued once from a module is not issued again, because ``warn_explicit``
remembers ``(text, category, lineno)`` in that module's ``__warningregistry__``.
That is the single most common way a warning test passes alone and fails in a
suite. ``catch_warnings.__enter__`` bumps ``warnings._filters_version``, and
``warn_explicit`` clears any registry whose version does not match -- so entering
a capture invalidates every registry in the process. This module gets that for
free by using ``catch_warnings`` rather than saving and restoring
``warnings.filters`` by hand, which is the tempting shortcut and the one that
reintroduces the bug.

**Ambient filters do not apply inside the block.** Capture runs under
``action="always"``, so a ``DeprecationWarning`` that the interpreter ignores by
default is still seen, and ``-W error`` does not turn the warning under test into
an exception. Both are deliberate: an assertion that a warning was issued cannot
be written at all if the project's filters have already converted it into
something else, and a test that says "this call deprecates" should not have to
know how the suite is configured. It is also what ``pytest.warns`` does.

**Warnings nobody asked about are re-issued on the way out.** A capture that
matched ``UserWarning`` and swallowed a ``DeprecationWarning`` would have
disarmed the project's own filters for the duration of the block -- silently, and
in the direction that loses information. So every warning outside the category
under test is handed back to ``warnings.warn_explicit`` once the ambient filters
are restored, which is where it would have gone had the block not been there.
Two consequences follow, and both are the price of being faithful rather than
convenient: under ``-W error`` a re-issued warning raises, at the end of the
block instead of in the middle of the call that issued it; and the re-issue
carries no registry, so a ``once`` filter shows it again. A block that did not
finish -- one whose body raised -- re-issues nothing: its exception is the
finding, and running the project's filters over the warnings it managed to issue
first could raise a second exception that would replace it.
"""

from typing import TYPE_CHECKING, Any, Never, Self, override

from lovely_assertions._core import Expect, describe_predicate
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting
from lovely_assertions._text import count_of, length_note, pattern_text, regex_matcher

if TYPE_CHECKING:
    import re
    from collections.abc import Callable, Sequence
    from contextlib import AbstractContextManager
    from types import TracebackType
    from warnings import WarningMessage

    from lovely_assertions._occurrence import Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = [
    "WarnedExpect",
    "allowed",
    "expect_warns",
    "issued_report",
    "matching",
    "reissue_unmatched",
    "warned_report",
]

#: Raised from the handle ``expect_warns`` yields, for as long as the block has
#: not finished. Anything else -- a placeholder subject, a bare ``AttributeError``
#: from the unset slot -- would leave the reader guessing. ``_callable.py`` says
#: the same thing about the same moment, in the same words.
_NOT_CAPTURED_YET = (
    "the warnings are only available after the `with expect_warns(...)` block has finished"
)


# ---------------------------------------------------------------------------
# Rendering -- failure path only.
#
# No f-strings here: an f-string is a message, and a message is only ever built
# inside the `_fail` call itself, so a passing assertion formats nothing.
# ---------------------------------------------------------------------------
def _rendered(value: object, /) -> str:
    """Render a value for a failure message, bounded by the formatting scope.

    Through :func:`~lovely_assertions.format_value` rather than ``repr``, so a
    warning class with a registered formatter reads as itself, and bounded by
    ``max_chars`` read at the moment of the failure rather than by a module
    constant -- a block that opened ``formatting(max_chars=...)`` asked for the
    longer rendering and gets it.

    ``_callable._rendered`` is the same helper against a fixed cap. The two are
    not shared because importing a private name across modules is what pyright
    reports as ``reportPrivateUsage``, and the suppression it would take costs
    more than the few lines it would save. Every subject module here --
    ``_enum``, ``_path``, ``_datetime``, ``_ordered``, ``_type`` -- carries its
    own ``rendered`` for that same reason.
    """
    text = format_value(value)
    limit = current_formatting().max_chars
    if len(text) <= limit:
        return text
    return text[:limit] + "..." + length_note(len(text))


def _located(record: "WarningMessage", /) -> str:
    """One warning, with the place ``stacklevel`` said it came from. Failure path only.

    The location is the half of a warning that a message usually drops, and it is
    the half that ends the search: two ``DeprecationWarning('deprecated')`` from
    different call sites are the same string and different findings. The filename
    is printed as recorded -- absolute, normally -- rather than shortened to a
    basename, because two files in a project share a basename often enough that a
    shortened one sends the reader to the wrong one.
    """
    return _rendered(record.message) + " at " + record.filename + ":" + str(record.lineno)


def _listed(records: "Sequence[WarningMessage]", /) -> str:
    """Lay a run of warnings out in a sentence, bounded and counted. Failure path only.

    The bound is ``max_items`` from the scope in force, and what is left out is
    counted rather than dropped silently: a message that truncates without saying
    so is a message the reader will trust wrongly. ``_callable._render_notes``
    does the same for an exception's notes.
    """
    limit = current_formatting().max_items
    shown = ", ".join([_located(record) for record in records[:limit]])
    if len(records) <= limit:
        return shown
    return shown + ", ... (" + str(len(records) - limit) + " more)"


def _messages_of(found: "tuple[Warning, ...]", /) -> str:
    """Describe the messages the captured warnings carried. Failure path only.

    The listing is the point. "No warning matched" is a fact the reader already
    had; *which* messages were there is the one they would otherwise go and print
    by hand, and the singular case gets a singular sentence because a message
    that says "the messages were 'x'" reads as one nobody looked at.
    """
    if not found:
        return "no warning was captured"
    if len(found) == 1:
        return "the message was " + _rendered(str(found[0]))
    limit = current_formatting().max_items
    shown = ", ".join([_rendered(str(warning)) for warning in found[:limit]])
    if len(found) <= limit:
        return "the messages were " + shown
    return "the messages were " + shown + ", ... (" + str(len(found) - limit) + " more)"


def warned_report(
    records: "Sequence[WarningMessage]", found: int, occurrences: "Occurrence | None", /
) -> str:
    """The tail of a failure that expected a warning and did not get it. **Failure path only.**

    Shared by the three sites that report it -- the context manager's ``__exit__``
    and ``CallableExpect.warns``, in both their constrained and unconstrained
    forms -- because a tail written three times is a tail that will read three
    ways. It takes the *pieces* and never a built message, so nothing is formatted
    until one of the branches below runs, and all of them are already inside a
    failure.

    The constrained form borrows ``CollectionExpect.contains``'s sentence --
    ``{describe()}, but found {n}: {listing}`` -- rather than inventing a second
    way to say the same thing, so a reader who has seen one occurrence failure has
    seen them all.
    """
    if occurrences is not None:
        # The leading space belongs to the constraint, not to the caller: without a
        # constraint the tail starts at the comma, so the two forms cannot share
        # one separator and the sentence has to carry it here.
        return " " + occurrences.describe() + ", but found " + str(found) + ": " + _issued(records)
    if not records:
        return ", but nothing was warned"
    return ", but the warnings issued were " + _listed(records)


def _issued(records: "Sequence[WarningMessage]", /) -> str:
    """The listing, or a phrase that fits where the listing would have gone."""
    if not records:
        return "no warnings at all"
    return _listed(records)


def issued_report(records: "Sequence[WarningMessage]", category: type[Warning], /) -> str:
    """The tail of a failure that expected *no* warning. **Failure path only.**

    Only the offending warnings are listed. The others were re-issued on the way
    out and are not what failed, so naming them here would pad the finding with
    the one thing the assertion deliberately did not care about.
    """
    offending = [record for record in records if isinstance(record.message, category)]
    if len(offending) == 1:
        return "issued " + _located(offending[0])
    return "issued " + count_of(len(offending), "warning") + ": " + _listed(offending)


# ---------------------------------------------------------------------------
# The capture, and the verdict over it
# ---------------------------------------------------------------------------
def matching[W: Warning](
    records: "Sequence[WarningMessage]", category: type[W], /
) -> "tuple[W, ...]":
    """The warnings of ``category`` among ``records``, in the order they were issued.

    A subclass counts, matching ``raises`` and ``isinstance`` and every other type
    test in this library; ``raises_exactly`` is where the other question lives,
    and no warning test has yet wanted it.

    A plain loop rather than a comprehension because this runs on a *passing*
    assertion, where the only allocation allowed is the iterator a ``for`` needs
    -- ``_text.holds_every`` states the same rule at more length. The tuple it
    returns is the assertion's product, not waste: it is the subject the caller
    goes on to assert against.

    ``WarningMessage.message`` is typed ``Warning | str`` and is a ``Warning``
    every time in practice -- ``warn_explicit`` instantiates the category before
    it records anything -- so the ``isinstance`` is a narrowing the checkers need
    rather than a check the runtime does.
    """
    found: list[W] = []
    for record in records:
        message = record.message
        if isinstance(message, category):
            found.append(message)
    return tuple(found)


def allowed(found: int, occurrences: "Occurrence | None", /) -> bool:
    """Whether ``found`` matching warnings satisfy the constraint.

    ``None`` means "at least one", which is what the assertion says when it is
    written without a count. It is not spelled ``at_least(1)`` internally because
    that would put "at least once" into every message that has no constraint in
    it, and the reader would go looking for the argument that produced it.
    """
    if occurrences is None:
        return found > 0
    return occurrences.allows(found)


def reissue_unmatched(records: "Sequence[WarningMessage]", category: type[Warning], /) -> None:
    """Hand every warning the assertion was not about back to the ambient filters.

    Called once the capture has been closed, so the project's own filters and
    ``showwarning`` are back in place and the warning goes where it would have
    gone without the block. The module docstring gives the reasoning and the two
    prices; what is here is the mechanics.

    ``warn_explicit`` rather than ``warn``: it takes the recorded filename and
    line number, so a re-issued warning still points at the code that issued it
    instead of at this function. ``registry=None`` is left to default, which makes
    ``warn_explicit`` use a throwaway dict -- there is no way to recover the
    module registry the original went through, and a fresh one shows the warning
    rather than hiding it, which is the safe direction to be wrong in.

    The instance is passed through as it stands, so its type, its arguments and
    anything a subclass carries survive. A ``str`` cannot reach here through
    ``warnings.warn`` -- see :func:`matching` -- but the annotation permits one,
    and re-wrapping it in the recorded category is precisely what ``warn_explicit``
    would have done with it.
    """
    import warnings  # noqa: PLC0415  (deferred: only a warning assertion pays for it)

    for record in records:
        message = record.message
        if isinstance(message, category):
            continue
        warnings.warn_explicit(
            message if isinstance(message, Warning) else record.category(message),
            record.category,
            record.filename,
            record.lineno,
            source=record.source,
        )


# ---------------------------------------------------------------------------
# The subject
# ---------------------------------------------------------------------------
class WarnedExpect[W: Warning](Expect[tuple[W, ...]]):
    """The warnings that were issued, as a subject.

    Everything on :class:`~lovely_assertions.Expect` already works here -- the
    subject is an ordinary tuple, so ``is_equal_to``, ``matches`` and
    ``satisfies`` apply to it as a whole -- and this class adds only the
    assertions that are about being a run of warnings.

    Those read "some warning", never "every warning". A call that deprecates one
    argument and defaults another issues two warnings and the test is about one of
    them; an assertion that quantified over all of them would fail on the warning
    the test was not written about. ``with_note_matching`` on the exception
    subject makes the same choice about notes, for the same reason.
    """

    __slots__ = ()

    @property
    def which(self) -> Self:
        """The warnings themselves: here a spelling, not a step.

        Elsewhere ``.which`` descends into a value an assertion *found*. ``warns``
        found the warnings and made them the subject already, so there is nothing
        to descend into; ``.which`` exists because
        ``warns(UserWarning).which.with_message("x")`` is how the assertion reads
        aloud, and it costs a property call that returns ``self``. ``RaisedExpect``
        carries the same property for the same reason.
        """
        return self

    # -- message -----------------------------------------------------------
    def with_message(self, pattern: "str | re.Pattern[str]", /, *, because: str = "") -> Self:
        """Assert some captured warning's message matches the regular expression ``pattern``.

        A ``re.search``, not a full match, exactly as ``StringExpect.matches`` and
        ``RaisedExpect.with_message``: ``with_message("deprecated")`` passes for
        ``"parse() is deprecated since 2.0"``. Anchor the pattern yourself when the
        whole message is meant.

        The message is ``str(warning)``, which is what the interpreter prints --
        not ``args[0]``, which is only sometimes the same thing.
        """
        matcher = regex_matcher(pattern)
        for warning in self._subject:
            if matcher.search(str(warning)) is not None:
                return self
        return self._fail(
            f"to have a message matching {_rendered(pattern_text(pattern))},"
            f" but {_messages_of(self._subject)}",
            because,
        )

    def with_message_containing(self, text: str, /, *, because: str = "") -> Self:
        """Assert some captured warning's message contains ``text`` -- a substring, no regex.

        The message is ``str(warning)``, as in :meth:`with_message`; reach for
        that one when the expectation is a regular expression rather than a
        literal fragment. One matching warning is enough, and the failure lists
        the message of every warning the subject holds, bounded like every other
        listing in a message.
        """
        for warning in self._subject:
            if text in str(warning):
                return self
        return self._fail(
            f"to have a message containing {_rendered(text)}, but {_messages_of(self._subject)}",
            because,
        )

    # -- predicate ---------------------------------------------------------
    def where(self, predicate: "Callable[[W], bool]", /, *, because: str = "") -> Self:
        """Assert some captured warning satisfies ``predicate``.

        The warning-flavoured spelling of ``matches``, and the reason ``warns``
        narrows to the category asked for: a warning class that carries fields --
        a removal version, an offending attribute name -- gets them checked here
        with the type the checker knows, where ``matches`` would hand the
        predicate the whole tuple.

        The expectation says "to satisfy", not "to warn something satisfying",
        because the subject name is not always the caller: reached through the
        callable form it is the thunk, and ``Expected legacy to warn something
        satisfying is_final, but ...`` reads as a claim about ``legacy`` that was
        never made. What was tested is named in the tail either way.
        """
        for warning in self._subject:
            if predicate(warning):
                return self
        return self._fail(
            f"to satisfy {describe_predicate(predicate)}, but {_unsatisfied(self._subject)}",
            because,
        )


def _unsatisfied(found: "tuple[Warning, ...]", /) -> str:
    """Say which warnings the predicate turned down. Failure path only.

    Separate from :func:`_messages_of` because a predicate is not about the
    message: it was handed the warning objects, so the objects are what the
    reader has to look at to see why none of them qualified.
    """
    if not found:
        return "no warning was captured"
    if len(found) == 1:
        return _rendered(found[0]) + " did not"
    limit = current_formatting().max_items
    shown = ", ".join([_rendered(warning) for warning in found[:limit]])
    if len(found) <= limit:
        return "none of them did: " + shown
    return "none of them did: " + shown + ", ... (" + str(len(found) - limit) + " more)"


class _CaughtWarnings[W: Warning](WarnedExpect[W]):
    """The handle :func:`expect_warns` yields: a subject that arrives late.

    It is the context manager *and* the subject, so ``as warned`` binds the object
    the assertions are made on. Its ``_subject`` slot stays unset until
    :meth:`__exit__` fills it, which is what makes an access from inside the block
    an error rather than a lie (see :meth:`__getattr__`). ``_callable._CaughtExpect``
    is the same design against exceptions, and the differences between the two are
    each noted where they appear.
    """

    #: Five attributes beyond the inherited subject: what the block was asked for,
    #: how many times, the reason to report if it does not happen, the open
    #: capture, and the log it is filling. Two more carry the soft-scope seam:
    #: ``_absorbed``, whether a soft scope has already collected this block's
    #: failure, at which point the rest of the chain has nothing left to say, and
    #: ``_stand_in``, the value a narrowing assertion is handed once it has.
    __slots__ = (
        "_absorbed",
        "_because",
        "_capture",
        "_expected",
        "_occurrences",
        "_records",
        "_stand_in",
    )

    def __init__(
        self, expected: type[W], occurrences: "Occurrence | None", because: str, /
    ) -> None:
        self._expected: type[W] = expected
        self._occurrences: Occurrence | None = occurrences
        self._because: str = because
        self._absorbed: bool = False
        # Named here rather than recovered from the source, which is the one place
        # this differs from `expect_raises`. Name recovery reads the *first
        # argument* of a call it recognises as an entry point, and the set of
        # entry points lives in `_names.py`; naming the category outright gets the
        # same "Expected UserWarning to ..." without that coupling, spares the
        # frame walk a failure would otherwise pay for, and says `UserWarning`
        # even where the caller passed the category in a variable.
        self._name = expected.__name__

    def __getattr__(self, name: str) -> Never:
        """Explain the one attribute that can legitimately be missing.

        ``_subject`` is an unset slot until the block finishes, so ``.subject``,
        ``__repr__`` and every inherited assertion land here when they are reached
        from *inside* the block. Saying why beats the bare ``AttributeError`` the
        slot would raise, and beats a placeholder even more: a placeholder would
        let the assertion run and report on nothing. Every other name is a typo
        and keeps the ``AttributeError`` it deserves.

        A plain ``RuntimeError``, where ``_callable`` needs a private subclass: its
        ``__exit__`` has to tell its own guard from a failure of the code under
        test, and this one does not -- any exception crossing the block means the
        block did not finish, and none of them is reported.
        """
        if name == "_subject":
            raise RuntimeError(_NOT_CAPTURED_YET)
        raise AttributeError(name)

    # -- the soft-scope seam -----------------------------------------------
    @override
    def _fail(
        self, expectation: str, because: str = "", /, *, cause: BaseException | None = None
    ) -> Self:
        """As ``Expect._fail``, unless the failure has already been reported.

        In a soft scope, :meth:`__exit__` collects its failure and execution
        carries on into a chain whose warnings were never captured. The object
        bound by ``as warned`` cannot be swapped for the stand-in that absorbs a
        narrowing failure elsewhere, so the absorbing happens here instead: one
        root cause, one message.

        Where ``_CaughtExpect`` also has to override ``where``, ``matches`` and
        ``satisfies``, this family does not. Those three hand the subject to a
        user's callable, and an exception subject has no harmless value to hand
        over -- so it gets the stand-in, whose every attribute is itself, and
        ``len(error.args)`` inside a predicate raises ``TypeError`` from inside the
        soft block. A tuple has ``()``, which is a real value of the declared type,
        and a predicate written for real warnings runs against no warnings without
        complaint -- so :meth:`__exit__` keeps ``()`` as the subject and those three
        need no guard.

        That does not reach the *narrowing* assertions. They hand their result to
        the rest of the chain rather than to a predicate, and what they owe it is a
        value that goes on absorbing, not one that is merely safe to read: ``()``
        would answer ``.which`` with an ``AttributeError``, which is not an
        ``AssertionError`` and so would escape the soft scope and lose every
        failure already collected. :meth:`_fail_narrowing` hands back the stand-in
        for exactly that reason.
        """
        if self._absorbed:
            return self
        return super()._fail(expectation, because, cause=cause)

    @override
    def _fail_narrowing(
        self, expectation: str, because: str = "", /, *, cause: BaseException | None = None
    ) -> Any:
        """As ``Expect._fail_narrowing``, absorbed once the failure has been reported.

        The stand-in and not the subject: see :meth:`_fail` for why the empty
        tuple that serves every other absorbed assertion cannot serve this one.
        """
        if self._absorbed:
            return self._stand_in
        return super()._fail_narrowing(expectation, because, cause=cause)

    # -- the context manager -----------------------------------------------
    def __enter__(self) -> "WarnedExpect[W]":
        """Open the capture. Everything about it is argued in the module docstring.

        ``action="always"`` is the 3.11 spelling of ``simplefilter("always")``
        inside the block, and is used in preference to calling ``simplefilter``
        by hand because it makes the filter change and its restoration one
        object's business rather than two statements that can be separated.
        """
        import warnings  # noqa: PLC0415  (deferred: only a warning assertion pays for it)

        capture = warnings.catch_warnings(record=True, action="always")
        self._capture: warnings.catch_warnings[list[WarningMessage]] = capture
        self._records: list[WarningMessage] = capture.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: "TracebackType | None",
        /,
    ) -> None:
        """Close the capture, then judge it -- and only if the block finished.

        The capture is closed first, unconditionally, so the process's filters and
        ``showwarning`` are restored whatever else happens here. An exception
        crossing the block means the block did not finish, so there is nothing to
        judge: the exception is the finding, and it travels. That is what
        ``pytest.warns`` does with the same situation, and what
        ``_CaughtExpect.__exit__`` does with a ``BaseException``.

        Returns ``None``, where ``_CaughtExpect.__exit__`` returns a ``bool``, and
        the difference is the whole of the difference between the two families.
        ``expect_raises`` suppresses the exception it was asked for, because that
        exception is its subject; a warning is not raised, so there is nothing here
        to suppress -- and suppressing a block's genuine exception because a
        warning assertion failed would hide the more interesting failure. Declared
        as ``None`` rather than as ``bool`` so that the promise is the signature
        rather than a sentence in a docstring; mypy asks for exactly that.
        """
        records = self._records
        self._capture.__exit__(exc_type, exc, traceback)
        if exc is not None:
            return
        found = matching(records, self._expected)
        reissue_unmatched(records, self._expected)
        if allowed(len(found), self._occurrences):
            self._subject = found
            return
        # The subject is filled in before the failure is reported, not after: in a
        # soft scope the report returns and the chain runs on, and it has to run
        # against a real value. The empty tuple is one -- "no warning matched" --
        # which is why the assertions that hand the subject to a callable of the
        # user's need no guard here.
        self._subject = ()
        # Reported through `_fail_narrowing` rather than `_fail` for its return
        # value alone -- the sentence is the same either way. What it hands back is
        # the stand-in that a narrowing assertion further down the chain has to be
        # given: `()` would answer the `.which` after it with an `AttributeError`,
        # which crosses the soft scope instead of being absorbed inside it.
        self._stand_in: Any = self._fail_narrowing(
            f"to be warned{warned_report(records, len(found), self._occurrences)}", self._because
        )
        # Only reached inside a soft scope; the report raised otherwise. The
        # failure is on the report, so everything downstream of it has one root
        # cause already named and nothing of its own to add.
        self._absorbed = True


def expect_warns[W: Warning](
    category: type[W], /, *, occurrences: "Occurrence | None" = None, because: str = ""
) -> "AbstractContextManager[WarnedExpect[W]]":
    """Assert that the block issues a warning of ``category``; continue on the warnings.

        with expect_warns(DeprecationWarning) as warned:
            legacy()
        warned.with_message_containing("use parse_iso instead")

    The primary form, because it sits where ``pytest.warns`` sits: the code under
    test stays a statement instead of being folded into a lambda. What it does
    that ``pytest.warns`` does not is listed in the module docstring, at the top
    of this file, along with the cases where ``pytest.warns`` is the better
    answer.

    A subclass of ``category`` counts. ``expect_warns(Warning)`` is how "any
    warning at all" is spelled -- there is no default, for the reason
    ``expect_raises`` has none: an assertion whose subject is implicit is an
    assertion whose failure message has nothing to name.

    ``occurrences`` takes a count constraint -- ``occurrences=exactly(2)``,
    ``at_least(1)``, ``at_most(3)`` -- and counts only warnings of ``category``.
    Without it the assertion means "at least one".

    Inside the block there are no warnings yet, so ``warned.subject`` raises a
    ``RuntimeError`` that says so. The declared return type is a plain context
    manager over :class:`WarnedExpect`, which is what the ``as`` binding needs; the
    handle's own class is an implementation detail.
    """
    return _CaughtWarnings(category, occurrences, because)
