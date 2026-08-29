"""The warning catalogue: ``WarnedExpect``, ``expect_warns``, ``warns``, ``does_not_warn``.

Behaviour and messages are what any warning helper is judged on. The global
state, the ``__warningregistry__`` trap and the soft-assertion path are the
things a warning helper usually gets wrong.

*Behaviour* -- what passes, what fails, and what is deliberately not judged: a
block whose body raised did not finish, so the warnings it managed to issue are
not a verdict about anything.

*Messages* -- asserted verbatim, including the file and line each warning came
from. "Your warning did not fire" is worth very little without the four that did,
and that listing is the whole reason this exists next to ``pytest.warns``.

*The global state* -- ``warnings`` keeps its filters and its ``showwarning`` in
module globals, so a capture that does not put them back exactly leaves every
later test in the process running under someone else's configuration. Restoration
is checked on the passing path, on the failing path, and under nesting.

*The* ``__warningregistry__`` *trap* -- a warning already issued once from a
module is not issued again, which is how a warning test passes alone and fails in
a suite. Two tests: one that shows the trap is real, and one that shows a capture
walks straight through it.

*The soft-assertion path* -- a failed ``expect_warns`` never captured anything, so
the rest of the chain has to be absorbed rather than produce a second failure
derived from the first.

Some tests carry ``@pytest.mark.filterwarnings("ignore")``. They are the ones
that issue a warning the assertion under test was *not* about, which this
library re-issues to the ambient filters on the way out -- so without the mark
they land in pytest's run summary and read as warnings the library emitted.
The mark changes nothing about what is captured: inside a block the ambient
filters do not apply.

``expect()`` does not dispatch on callables, so the callable-form subjects here
are built directly, exactly as ``tests/test_exceptions.py`` builds them;
``expect_warns`` needs no dispatch at all.
"""

import threading
import warnings
from typing import TYPE_CHECKING, Any, Final

import pytest

from lovely_assertions import AssertionFailure, expect, formatting, soft_assertions
from lovely_assertions._callable import CallableExpect, expect_raises
from lovely_assertions._occurrence import at_least, at_most, exactly
from lovely_assertions._warnings import WarnedExpect, expect_warns

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


class Removed(DeprecationWarning):
    """A subclass, so "a subclass counts" is testable rather than asserted."""


class Coded(UserWarning):
    """A warning that carries a field, which is what ``.where`` is for."""

    def __init__(self, message: str, code: int) -> None:
        super().__init__(message)
        self.code = code


DEPRECATED: Final = "parse() is deprecated"
UNRELATED: Final = "unrelated"

#: Two warning messages that straddle the 120-character rendering budget. A
#: message is rendered through ``repr``, which adds the two quotes, so the
#: message itself is two characters shorter than the rendering it produces. The
#: budget is spelled out rather than read back from ``formatting()``: a constant
#: taken from the library would agree with the library by construction, and the
#: boundary is exactly what could otherwise drift by one unnoticed.
MAX_CHARS: Final = 120
AT_THE_BUDGET: Final = "x" * (MAX_CHARS - 2)
OVER_THE_BUDGET: Final = "x" * (MAX_CHARS - 1)


def warn_deprecated() -> None:
    warnings.warn(DEPRECATED, DeprecationWarning, stacklevel=1)


def warn_twice() -> None:
    warnings.warn("first", UserWarning, stacklevel=1)
    warnings.warn("second", UserWarning, stacklevel=1)


def warn_unrelated() -> None:
    warnings.warn(UNRELATED, RuntimeWarning, stacklevel=1)


def warn_deprecated_and_unrelated() -> None:
    """One category the assertion asks about and one it does not, from a thunk.

    The callable form needs both in a single function, where the block form can
    just write two statements inside the ``with``.
    """
    warnings.warn(DEPRECATED, DeprecationWarning, stacklevel=1)
    warnings.warn(UNRELATED, RuntimeWarning, stacklevel=1)


def quiet() -> int:
    return 42


def boom() -> None:
    raise ValueError("bad input")


def warns_then_raises() -> None:
    warnings.warn(DEPRECATED, DeprecationWarning, stacklevel=1)
    raise ValueError("bad input")


async def never_awaited() -> None:  # pragma: no cover - never runs, which is the point
    warnings.warn("this line is never reached", UserWarning, stacklevel=1)


def mentions_parse(warning: Warning) -> bool:
    """A named predicate, so a failure message can name it."""
    return "parse" in str(warning)


def is_final(warning: Warning) -> bool:
    return "final" in str(warning)


#: Where each helper issues from, spelled as a failure message spells it. The
#: arithmetic is deliberate rather than recovered from a capture: a constant read
#: back out of the library would agree with the library by construction and pin
#: nothing. ``stacklevel=1`` attributes a warning to the ``warnings.warn`` line
#: itself, which is the line after the ``def``.
DEPRECATED_AT: Final = f"{__file__}:{warn_deprecated.__code__.co_firstlineno + 1}"
UNRELATED_AT: Final = f"{__file__}:{warn_unrelated.__code__.co_firstlineno + 1}"
FIRST_AT: Final = f"{__file__}:{warn_twice.__code__.co_firstlineno + 1}"
SECOND_AT: Final = f"{__file__}:{warn_twice.__code__.co_firstlineno + 2}"


