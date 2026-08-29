"""Three capabilities on the subject every other subject inherits from.

``is_truthy``/``is_falsy`` because Python has several unrelated ways to be falsy
and the message should say which one applies; ``satisfies_any``/``satisfies_none``
because chaining is an implicit AND and these are the only way to spell anything
else; and explicit naming, because subject recovery reads the source, and there
are places where the source does not contain the answer.

Around those, the parts of the chain that are read rather than asserted on: how a
finding that runs to several lines is laid out under the heading it belongs to
and punctuated beside its one-line neighbours, what containment and type
membership say the subject actually held, what ``Found`` and ``SoftScope`` say
when a debugger prints them, the path a nested scope composes, and the traceback
hook's answer when it is asked with no exception in hand.
"""

import pytest

from lovely_assertions import AssertionFailure, Expect, SoftScope, expect, soft_assertions
from lovely_assertions._exceptions import hide_internal_frames


class Empty:
    """Falsy through ``__len__``."""

    __slots__ = ()

    def __len__(self) -> int:
        return 0


class Never:
    """Falsy through ``__bool__``, with a useless ``repr`` — as domain types have."""

    __slots__ = ()

    def __bool__(self) -> bool:
        return False


class Ticket:
    """A domain type no subject in the dispatch table claims.

    Not callable, not a container, not a scalar: :func:`subject_for` answers
    ``None`` for it, which is the case ``Found.which`` has to fall through.
    """

    __slots__ = ()


class Heading(str):
    """A ``str`` subclass — an instance of ``str`` without being one exactly."""

    __slots__ = ()


def _message(callback: object) -> str:
    with pytest.raises(AssertionFailure) as caught:
        callback()  # type: ignore[operator]  # pyright: ignore[reportCallIssue]
    return str(caught.value)


# ---------------------------------------------------------------------------
# Truthiness, and saying which kind
# ---------------------------------------------------------------------------
def test_is_truthy_and_is_falsy_pass_where_they_should() -> None:
    expect(1).is_truthy()
    expect("x").is_truthy()
    expect([0]).is_truthy()
    expect(0).is_falsy()
    expect("").is_falsy()
    expect([]).is_falsy()
    expect(None).is_falsy()


def test_they_chain_like_any_other_assertion() -> None:
    subject = expect(1)
    assert subject.is_truthy() is subject


#: Annotated so `set()` does not come out as `set[Unknown]` under pyright strict.
_FALSY_KINDS: list[tuple[object, str]] = [
    (None, "it is None"),
    (0, "it is 0"),
    (0.0, "it is 0.0"),
    (False, "it is False"),
    ("", "it is an empty str"),
    ([], "it is an empty list"),
    ({}, "it is an empty dict"),
    (set(), "it is an empty set"),
]


@pytest.mark.parametrize(
    ("value", "expected"),
    _FALSY_KINDS,
    ids=["none", "zero", "zero-float", "false", "str", "list", "dict", "set"],
)
def test_is_truthy_names_the_kind_of_falsy(value: object, expected: str) -> None:
    """The reason to have this rather than ``matches(bool)``.

    Python is falsy in several unrelated ways, and which one applies is the whole
    content of the failure. ``matches(bool)`` can only say the predicate returned
    False, which the reader already knew.
    """
    assert _message(lambda: expect(value).is_truthy()) == (
        f"Expected value to be truthy, but {expected}."
    )


def test_a_custom_len_is_reported_as_an_empty_container() -> None:
    value = Empty()
    assert "empty Empty" in _message(lambda: expect(value).is_truthy())


def test_a_custom_bool_is_reported_as_such() -> None:
    """Its ``repr`` is an address, so naming the method is the useful thing."""
    value = Never()
    assert "Never.__bool__ returned False" in _message(lambda: expect(value).is_truthy())


def test_is_falsy_reports_the_value_that_was_truthy() -> None:
    count = 3
    assert _message(lambda: expect(count).is_falsy()) == "Expected count to be falsy, but was 3."


# ---------------------------------------------------------------------------
# satisfies_any / satisfies_none — the one composition chaining cannot spell
# ---------------------------------------------------------------------------
def test_satisfies_any_passes_when_one_branch_holds() -> None:
    subject = expect(5)
    assert (
        subject.satisfies_any(
            lambda it: it.is_equal_to(9),
            lambda it: it.is_equal_to(5),
        )
        is subject
    )


def test_satisfies_any_reports_every_branch_when_none_holds() -> None:
    port = 8080
    message = _message(
        lambda: expect(port).satisfies_any(
            lambda it: it.is_equal_to(80),
            lambda it: it.is_equal_to(443),
        )
    )
    assert "to satisfy at least one of 2 alternatives" in message
    assert "to equal 80" in message
    assert "to equal 443" in message


