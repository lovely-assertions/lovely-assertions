"""The exception catalogue: ``CallableExpect``, ``RaisedExpect``, ``expect_raises``.

Behaviour and messages are the obvious half of this; the soft-scope path, the
generator limitation and PEP 678 notes are the half that gets forgotten.

*Behaviour* -- what passes, what fails, and what is deliberately **not** caught:
a ``KeyboardInterrupt`` crossing an assertion is the run being cut short, not a
finding about the code.

*Messages* -- asserted verbatim. "It raised the wrong thing" is worth nothing
without saying what was raised instead, and the real exception has to survive as
the failure's ``__cause__`` so its traceback is still on screen.

*The soft-scope path* -- a failed ``raises`` has no exception to hand back, so the
rest of the chain has to be absorbed rather than produce a second failure derived
from the first.

*The generator limitation* -- calling a generator function raises nothing,
because it only builds a generator; the body does not run until something drains
it. A test pins that so the workaround is visible rather than surprising.

*PEP 678 notes* -- ``__notes__`` does not exist until the first ``add_note``, so
every reading of it has to survive its absence, and every failure has to list the
notes that *were* there. ``pytest.raises`` has no support for notes at all, which
is exactly why a reader who lands on one of these failures has nowhere else to
have looked.

``expect()`` does not dispatch on callables, so the subjects here are built
directly; ``expect_raises`` is the form that needs no dispatch at all.
"""

import re
from typing import TYPE_CHECKING, Any, Final

import pytest

from lovely_assertions import AssertionFailure, expect, register_formatter, soft_assertions
from lovely_assertions._callable import CallableExpect, RaisedExpect, expect_raises

if TYPE_CHECKING:
    from collections.abc import Generator, Iterator


class Interrupted(BaseException):
    """A ``BaseException`` that is not an ``Exception``, as Ctrl-C is."""


class UnrenderableError(Exception):
    """An exception that cannot be rendered. The finding must survive it anyway."""

    def __repr__(self) -> str:
        message = "repr exploded"
        raise RuntimeError(message)


def boom() -> None:
    """The ordinary failing call: one exception, one readable message."""
    raise ValueError("bad input")


def quiet() -> int:
    """A call that raises nothing at all."""
    return 42


def wrong() -> None:
    raise TypeError("nope")


def inner() -> None:
    """The exception the three callables below end up carrying as their cause."""
    raise KeyError("k")


def chained() -> None:
    """``raise ... from ...``: the cause is explicit."""
    try:
        inner()
    except KeyError as error:
        raise ValueError("outer") from error


def contexted() -> None:
    """A bare ``raise`` inside an ``except``: the cause is only the context."""
    try:
        inner()
    except KeyError:
        raise ValueError("outer")  # noqa: B904  (the missing `from` is the point)


def suppressed() -> None:
    """``raise ... from None``: the context is there and the code disowned it."""
    try:
        inner()
    except KeyError:
        raise ValueError("outer") from None


def crossed() -> None:
    """A stated cause *and* a different context in flight -- the two must not be confused.

    ``__cause__`` is the ``TypeError`` the code named; ``__context__`` is the
    ``KeyError`` that happened to be being handled. Without both being different
    exceptions, "``__cause__`` wins" is an untestable claim: every other fixture
    here sets the two to the same object.
    """
    try:
        inner()
    except KeyError:
        raise ValueError("outer") from TypeError("stated")


def interrupt() -> None:
    raise Interrupted


def hostile() -> None:
    raise UnrenderableError("x")


def touches_the_exception(error: BaseException) -> bool:
    """A predicate written for a real exception: it reaches into ``args``."""
    return len(error.args) == 1


def rows() -> "Iterator[int]":
    """A generator function: nothing it raises happens until it is drained."""
    yield 1
    raise ValueError("exhausted")


def is_fatal(error: BaseException) -> bool:
    """A named predicate, so the failure message can name it."""
    return "fatal" in str(error)


def is_a_fatal_report(error: BaseException) -> None:
    """A named inspector: it asserts rather than returning a verdict.

    Two assertions, so what ``satisfies`` reports that a predicate cannot is
    visible -- both findings, on one failure.
    """
    expect(error.args).has_length(2)
    expect(str(error)).contains("fatal")


def annotated() -> None:
    """The PEP 678 case: an exception a library re-raised with context attached."""
    error = ValueError("bad input")
    error.add_note("attempt 1 of 3 failed")
    error.add_note("giving up")
    raise error


def annotated_once() -> None:
    raise_with_notes("only this one")


def raise_with_notes(*notes: str) -> None:
    """Raise a ``ValueError`` carrying exactly ``notes``, in order."""
    error = ValueError("bad input")
    for note in notes:
        error.add_note(note)
    raise error


#: Longer than the cap a failure message renders in full.
LONG_MESSAGE: Final = "x" * 300


# ---------------------------------------------------------------------------
# raises
# ---------------------------------------------------------------------------
def test_raises_hands_back_the_exception_as_the_subject() -> None:
    caught = CallableExpect(boom).raises(ValueError)
    assert isinstance(caught, RaisedExpect)
    assert isinstance(caught.subject, ValueError)
    assert caught.subject.args == ("bad input",)


def test_raises_accepts_a_subclass() -> None:
    CallableExpect(boom).raises(Exception)
    CallableExpect(boom).raises(ValueError)