@pytest.fixture
def undisturbed() -> "Iterator[None]":
    """Fail the test that leaves the process's warning configuration changed.

    Every test here runs inside a capture of its own, and a capture that does not
    restore exactly is the one bug in this module that would not show up as a
    failing assertion -- it would show up three files later as a warning that
    stopped firing. So the check is an autouse-shaped guarantee applied by name,
    and the tests that deliberately change the ambient filters do their changing
    inside a ``catch_warnings`` of their own.
    """
    filters = warnings.filters[:]
    showwarning = warnings.showwarning
    yield
    assert warnings.filters == filters, "the capture did not restore `warnings.filters`"
    assert warnings.showwarning is showwarning, "the capture did not restore `showwarning`"


# ---------------------------------------------------------------------------
# expect_warns: the primary form
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("undisturbed")
def test_expect_warns_hands_back_the_warnings_as_the_subject() -> None:
    with expect_warns(DeprecationWarning) as warned:
        warn_deprecated()
    assert isinstance(warned, WarnedExpect)
    assert [str(warning) for warning in warned.subject] == [DEPRECATED]


@pytest.mark.usefixtures("undisturbed")
def test_the_subject_holds_every_matching_warning_in_order() -> None:
    with expect_warns(UserWarning) as warned:
        warn_twice()
    assert [str(warning) for warning in warned.subject] == ["first", "second"]


@pytest.mark.usefixtures("undisturbed")
def test_a_subclass_counts() -> None:
    with expect_warns(DeprecationWarning) as warned:
        warnings.warn("gone in 3.0", Removed, stacklevel=1)
    assert [type(warning) for warning in warned.subject] == [Removed]


@pytest.mark.usefixtures("undisturbed")
def test_the_bare_warning_category_is_how_any_warning_is_spelled() -> None:
    with expect_warns(Warning) as warned:
        warn_unrelated()
    assert len(warned.subject) == 1


@pytest.mark.usefixtures("undisturbed")
def test_and_and_which_are_the_same_subject() -> None:
    """``.which`` is a spelling here: the warnings are the subject already."""
    with expect_warns(DeprecationWarning) as warned:
        warn_deprecated()
    assert warned.and_ is warned
    assert warned.which is warned


@pytest.mark.usefixtures("undisturbed")
def test_the_generic_catalogue_applies_to_the_captured_tuple() -> None:
    with expect_warns(UserWarning) as warned:
        warn_twice()
    warned.is_not_none().and_.matches(lambda captured: len(captured) == 2)


@pytest.mark.usefixtures("undisturbed")
def test_expect_warns_reports_that_nothing_at_all_was_warned() -> None:
    with pytest.raises(AssertionFailure) as caught, expect_warns(UserWarning):
        pass
    assert str(caught.value) == "Expected UserWarning to be warned, but nothing was warned."


@pytest.mark.usefixtures("undisturbed")
@pytest.mark.filterwarnings("ignore")
def test_expect_warns_lists_the_warnings_that_were_issued_instead() -> None:
    """The differentiator over ``pytest.warns``, which reports only the absence."""
    with pytest.raises(AssertionFailure) as caught, expect_warns(UserWarning):
        warn_deprecated()
        warn_unrelated()
    assert str(caught.value) == (
        f"Expected UserWarning to be warned, but the warnings issued were"
        f" DeprecationWarning('{DEPRECATED}') at {DEPRECATED_AT},"
        f" RuntimeWarning('{UNRELATED}') at {UNRELATED_AT}."
    )


@pytest.mark.usefixtures("undisturbed")
@pytest.mark.filterwarnings("ignore")
def test_the_location_is_the_file_and_line_the_warning_came_from() -> None:
    """``stacklevel`` chooses the frame; the message prints whichever one it chose.

    Pinned on its own because the two lines of ``warn_twice`` are the only place
    in this file where two warnings differ *only* in where they came from, which
    is the case the location exists for.
    """
    with pytest.raises(AssertionFailure) as caught, expect_warns(DeprecationWarning):
        warn_twice()
    assert f"UserWarning('first') at {FIRST_AT}" in str(caught.value)
    assert f"UserWarning('second') at {SECOND_AT}" in str(caught.value)


@pytest.mark.usefixtures("undisturbed")
@pytest.mark.filterwarnings("ignore")
def test_a_stacklevel_of_two_points_at_the_caller() -> None:
    line = warn_deprecated.__code__.co_firstlineno + 1

    def blames_its_caller() -> None:
        warnings.warn("blamed", UserWarning, stacklevel=2)

    with pytest.raises(AssertionFailure) as caught, expect_warns(DeprecationWarning):
        blames_its_caller()
    assert f"UserWarning('blamed') at {__file__}:" in str(caught.value)
    assert f":{line}" not in str(caught.value), "stacklevel=2 must not name the warning's own line"


@pytest.mark.usefixtures("undisturbed")
def test_a_reason_reads_at_the_end_of_the_sentence() -> None:
    with pytest.raises(AssertionFailure) as caught, expect_warns(UserWarning, because="D10"):
        pass
    assert str(caught.value) == (
        "Expected UserWarning to be warned, but nothing was warned because D10."
    )


@pytest.mark.usefixtures("undisturbed")
def test_the_subject_can_be_renamed() -> None:
    with pytest.raises(AssertionFailure) as caught, expect_warns(UserWarning) as warned:
        warned.described_as("the migration")
    assert str(caught.value).startswith("Expected the migration to be warned")


