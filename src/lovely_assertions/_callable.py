"""Assertions for callables and the exceptions they raise.

Two entry forms land on the same subject. The **callable form** wraps a thunk,
``expect(lambda: parse("x")).raises(ValueError)``; the **context-manager form**
is the primary one, and sits where ``pytest.raises`` sits::

    with expect_raises(ValueError) as caught:
        parse("x")
    caught.with_message_containing("invalid")

Both hand back a :class:`RaisedExpect`, whose subject *is* the caught exception,
so the whole generic catalogue applies to it.

Several rules run through the module.

**The real exception is never dropped.** When the call raises something other
than what was asked for, that exception's traceback is the most valuable thing on
screen, so every failure reported from inside an ``except`` hands it to ``_fail``
as ``cause=`` and the ``AssertionFailure`` is raised ``from`` it. The message
explains the test, the ``__cause__`` explains the code, and neither is paid for
until something actually fails.

**``BaseException`` is not ``Exception``.** The wrong-type branches and
``does_not_raise()`` catch ``Exception`` only. A ``KeyboardInterrupt`` means the
user pressed Ctrl-C and a ``SystemExit`` means something called ``sys.exit``;
turning either into an assertion failure would hijack the interpreter's own
control flow. Ask for one by name -- ``raises(SystemExit)``,
``does_not_raise(KeyboardInterrupt)`` -- and it is caught, because then it is the
subject of the test rather than an interruption of it.

**A cause is ``__cause__`` first, ``__context__`` second.** ``raise X from Y``
sets ``__cause__`` and a bare ``raise`` inside an ``except`` sets ``__context__``;
both are what a reader calls "the inner exception", so :meth:`RaisedExpect.with_cause`
looks at both and every failure it reports names the attribute it looked at.

**``__notes__`` is absent until the first ``add_note``** (PEP 678), so it is read
with :func:`_notes_of` and never with an attribute access. Every note assertion
lists the notes that *were* attached, because when the expected one is missing
that listing is the entire finding -- and ``pytest.raises`` offers nothing here
at all, so a reader who lands on a failure has nowhere else to have looked.

**Warnings live here too, and only their callable form does.** ``warns`` and
``does_not_warn`` sit beside ``raises`` and ``does_not_raise`` at the bottom of
:class:`CallableExpect`; everything they are made of -- the capture, the verdict,
the listing, :class:`~lovely_assertions._warnings.WarnedExpect` and the
``expect_warns`` block -- is in :mod:`lovely_assertions._warnings`, whose module
docstring argues the design. They are written here rather than there for one
reason: an ``async def`` handed to a synchronous assertion has to be refused, and
:func:`_reject_awaitable` is that refusal. A second copy of it in another module
would be a second thing to keep in step with the first.
"""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Never, Self, cast, override

from lovely_assertions._core import Expect, describe_predicate
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._text import length_note, pattern_text, regex_matcher
from lovely_assertions._warnings import (
    WarnedExpect,
    allowed,
    issued_report,
    matching,
    reissue_unmatched,
    warned_report,
)

if TYPE_CHECKING:
    import re
    from contextlib import AbstractContextManager
    from types import TracebackType

    from lovely_assertions._occurrence import Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["CallableExpect", "RaisedExpect", "expect_raises"]

#: Longest rendering kept in full in a failure message. An exception message can
#: be a whole serialised payload, and a message that dumps one hides the finding
#: instead of explaining it. 120 characters is about a terminal line, the same cap
#: the string subject uses.
_MAX_RENDERED = 120

#: Raised from the handle ``expect_raises`` yields, for as long as the block has
#: not finished. Anything else -- a placeholder subject, a bare ``AttributeError``
#: from the unset slot -- would leave the reader guessing.
_NOT_CAUGHT_YET = (
    "the exception is only available after the `with expect_raises(...)` block has finished"
)


class _TooEarlyError(RuntimeError):
    """Raised when the handle is asked for its exception before the block ends.

    A ``RuntimeError`` as promised, and a private subclass so that :meth:`_CaughtExpect.__exit__`
    can tell its own guard from a failure of the code under test and let it
    travel unreported -- "the exception is only available afterwards" is already
    the whole finding, and wrapping it in "the wrong exception was raised" would
    bury it.
    """

    __slots__ = ()