def test_and_and_which_are_the_same_subject() -> None:
    """``.which`` is a spelling here: ``raises`` already made the exception the subject."""
    caught = CallableExpect(boom).raises(ValueError)
    assert caught.and_ is caught
    assert caught.which is caught


def test_the_generic_catalogue_applies_to_the_exception() -> None:
    CallableExpect(boom).raises(ValueError).is_instance_of(Exception)
    CallableExpect(boom).raises(ValueError).is_not_none()


def test_raises_reports_nothing_raised_and_what_came_back_instead() -> None:
    """The return value is named: it is the only clue when the call was a no-op."""
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(quiet).raises(ValueError)
    assert str(caught.value) == (
        "Expected quiet to raise ValueError, but nothing was raised (the call returned 42)."
    )


def test_raises_reports_the_wrong_type_and_keeps_the_real_exception() -> None:
    """The real traceback is the valuable half; it survives as ``__cause__``."""
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(wrong).raises(ValueError)
    assert str(caught.value) == "Expected wrong to raise ValueError, but raised TypeError('nope')."
    cause = caught.value.__cause__
    assert isinstance(cause, TypeError)
    assert cause.args == ("nope",)
    assert cause.__traceback__ is not None


def test_raises_takes_a_reason() -> None:
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(quiet).raises(ValueError, because="the parser must reject junk")
    assert "because the parser must reject junk." in str(caught.value)


# ---------------------------------------------------------------------------
# raises_exactly
# ---------------------------------------------------------------------------
def test_raises_exactly_accepts_only_the_exact_type() -> None:
    CallableExpect(boom).raises_exactly(ValueError)
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(boom).raises_exactly(Exception)
    assert str(caught.value) == (
        "Expected boom to raise exactly Exception, but raised ValueError('bad input')."
    )
    assert isinstance(caught.value.__cause__, ValueError)


def test_raises_exactly_reports_nothing_raised() -> None:
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(quiet).raises_exactly(ValueError)
    assert str(caught.value) == (
        "Expected quiet to raise exactly ValueError, but nothing was raised (the call returned 42)."
    )


# ---------------------------------------------------------------------------
# does_not_raise
# ---------------------------------------------------------------------------
def test_does_not_raise_passes_and_chains() -> None:
    subject = CallableExpect(quiet)
    assert subject.does_not_raise() is subject
    assert subject.does_not_raise(ValueError) is subject


def test_does_not_raise_reports_what_escaped() -> None:
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(boom).does_not_raise()
    assert str(caught.value) == "Expected boom not to raise, but raised ValueError('bad input')."
    assert isinstance(caught.value.__cause__, ValueError)


def test_does_not_raise_names_the_type_it_was_watching_for() -> None:
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(boom).does_not_raise(ValueError)
    assert str(caught.value) == (
        "Expected boom not to raise ValueError, but raised ValueError('bad input')."
    )


def test_does_not_raise_of_a_type_lets_other_exceptions_through() -> None:
    """The assertion is about that type; burying an unrelated error would hide it."""
    with pytest.raises(TypeError):
        CallableExpect(wrong).does_not_raise(ValueError)


def test_does_not_raise_of_a_subclass_covers_the_subclass() -> None:
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(boom).does_not_raise(Exception)
    assert "not to raise Exception, but raised ValueError('bad input')" in str(caught.value)


def test_an_explicit_none_means_no_filter() -> None:
    """The default is a sentinel, not an overload: ``None`` reads as "nothing at all"."""
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(boom).does_not_raise(None)
    assert str(caught.value) == "Expected boom not to raise, but raised ValueError('bad input')."


# ---------------------------------------------------------------------------
# BaseException is not Exception
# ---------------------------------------------------------------------------
def test_a_base_exception_is_not_swallowed_by_does_not_raise() -> None:
    """Ctrl-C means the run is over. Reporting "it raised" would hijack it."""
    with pytest.raises(Interrupted):
        CallableExpect(interrupt).does_not_raise()


def test_a_base_exception_is_not_swallowed_by_the_wrong_type_branch() -> None:
    with pytest.raises(Interrupted):
        CallableExpect(interrupt).raises(ValueError)


def test_a_base_exception_asked_for_by_name_is_caught() -> None:
    """Naming it makes it the subject of the test rather than an interruption of it."""
    CallableExpect(interrupt).raises(Interrupted)
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(interrupt).does_not_raise(Interrupted)
    assert "not to raise Interrupted, but raised Interrupted()" in str(caught.value)


def test_a_base_exception_travels_through_expect_raises() -> None:
    with pytest.raises(Interrupted), expect_raises(ValueError):
        interrupt()


# ---------------------------------------------------------------------------
# with_message / with_message_containing
# ---------------------------------------------------------------------------
def test_with_message_is_a_search_not_a_full_match() -> None:
    CallableExpect(boom).raises(ValueError).with_message("bad")
    CallableExpect(boom).raises(ValueError).with_message("^bad input$")
    CallableExpect(boom).raises(ValueError).with_message(re.compile("INPUT", re.IGNORECASE))


def test_with_message_reports_the_pattern_and_the_message() -> None:
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(boom).raises(ValueError).with_message("^good")
    assert str(caught.value) == (
        "Expected boom to have a message matching '^good', but the message was 'bad input'."
    )