# ---------------------------------------------------------------------------
# Occurrences
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("undisturbed")
@pytest.mark.filterwarnings("ignore")
def test_an_occurrence_constraint_counts_only_the_category_asked_for() -> None:
    with expect_warns(UserWarning, occurrences=exactly(2)) as warned:
        warn_twice()
        warn_unrelated()
    assert len(warned.subject) == 2


@pytest.mark.usefixtures("undisturbed")
def test_a_missed_count_says_what_it_found_and_lists_everything() -> None:
    with (
        pytest.raises(AssertionFailure) as caught,
        expect_warns(DeprecationWarning, occurrences=exactly(2)),
    ):
        warn_deprecated()
    assert str(caught.value) == (
        f"Expected DeprecationWarning to be warned exactly twice, but found 1:"
        f" DeprecationWarning('{DEPRECATED}') at {DEPRECATED_AT}."
    )


@pytest.mark.usefixtures("undisturbed")
def test_a_missed_count_with_nothing_at_all_still_reads_as_a_sentence() -> None:
    with (
        pytest.raises(AssertionFailure) as caught,
        expect_warns(UserWarning, occurrences=at_least(1)),
    ):
        pass
    assert str(caught.value) == (
        "Expected UserWarning to be warned at least once, but found 0: no warnings at all."
    )


@pytest.mark.usefixtures("undisturbed")
def test_at_most_is_the_upper_bound_and_holds_at_zero() -> None:
    with expect_warns(UserWarning, occurrences=at_most(2)) as warned:
        warn_twice()
    assert len(warned.subject) == 2
    with expect_warns(UserWarning, occurrences=at_most(1)):
        pass


@pytest.mark.usefixtures("undisturbed")
@pytest.mark.filterwarnings("ignore")
def test_exactly_zero_is_the_claim_that_it_never_appears() -> None:
    """``_occurrence`` keeps ``exactly(0)`` on purpose; nothing here may refuse it."""
    with expect_warns(UserWarning, occurrences=exactly(0)) as warned:
        warn_unrelated()
    assert warned.subject == ()


@pytest.mark.usefixtures("undisturbed")
def test_a_constraint_that_could_never_pass_is_refused_where_it_is_written() -> None:
    """A constraint no subject could ever satisfy is refused where it was written.

    ``at_least(0)`` is always true, so it asks nothing. Accepting it would turn a
    caller's mistake into a passing assertion about a subject; raising here points
    at the line that wrote it instead.
    """
    with pytest.raises(ValueError, match="at_least\\(0\\)"):
        at_least(0)


# ---------------------------------------------------------------------------
# The callable form
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("undisturbed")
def test_warns_hands_back_the_warnings_and_names_the_callable() -> None:
    warned = CallableExpect(warn_deprecated).warns(DeprecationWarning)
    assert [str(warning) for warning in warned.subject] == [DEPRECATED]


@pytest.mark.usefixtures("undisturbed")
def test_warns_names_the_callable_it_was_called_on() -> None:
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(quiet).warns(UserWarning)
    assert str(caught.value) == "Expected quiet to warn UserWarning, but nothing was warned."


@pytest.mark.usefixtures("undisturbed")
def test_warns_takes_the_occurrence_constraints_too() -> None:
    CallableExpect(warn_twice).warns(UserWarning, occurrences=exactly(2))
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(warn_twice).warns(UserWarning, occurrences=exactly(3))
    assert "to warn UserWarning exactly 3 times, but found 2:" in str(caught.value)


@pytest.mark.usefixtures("undisturbed")
def test_does_not_warn_passes_on_a_quiet_call() -> None:
    assert CallableExpect(quiet).does_not_warn().subject is quiet


@pytest.mark.usefixtures("undisturbed")
def test_does_not_warn_reports_what_was_issued() -> None:
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(warn_unrelated).does_not_warn()
    assert str(caught.value) == (
        f"Expected warn_unrelated not to warn, but issued RuntimeWarning('{UNRELATED}')"
        f" at {UNRELATED_AT}."
    )


@pytest.mark.usefixtures("undisturbed")
def test_does_not_warn_counts_several_rather_than_naming_one() -> None:
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(warn_twice).does_not_warn()
    assert str(caught.value) == (
        f"Expected warn_twice not to warn, but issued 2 warnings:"
        f" UserWarning('first') at {FIRST_AT}, UserWarning('second') at {SECOND_AT}."
    )


@pytest.mark.usefixtures("undisturbed")
@pytest.mark.filterwarnings("ignore")
def test_does_not_warn_with_a_category_ignores_the_others() -> None:
    CallableExpect(warn_unrelated).does_not_warn(UserWarning)
    with pytest.raises(AssertionFailure) as caught:
        CallableExpect(warn_unrelated).does_not_warn(RuntimeWarning)
    assert str(caught.value).startswith("Expected warn_unrelated not to warn RuntimeWarning,")


@pytest.mark.usefixtures("undisturbed")
def test_the_four_catch_warnings_blocks_this_repository_writes_by_hand() -> None:
    """The assertion ``pytest.warns`` has no spelling for, in its intended shape."""
    CallableExpect(quiet).does_not_warn(RuntimeWarning)
    CallableExpect(lambda: None).does_not_warn()


# ---------------------------------------------------------------------------
# The assertions on the captured warnings
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("undisturbed")
def test_with_message_searches_rather_than_matching_the_whole_string() -> None:
    with expect_warns(DeprecationWarning) as warned:
        warn_deprecated()
    warned.with_message("deprecated").and_.with_message(r"parse\(\) is")