#: Where :func:`_cause_of` found what it found, named as the reader will see it in
#: a traceback. ``_SUPPRESSED`` is the ``raise ... from None`` case: there is a
#: ``__context__``, and the author of the code said not to treat it as the cause.
_FROM_CAUSE = "__cause__"
_FROM_CONTEXT = "__context__"
_SUPPRESSED = "suppressed"
_NO_CAUSE = "none"

#: Longest run of notes listed in a failure message, matching the collection
#: subject's budget. A retry loop that adds a note per attempt can attach a great
#: many, and a message that dumps all of them hides the finding instead of
#: explaining it.
_MAX_NOTES = 10


# ---------------------------------------------------------------------------
# Helpers -- failure path only.
#
# No f-strings here: an f-string is a message, and a message is only ever built
# inside the `_fail` call itself, so a passing assertion formats nothing.
# ---------------------------------------------------------------------------
def _rendered(value: object, /) -> str:
    """Render a value for a failure message, eliding an over-long one.

    One helper for exceptions, messages, notes and return values alike, and all
    of them go through :func:`~lovely_assertions.format_value`, so a project that
    registered a formatter for its own exception type reads it here as it reads
    it everywhere else. When nothing claims the value the rendering is its
    ``repr``, so a message keeps its quotes and an exception keeps its type.

    A ``str`` nothing claimed is clipped *before* it is rendered, which is how
    the string subject does it. Clipping the rendering instead cuts the closing
    quote -- or the middle of an escape sequence -- in half, and counts the two
    quotes towards the length it reports back, so a 300-character message would
    be reported as 302 characters long. Everything else is clipped after, because
    a partial rendering is the only one such a value has.

    A hostile ``__repr__`` costs the reader detail and nothing more:
    ``format_value`` describes such a value by its type rather than raising. That
    is the contract this needs, not laziness -- the assertion has *already*
    failed, and an error thrown while reporting it would also throw away the
    ``__cause__`` that was about to explain it.
    """
    text = format_value(value)
    # A rendering identical to the `repr` means the registry declined, so the
    # careful clip below applies to a string this module is rendering itself. A
    # formatter that did claim it owns the rendering, which is clipped like any
    # other.
    if isinstance(value, str) and text == repr(value):
        if len(value) <= _MAX_RENDERED:
            return text
        return repr(value[:_MAX_RENDERED] + "...") + length_note(len(value))
    if len(text) <= _MAX_RENDERED:
        return text
    return text[:_MAX_RENDERED] + "..." + length_note(len(text))


def _cause_of(exception: BaseException, /) -> tuple[BaseException | None, str]:
    """The exception's cause, and the name of the attribute it came from.

    ``__cause__`` wins over ``__context__``: it is the one the code stated
    explicitly with ``raise X from Y``, where ``__context__`` is whatever
    happened to be in flight. ``raise X from None`` is honoured as the denial it
    is -- the context is still there, but reporting it as the cause would
    contradict the code -- and is reported as suppressed rather than as absent.
    """
    cause = exception.__cause__
    if cause is not None:
        return cause, _FROM_CAUSE
    context = exception.__context__
    if context is None:
        return None, _NO_CAUSE
    if exception.__suppress_context__:
        return None, _SUPPRESSED
    return context, _FROM_CONTEXT


def _notes_of(exception: BaseException, /) -> "list[str] | None":
    """The exception's PEP 678 notes, or ``None`` when it has none.

    ``__notes__`` does not exist until the first ``add_note``, so this is a
    ``getattr`` with a default rather than an attribute access -- an exception
    with no notes is the ordinary case, not an error to catch.

    The annotation is what typeshed and PEP 678 promise, and the ``isinstance``
    is what actually holds: CPython's ``add_note`` refuses to append to anything
    that is not a ``list``, so a ``__notes__`` of some other shape was never
    built by the documented API. It also catches the one value the library itself
    can put there -- the stand-in a soft scope hands back after a failed
    ``expect_raises``, whose every attribute is itself. Iterating that would raise
    a ``TypeError`` from inside a soft block and cost the scope its whole report.
    """
    notes: list[str] | None = getattr(exception, "__notes__", None)
    return notes if isinstance(notes, list) else None