def test_with_message_renders_a_compiled_pattern_as_its_source() -> None:
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(boom).raises(ValueError).with_message(re.compile("^good"))
    assert "matching '^good'" in str(caught.value)


def test_with_message_containing_is_a_plain_substring() -> None:
    CallableExpect(boom).raises(ValueError).with_message_containing("ad in")
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(boom).raises(ValueError).with_message_containing("^bad")
    assert str(caught.value) == (
        "Expected boom to have a message containing '^bad', but the message was 'bad input'."
    )


def test_a_long_message_is_truncated_rather_than_dumped() -> None:
    """Clipped before it is rendered, so the quotes still balance and the count is the text's."""

    def verbose() -> None:
        raise ValueError(LONG_MESSAGE)

    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(verbose).raises(ValueError).with_message_containing("missing")
    message = str(caught.value)
    assert LONG_MESSAGE not in message
    # 300, not 302: the reader is told how long the message is, not how long its
    # `repr` would have been with the quotes counted in.
    assert "truncated from 300 characters" in message
    assert "'" + "x" * 120 + "...'" in message


def test_the_rendering_cap_is_inclusive() -> None:
    """A value exactly at the cap is short enough to read, so it is shown whole."""

    def at_cap() -> None:
        raise ValueError("y" * 120)

    def one_over() -> None:
        raise ValueError("y" * 121)

    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(at_cap).raises(ValueError).with_message_containing("missing")
    assert "truncated" not in str(caught.value)
    assert "y" * 120 in str(caught.value)

    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(one_over).raises(ValueError).with_message_containing("missing")
    assert "truncated from 121 characters" in str(caught.value)


def test_an_over_long_exception_is_clipped_inside_its_repr() -> None:
    """A value that is not a ``str`` is clipped *after* rendering, and says so.

    The message assertions clip the text first, so their quotes still balance and
    the count they report is the message's own. An exception has no rendering but
    its ``repr``, so the cut lands inside it -- no closing quote survives -- and
    the length reported is the ``repr``'s, not the message's.
    """

    def verbose() -> None:
        raise ValueError("x" * 130)

    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(verbose).raises(KeyError)

    # 144: `ValueError('` and `')` around 130 characters. 108: what is left of
    # the 120-character budget once `ValueError('` has been spent.
    assert str(caught.value) == (
        "Expected verbose to raise KeyError, but raised ValueError('"
        + "x" * 108
        + "... (truncated from 144 characters)."
    )


def test_a_hostile_repr_costs_detail_not_the_finding() -> None:
    """An assertion that has already failed must not turn into a library error.

    ``_diff`` states the rule for the diff engine; it holds here too, and it
    holds harder: rendering the exception is the last thing between the reader
    and the ``__cause__`` that explains their test.
    """
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(hostile).raises(ValueError)
    assert str(caught.value) == (
        "Expected hostile to raise ValueError,"
        " but raised <UnrenderableError with an unusable __repr__>."
    )
    assert isinstance(caught.value.__cause__, UnrenderableError)


def test_the_message_is_str_of_the_exception() -> None:
    """Not ``args[0]``: ``str(exception)`` is what a traceback prints."""

    def multi() -> None:
        raise ValueError("first", "second")

    CallableExpect(multi).raises(ValueError).with_message_containing("('first', 'second')")


# ---------------------------------------------------------------------------
# Rendering goes through the formatter registry
#
# One helper renders everything these messages print -- the exception that was
# raised, the one that was wanted instead, the cause, the notes, the message and
# the value a non-raising call returned. A registered formatter has to reach all
# of it, or the same exception reads two ways in one report.
# ---------------------------------------------------------------------------
class SecretError(Exception):
    """An exception whose ``repr`` prints what a project would rather it did not."""


class RedactingFormatter:
    """Render a ``SecretError`` without its payload, as a secret scrubber would."""

    __slots__ = ()

    def can_handle(self, value: object, /) -> bool:
        return isinstance(value, SecretError)

    def format(self, value: object, /) -> str:
        return "<redacted>"


# Registered once, at import, for a type declared in this file -- global
# registration for real, that still cannot reach into any other test's messages.
register_formatter(RedactingFormatter())


def leaks() -> None:
    raise SecretError("token=hunter2")


def leaks_underneath() -> None:
    """The payload is in the cause, which the ``with_cause`` failure names too."""
    try:
        leaks()
    except SecretError as error:
        raise ValueError("outer") from error


def returns_the_error() -> SecretError:
    """A call that hands its error back rather than raising it."""
    return SecretError("token=hunter2")


def test_expect_raises_renders_the_wrong_exception_through_the_registry() -> None:
    with pytest.raises(AssertionFailure) as caught, expect_raises(KeyError):
        leaks()

    assert str(caught.value) == "Expected KeyError to be raised, but <redacted> was raised instead."


def test_raises_renders_the_wrong_exception_through_the_registry() -> None:
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(leaks).raises(KeyError)

    assert str(caught.value) == "Expected leaks to raise KeyError, but raised <redacted>."
    assert isinstance(caught.value.__cause__, SecretError)


def test_a_cause_is_rendered_through_the_registry() -> None:
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(leaks_underneath).raises(ValueError).with_cause(KeyError)

    assert str(caught.value) == (
        "Expected leaks_underneath to have a cause of type KeyError, but __cause__ was <redacted>."
    )