@pytest.mark.usefixtures("undisturbed")
def test_with_message_passes_when_any_captured_warning_matches() -> None:
    with expect_warns(UserWarning) as warned:
        warn_twice()
    warned.with_message("^second$")


@pytest.mark.usefixtures("undisturbed")
def test_with_message_lists_the_one_message_there_was() -> None:
    with pytest.raises(AssertionFailure) as caught:
        with expect_warns(DeprecationWarning) as warned:
            warn_deprecated()
        warned.with_message("removed")
    assert str(caught.value) == (
        f"Expected DeprecationWarning to have a message matching 'removed',"
        f" but the message was '{DEPRECATED}'."
    )


@pytest.mark.usefixtures("undisturbed")
def test_with_message_lists_all_of_them_when_there_were_several() -> None:
    with pytest.raises(AssertionFailure) as caught:
        with expect_warns(UserWarning) as warned:
            warn_twice()
        warned.with_message("third")
    assert str(caught.value) == (
        "Expected UserWarning to have a message matching 'third',"
        " but the messages were 'first', 'second'."
    )


@pytest.mark.usefixtures("undisturbed")
def test_with_message_containing_is_a_substring_and_not_a_pattern() -> None:
    with expect_warns(DeprecationWarning) as warned:
        warnings.warn("parse() is deprecated (see docs)", DeprecationWarning, stacklevel=1)
    warned.with_message_containing("(see docs)")
    with pytest.raises(AssertionFailure) as caught:
        warned.with_message_containing("removed")
    assert str(caught.value) == (
        "Expected DeprecationWarning to have a message containing 'removed',"
        " but the message was 'parse() is deprecated (see docs)'."
    )


@pytest.mark.usefixtures("undisturbed")
def test_where_reaches_the_fields_a_warning_class_carries() -> None:
    with expect_warns(Coded) as warned:
        warnings.warn(Coded("final call", 7), stacklevel=1)
    warned.where(lambda warning: warning.code == 7)


@pytest.mark.usefixtures("undisturbed")
def test_where_names_the_predicate_and_the_warning_that_turned_it_down() -> None:
    with pytest.raises(AssertionFailure) as caught:
        with expect_warns(DeprecationWarning) as warned:
            warn_deprecated()
        warned.where(is_final)
    assert str(caught.value) == (
        f"Expected DeprecationWarning to satisfy is_final,"
        f" but DeprecationWarning('{DEPRECATED}') did not."
    )


@pytest.mark.usefixtures("undisturbed")
def test_where_says_none_of_them_when_there_were_several() -> None:
    with pytest.raises(AssertionFailure) as caught:
        with expect_warns(UserWarning) as warned:
            warn_twice()
        warned.where(mentions_parse)
    assert str(caught.value) == (
        "Expected UserWarning to satisfy mentions_parse, but none of them did:"
        " UserWarning('first'), UserWarning('second')."
    )


@pytest.mark.usefixtures("undisturbed")
def test_where_counts_the_warnings_it_left_out_of_the_listing() -> None:
    """The turned-down warnings are bounded like every other listing, and counted.

    ``where`` lists the warning *objects* rather than their messages, so it has a
    truncation tail of its own; a listing that stopped without saying so would
    read as the whole of what was captured.
    """
    with pytest.raises(AssertionFailure) as caught, formatting(max_items=1):
        with expect_warns(UserWarning) as warned:
            warn_twice()
        warned.where(mentions_parse)

    assert str(caught.value) == (
        "Expected UserWarning to satisfy mentions_parse, but none of them did:"
        " UserWarning('first'), ... (1 more)."
    )


@pytest.mark.usefixtures("undisturbed")
def test_the_listing_honours_the_formatting_scope() -> None:
    with pytest.raises(AssertionFailure) as caught, formatting(max_items=1):
        with expect_warns(UserWarning) as warned:
            warn_twice()
        warned.with_message("third")
    assert str(caught.value) == (
        "Expected UserWarning to have a message matching 'third',"
        " but the messages were 'first', ... (1 more)."
    )


@pytest.mark.usefixtures("undisturbed")
@pytest.mark.filterwarnings("ignore")
def test_the_issued_listing_honours_the_formatting_scope_too() -> None:
    with (
        pytest.raises(AssertionFailure) as caught,
        formatting(max_items=1),
        expect_warns(DeprecationWarning),
    ):
        warn_twice()
    assert str(caught.value) == (
        f"Expected DeprecationWarning to be warned, but the warnings issued were"
        f" UserWarning('first') at {FIRST_AT}, ... (1 more)."
    )


@pytest.mark.usefixtures("undisturbed")
def test_a_warning_message_at_the_character_budget_is_shown_whole() -> None:
    """The control for the clipping below: at the budget nothing is elided.

    Without it the boundary is free to drift by one in either direction, and a
    message shortened by a character nobody asked to lose is exactly the kind of
    change no other test in this file would notice.
    """
    with expect_warns(UserWarning) as warned:
        warnings.warn(AT_THE_BUDGET, UserWarning, stacklevel=1)

    with pytest.raises(AssertionFailure) as caught:
        warned.with_message_containing("removed")

    assert str(caught.value) == (
        "Expected UserWarning to have a message containing 'removed',"
        " but the message was " + repr(AT_THE_BUDGET) + "."
    )