def _render_notes(notes: "list[str] | None", /) -> str:
    """Describe the notes an exception carried. Failure path only.

    The listing is the point of these messages. "No note matched" is a fact the
    reader already had; *which* notes were there is the one they have to go and
    look up otherwise, and PEP 678 notes exist precisely because they carry the
    context that explains the failure.
    """
    if not notes:
        return "it carried no notes"
    if len(notes) == 1:
        return "its only note was " + _rendered(notes[0])
    shown = ", ".join(_rendered(note) for note in notes[:_MAX_NOTES])
    if len(notes) <= _MAX_NOTES:
        return "its notes were " + shown
    return "its notes were " + shown + ", ... (" + str(len(notes) - _MAX_NOTES) + " more)"


def _is_awaitable(value: object, /) -> bool:
    """Whether ``value`` is awaitable.

    Deliberately a plain ``bool`` and not a ``TypeIs``: a narrowing return would
    re-type the caller's variable to ``Awaitable[Unknown]``, which is the one
    thing pyright's strict mode will not accept being passed on. Nothing
    downstream needs the narrowed type.
    """
    return isinstance(value, Awaitable)


def _close_quietly(value: object, /) -> None:
    """Close a coroutine that will never be awaited.

    Without it the reader is handed a "coroutine was never awaited" warning from
    somewhere unrelated to the test that caused it. Takes ``object`` rather than
    narrowing to ``Coroutine`` on purpose: a parameterised generic is exactly the
    shape pyright calls partially unknown and mypy calls a redundant cast, and
    neither checker needs an opinion here. Anything without ``close`` -- a Future,
    a custom ``__await__`` -- is not ours to close anyway.
    """
    close = getattr(value, "close", None)
    if callable(close):
        close()


def _reject_awaitable(returned: object, /) -> None:
    """Refuse a result that was never actually run.

    Calling an ``async def`` returns a coroutine without executing a line of its
    body, so a synchronous exception assertion sees no exception and reports
    success. Without this refusal ``expect(async_fn).does_not_raise()`` passes for
    a function that raises unconditionally -- a green test that asserts nothing,
    which is the one outcome this library exists to prevent.

    Raised, not reported: handing an async callable to a synchronous assertion is
    a mistake in the test, and an ``AssertionFailure`` would present it as a
    finding about the subject. The coroutine is closed on the way out so the
    reader is not also handed a "never awaited" warning from somewhere else
    entirely.
    """
    if not _is_awaitable(returned):
        return
    _close_quietly(returned)
    message = (
        "the callable returned a coroutine without running: an async callable "
        "cannot be asserted on synchronously. Await it and assert on the result, "
        "or assert on a lambda that runs it -- expect(lambda: asyncio.run(fn()))"
    )
    raise TypeError(message)