def test_the_value_a_non_raising_call_returned_goes_through_the_registry() -> None:
    """The site where a bypass is loudest: a plain object renders as its address."""
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(returns_the_error).raises(ValueError)

    assert str(caught.value) == (
        "Expected returns_the_error to raise ValueError,"
        " but nothing was raised (the call returned <redacted>)."
    )


class SecretScrubbing:
    """A formatter for the strings a message prints, as a secret scrubber would be.

    Scoped rather than registered globally: a formatter that claims strings would
    rewrite every other test's messages for the rest of the session.
    """

    __slots__ = ()

    def can_handle(self, value: object, /) -> bool:
        return isinstance(value, str) and "sk-" in value

    def format(self, value: object, /) -> str:
        return "'<scrubbed>'"


def carries_a_key() -> None:
    raise ValueError("refused sk-live-4242")


def carries_a_long_key() -> None:
    """A secret past the rendering cap, where a length-based clip would run first."""
    raise ValueError("refused sk-live-" + "4" * 400)


def test_an_exception_message_is_rendered_through_the_registry_too() -> None:
    """A ``str`` is a value like any other, so the registry decides how it reads.

    The expected substring carries no secret, so it renders as itself and the
    sentence still says which half of it was scrubbed.
    """
    with soft_assertions(formatters=(SecretScrubbing(),)) as scope:
        CallableExpect(carries_a_key).raises(ValueError).with_message_containing("accepted")
        collected = scope.discard()

    assert collected == [
        (
            "Expected carries_a_key to have a message containing 'accepted',"
            " but the message was '<scrubbed>'."
        )
    ]


def test_an_over_long_message_is_still_the_formatters_rendering() -> None:
    """Length must not defeat the registry.

    Clipping the string itself is right only while nothing has claimed it; doing
    it to a claimed one would print the very text the formatter hid.
    """
    with soft_assertions(formatters=(SecretScrubbing(),)) as scope:
        CallableExpect(carries_a_long_key).raises(ValueError).with_message_containing("accepted")
        collected = scope.discard()

    assert collected == [
        (
            "Expected carries_a_long_key to have a message containing 'accepted',"
            " but the message was '<scrubbed>'."
        )
    ]


# ---------------------------------------------------------------------------
# Notes (PEP 678)
# ---------------------------------------------------------------------------
def test_with_note_matches_a_whole_note() -> None:
    """Exact, not a substring: ``with_note_matching`` is the search."""
    CallableExpect(annotated).raises(ValueError).with_note("giving up")
    CallableExpect(annotated).raises(ValueError).with_note("attempt 1 of 3 failed")
    with pytest.raises(AssertionFailure, match="to carry the note"):
        CallableExpect(annotated).raises(ValueError).with_note("giving")


def test_with_note_lists_the_notes_that_were_there() -> None:
    """The whole value of the assertion when the expected note is missing."""
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(annotated).raises(ValueError).with_note("retry 3 of 3")
    assert str(caught.value) == (
        "Expected annotated to carry the note 'retry 3 of 3',"
        " but its notes were 'attempt 1 of 3 failed', 'giving up'."
    )


def test_an_exception_with_no_notes_says_so_rather_than_listing_nothing() -> None:
    """``__notes__`` does not exist until the first ``add_note``; the message reads as it."""
    assert not hasattr(ValueError("bad input"), "__notes__")
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(boom).raises(ValueError).with_note("retry 3 of 3")
    assert str(caught.value) == (
        "Expected boom to carry the note 'retry 3 of 3', but it carried no notes."
    )


def test_one_note_is_reported_as_one() -> None:
    """A message that says "its notes were 'x'" reads as a message nobody looked at."""
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(annotated_once).raises(ValueError).with_note("something else")
    assert str(caught.value) == (
        "Expected annotated_once to carry the note 'something else',"
        " but its only note was 'only this one'."
    )


def test_with_note_matching_is_a_search_over_every_note() -> None:
    """A search, not a match: every pattern here but the last one is unanchored.

    ``"1 of 3"`` is the one that separates ``re.search`` from ``re.match`` -- it
    sits in the middle of the note, which is where the interesting part of a
    retry note usually sits. Anchoring is the caller's to ask for, and ``"^retry"``
    shows it still works when they do.
    """
    CallableExpect(annotated).raises(ValueError).with_note_matching(r"attempt \d")
    CallableExpect(annotated).raises(ValueError).with_note_matching("1 of 3")
    CallableExpect(annotated).raises(ValueError).with_note_matching("failed$")
    CallableExpect(annotated).raises(ValueError).with_note_matching("^giving")
    CallableExpect(annotated).raises(ValueError).with_note_matching(re.compile("GIVING", re.I))
    CallableExpect(annotated).raises(ValueError).with_note_matching(re.compile("ING UP", re.I))
    with pytest.raises(AssertionFailure, match="to carry a note matching"):
        CallableExpect(annotated).raises(ValueError).with_note_matching("^retry")


def test_with_note_matching_reports_the_pattern_and_the_notes() -> None:
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(annotated).raises(ValueError).with_note_matching("^retry")
    assert str(caught.value) == (
        "Expected annotated to carry a note matching '^retry',"
        " but its notes were 'attempt 1 of 3 failed', 'giving up'."
    )