@pytest.mark.usefixtures("undisturbed")
def test_a_warning_message_over_the_character_budget_is_clipped_and_counted() -> None:
    """One character more, and the rendering stops at the budget and says so.

    The length note is the half that matters: a message clipped in silence reads
    as the whole of what the warning carried, and the reader compares it against
    the wrong thing.
    """
    with expect_warns(UserWarning) as warned:
        warnings.warn(OVER_THE_BUDGET, UserWarning, stacklevel=1)

    with pytest.raises(AssertionFailure) as caught:
        warned.with_message_containing("removed")

    assert str(caught.value) == (
        "Expected UserWarning to have a message containing 'removed', but the message was "
        + repr(OVER_THE_BUDGET)[:MAX_CHARS]
        + "... (truncated from "
        + str(MAX_CHARS + 1)
        + " characters)."
    )


@pytest.mark.usefixtures("undisturbed")
def test_the_clipped_rendering_follows_the_formatting_scope_rather_than_a_constant() -> None:
    """A block that asked for a longer rendering gets it -- the cap is read at failure time."""
    with expect_warns(UserWarning) as warned:
        warnings.warn(OVER_THE_BUDGET, UserWarning, stacklevel=1)

    with pytest.raises(AssertionFailure) as caught, formatting(max_chars=20):
        warned.with_message_containing("removed")

    assert str(caught.value) == (
        "Expected UserWarning to have a message containing 'removed', but the message was "
        + repr(OVER_THE_BUDGET)[:20]
        + "... (truncated from "
        + str(MAX_CHARS + 1)
        + " characters)."
    )


# ---------------------------------------------------------------------------
# Soft assertions -- the second differentiator over ``pytest.warns``
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("undisturbed")
def test_a_failed_expect_warns_is_collected_rather_than_raised() -> None:
    """``pytest.warns`` raises, so it ends the test at the first finding."""
    with soft_assertions() as scope:
        with expect_warns(UserWarning):
            pass
        collected = scope.discard()
    assert collected == ["Expected UserWarning to be warned, but nothing was warned."]


@pytest.mark.usefixtures("undisturbed")
def test_a_failed_expect_warns_in_a_soft_scope_absorbs_the_rest_of_the_chain() -> None:
    """One root cause, one message: the handle is bound by ``as`` and cannot be swapped."""
    with soft_assertions() as scope:
        with expect_warns(UserWarning) as warned:
            pass
        warned.with_message("x").and_.with_message_containing("y")
        warned.where(mentions_parse)
        warned.matches(lambda captured: len(captured) == 1)
        warned.satisfies(lambda captured: expect(captured).is_not_none())
        collected = scope.discard()
    assert collected == ["Expected UserWarning to be warned, but nothing was warned."]


@pytest.mark.usefixtures("undisturbed")
def test_a_narrowing_assertion_after_an_absorbed_capture_adds_no_second_failure() -> None:
    """The chain above continues into the *narrowing* assertions too.

    ``is_instance_of`` reports through ``_fail_narrowing`` rather than ``_fail``,
    so the absorbing seam has to be cut twice; a subject that never captured
    anything is not an instance of anything either, and saying so would be a
    second finding derived from the first.
    """
    with soft_assertions() as scope:
        with expect_warns(UserWarning) as warned:
            pass
        warned.is_instance_of(str)
        warned.is_exactly_instance_of(str)
        collected = scope.discard()

    assert collected == ["Expected UserWarning to be warned, but nothing was warned."]


@pytest.mark.usefixtures("undisturbed")
def test_a_chain_past_an_absorbed_narrowing_keeps_every_collected_failure() -> None:
    """``.which`` is where an empty capture handed back as a subject runs out.

    A tuple has no ``which``, and the ``AttributeError`` it answers with is not an
    ``AssertionError`` -- so it crosses the scope instead of being collected, and
    takes with it every failure the block had already gathered. The narrowing seam
    has to hand back something that goes on absorbing.
    """
    with pytest.raises(AssertionFailure) as caught, soft_assertions():
        expect(1).is_equal_to(2)
        with expect_warns(UserWarning) as warned:
            pass
        warned.is_instance_of(UserWarning).which.is_equal_to("x")

    assert str(caught.value) == (
        "2 assertions failed:\n"
        "  (1) Expected 1 to equal 2, but was 1.\n"
        "  (2) Expected UserWarning to be warned, but nothing was warned."
    )


@pytest.mark.usefixtures("undisturbed")
def test_an_absorbed_narrowing_hands_back_the_absorbing_stand_in() -> None:
    """What it hands back is the stand-in, not the empty capture it kept as a subject.

    ``()`` is the right subject for the assertions that pass it to a predicate of
    the user's, and the wrong thing to hand the rest of a chain. So this family
    keeps both, and the two are told apart by their ``repr`` -- which is the whole
    reason the stand-in has one.
    """
    with soft_assertions() as scope:
        with expect_warns(UserWarning) as warned:
            pass
        narrowed = warned.is_instance_of(str)
        scope.discard()

    assert "narrowing failed" in repr(narrowed)
    assert warned.subject == ()


@pytest.mark.usefixtures("undisturbed")
def test_a_narrowing_assertion_on_a_captured_subject_still_reports_normally() -> None:
    """Nothing was absorbed, so the seam delegates and the failure is the ordinary one."""
    with expect_warns(UserWarning) as warned:
        warn_twice()

    with pytest.raises(AssertionFailure) as caught:
        warned.is_instance_of(str)

    assert str(caught.value) == "Expected UserWarning to be an instance of str, but was tuple."