def test_satisfies_any_stops_at_the_first_branch_that_holds() -> None:
    """A later branch must not run once the assertion is settled."""
    ran: list[int] = []

    def record(index: int) -> object:
        ran.append(index)
        return None

    expect(5).satisfies_any(
        lambda it: (record(1), it.is_equal_to(5))[1],
        lambda it: (record(2), it.is_equal_to(9))[1],
    )
    assert ran == [1]


def test_satisfies_none_is_the_complement() -> None:
    expect(5).satisfies_none(lambda it: it.is_equal_to(9))
    port = 8080
    message = _message(
        lambda: expect(port).satisfies_none(
            lambda it: it.is_equal_to(80),
            lambda it: it.is_equal_to(8080),
        )
    )
    assert "alternative 2" in message


def test_the_branch_receives_the_concrete_subject() -> None:
    """A branch gets ``Self``, so a string subject autocompletes to string assertions."""
    expect("hello").satisfies_any(lambda it: it.starts_with("he"))


def test_an_empty_call_is_a_caller_bug() -> None:
    with pytest.raises(ValueError, match="at least one"):
        expect(5).satisfies_any()


def test_a_real_error_inside_a_branch_propagates() -> None:
    with pytest.raises(ZeroDivisionError):
        expect(5).satisfies_any(lambda _it: 1 / 0)


# ---------------------------------------------------------------------------
# Explicit naming, where reading the source cannot help
# ---------------------------------------------------------------------------
def test_a_name_replaces_the_recovered_one() -> None:
    value = 3
    assert _message(lambda: expect(value, name="row 3").is_equal_to(4)) == (
        "Expected row 3 to equal 4, but was 3."
    )


def test_the_loop_that_motivates_it() -> None:
    """Recovery names the loop variable, which is the same for every iteration."""
    rows = [{"id": 0}, {"id": 9}]  # the second row is the wrong one
    with pytest.raises(AssertionFailure) as caught:
        for index, row in enumerate(rows):
            expect(row, name=f"rows[{index}]").is_equal_to({"id": index})
    assert "Expected rows[1] " in str(caught.value)


def test_described_as_names_a_subject_already_built() -> None:
    value = 3
    assert _message(lambda: expect(value).described_as("the retry count").is_equal_to(4)) == (
        "Expected the retry count to equal 4, but was 3."
    )


def test_described_as_returns_the_same_subject_type() -> None:
    subject = expect("hello")
    assert subject.described_as("greeting").starts_with("he").subject == "hello"


def test_a_name_survives_a_soft_scope_path() -> None:
    with soft_assertions("sync") as scope:
        expect(3, name="row 3").is_equal_to(4)
        collected = scope.discard()
    assert collected == ["Expected sync/row 3 to equal 4, but was 3."]


def test_naming_is_optional_and_costs_nothing_when_unused() -> None:
    balance = 4
    assert _message(lambda: expect(balance).is_equal_to(3)) == (
        "Expected balance to equal 3, but was 4."
    )


def test_a_branch_that_returns_a_verdict_is_refused() -> None:
    """A branch is an inspector: it asserts, it does not report.

    This is the shape the bug takes here. A branch returning ``False`` collects
    nothing, and "collected nothing" is how a branch says it held -- so
    ``satisfies_any`` would return green on a branch that tested the subject
    against nothing at all. ``satisfies_none`` reads the same emptiness the other
    way round and fails on it.
    """
    with pytest.raises(TypeError, match="instead of asserting anything"):
        expect(5).satisfies_any(lambda it: it.subject > 100)
    with pytest.raises(TypeError, match="instead of asserting anything"):
        expect(5).satisfies_none(lambda it: it.subject > 100)


def test_the_branch_refusal_names_no_sibling() -> None:
    """There is no predicate-taking twin of these two, so none is offered.

    ``matches`` is the twin of ``satisfies`` and ``only_contains`` of
    ``all_satisfy``; composition over branches has no such pair, and inventing a
    pointer to a method that does not exist would be worse than none.
    """
    with pytest.raises(TypeError) as caught:
        expect(5).satisfies_any(lambda it: it.subject > 100)
    message = str(caught.value)
    assert "use `" not in message
    assert message.endswith("assert instead: `lambda it: expect(it).is_positive()`")


def test_a_branch_that_asserts_is_untouched() -> None:
    subject = expect(5)
    assert subject.satisfies_any(lambda it: it.is_equal_to(5)) is subject
    assert subject.satisfies_none(lambda it: it.is_equal_to(9)) is subject