class CallableExpect(Expect[Callable[..., object]]):
    """Assertions about what calling the subject does.

    The subject is normally a zero-argument thunk -- ``lambda: parse("x")`` --
    because the assertion has to do the calling itself. A callable that needs
    arguments is wrapped in one; a generator function needs draining as well, and
    ``expect(lambda: list(rows()))`` is how: calling a generator function only
    builds a generator, so nothing it would raise has happened yet.

    Every assertion here calls the subject exactly once, so a chain of them calls
    it once per link -- which is what a reader wants from a thunk and what makes a
    callable with side effects worth wrapping in a fresh lambda each time.
    """

    __slots__ = ()

    # -- raising -----------------------------------------------------------
    def raises[E: BaseException](
        self, exception_type: type[E], /, *, because: str = ""
    ) -> "RaisedExpect[E]":
        """Assert the call raises ``exception_type`` or a subclass; continue on the exception.

        The exception becomes the new subject, so ``.which``, ``.and_`` and every
        generic assertion apply to it. When the call raises something else, the
        failure is raised *from* that exception: its traceback is what will
        actually explain the test, and losing it would be the expensive half of
        the report.

        A ``KeyboardInterrupt`` or a ``SystemExit`` that was not asked for is left
        to travel; name one as ``exception_type`` and it is caught like anything
        else, because then it is the subject of the test rather than the run being
        cut short. Handing over an ``async def`` raises :class:`TypeError` instead
        of reporting a failure -- calling one returns a coroutine without running a
        line of its body, so there was never anything to raise.

        :meth:`raises_exactly` is the same assertion with subclasses excluded.
        """
        try:
            returned = self._subject()
        except (exception_type, Exception) as actual:
            # The tuple is "what was asked for" plus "what an ordinary bug looks
            # like". Everything outside it -- KeyboardInterrupt, SystemExit --
            # is the interpreter talking and is left to travel.
            if isinstance(actual, exception_type):
                return RaisedExpect(actual)
            return cast(
                "RaisedExpect[E]",
                self._fail_narrowing(
                    f"to raise {exception_type.__name__}, but raised {_rendered(actual)}",
                    because,
                    cause=actual,
                ),
            )
        else:
            _reject_awaitable(returned)
            return cast(
                "RaisedExpect[E]",
                self._fail_narrowing(
                    f"to raise {exception_type.__name__}, but nothing was raised"
                    f" (the call returned {_rendered(returned)})",
                    because,
                ),
            )

    def raises_exactly[E: BaseException](
        self, exception_type: type[E], /, *, because: str = ""
    ) -> "RaisedExpect[E]":
        """Assert the call raises ``exception_type`` itself -- a subclass does not count.

        The test is on the type object, so ``raises_exactly(Exception)`` is not
        satisfied by a ``ValueError``. Reach for :meth:`raises` unless the point of
        the test is *which* exception the code chose; everything else is the same,
        including the exception becoming the new subject and a wrong-type failure
        being raised from the real exception so its traceback survives.
        """
        try:
            returned = self._subject()
        except (exception_type, Exception) as actual:
            # The type is read into a name first, as `is_exactly_instance_of`
            # does: comparing the type object is what "exactly" means, and it
            # leaves the cast below stating what neither checker can derive.
            actual_type = type(actual)
            if actual_type is exception_type:
                return RaisedExpect(cast("E", actual))
            return cast(
                "RaisedExpect[E]",
                self._fail_narrowing(
                    f"to raise exactly {exception_type.__name__}, but raised {_rendered(actual)}",
                    because,
                    cause=actual,
                ),
            )
        else:
            _reject_awaitable(returned)
            return cast(
                "RaisedExpect[E]",
                self._fail_narrowing(
                    f"to raise exactly {exception_type.__name__}, but nothing was raised"
                    f" (the call returned {_rendered(returned)})",
                    because,
                ),
            )

    def does_not_raise(
        self, exception_type: type[BaseException] | None = None, /, *, because: str = ""
    ) -> Self:
        """Assert the call raises nothing, or nothing of type ``exception_type``.

        The optional argument is a default rather than an overload pair: both
        forms take the same subject and return the same ``Self``, so overloads
        would buy one thing only -- rejecting a literal ``None`` -- at the price
        of a doubled signature. Passing ``None`` explicitly means what it reads
        as: no filter, so nothing may escape.

        With no argument the assertion catches ``Exception``, not
        ``BaseException``: a ``KeyboardInterrupt`` or a ``SystemExit`` crossing
        the call is the interpreter's business, and reporting "it raised" for a
        Ctrl-C would swallow the interruption. Name one to test for it.

        With an argument, exceptions of *other* types travel on untouched -- the
        assertion is about that type, and burying an unrelated error under it
        would hide the more interesting failure.
        """
        unwanted: type[BaseException] = Exception if exception_type is None else exception_type
        try:
            returned = self._subject()
        except unwanted as actual:
            if exception_type is None:
                return self._fail(
                    f"not to raise, but raised {_rendered(actual)}", because, cause=actual
                )
            return self._fail(
                f"not to raise {exception_type.__name__}, but raised {_rendered(actual)}",
                because,
                cause=actual,
            )
        else:
            _reject_awaitable(returned)
            return self

    # -- warning -----------------------------------------------------------
    def warns[W: Warning](
        self,
        category: type[W],
        /,
        *,
        occurrences: "Occurrence | None" = None,
        because: str = "",
    ) -> "WarnedExpect[W]":
        """Assert the call issues a warning of ``category``; continue on the warnings.

            expect(legacy).warns(DeprecationWarning).with_message_containing("removed in 3.0")

        The callable-form twin of ``expect_warns``, which is the primary spelling;
        everything about what is captured, what is restored, and what happens to
        warnings of other categories is argued in :mod:`lovely_assertions._warnings`.

        A subclass counts, and ``occurrences`` takes a count constraint
        (``exactly(2)``, ``at_least(1)``) over the warnings of ``category`` alone.
        Without one, the assertion means "at least one".

        The subject becomes the warnings that were issued -- a tuple, because a
        call may issue several where it can raise only one -- typed as
        ``category``, so a warning class that carries fields gets them checked in
        ``.where(...)`` with the type the checker knows.

        **One thing the context-manager form does better**, said here because it is
        visible in the failure message and would otherwise look like a bug.
        ``warnings.warn(..., stacklevel=2)`` reports the *caller* of the function
        that warned, and in this form that caller is the thunk's invocation --
        inside this method. So a failure lists the location as ``_callable.py``
        rather than as the test's own line. ``expect_warns`` has no such frame in
        between and reports the block. This is not fixable from here: the frame the
        warning names is chosen by the code that issued it, and a thunk really is
        called from a different place than a ``with`` body.
        """
        import warnings  # noqa: PLC0415  (deferred: only a warning assertion pays for it)

        with warnings.catch_warnings(record=True, action="always") as records:
            returned = self._subject()
        _reject_awaitable(returned)
        found = matching(records, category)
        reissue_unmatched(records, category)
        if allowed(len(found), occurrences):
            return WarnedExpect(found)
        return cast(
            "WarnedExpect[W]",
            self._fail_narrowing(
                f"to warn {category.__name__}{warned_report(records, len(found), occurrences)}",
                because,
            ),
        )

    def does_not_warn(self, category: type[Warning] | None = None, /, *, because: str = "") -> Self:
        """Assert the call issues no warning, or none of type ``category``.

        The assertion ``pytest.warns`` has no spelling for at all: it can only say
        that something *did* warn, so "this call must stop deprecating" otherwise
        gets written by hand around a ``catch_warnings`` block.

        The optional argument is a default rather than an overload pair, for the
        reason :meth:`does_not_raise` gives: both forms take the same subject and
        return the same ``Self``. Passing ``None`` explicitly means what it reads
        as -- no filter, so nothing at all may be issued.

        With an argument, warnings of *other* categories are re-issued to the
        project's own filters on the way out rather than swallowed, which is the
        warning-shaped version of ``does_not_raise``'s "exceptions of other types
        travel on untouched". Under ``-W error`` that re-issue raises, at the end
        of the assertion rather than in the middle of the call -- the module
        docstring in :mod:`lovely_assertions._warnings` argues why that is the
        faithful answer rather than the convenient one.
        """
        import warnings  # noqa: PLC0415  (deferred: only a warning assertion pays for it)

        unwanted: type[Warning] = Warning if category is None else category
        with warnings.catch_warnings(record=True, action="always") as records:
            returned = self._subject()
        _reject_awaitable(returned)
        found = matching(records, unwanted)
        reissue_unmatched(records, unwanted)
        if not found:
            return self
        if category is None:
            return self._fail(f"not to warn, but {issued_report(records, unwanted)}", because)
        return self._fail(
            f"not to warn {category.__name__}, but {issued_report(records, unwanted)}", because
        )