@pytest.mark.usefixtures("undisturbed")
def test_the_empty_capture_is_a_real_value_a_predicate_can_survive() -> None:
    """The reason the callable-taking assertions need no guard: ``()`` is a warning tuple.

    ``_CaughtExpect`` has to guard ``where``, ``matches`` and ``satisfies``
    because an absorbed exception subject is a stand-in whose every attribute is
    itself, and a predicate written for a real exception raises ``TypeError`` on
    it -- which aborts the scope and loses every failure it had collected. A
    predicate written for real warnings runs happily against no warnings.
    """
    with pytest.raises(AssertionFailure) as caught, soft_assertions():
        with expect_warns(UserWarning) as warned:
            pass
        warned.where(mentions_parse)
        CallableExpect(warn_unrelated).does_not_warn()
    message = str(caught.value)
    assert "2 assertions failed:" in message
    assert "Expected UserWarning to be warned, but nothing was warned" in message
    assert "not to warn, but issued RuntimeWarning" in message


@pytest.mark.usefixtures("undisturbed")
def test_a_passing_warning_assertion_in_a_soft_scope_reports_nothing() -> None:
    with soft_assertions() as scope:
        CallableExpect(warn_deprecated).warns(DeprecationWarning).with_message("deprecated")
        with expect_warns(DeprecationWarning) as warned:
            warn_deprecated()
        warned.with_message_containing("parse")
        assert scope.discard() == []


@pytest.mark.usefixtures("undisturbed")
def test_a_scope_name_prefixes_a_warning_failure() -> None:
    with (
        pytest.raises(AssertionFailure) as caught,
        soft_assertions("Migration"),
        expect_warns(UserWarning),
    ):
        pass
    assert "Expected Migration/UserWarning to be warned" in str(caught.value)


# ---------------------------------------------------------------------------
# The global state: filters, nesting, threads
# ---------------------------------------------------------------------------
def test_capturing_restores_the_filters_and_showwarning_exactly() -> None:
    filters = warnings.filters[:]
    showwarning = warnings.showwarning
    with expect_warns(UserWarning):
        warnings.warn("x", UserWarning, stacklevel=1)
    assert warnings.filters == filters
    assert warnings.showwarning is showwarning


def test_the_filters_come_back_even_when_the_assertion_fails() -> None:
    """The restoration must not be on the happy path only, or a red suite goes redder."""
    filters = warnings.filters[:]
    with pytest.raises(AssertionFailure), expect_warns(UserWarning):
        pass
    assert warnings.filters == filters


def test_the_filters_come_back_even_when_the_block_raises() -> None:
    filters = warnings.filters[:]
    with pytest.raises(ValueError, match="bad input"), expect_warns(UserWarning):
        boom()
    assert warnings.filters == filters


@pytest.mark.usefixtures("undisturbed")
def test_captures_nest_and_the_outer_one_sees_what_the_inner_declined() -> None:
    """Re-entrancy, and the re-issue of unmatched warnings, in one observation.

    The inner block wanted a ``DeprecationWarning``; the ``UserWarning`` issued
    inside it is not its business, so it goes back to whatever was listening --
    which, here, is the outer capture. A capture that swallowed it would have
    disarmed the outer assertion.
    """
    with expect_warns(UserWarning) as outer:
        with expect_warns(DeprecationWarning) as inner:
            warn_deprecated()
            warnings.warn("not mine", UserWarning, stacklevel=1)
        assert [str(warning) for warning in inner.subject] == [DEPRECATED]
    assert [str(warning) for warning in outer.subject] == ["not mine"]


@pytest.mark.usefixtures("undisturbed")
def test_a_warning_from_another_thread_lands_in_whatever_block_is_open() -> None:
    """Not a feature: ``warnings`` keeps one ``showwarning`` for the process.

    Pinned rather than fixed, because the only fix would be a lock held across
    the user's entire block -- arbitrary code, including code that waits on the
    very thread this is about.
    """
    with expect_warns(UserWarning) as warned:
        thread = threading.Thread(target=warn_twice)
        thread.start()
        thread.join()
    assert [str(warning) for warning in warned.subject] == ["first", "second"]


# ---------------------------------------------------------------------------
# Ambient filters
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("undisturbed")
def test_a_warning_the_ambient_filters_ignore_is_still_captured() -> None:
    """The ``DeprecationWarning`` case, which is ignored by default outside tests."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with expect_warns(DeprecationWarning) as warned:
            warn_deprecated()
        assert len(warned.subject) == 1


@pytest.mark.usefixtures("undisturbed")
def test_an_error_filter_does_not_turn_the_warning_under_test_into_an_exception() -> None:
    """``-W error``. An assertion that a warning fired cannot be written otherwise."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with expect_warns(UserWarning) as warned:
            warnings.warn("still a warning in here", UserWarning, stacklevel=1)
        assert len(warned.subject) == 1


@pytest.mark.usefixtures("undisturbed")
def test_an_error_filter_still_bites_the_warnings_nobody_asked_about() -> None:
    """The other half of the same decision: what is re-issued meets the real filters.

    The warning is re-issued after the capture closes, so it raises there rather
    than inside the call that issued it. Faithful to the ambient filters, but
    later: the traceback points at the end of the block, not at the warning's own
    line. That is the price of not swallowing what the assertion was not about.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        with pytest.raises(RuntimeWarning, match=UNRELATED), expect_warns(UserWarning):
            warnings.warn("mine", UserWarning, stacklevel=1)
            warn_unrelated()


@pytest.mark.usefixtures("undisturbed")
def test_does_not_warn_reports_a_failure_where_an_error_filter_would_raise() -> None:
    """Under ``-W error`` the bare ``catch_warnings`` idiom cannot be written at all.

    The warning becomes an exception inside the call, so the test reports a
    ``RuntimeWarning`` instead of the finding. Here it is an assertion failure,
    which a soft scope can collect.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with soft_assertions() as scope:
            CallableExpect(warn_twice).does_not_warn()
            collected = scope.discard()
    assert len(collected) == 1
    assert "not to warn, but issued 2 warnings" in collected[0]