# ---------------------------------------------------------------------------
# A finding that runs to several lines keeps its block under its own bullet
# ---------------------------------------------------------------------------
def test_satisfies_any_indents_a_multi_line_alternative_under_its_heading() -> None:
    """A branch's difference block has to stay attached to the branch it came from.

    Every alternative is reported, each one can carry a detail block of its own,
    and flush-left continuation lines would leave the reader unable to tell which
    heading a difference belongs to.
    """
    reading = [1, 2, 3]

    message = _message(
        lambda: expect(reading).satisfies_any(
            lambda it: it.is_equal_to([1, 5, 3]),
            lambda it: it.is_equal_to([1, 2, 9]),
        )
    )

    assert message == (
        "Expected reading to satisfy at least one of 2 alternatives, but none did.\n"
        "  alternative 1:\n"
        "    - Expected reading to equal [1, 5, 3], but was [1, 2, 3]\n"
        "        first difference at index 1: 2 instead of 5\n"
        "  alternative 2:\n"
        "    - Expected reading to equal [1, 2, 9], but was [1, 2, 3]\n"
        "        first difference at index 2: 3 instead of 9"
    )


def test_satisfies_indents_a_multi_line_finding_under_its_bullet() -> None:
    """One nested failure, several lines: the block sits under the bullet.

    A mapping comparison reports a line per key that disagrees, and those lines
    belong to the finding above them rather than to the list.
    """
    row = {"id": 1, "name": "a"}

    message = _message(
        lambda: expect(row).satisfies(lambda it: expect(it).is_equal_to({"id": 2, "name": "b"}))
    )

    assert message == (
        "Expected the value to satisfy the inspection.\n"
        "  - Expected the value to equal {'id': 2, 'name': 'b'},"
        " but was {'id': 1, 'name': 'a'}\n"
        "      values differ at key 'id': 1 instead of 2\n"
        "      values differ at key 'name': 'a' instead of 'b'"
    )


def test_satisfies_any_punctuates_every_alternative_the_same_way() -> None:
    """One list, one rule: no bullet in it ends on a full stop.

    The full stop belongs to the sentence, so it comes off the first line of a
    finding whether or not a difference block follows it. Dropping it from the
    message as a whole reaches only the last line, which for a finding with a
    block is a line that never had one -- and the reader sees one list punctuated
    two ways.
    """
    reading = [1, 2, 3]

    message = _message(
        lambda: expect(reading).satisfies_any(
            lambda it: it.has_length(9),
            lambda it: it.is_equal_to([1, 5, 3]),
        )
    )

    assert message == (
        "Expected reading to satisfy at least one of 2 alternatives, but none did.\n"
        "  alternative 1:\n"
        "    - Expected reading to have length 9, but had 3: [1, 2, 3]\n"
        "  alternative 2:\n"
        "    - Expected reading to equal [1, 5, 3], but was [1, 2, 3]\n"
        "        first difference at index 1: 2 instead of 5"
    )


def test_satisfies_punctuates_every_finding_the_same_way() -> None:
    """The findings list under one inspector reads by the same rule."""
    reading = [1, 2, 3]

    message = _message(
        lambda: expect(reading).satisfies(
            lambda it: expect(it).has_length(9).is_equal_to([1, 5, 3])
        )
    )

    assert message == (
        "Expected the value to satisfy the inspection.\n"
        "  - Expected the value to have length 9, but had 3: [1, 2, 3]\n"
        "  - Expected the value to equal [1, 5, 3], but was [1, 2, 3]\n"
        "      first difference at index 1: 2 instead of 5"
    )


def test_a_soft_scope_keeps_the_full_stop_on_every_numbered_message() -> None:
    """The aggregate is the other choice, made consistently.

    A numbered entry there is the whole message a raising scope would have
    raised, reproduced unaltered, so it keeps its full stop -- and keeps it for a
    one-line entry and an entry carrying a difference block alike.
    """
    reading = [1, 2, 3]

    with pytest.raises(AssertionFailure) as caught, soft_assertions():
        expect(reading).has_length(9)
        expect(reading).is_equal_to([1, 5, 3])

    assert str(caught.value) == (
        "2 assertions failed:\n"
        "  (1) Expected reading to have length 9, but had 3: [1, 2, 3].\n"
        "  (2) Expected reading to equal [1, 5, 3], but was [1, 2, 3].\n"
        "        first difference at index 1: 2 instead of 5"
    )


# ---------------------------------------------------------------------------
# Containment, and saying what was in the variable
# ---------------------------------------------------------------------------
def test_is_in_reports_the_value_that_was_not_in_the_container() -> None:
    """Naming the container alone sends the reader back to look up the subject."""
    role = "viewer"

    message = _message(lambda: expect(role).is_in(["admin", "editor"]))

    assert message == "Expected role to be in ['admin', 'editor'], but was 'viewer'."