class RaisedExpect[E: BaseException](Expect[E]):
    """The exception that was raised, as a subject.

    Everything on :class:`~lovely_assertions.Expect` already works here --
    ``is_instance_of``, ``satisfies``, ``is_equal_to`` on ``.args`` through
    ``.subject`` -- so this class adds only what is about being an exception.
    """

    __slots__ = ()

    @property
    def which(self) -> Self:
        """The exception itself: here a spelling, not a step.

        Elsewhere ``.which`` descends into a value an assertion *found*. ``raises``
        found the exception and made it the subject already, so there is nothing
        to descend into; ``.which`` exists because
        ``raises(ValueError).which.with_message("x")`` is how the assertion reads
        aloud, and it costs a property call that returns ``self``.
        """
        return self

    # -- message -----------------------------------------------------------
    def with_message(self, pattern: "str | re.Pattern[str]", /, *, because: str = "") -> Self:
        """Assert the exception's message matches the regular expression ``pattern``.

        A ``re.search``, not a full match, exactly as ``StringExpect.matches``:
        ``with_message("invalid")`` passes for ``"invalid literal for int()"``.
        Anchor the pattern yourself when the whole message is meant. The message
        is ``str(exception)``, which is what a traceback prints -- not
        ``args[0]``, which is only sometimes the same thing.
        """
        message = str(self._subject)
        if regex_matcher(pattern).search(message) is not None:
            return self
        return self._fail(
            f"to have a message matching {_rendered(pattern_text(pattern))},"
            f" but the message was {_rendered(message)}",
            because,
        )

    def with_message_containing(self, text: str, /, *, because: str = "") -> Self:
        """Assert the exception's message contains ``text`` -- a plain substring, no regex.

        The message is ``str(exception)``, as in :meth:`with_message`; reach for
        that one when the expectation is a regular expression rather than a
        literal fragment, and for this one when the fragment contains characters a
        pattern would give meaning to. The failure quotes the whole message it
        searched, elided if it is very long.
        """
        message = str(self._subject)
        if text in message:
            return self
        return self._fail(
            f"to have a message containing {_rendered(text)},"
            f" but the message was {_rendered(message)}",
            because,
        )

    # -- notes (PEP 678) ---------------------------------------------------
    def with_note(self, text: str, /, *, because: str = "") -> Self:
        """Assert the exception carries ``text`` as one of its notes, exactly.

        ``exc.add_note(...)`` is how a library on Python 3.11+ attaches context to
        an exception it re-raises, and the note is often the only place the
        interesting detail lives. The match is on the whole note, not a substring
        of one: :meth:`with_note_matching` is the search.
        """
        notes = _notes_of(self._subject)
        if notes is not None and text in notes:
            return self
        return self._fail(
            f"to carry the note {_rendered(text)}, but {_render_notes(notes)}", because
        )

    def with_note_matching(
        self,
        pattern: "str | re.Pattern[str]",
        /,
        *,
        because: str = "",
    ) -> Self:
        """Assert some note matches the regular expression ``pattern``.

        A ``re.search`` per note, not a full match, exactly as
        :meth:`with_message`: ``with_note_matching("attempt 3")`` finds it inside
        ``"failed on attempt 3 of 3"``. Anchor the pattern yourself when a whole
        note is meant.
        """
        notes = _notes_of(self._subject)
        if notes is not None:
            matcher = regex_matcher(pattern)
            for note in notes:
                if matcher.search(note) is not None:
                    return self
        return self._fail(
            f"to carry a note matching {_rendered(pattern_text(pattern))},"
            f" but {_render_notes(notes)}",
            because,
        )

    def has_no_notes(self, *, because: str = "") -> Self:
        """Assert nothing has been attached to the exception with ``add_note``.

        Worth asserting because a note is invisible until something prints the
        traceback: an exception that has quietly accumulated retry context is a
        different exception from the one the test meant to provoke.
        """
        notes = _notes_of(self._subject)
        if not notes:
            return self
        return self._fail(f"to carry no notes, but {_render_notes(notes)}", because)

    # -- cause -------------------------------------------------------------
    def with_cause[C: BaseException](
        self, exception_type: type[C], /, *, because: str = ""
    ) -> "RaisedExpect[C]":
        """Assert the exception has a cause of type ``exception_type``; continue on the cause.

        ``__cause__`` first, then ``__context__`` (see :func:`_cause_of`), and
        the failure names which of the two it looked at -- "it has no cause" and
        "its cause is a TypeError that happened to be in flight" are different
        findings and deserve different messages.
        """
        found, source = _cause_of(self._subject)
        if isinstance(found, exception_type):
            return RaisedExpect(found)
        if found is not None:
            return cast(
                "RaisedExpect[C]",
                self._fail_narrowing(
                    f"to have a cause of type {exception_type.__name__},"
                    f" but {source} was {_rendered(found)}",
                    because,
                ),
            )
        return cast("RaisedExpect[C]", self._fail_no_cause(exception_type, source, because))

    def with_cause_exactly[C: BaseException](
        self, exception_type: type[C], /, *, because: str = ""
    ) -> "RaisedExpect[C]":
        """Assert the cause is ``exception_type`` itself -- a subclass does not count.

        ``__cause__`` first, then ``__context__``, exactly as :meth:`with_cause`,
        and the cause becomes the new subject. With no cause at all the finding is
        the absence rather than the type, so the message is the one
        :meth:`with_cause` gives: it says whether the context was suppressed with
        ``raise ... from None`` or simply never set. Reach for :meth:`with_cause`
        unless the point of the test is which exception type the code wrapped.
        """
        found, source = _cause_of(self._subject)
        found_type = type(found)
        if found_type is exception_type:
            return RaisedExpect(cast("C", found))
        if found is not None:
            return cast(
                "RaisedExpect[C]",
                self._fail_narrowing(
                    f"to have a cause of exactly {exception_type.__name__},"
                    f" but {source} was {_rendered(found)}",
                    because,
                ),
            )
        return cast("RaisedExpect[C]", self._fail_no_cause(exception_type, source, because))

    def _fail_no_cause(
        self, exception_type: type[BaseException], source: str, because: str, /
    ) -> Any:  # noqa: ANN401  (the stand-in a soft scope hands back is deliberately untyped)
        """Report a missing cause. **Failure path only**, and shared by both cause assertions.

        A helper is safe here where it would not be for the general case: it
        takes the *pieces*, never a built message, so nothing is formatted until
        one of the branches below runs -- and both of them are already inside a
        failure. It says "of type" for :meth:`with_cause_exactly` too: with no
        cause at all, the difference between "of type" and "of exactly" has
        nothing to bite on, and the finding is the absence either way.
        """
        if source == _SUPPRESSED:
            return self._fail_narrowing(
                f"to have a cause of type {exception_type.__name__},"
                f" but its context was suppressed with `raise ... from None`",
                because,
            )
        return self._fail_narrowing(
            f"to have a cause of type {exception_type.__name__},"
            f" but neither __cause__ nor __context__ was set",
            because,
        )

    # -- predicate ---------------------------------------------------------
    def where(self, predicate: "Callable[[E], bool]", /, *, because: str = "") -> Self:
        """Assert the exception satisfies ``predicate``.

        The exception-flavoured spelling of ``matches``: FluentAssertions' ``Where``
        is where the attributes a specific exception carries -- ``errno``,
        ``response.status_code`` -- get asserted on, and the predicate is typed
        with the exception type ``raises`` narrowed to.

        The expectation says "to satisfy", not "to raise an exception
        satisfying", because the subject name is not always the caller: reached
        through ``with_cause`` it is the *outer* call, and
        ``Expected chained to raise an exception satisfying is_fatal, but
        KeyError('k') did not`` says that ``chained`` raised a ``KeyError``, which
        it did not. What was tested is named in the tail either way.
        """
        subject = self._subject
        if predicate(subject):
            return self
        return self._fail(
            f"to satisfy {describe_predicate(predicate)}, but {_rendered(subject)} did not",
            because,
        )