@pytest.mark.usefixtures("undisturbed")
def test_the_callable_form_re_issues_what_it_was_not_about_too() -> None:
    """The same decision, through the other entry point, which repeats the call.

    ``warns`` and ``does_not_warn`` each open their own capture and call
    ``reissue_unmatched`` themselves; they do not go through ``_CaughtWarnings``.
    So the helper being right says nothing about whether this form still calls
    it, and the block-form test above cannot cover this line. Deleting the call
    from ``warns`` leaves every other test in this file green.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        with pytest.raises(RuntimeWarning, match=UNRELATED):
            CallableExpect(warn_deprecated_and_unrelated).warns(DeprecationWarning)


@pytest.mark.usefixtures("undisturbed")
def test_does_not_warn_re_issues_the_categories_it_was_not_asked_about() -> None:
    """And the third copy of the call, which is the one that passes while it does it.

    ``does_not_warn(DeprecationWarning)`` is satisfied here -- no deprecation was
    issued -- so the re-issue happens on the *passing* path, where a swallowed
    ``RuntimeWarning`` would leave no trace at all.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        with pytest.raises(RuntimeWarning, match=UNRELATED):
            CallableExpect(warn_unrelated).does_not_warn(DeprecationWarning)


# ---------------------------------------------------------------------------
# The __warningregistry__ trap
# ---------------------------------------------------------------------------
#: What ``warn_explicit`` keeps in a ``__warningregistry__``: the filter version
#: under one key, and a truthy marker under the ``(text, category, lineno)`` of
#: every warning already shown. Spelled out because the checkers will not take
#: ``dict[str, Any]`` for it, and they are right to refuse -- the key type is
#: half of what makes the trap work.
type Registry = dict[str | tuple[str, type[Warning], int], int]

TRAPPED: Final = "issued once, and never again"
TRAP_FILE: Final = "trap.py"
TRAP_LINE: Final = 1


def _swallow(*_args: Any, **_kwargs: Any) -> None:
    """A ``showwarning`` that shows nothing, so priming the registry stays quiet."""


def _recorder(seen: list[str]) -> "Callable[..., None]":
    """A ``showwarning`` that records what reached it."""

    def showwarning(message: Any, *_args: Any, **_kwargs: Any) -> None:
        seen.append(str(message))

    return showwarning


def _primed_registry() -> "Registry":
    """A ``__warningregistry__`` that has already seen :data:`TRAPPED`, and is *live*.

    Live is the whole trap, and the reason this is fifteen lines rather than a
    dict literal. ``warn_explicit`` clears any registry whose ``version`` does not
    match the interpreter's current filter version, so a registry primed with a
    stale version disarms itself and the test below would pass for free. The
    version counter lives in the C ``_warnings`` module and is not readable from
    Python, so the entry is made the only way it can be made honestly: by issuing
    the warning under a filter that writes the registry.

    The restore at the end is an assignment rather than a ``catch_warnings`` on
    purpose. Putting the filters back must not bump the version -- ``simplefilter``
    and ``catch_warnings`` both do -- or the registry goes stale between the
    priming and the assertion.
    """
    registry: Registry = {}
    filters = warnings.filters[:]
    showwarning = warnings.showwarning
    try:
        warnings.showwarning = _swallow
        warnings.filterwarnings("default", category=UserWarning)
        warnings.warn_explicit(TRAPPED, UserWarning, TRAP_FILE, TRAP_LINE, registry=registry)
    finally:
        warnings.showwarning = showwarning
        warnings.filters = filters
    return registry


# The control warning has to reach `showwarning` to be a control, so the ambient
# filter is pinned rather than inherited. The mark is applied before the body
# runs, which matters: `_primed_registry` makes the last change to the filters,
# and any change after it would clear the registry it had just primed.
@pytest.mark.filterwarnings("always")
def test_the_registry_trap_is_real() -> None:
    """Without this, the test below proves nothing -- it could be passing for free.

    No ``catch_warnings`` here, on purpose: entering one bumps the filter version
    and defuses the very trap being demonstrated. Replacing ``showwarning`` does
    not, so that is the observation channel. The second warning is the control: it
    shares everything with the first but its key, and it comes through.
    """
    registry = _primed_registry()
    seen: list[str] = []
    showwarning = warnings.showwarning
    try:
        warnings.showwarning = _recorder(seen)
        warnings.warn_explicit(TRAPPED, UserWarning, TRAP_FILE, TRAP_LINE, registry=registry)
        warnings.warn_explicit("never seen before", UserWarning, TRAP_FILE, 2, registry=registry)
    finally:
        warnings.showwarning = showwarning
    assert seen == ["never seen before"], "a live registry entry must swallow its warning"