def test_with_note_matching_renders_a_compiled_pattern_as_its_source() -> None:
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(boom).raises(ValueError).with_note_matching(re.compile("^retry"))
    assert "matching '^retry'" in str(caught.value)


def test_has_no_notes_passes_when_nothing_was_attached() -> None:
    CallableExpect(boom).raises(ValueError).has_no_notes()


def test_has_no_notes_reports_what_was_attached() -> None:
    """A note is invisible until something prints the traceback, which is the point."""
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(annotated).raises(ValueError).has_no_notes()
    assert str(caught.value) == (
        "Expected annotated to carry no notes,"
        " but its notes were 'attempt 1 of 3 failed', 'giving up'."
    )
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(annotated_once).raises(ValueError).has_no_notes()
    assert str(caught.value) == (
        "Expected annotated_once to carry no notes, but its only note was 'only this one'."
    )


def test_a_long_note_is_truncated_rather_than_dumped() -> None:
    """The same cap the message assertions use: a note can be a serialised payload."""
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(lambda: raise_with_notes(LONG_MESSAGE)).raises(ValueError).has_no_notes()
    message = str(caught.value)
    assert LONG_MESSAGE not in message
    assert "truncated from 300 characters" in message


def test_a_great_many_notes_are_cut_off_and_counted() -> None:
    """A retry loop attaches one per attempt; a message that dumps all of them hides itself."""
    many = tuple("note " + str(index) for index in range(13))
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(lambda: raise_with_notes(*many)).raises(ValueError).has_no_notes()
    assert str(caught.value).endswith(
        "but its notes were 'note 0', 'note 1', 'note 2', 'note 3', 'note 4', 'note 5',"
        " 'note 6', 'note 7', 'note 8', 'note 9', ... (3 more)."
    )


def test_the_note_assertions_chain_and_take_a_reason() -> None:
    caught = CallableExpect(annotated).raises(ValueError)
    assert caught.with_note("giving up").with_note_matching("attempt").and_ is caught
    with pytest.raises(AssertionFailure, match="because R"):
        CallableExpect(boom).raises(ValueError).with_note("x", because="R")
    with pytest.raises(AssertionFailure, match="because R"):
        CallableExpect(boom).raises(ValueError).with_note_matching("x", because="R")
    with pytest.raises(AssertionFailure, match="because R"):
        CallableExpect(annotated).raises(ValueError).has_no_notes(because="R")


def test_an_emptied_notes_list_reads_as_no_notes() -> None:
    """``__notes__`` can exist and be empty -- a note removed again, a list cleared.

    "Nothing has been attached" is the question ``has_no_notes`` asks, and an
    empty list is one of its two right answers; reading it as "the attribute is
    absent" instead would fail the assertion and then have to describe a listing
    of nothing.
    """
    error = ValueError("bad input")
    error.add_note("attempt 1 of 3 failed")
    error.__notes__.clear()
    subject: RaisedExpect[ValueError] = RaisedExpect(error)
    subject.has_no_notes()
    with pytest.raises(AssertionFailure) as caught:
        subject.with_note("attempt 1 of 3 failed")
    assert str(caught.value) == (
        "Expected the value to carry the note 'attempt 1 of 3 failed', but it carried no notes."
    )
    with pytest.raises(AssertionFailure, match="but it carried no notes"):
        subject.with_note_matching("attempt")


def test_a_mangled_notes_attribute_is_read_as_no_notes() -> None:
    """PEP 678 says ``__notes__`` is a list, and ``add_note`` refuses to make it anything else.

    So a ``__notes__`` of another shape was never built by the documented API.
    Iterating it blindly would be the library guessing; treating it as no notes is
    the library declining to. The same check is what keeps the soft-scope stand-in
    below out of a ``for`` loop.
    """
    error = ValueError("bad input")
    error.__notes__ = "not a list"  # type: ignore[assignment]  # pyright: ignore[reportAttributeAccessIssue]
    subject: RaisedExpect[ValueError] = RaisedExpect(error)
    subject.has_no_notes()
    with pytest.raises(AssertionFailure, match="but it carried no notes"):
        subject.with_note("n")


def test_the_note_assertions_never_cost_an_absorbed_scope_its_report() -> None:
    """The stand-in's every attribute is itself, ``__notes__`` included.

    Reading it as a list of notes would put a ``_AbsorbingSubject`` into a ``for``
    loop and raise a ``TypeError`` from inside the soft block, which aborts the
    scope and throws away every failure it had collected -- the one thing the
    absorbing mechanism exists to prevent.
    """
    with soft_assertions() as scope:
        with expect_raises(ValueError) as caught:
            wrong()
        caught.with_note("x").with_note_matching("y").has_no_notes()
        collected = scope.discard()
    assert collected == [
        "Expected ValueError to be raised, but TypeError('nope') was raised instead."
    ]


# ---------------------------------------------------------------------------
# with_cause / with_cause_exactly
# ---------------------------------------------------------------------------
def test_with_cause_finds_an_explicit_cause() -> None:
    cause = CallableExpect(chained).raises(ValueError).with_cause(KeyError)
    assert isinstance(cause.subject, KeyError)
    assert cause.subject.args == ("k",)