def test_is_not_in_reports_the_value_that_was_in_the_container() -> None:
    """Which of the forbidden entries matched is the whole content of the failure."""
    role = "admin"

    message = _message(lambda: expect(role).is_not_in(["admin", "editor"]))

    assert message == "Expected role not to be in ['admin', 'editor'], but was 'admin'."


def test_is_in_clips_a_subject_too_large_to_print() -> None:
    """Both halves of the sentence are bounded, or a big subject drowns the message."""
    payload = "x" * 500

    message = _message(lambda: expect(payload).is_in(["a"]))

    assert "more characters)." in message
    assert len(message) < 500


# ---------------------------------------------------------------------------
# Type membership, and the subclass that makes it fail
# ---------------------------------------------------------------------------
def test_is_not_instance_of_names_the_type_the_subject_actually_had() -> None:
    """A subclass is an instance, and it is the case a reader does not expect.

    Without the actual type the message says only what was ruled out, leaving the
    reader to guess whether the subject was the named type or something deriving
    from it -- which is exactly the distinction between this assertion and
    ``is_not_exactly_instance_of``.
    """
    heading = Heading("intro")

    message = _message(lambda: expect(heading).is_not_instance_of(str))

    assert message == "Expected heading not to be an instance of str, but was Heading."


def test_is_not_instance_of_names_the_exact_type_too() -> None:
    label = "x"

    message = _message(lambda: expect(label).is_not_instance_of(str))

    assert message == "Expected label not to be an instance of str, but was str."


# ---------------------------------------------------------------------------
# Continuing from a found value
# ---------------------------------------------------------------------------
def test_found_repr_shows_the_value_it_holds() -> None:
    """A ``Found`` is a fork in the chain, so its repr has to say what it forked on.

    ``.and_`` and ``.which`` go to two different objects, and a debugger printing
    the parent subject would say nothing about which value was found.
    """
    payload = "yes"

    found = expect(payload).is_instance_of(str)

    assert repr(found) == "Found('yes')"


def test_which_falls_back_to_the_generic_subject_for_a_type_nothing_claims() -> None:
    """The type the caller named decides -- and a plain domain class names nothing.

    ``is_instance_of`` records the type that was written so ``.which`` honours it
    rather than re-dispatching the value. Nothing claims ``Ticket``, so the lookup
    comes back empty and the value is dispatched exactly as ``expect()`` would
    dispatch it: the generic subject, holding the same object.
    """
    ticket = Ticket()

    continued = expect(ticket).is_instance_of(Ticket).which

    assert type(continued) is Expect
    assert continued.subject is ticket


# ---------------------------------------------------------------------------
# What a soft scope says about itself
# ---------------------------------------------------------------------------
def test_soft_scope_repr_names_the_scope_and_counts_what_it_holds() -> None:
    """The two facts a reader stopped inside a block wants: which scope, how bad."""
    with soft_assertions("sync") as scope:
        expect(3).is_equal_to(4)
        rendered = repr(scope)
        scope.discard()

    assert rendered == "SoftScope('sync', failures=1)"


def test_soft_scope_repr_of_an_unopened_anonymous_scope_says_so() -> None:
    scope = SoftScope()

    assert repr(scope) == "SoftScope(None, failures=0)"


def test_soft_scope_path_joins_a_nested_scope_to_its_parent() -> None:
    """The path is what prefixes every subject name the block reports."""
    with soft_assertions("sync") as outer, soft_assertions("rows") as inner:
        paths = (outer.path, inner.path)

    assert paths == ("sync", "sync/rows")


def test_soft_scope_path_drops_an_anonymous_scope_from_the_chain() -> None:
    """An unnamed scope groups without contributing a segment.

    It still collects and still hands its failures up; it just has nothing to add
    to the name, so the scope inside it composes with its grandparent instead.
    """
    with (
        soft_assertions("sync") as outer,
        soft_assertions() as anonymous,
        soft_assertions("rows") as inner,
    ):
        paths = (outer.path, anonymous.path, inner.path)

    assert paths == ("sync", "sync", "sync/rows")


# ---------------------------------------------------------------------------
# The traceback hook, asked without an exception
# ---------------------------------------------------------------------------
def test_hide_internal_frames_hides_the_library_when_asked_with_no_exception() -> None:
    """``__tracebackhide__`` is read as a plain flag as well as called with an excinfo.

    pytest hands the callable its ``ExceptionInfo``, and the answer then depends
    on what is propagating. A caller with nothing to hand it -- anything reading
    the name the way a bare ``__tracebackhide__ = True`` would be read -- gets the
    library's own default, which is to stay out of the traceback.
    """
    assert hide_internal_frames() is True