@pytest.mark.usefixtures("undisturbed")
def test_a_warning_the_registry_has_already_seen_is_captured_anyway() -> None:
    """The trap every serious warning helper has to deal with, and how this one does.

    Not by clearing registries -- there is no way to reach them all -- but by
    using ``catch_warnings``, whose ``__enter__`` bumps ``_filters_version`` and
    so invalidates every registry in the process at once.
    """
    registry = _primed_registry()
    with expect_warns(UserWarning) as warned:
        warnings.warn_explicit(TRAPPED, UserWarning, TRAP_FILE, TRAP_LINE, registry=registry)
    assert [str(warning) for warning in warned.subject] == [TRAPPED]


@pytest.mark.usefixtures("undisturbed")
def test_the_same_warning_twice_in_one_block_is_captured_twice() -> None:
    """``action="always"`` never writes the registry, so a repeat is not deduplicated."""
    registry: Registry = {}
    with expect_warns(UserWarning, occurrences=exactly(2)) as warned:
        warnings.warn_explicit(TRAPPED, UserWarning, TRAP_FILE, TRAP_LINE, registry=registry)
        warnings.warn_explicit(TRAPPED, UserWarning, TRAP_FILE, TRAP_LINE, registry=registry)
    assert len(warned.subject) == 2


# ---------------------------------------------------------------------------
# How a warning was raised
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("undisturbed")
def test_a_warning_raised_as_a_class_as_an_instance_or_as_text_all_count() -> None:
    """``warnings.warn`` accepts all three and records an instance for each.

    The class form is annotated through an ``Any`` because typeshed says a
    message is a ``str`` or a ``Warning`` and a class is neither -- legal at
    runtime, unsayable in the type system, and worth pinning precisely because a
    capture written against ``record.message`` being a string would break on it.
    """
    as_a_class: Any = UserWarning
    with expect_warns(UserWarning, occurrences=exactly(3)) as warned:
        warnings.warn(as_a_class, stacklevel=1)
        warnings.warn(UserWarning("an instance"), stacklevel=1)
        warnings.warn("some text", UserWarning, stacklevel=1)
    assert [type(warning) for warning in warned.subject] == [UserWarning] * 3


# ---------------------------------------------------------------------------
# Blocks that did not finish, and blocks inside other blocks
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("undisturbed")
def test_an_exception_in_the_block_travels_and_nothing_is_judged() -> None:
    """A block that did not finish has not been observed; its exception is the finding."""
    with pytest.raises(ValueError, match="bad input"), expect_warns(UserWarning):
        boom()


@pytest.mark.usefixtures("undisturbed")
def test_a_block_that_warned_and_then_raised_still_lets_the_exception_out() -> None:
    with pytest.raises(ValueError, match="bad input"), expect_warns(DeprecationWarning):
        warns_then_raises()


@pytest.mark.usefixtures("undisturbed")
def test_expect_warns_nests_inside_expect_raises() -> None:
    with expect_raises(ValueError) as caught, expect_warns(DeprecationWarning) as warned:
        warns_then_raises()
    caught.with_message("bad input")
    with pytest.raises(RuntimeError, match="only available after"):
        _ = warned.subject


@pytest.mark.usefixtures("undisturbed")
def test_expect_raises_nests_inside_expect_warns() -> None:
    """The order that works all the way through: the inner block absorbs the exception."""
    with expect_warns(DeprecationWarning) as warned:
        with expect_raises(ValueError) as caught:
            warns_then_raises()
        caught.with_message("bad input")
    warned.with_message_containing("deprecated")


@pytest.mark.usefixtures("undisturbed")
def test_the_subject_is_unavailable_until_the_block_has_finished() -> None:
    with (
        pytest.raises(RuntimeError, match="only available after"),
        expect_warns(UserWarning) as warned,
    ):
        _ = warned.subject


@pytest.mark.usefixtures("undisturbed")
def test_an_ordinary_typo_on_the_handle_is_still_an_attribute_error() -> None:
    """``__getattr__`` explains ``_subject``, and explains nothing else.

    Reached through an ``Any`` rather than through a suppression comment: the
    handle's static type does not have this attribute, which is the whole point,
    and both checkers would be right to say so.
    """
    with pytest.raises(AttributeError, match="with_mesage"), expect_warns(UserWarning) as warned:
        handle: Any = warned
        _ = handle.with_mesage


# ---------------------------------------------------------------------------
# Async, refused through the guard the exception family already had
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("undisturbed")
def test_warns_refuses_an_async_callable() -> None:
    """Calling an ``async def`` returns a coroutine without running a line of it.

    Nothing warns, so the assertion would report "nothing was warned" about code
    that was never executed -- a finding about the test, dressed as a finding
    about the subject. ``_reject_awaitable`` is the exception family's guard and
    this reuses it rather than growing a second one.
    """
    with pytest.raises(TypeError) as caught:
        CallableExpect(never_awaited).warns(UserWarning)
    assert "coroutine" in str(caught.value)


@pytest.mark.usefixtures("undisturbed")
def test_does_not_warn_refuses_an_async_callable() -> None:
    """The dangerous half: this one would have *passed* for code that warns."""
    with pytest.raises(TypeError) as caught:
        CallableExpect(never_awaited).does_not_warn()
    assert "coroutine" in str(caught.value)


@pytest.mark.usefixtures("undisturbed")
def test_the_refused_coroutine_is_closed_rather_than_leaked() -> None:
    """An un-awaited coroutine warns at collection time, from somewhere unrelated."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        with pytest.raises(TypeError):
            CallableExpect(never_awaited).warns(UserWarning)