def test_with_cause_finds_an_implicit_context() -> None:
    """A bare ``raise`` inside an ``except`` is still "the inner exception"."""
    cause = CallableExpect(contexted).raises(ValueError).with_cause(KeyError)
    assert isinstance(cause.subject, KeyError)


def test_the_cause_chains_further_assertions() -> None:
    CallableExpect(chained).raises(ValueError).with_cause(KeyError).with_message_containing("k")


def test_with_cause_names_the_attribute_it_looked_at() -> None:
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(chained).raises(ValueError).with_cause(TypeError)
    assert str(caught.value) == (
        "Expected chained to have a cause of type TypeError, but __cause__ was KeyError('k')."
    )

    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(contexted).raises(ValueError).with_cause(TypeError)
    assert str(caught.value) == (
        "Expected contexted to have a cause of type TypeError, but __context__ was KeyError('k')."
    )


def test_with_cause_reports_no_cause_at_all() -> None:
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(boom).raises(ValueError).with_cause(KeyError)
    assert str(caught.value) == (
        "Expected boom to have a cause of type KeyError,"
        " but neither __cause__ nor __context__ was set."
    )


def test_a_suppressed_context_is_reported_as_suppressed_not_as_absent() -> None:
    """``raise X from None`` is a denial by the code, and worth saying out loud."""
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(suppressed).raises(ValueError).with_cause(KeyError)
    assert str(caught.value) == (
        "Expected suppressed to have a cause of type KeyError,"
        " but its context was suppressed with `raise ... from None`."
    )


def test_an_explicit_cause_wins_over_the_context_in_flight() -> None:
    """``__cause__`` is what the code stated; ``__context__`` is what happened to be around."""
    cause = CallableExpect(crossed).raises(ValueError).with_cause(TypeError)
    assert cause.subject.args == ("stated",)

    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(crossed).raises(ValueError).with_cause(KeyError)
    assert str(caught.value) == (
        "Expected crossed to have a cause of type KeyError, but __cause__ was TypeError('stated')."
    )


def test_with_cause_exactly_rejects_a_subclass() -> None:
    CallableExpect(chained).raises(ValueError).with_cause_exactly(KeyError)
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(chained).raises(ValueError).with_cause_exactly(LookupError)
    assert str(caught.value) == (
        "Expected chained to have a cause of exactly LookupError, but __cause__ was KeyError('k')."
    )


def test_with_cause_exactly_reports_no_cause_at_all() -> None:
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(boom).raises(ValueError).with_cause_exactly(KeyError)
    assert "neither __cause__ nor __context__ was set" in str(caught.value)


# ---------------------------------------------------------------------------
# where
# ---------------------------------------------------------------------------
def test_where_passes_when_the_predicate_holds() -> None:
    CallableExpect(boom).raises(ValueError).where(lambda error: error.args == ("bad input",))


def test_where_names_the_predicate_and_the_exception() -> None:
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(boom).raises(ValueError).where(is_fatal)
    assert str(caught.value) == (
        "Expected boom to satisfy is_fatal, but ValueError('bad input') did not."
    )


def test_where_does_not_claim_the_named_call_raised_the_subject() -> None:
    """Down a ``with_cause`` chain the name is the *outer* call, so "to raise" would lie.

    ``chained`` raises a ``ValueError``; the ``KeyError`` is only its cause. An
    expectation reading "to raise an exception satisfying ..." would report that
    ``chained`` raised the ``KeyError``.
    """
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(chained).raises(ValueError).with_cause(KeyError).where(is_fatal)
    assert str(caught.value) == ("Expected chained to satisfy is_fatal, but KeyError('k') did not.")


def test_where_falls_back_for_a_lambda() -> None:
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(boom).raises(ValueError).where(lambda error: not error.args)
    assert "to satisfy the predicate" in str(caught.value)


# ---------------------------------------------------------------------------
# expect_raises: the context-manager form
# ---------------------------------------------------------------------------
def test_expect_raises_catches_and_hands_back_the_exception() -> None:
    with expect_raises(ValueError) as caught:
        boom()
    assert isinstance(caught.subject, ValueError)
    caught.with_message_containing("bad input")


def test_expect_raises_accepts_a_subclass() -> None:
    with expect_raises(Exception) as caught:
        boom()
    assert isinstance(caught.subject, ValueError)


def test_expect_raises_reports_when_nothing_was_raised() -> None:
    """The subject name is the type asked for: it is what the entry point was given."""
    with pytest.raises(AssertionFailure) as caught, expect_raises(ValueError):
        pass
    assert str(caught.value) == "Expected ValueError to be raised, but nothing was raised."


def test_expect_raises_reports_the_wrong_type_and_keeps_the_real_exception() -> None:
    """Unlike ``pytest.raises``, which lets the wrong exception stand on its own."""
    with pytest.raises(AssertionFailure) as caught, expect_raises(ValueError):
        wrong()
    assert str(caught.value) == (
        "Expected ValueError to be raised, but TypeError('nope') was raised instead."
    )
    assert isinstance(caught.value.__cause__, TypeError)


def test_expect_raises_takes_a_reason() -> None:
    with pytest.raises(AssertionFailure) as caught, expect_raises(ValueError, because="junk"):
        pass
    assert str(caught.value) == (
        "Expected ValueError to be raised, but nothing was raised because junk."
    )