class _CaughtExpect[E: BaseException](RaisedExpect[E]):
    """The handle :func:`expect_raises` yields: a subject that arrives late.

    It is the context manager *and* the subject, so ``as caught`` binds the object
    the assertions are made on. Its ``_subject`` slot stays unset until
    :meth:`__exit__` fills it, which is what makes an access from inside the block
    an error rather than a lie (see :meth:`__getattr__`).
    """

    #: Three attributes beyond the inherited subject, each of them a piece of
    #: state the subject cannot carry: what the block was asked to raise, the
    #: reason to report if it does not, and whether a soft scope has already
    #: collected that failure -- at which point the rest of the chain has nothing
    #: left to say.
    __slots__ = ("_absorbed", "_because", "_expected")

    def __init__(self, expected: type[E], because: str, /) -> None:
        self._expected: type[E] = expected
        self._because: str = because
        self._absorbed: bool = False

    def __getattr__(self, name: str) -> Never:
        """Explain the one attribute that can legitimately be missing.

        ``_subject`` is an unset slot until the block finishes, so ``.subject``,
        ``__repr__`` and every inherited assertion land here when they are reached
        from *inside* the block. Saying why beats the bare ``AttributeError`` the
        slot would raise, and beats a placeholder even more: a placeholder would
        let the assertion run and report on nothing. Every other name is a typo
        and keeps the ``AttributeError`` it deserves.
        """
        if name == "_subject":
            raise _TooEarlyError(_NOT_CAUGHT_YET)
        raise AttributeError(name)

    # -- the soft-scope seam -----------------------------------------------
    @override
    def _fail(
        self, expectation: str, because: str = "", /, *, cause: BaseException | None = None
    ) -> Self:
        """As ``Expect._fail``, unless the failure has already been reported.

        In a soft scope, ``__exit__`` collects its failure and execution carries
        on into a chain whose subject never existed. ``_ABSORBING`` solves that
        for a returned subject, but the object bound by ``as caught`` cannot be
        swapped, so the absorbing happens here instead: one root cause, one
        message.
        """
        if self._absorbed:
            return self
        return super()._fail(expectation, because, cause=cause)

    @override
    def _fail_narrowing(
        self, expectation: str, because: str = "", /, *, cause: BaseException | None = None
    ) -> Any:
        """As ``Expect._fail_narrowing``, absorbed once the failure has been reported."""
        if self._absorbed:
            return self._subject
        return super()._fail_narrowing(expectation, because, cause=cause)

    def _absorb(self, stand_in: Any, /) -> None:  # noqa: ANN401  (the stand-in is Any by design)
        """Keep what a soft scope handed back, and stop asserting.

        Only reached when ``_fail_narrowing`` collected instead of raising: the
        stand-in it returns is the same one every other narrowing assertion
        hands back, which is how the rest of the chain gets absorbed rather than
        reporting a second failure derived from the first.
        """
        self._subject = cast("E", stand_in)
        self._absorbed = True

    # -- user callables, once there is no subject to hand them ---------------
    @override
    def where(self, predicate: Callable[[E], bool], /, *, because: str = "") -> Self:
        """As :meth:`RaisedExpect.where`, unless the failure was already reported.

        These three are the assertions that hand the subject to a callable of the
        user's, and the stand-in cannot survive being handed to one: every
        attribute of it is itself, so ``len(error.args)`` in a predicate written
        for a real exception raises ``TypeError`` from inside the soft block. That
        aborts the scope, which then reports *nothing* -- the collected failures
        included. Absorbed means there is nothing left to ask about, so nothing
        is asked.
        """
        if self._absorbed:
            return self
        return super().where(predicate, because=because)

    @override
    def matches(self, predicate: Callable[[E], bool], /, *, because: str = "") -> Self:
        """As ``Expect.matches``, absorbed once the failure has been reported."""
        if self._absorbed:
            return self
        return super().matches(predicate, because=because)

    @override
    def satisfies(self, inspector: Callable[[E], object], /, *, because: str = "") -> Self:
        """As ``Expect.satisfies``, absorbed once the failure has been reported."""
        if self._absorbed:
            return self
        return super().satisfies(inspector, because=because)

    # -- the context manager -----------------------------------------------
    def __enter__(self) -> "RaisedExpect[E]":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: "TracebackType | None",
        /,
    ) -> bool:
        if isinstance(exc, _TooEarlyError):
            # Our own guard, tripped inside the block. It says everything there
            # is to say; reporting it as "the wrong exception" would not.
            return False
        if exc is None:
            self._absorb(
                self._fail_narrowing("to be raised, but nothing was raised", self._because)
            )
            return False
        if isinstance(exc, self._expected):
            self._subject = exc
            return True
        if not isinstance(exc, Exception):
            # A KeyboardInterrupt or a SystemExit is not a finding about the
            # block; it is the run being cut short. Let it travel.
            return False
        self._absorb(
            self._fail_narrowing(
                f"to be raised, but {_rendered(exc)} was raised instead", self._because, cause=exc
            )
        )
        # Soft scope only: the failure is collected, so suppress the exception
        # rather than let it out to abort a block that is meant to keep going.
        return True


def expect_raises[E: BaseException](
    exception_type: type[E], /, *, because: str = ""
) -> "AbstractContextManager[RaisedExpect[E]]":
    """Assert that the block raises ``exception_type``; continue on the exception.

        with expect_raises(ValueError) as caught:
            parse("x")
        caught.with_message_containing("invalid")

    The primary form, because it sits where ``pytest.raises`` sits: the code
    under test stays a statement instead of being folded into a lambda. It
    differs from ``pytest.raises`` on the wrong-type case, which it reports as
    the assertion failure it is, with the real exception attached as the cause,
    rather than letting it pass for whatever the runner makes of it.

    Inside the block there is no exception yet, so ``caught.subject`` raises a
    ``RuntimeError`` that says so. The declared return type is a plain context
    manager over :class:`RaisedExpect`, which is what the ``as`` binding needs;
    the handle's own class is an implementation detail.
    """
    return _CaughtExpect(exception_type, because)