def test_the_exception_is_not_available_inside_the_block() -> None:
    """A placeholder would let the assertion run against nothing; say so instead."""
    with pytest.raises(RuntimeError) as caught, expect_raises(ValueError) as pending:
        _ = pending.subject
    assert "only available after" in str(caught.value)
    assert not isinstance(caught.value, AssertionFailure)


def test_an_assertion_inside_the_block_says_the_same_thing() -> None:
    with pytest.raises(RuntimeError) as caught, expect_raises(ValueError) as pending:
        pending.with_message("bad")
    assert "only available after" in str(caught.value)


def test_the_early_access_guard_is_not_reported_as_the_wrong_exception() -> None:
    """The guard says everything there is to say; wrapping it would bury it."""
    with pytest.raises(RuntimeError) as caught, expect_raises(RuntimeError) as pending:
        _ = pending.subject
    assert "only available after" in str(caught.value)


def test_expect_raises_takes_a_reason_when_the_wrong_thing_was_raised() -> None:
    """The reason belongs to the assertion, not to one of its branches."""
    with pytest.raises(AssertionFailure) as caught, expect_raises(ValueError, because="junk"):
        wrong()
    assert str(caught.value) == (
        "Expected ValueError to be raised, but TypeError('nope') was raised instead because junk."
    )


def test_only_the_missing_exception_is_explained() -> None:
    """Every other name on the handle is a typo and keeps the ``AttributeError`` it deserves."""
    handle = expect_raises(ValueError)
    typo = "with_mesage"
    with pytest.raises(AttributeError, match=typo):
        _ = getattr(handle, typo)


def test_the_handle_is_a_raised_expect_after_the_block() -> None:
    with expect_raises(ValueError) as caught:
        chained()
    assert isinstance(caught, RaisedExpect)
    assert caught.and_ is caught
    caught.which.with_cause(KeyError).with_message_containing("k")


def test_the_handles_predicate_assertions_report_against_the_exception() -> None:
    """``where`` and ``matches`` on the *handle*, shown failing.

    Without a failing exercise through the handle, the branch that builds these
    two messages is never rendered by any test, and either one could be neutered
    to ``return self`` with the whole suite still green.

    The two do not say the same thing, and the difference is the point. ``where``
    names the predicate it was given; ``matches`` says only "the predicate".
    Neither names a call, because this spelling has none -- the one above says
    ``boom`` where these say the subject.

    Both take a **predicate**, which is the other thing worth pinning here.
    Writing an inspector instead -- ``lambda error: expect(str(error))
    .is_equal_to("fatal")`` -- runs, and appears to work in both directions,
    because a failing inner assertion raises rather than returning ``False``.
    Only the type checkers object, which is why the spelling is pinned here.
    """
    with pytest.raises(AssertionFailure) as failure:
        with expect_raises(ValueError) as caught:
            boom()
        caught.matches(lambda error: "fatal" in str(error))
    assert str(failure.value) == (
        "Expected the value to match the predicate, but ValueError('bad input') did not."
    )

    with pytest.raises(AssertionFailure) as failure:
        with expect_raises(ValueError) as caught:
            boom()
        caught.where(is_fatal)
    assert str(failure.value) == (
        "Expected the value to satisfy is_fatal, but ValueError('bad input') did not."
    )


def test_the_handles_inspector_reports_every_finding_about_the_exception() -> None:
    """``satisfies`` on the *handle*, shown failing -- the third of the three.

    It is the one that takes an **inspector** rather than a predicate, and the
    difference shows in the message: the findings are the assertions made inside
    it, and a run reports all of them rather than stopping at the first. A
    predicate could only ever have said "did not".
    """
    with pytest.raises(AssertionFailure) as failure:
        with expect_raises(ValueError) as caught:
            boom()
        caught.satisfies(is_a_fatal_report)

    assert str(failure.value) == (
        "Expected the value to satisfy the inspection.\n"
        "  - Expected error.args to have length 2, but had 1: ('bad input',)\n"
        "  - Expected str(error) to contain 'fatal', but was 'bad input'"
    )


# ---------------------------------------------------------------------------
# Soft scopes: one root cause, one message
# ---------------------------------------------------------------------------
def test_a_failed_raises_in_a_soft_scope_absorbs_the_rest_of_the_chain() -> None:
    with soft_assertions() as scope:
        CallableExpect(quiet).raises(ValueError).with_message("x").with_cause(KeyError)
        collected = scope.discard()
    assert collected == [
        "Expected quiet to raise ValueError, but nothing was raised (the call returned 42)."
    ]


def test_a_failed_expect_raises_in_a_soft_scope_absorbs_the_rest_of_the_chain() -> None:
    """The handle is bound by ``as``, so it cannot be swapped for the stand-in: it absorbs."""
    with soft_assertions() as scope:
        with expect_raises(ValueError) as caught:
            pass
        caught.with_message("x").with_message_containing("y")
        caught.with_cause(KeyError).with_message("z")
        collected = scope.discard()
    assert collected == ["Expected ValueError to be raised, but nothing was raised."]


def test_a_soft_scope_suppresses_the_wrong_exception_rather_than_abort_the_block() -> None:
    """Nothing is raised in a soft scope, so letting it out would end the block early."""
    with soft_assertions() as scope:
        with expect_raises(ValueError) as caught:
            wrong()
        caught.with_message("x")
        collected = scope.discard()
    assert collected == [
        "Expected ValueError to be raised, but TypeError('nope') was raised instead."
    ]


def test_an_absorbed_handle_never_hands_the_stand_in_to_a_predicate() -> None:
    """``where``/``matches``/``satisfies`` run the user's own callable on the subject.

    Once the failure is collected there is no subject, only the stand-in that
    absorbs the chain -- and every attribute of it is itself, so a predicate
    written for a real exception blows up on it.
    """
    with soft_assertions() as scope:
        with expect_raises(ValueError) as caught:
            pass
        caught.where(touches_the_exception)
        caught.matches(touches_the_exception)
        caught.satisfies(lambda error: expect(error.args).has_length(1))
        collected = scope.discard()
    assert collected == ["Expected ValueError to be raised, but nothing was raised."]


def test_the_stand_in_never_costs_the_scope_its_report() -> None:
    """A ``TypeError`` out of the stand-in would abort the scope and lose every failure."""
    with pytest.raises(AssertionFailure) as caught, soft_assertions():
        with expect_raises(ValueError) as pending:
            pass
        pending.where(touches_the_exception)
        CallableExpect(boom).does_not_raise()
    message = str(caught.value)
    assert "2 assertions failed:" in message
    assert "Expected ValueError to be raised, but nothing was raised" in message
    assert "not to raise, but raised ValueError('bad input')" in message


def test_a_soft_scope_aggregates_exception_failures_with_the_rest() -> None:
    with pytest.raises(AssertionFailure) as caught, soft_assertions():
        CallableExpect(quiet).raises(ValueError)
        CallableExpect(boom).does_not_raise()
    message = str(caught.value)
    assert "2 assertions failed:" in message
    assert "to raise ValueError, but nothing was raised" in message
    assert "not to raise, but raised ValueError('bad input')" in message


def test_a_passing_exception_assertion_in_a_soft_scope_reports_nothing() -> None:
    with soft_assertions() as scope:
        CallableExpect(boom).raises(ValueError).with_message("bad")
        with expect_raises(ValueError) as caught:
            boom()
        caught.with_message_containing("input")
        assert scope.discard() == []


def test_a_scope_name_prefixes_an_exception_failure() -> None:
    with pytest.raises(AssertionFailure) as caught, soft_assertions("Parsing"):
        CallableExpect(quiet).raises(ValueError)
    assert "Expected Parsing/quiet to raise ValueError" in str(caught.value)


# ---------------------------------------------------------------------------
# The generator limitation
# ---------------------------------------------------------------------------
def test_a_generator_function_raises_nothing_until_it_is_drained() -> None:
    """Calling it only builds a generator, and the failure message shows exactly that."""
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(rows).raises(ValueError)
    assert "but nothing was raised (the call returned <generator object" in str(caught.value)


def test_draining_the_generator_is_the_workaround() -> None:
    CallableExpect(lambda: list(rows())).raises(ValueError).with_message_containing("exhausted")


# ---------------------------------------------------------------------------
# Awaitables that are not coroutines
# ---------------------------------------------------------------------------
class Pending:
    """An awaitable with nothing to close: a Future, a hand-written ``__await__``.

    The guard closes what it refuses so the reader is not handed a "never
    awaited" warning from somewhere unrelated -- but ``close`` is a coroutine's
    method, not an awaitable's, and an object is free not to have it.
    """

    __slots__ = ()

    def __await__(self) -> "Generator[Any]":
        yield


class Unclosable:
    """An awaitable carrying a ``close`` that is not a method.

    ``getattr(value, "close", None)`` finds something here, so a guard written as
    "is there a ``close``?" would call a string and hand the reader a ``TypeError``
    about ``str`` in place of the refusal.
    """

    __slots__ = ()

    close = "shut"

    def __await__(self) -> "Generator[Any]":
        yield


def test_an_awaitable_with_nothing_to_close_is_refused_all_the_same() -> None:
    """The refusal is about what was returned, not about whether it can be tidied up."""
    with pytest.raises(TypeError) as caught:
        CallableExpect(Pending).does_not_raise()

    assert str(caught.value) == (
        "the callable returned a coroutine without running: an async callable "
        "cannot be asserted on synchronously. Await it and assert on the result, "
        "or assert on a lambda that runs it -- expect(lambda: asyncio.run(fn()))"
    )


def test_a_close_that_is_not_callable_is_left_alone() -> None:
    """The reader gets the refusal, not a ``TypeError`` about the attribute it found."""
    with pytest.raises(TypeError) as caught:
        CallableExpect(Unclosable).does_not_raise()

    assert str(caught.value).startswith("the callable returned a coroutine without running")


# ---------------------------------------------------------------------------
# A passing assertion never reaches the failure path
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("no_failure_machinery")
def test_passing_exception_assertions_never_touch_the_failure_path() -> None:
    CallableExpect(quiet).does_not_raise()
    CallableExpect(quiet).does_not_raise(ValueError)
    caught = CallableExpect(chained).raises(ValueError, because="never evaluated")
    caught.with_message("outer").with_message_containing("out").where(bool)
    caught.with_cause(KeyError).is_instance_of(LookupError)
    caught.with_cause_exactly(KeyError)
    CallableExpect(boom).raises_exactly(ValueError)
    with expect_raises(ValueError) as pending:
        boom()
    pending.with_message("bad")
