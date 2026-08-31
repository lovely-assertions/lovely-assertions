"""``MockExpect`` -- a subject for ``unittest.mock`` (``_mock.py``).

Three things are pinned here, in this order of importance.

*The assertion cannot go missing.* A mock answers every attribute, so an
assertion made against one can be a no-op that passes. CPython has bolted a
denylist onto ``NonCallableMock.__getattr__`` to catch the misspellings somebody
thought of; the tests below show what that denylist still lets through, and that
``expect()`` needs no denylist to refuse all of it.

*The dispatch predicate is exact.* ``hasattr`` on a mock *instance* is useless --
it is ``True`` for everything -- so :func:`~lovely_assertions._mock.is_mock` asks
the class. Every flavour ``unittest.mock`` ships is enumerated, and so are the
things that live in ``unittest.mock`` and are not mocks, and a hand-written spy
carrying one familiar method.

*The messages are the product.* ``assert_called_once_with`` fails three different
ways and reports one sentence about the call count. Each of the three has its own
message here, pinned byte for byte, including the two lines ``unittest.mock``
never prints: which calls *did* match, and which argument was wrong.
"""

import ast
import subprocess
import sys
from pathlib import Path
from types import FunctionType
from typing import TYPE_CHECKING, Any, ClassVar, Final
from unittest.mock import (
    AsyncMock,
    MagicMock,
    Mock,
    NonCallableMagicMock,
    NonCallableMock,
    PropertyMock,
    call,
    create_autospec,
    patch,
    sentinel,
)

import pytest
from benchmarks import blocks_allocated

from _happy_calls import declared_by_the_subject
from _package import sources
from lovely_assertions import AssertionFailure, SequenceExpect, expect, soft_assertions
from lovely_assertions import _mock as mock_module
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatting import formatting
from lovely_assertions._mock import MockExpect, _recognition, is_mock
from lovely_assertions._occurrence import at_least, at_most, exactly, less_than, more_than

if TYPE_CHECKING:
    from collections.abc import Callable

REPO_ROOT: Final = Path(__file__).resolve().parent.parent


def _message(callback: "Callable[[], object]") -> str:
    """The text of the failure ``callback`` produces."""
    with pytest.raises(AssertionFailure) as caught:
        callback()
    return str(caught.value)


def _called(*calls: tuple[tuple[Any, ...], dict[str, Any]]) -> Mock:
    """A mock that has already been called, once per pair given."""
    made = Mock()
    for args, kwargs in calls:
        made(*args, **kwargs)
    return made


# ---------------------------------------------------------------------------
# Why this module exists
# ---------------------------------------------------------------------------
def test_a_borrowed_assertion_name_still_passes_silently_on_a_bare_mock() -> None:
    """The claim in the module docstring, checked rather than asserted in prose.

    ``unittest.mock`` refuses names beginning ``assert`` and a denylist of the
    assertion names with ``assert_`` stripped off, so the textbook typo is caught
    on a current interpreter. A name borrowed from another framework -- including
    the one *this* module ships -- is not.
    """
    fetch = Mock()
    result = fetch.was_called_once_with("/users")
    assert isinstance(result, Mock), "unittest.mock let a bare assertion name through"
    assert fetch.call_args_list == [], "and the mock was never actually called"


def test_the_denylist_does_catch_the_textbook_typo() -> None:
    """Stated for symmetry: the claim above is about what is left, not about a gap."""
    with pytest.raises(AttributeError):
        Mock().assert_called_once_wth("/users")


def test_an_unsafe_mock_turns_the_denylist_off_entirely() -> None:
    unsafe = Mock(unsafe=True)
    assert isinstance(unsafe.assert_called_once_wth("/users"), Mock)


def test_the_subject_refuses_every_misspelling_without_a_denylist() -> None:
    """The point. ``__slots__`` plus a fixed catalogue needs no list of typos."""
    subject = MockExpect(Mock())
    for typo in (
        "was_called_once_wth",
        "assert_called_once_with",
        "verify_called_with",
        "toHaveBeenCalledWith",
        "was_calledd",
    ):
        with pytest.raises(AttributeError):
            getattr(subject, typo)


def test_the_parent_child_trap_no_denylist_could_catch() -> None:
    """``api.assert_not_called()`` passes after ``api.get(...)``; ours says which."""
    api = Mock()
    api.get("/a")
    api.assert_not_called()  # passes: the call went to the child
    MockExpect(api).was_not_called()  # so does ours -- the claim is the same claim
    message = _message(lambda: MockExpect(api.get).was_not_called())
    assert message == (
        "Expected api.get not to have been called, but it was called 1 time: [('/a')]."
    )


# ---------------------------------------------------------------------------
# The dispatch predicate
# ---------------------------------------------------------------------------
def _target(first: int, second: int = 2) -> int:
    """A plain function, to be autospec'd."""
    return first + second


async def _async_target(first: int) -> int:
    """The same, asynchronous: ``create_autospec`` builds a different shape for it."""
    return first


#: Every mock flavour ``unittest.mock`` ships. ``create_autospec`` is in the list
#: three times over, because it is the one users are told to prefer and it hands
#: back a different *kind* of thing depending on what it was given: a MagicMock
#: for a class or a method, and -- for a plain function -- a real function object
#: carrying the mock protocol as instance attributes.
_FLAVOURS: Final[dict[str, "Callable[[], object]"]] = {
    "Mock": Mock,
    "MagicMock": MagicMock,
    "AsyncMock": AsyncMock,
    "NonCallableMock": NonCallableMock,
    "NonCallableMagicMock": NonCallableMagicMock,
    "PropertyMock": PropertyMock,
    "autospec of a class": lambda: create_autospec(Mock),
    "autospec of a method": lambda: create_autospec(Mock).mock_add_spec,
    "autospec of a function": lambda: create_autospec(_target),
    "autospec of an async function": lambda: create_autospec(_async_target),
    "spec'd Mock": lambda: Mock(spec=list),
    "a child mock": lambda: Mock().child,
    "a return value": lambda: Mock().method.return_value,
}


@pytest.mark.parametrize("flavour", list(_FLAVOURS), ids=list(_FLAVOURS))
def test_every_mock_flavour_is_recognised(flavour: str) -> None:
    assert is_mock(_FLAVOURS[flavour]()) is True


def test_a_spec_does_not_hide_the_real_type() -> None:
    """``Mock(spec=list).__class__`` *is* ``list``; the predicate must not believe it."""
    spied = Mock(spec=list)
    assert spied.__class__ is list
    assert is_mock(spied) is True
    assert is_mock([]) is False


#: Things that live in ``unittest.mock`` and are not mocks. An ``isinstance``
#: against ``NonCallableMock`` would decline these too; a check on the *module* a
#: class comes from would claim every one of them.
_NEIGHBOURS: Final[dict[str, object]] = {
    "a call object": call(1, x=2),
    "a bare call": call,
    "a child call": call.child.method(3),
    "a sentinel": sentinel.missing,
    "a patcher": patch("builtins.len"),
}


@pytest.mark.parametrize("neighbour", list(_NEIGHBOURS), ids=list(_NEIGHBOURS))
def test_the_neighbours_of_mock_are_not_mocks(neighbour: str) -> None:
    assert is_mock(_NEIGHBOURS[neighbour]) is False


def test_a_call_object_answers_any_attribute_and_is_still_not_a_mock() -> None:
    """The trap that makes an instance-level check wrong twice over.

    ``call.anything`` builds a child call, so ``hasattr`` on the instance says
    yes to every name -- exactly as it does for a mock. The class says no.
    """
    one = call(1)
    assert hasattr(one, "assert_called_with")
    assert not hasattr(type(one), "assert_called_with")
    assert is_mock(one) is False


@pytest.mark.parametrize(
    "value",
    [None, 3, "text", [1], {"a": 1}, {1, 2}, (1,), object(), is_mock, Mock],
    ids=["none", "int", "str", "list", "dict", "set", "tuple", "object", "function", "the class"],
)
def test_ordinary_values_are_not_mocks(value: object) -> None:
    assert is_mock(value) is False


def test_a_hand_written_spy_with_one_familiar_method_is_not_claimed() -> None:
    """One name is not enough: the assertions here read more than one attribute."""

    class Spy:
        def assert_called_with(self, *args: object, **kwargs: object) -> None: ...

    assert is_mock(Spy()) is False


def test_an_object_carrying_the_whole_protocol_is_claimed_on_purpose() -> None:
    """Duck typing, stated as a decision rather than discovered as a surprise.

    A class with all five names *is* a mock in every sense this module needs,
    whichever package built it -- which is what keeps the ``mock`` backport on
    PyPI, and a project's own recorder, working.
    """

    class Recorder:
        call_args_list: ClassVar[list[object]] = []
        mock_calls: ClassVar[list[object]] = []

        def assert_called_with(self, *args: object, **kwargs: object) -> None: ...
        def assert_any_call(self, *args: object, **kwargs: object) -> None: ...
        def reset_mock(self) -> None: ...

    recorder = Recorder()
    assert is_mock(recorder) is True
    MockExpect(recorder).was_not_called()


def test_an_autospec_of_a_function_is_not_a_mock_object_at_all() -> None:
    """The one case that has to be asked of the instance, and why it is safe.

    ``create_autospec(fn)`` returns a real ``function`` built to carry ``fn``'s
    signature, with the mock protocol hung off it and a ``MagicMock`` behind.
    Its class declares none of the five names. A function cannot define
    ``__getattr__``, so asking the object itself cannot be answered by anything
    but a real attribute -- which is what makes the exception narrow rather than
    a hole.
    """
    spied = create_autospec(_target)
    assert type(spied) is FunctionType
    assert not hasattr(type(spied), "assert_called_with")
    assert hasattr(spied, "assert_called_with")
    assert is_mock(spied) is True
    assert is_mock(_target) is False
    assert is_mock(lambda: None) is False


def test_an_autospec_of_a_function_works_end_to_end() -> None:
    """Autospec is the form the documentation recommends; it has to be usable."""
    spied = create_autospec(_target)
    spied(1, second=9)
    MockExpect(spied).was_called_once_with(1, second=9)
    assert _message(lambda: MockExpect(spied).was_called_once_with(1, second=3)) == (
        "Expected spied to have been called once with (1, second=3),"
        " but was called with (1, second=9).\n"
        "  keyword arguments:\n"
        "    values differ at key 'second': 9 instead of 3"
    )


def test_every_marker_is_load_bearing() -> None:
    """``MOCK_MARKERS`` and the ``and`` chain inside :func:`is_mock` cannot drift apart.

    :func:`is_mock` spells its five checks out rather than looping over
    ``MOCK_MARKERS``, because a generator expression on ``expect()``'s dispatch
    path would build a frame per call. This holds the two together from both
    sides: dropping any one name from an otherwise complete impostor must be
    noticed, and the tuple must list nothing the function does not ask for.
    """
    markers: tuple[str, ...] = _recognition.MOCK_MARKERS
    assert len(markers) == len(set(markers)) == 5
    # The value behind each name is irrelevant: `is_mock` asks whether the class
    # answers the name at all, which is the only question a class can be asked
    # about a mock without running its `__getattr__`.
    for dropped in markers:
        namespace: dict[str, object] = {name: None for name in markers if name != dropped}
        impostor = type("Impostor", (), namespace)()
        assert is_mock(impostor) is False, (
            f"is_mock ignored the absence of {dropped!r}, which MOCK_MARKERS lists"
        )
    complete = type("Complete", (), dict.fromkeys(markers))()
    assert is_mock(complete) is True


def test_the_predicate_allocates_nothing() -> None:
    """It sits in ``expect()``'s dispatch, so every subject in the library pays it."""
    baseline = blocks_allocated(lambda: None)
    plain = object()
    mocked = Mock()
    assert blocks_allocated(lambda: is_mock(plain)) <= baseline
    assert blocks_allocated(lambda: is_mock(mocked)) <= baseline


# ---------------------------------------------------------------------------
# How often
# ---------------------------------------------------------------------------
def test_was_called_passes_for_any_number_of_calls() -> None:
    fetch = _called(((1,), {}))
    MockExpect(fetch).was_called()
    fetch(2)
    MockExpect(fetch).was_called()


def test_was_called_names_the_absence() -> None:
    fetch = Mock()
    assert _message(lambda: MockExpect(fetch).was_called()) == (
        "Expected fetch to have been called, but it was never called."
    )


def test_was_not_called_lists_what_was_there() -> None:
    """The half ``assert_not_called`` leaves out: three calls, but with what?"""
    fetch = _called((("/a",), {}), (("/b",), {"retry": True}))
    assert _message(lambda: MockExpect(fetch).was_not_called()) == (
        "Expected fetch not to have been called,"
        " but it was called 2 times: [('/a'), ('/b', retry=True)]."
    )


def test_was_not_called_passes_for_an_untouched_mock() -> None:
    MockExpect(Mock()).was_not_called()


def test_was_called_once_separates_none_from_several() -> None:
    never = Mock()
    assert _message(lambda: MockExpect(never).was_called_once()) == (
        "Expected never to have been called once, but it was never called."
    )
    twice = _called((("/a",), {}), (("/b",), {}))
    assert _message(lambda: MockExpect(twice).was_called_once()) == (
        "Expected twice to have been called once, but it was called 2 times: [('/a'), ('/b')]."
    )


def test_was_called_once_passes_for_exactly_one() -> None:
    MockExpect(_called(((1,), {}))).was_called_once()


def test_has_call_count_takes_a_plain_number() -> None:
    fetch = _called((("/a",), {}))
    MockExpect(fetch).has_call_count(1)
    assert _message(lambda: MockExpect(fetch).has_call_count(3)) == (
        "Expected fetch to have been called exactly 3 times, but it was called 1 time: [('/a')]."
    )


def test_has_call_count_singularises_the_expected_number_too() -> None:
    """ "exactly 1 times" is the tell that nobody read the output."""
    fetch = _called((("/a",), {}), (("/b",), {}))
    assert "called exactly 1 time," in _message(lambda: MockExpect(fetch).has_call_count(1))


def test_has_call_count_takes_an_occurrence_constraint() -> None:
    fetch = _called((("/a",), {}), (("/b",), {}), (("/c",), {}))
    MockExpect(fetch).has_call_count(at_least(2))
    MockExpect(fetch).has_call_count(at_most(3))
    MockExpect(fetch).has_call_count(more_than(2))
    MockExpect(fetch).has_call_count(less_than(4))
    MockExpect(fetch).has_call_count(exactly(3))
    assert _message(lambda: MockExpect(fetch).has_call_count(at_least(5))) == (
        "Expected fetch to have been called at least 5 times,"
        " but it was called 3 times: [('/a'), ('/b'), ('/c')]."
    )


def test_a_count_and_the_matching_constraint_say_the_same_thing() -> None:
    """``has_call_count(3)`` and ``has_call_count(exactly(3))`` are one assertion."""
    fetch = _called((("/a",), {}))
    assert _message(lambda: MockExpect(fetch).has_call_count(3)) == _message(
        lambda: MockExpect(fetch).has_call_count(exactly(3))
    )


def test_the_count_and_the_listing_can_never_disagree() -> None:
    """The reason ``call_count`` is never read: one source, one number.

    A mock lets ``call_count`` be reassigned; ``call_args_list`` is what the
    listing under the number comes from, so the number comes from there too.
    """
    fetch = _called((("/a",), {}))
    fetch.call_count = 99
    assert _message(lambda: MockExpect(fetch).has_call_count(2)) == (
        "Expected fetch to have been called exactly 2 times, but it was called 1 time: [('/a')]."
    )


# ---------------------------------------------------------------------------
# With what: was_called_with (the last call)
# ---------------------------------------------------------------------------
def test_was_called_with_passes_on_the_last_call() -> None:
    fetch = _called((("/a",), {}), (("/b",), {"timeout": 3}))
    MockExpect(fetch).was_called_with("/b", timeout=3)


def test_was_called_with_reports_the_absence_separately() -> None:
    fetch = Mock()
    assert _message(lambda: MockExpect(fetch).was_called_with("/users")) == (
        "Expected fetch to have been called with ('/users'), but it was never called."
    )


def test_was_called_with_names_the_keyword_that_differs() -> None:
    """The difference engine, doing on a call what it does on a mapping."""
    fetch = _called((("/users",), {"timeout": 5}))
    assert _message(lambda: MockExpect(fetch).was_called_with("/users", timeout=3)) == (
        "Expected fetch to have been called with ('/users', timeout=3),"
        " but was called with ('/users', timeout=5).\n"
        "  keyword arguments:\n"
        "    values differ at key 'timeout': 5 instead of 3"
    )


def test_was_called_with_names_the_position_that_differs() -> None:
    fetch = _called((("/users", 7), {}))
    assert _message(lambda: MockExpect(fetch).was_called_with("/users", 9)) == (
        "Expected fetch to have been called with ('/users', 9),"
        " but was called with ('/users', 7).\n"
        "  positional arguments:\n"
        "    first difference at index 1: 7 instead of 9"
    )


def test_was_called_with_reports_both_halves_when_both_differ() -> None:
    fetch = _called((("/users",), {"timeout": 5}))
    assert _message(lambda: MockExpect(fetch).was_called_with()) == (
        "Expected fetch to have been called with no arguments,"
        " but was called with ('/users', timeout=5).\n"
        "  positional arguments:\n"
        "    lengths differ: 1 item, expected 0\n"
        "    extra items: ['/users']\n"
        "  keyword arguments:\n"
        "    extra keys: ['timeout']"
    )


def test_was_called_with_says_when_an_earlier_call_matched() -> None:
    """The line ``assert_called_with`` never prints and the reader always needs."""
    fetch = _called((("/users",), {}), (("/other",), {}))
    assert _message(lambda: MockExpect(fetch).was_called_with("/users")) == (
        "Expected fetch to have been called with ('/users'),"
        " but was last called with ('/other').\n"
        "  positional arguments:\n"
        "    first difference at index 0: '/other' instead of '/users'\n"
        "  call 1 was made with those arguments; only the last call is checked"
    )


def test_the_earlier_match_note_pluralises_and_lists() -> None:
    fetch = _called((("/a",), {}), (("/a",), {}), (("/b",), {}))
    message = _message(lambda: MockExpect(fetch).was_called_with("/a"))
    assert message.endswith(
        "  calls 1 and 2 were made with those arguments; only the last call is checked"
    )


def test_a_single_call_is_not_called_the_last_one() -> None:
    """ "last called with" in front of the only call reads as though others were ignored."""
    fetch = _called((("/a",), {}))
    assert "but was called with ('/a')" in _message(lambda: MockExpect(fetch).was_called_with("/b"))
    twice = _called((("/a",), {}), (("/a",), {}))
    assert "but was last called with ('/a')" in _message(
        lambda: MockExpect(twice).was_called_with("/b")
    )


def test_was_called_with_no_arguments_asserts_a_call_with_none() -> None:
    """Passing nothing here asks about a call made with no arguments, not a caller slip.

    A variadic assertion given no arguments normally refuses, because the caller
    almost certainly forgot them. A call carrying no arguments is an ordinary thing
    to assert, so this family answers the question instead of raising.
    """
    bare = Mock()
    bare()
    MockExpect(bare).was_called_with()
    argued = _called((("/a",), {}))
    assert _message(lambda: MockExpect(argued).was_called_with()).startswith(
        "Expected argued to have been called with no arguments,"
    )


# ---------------------------------------------------------------------------
# With what: was_called_once_with (three bugs, three messages)
# ---------------------------------------------------------------------------
def test_was_called_once_with_passes() -> None:
    MockExpect(_called((("/a",), {"n": 1}))).was_called_once_with("/a", n=1)


def test_was_called_once_with_never_called() -> None:
    fetch = Mock()
    assert _message(lambda: MockExpect(fetch).was_called_once_with("/a")) == (
        "Expected fetch to have been called once with ('/a'), but it was never called."
    )


def test_was_called_once_with_called_with_something_else() -> None:
    fetch = _called((("/b",), {}))
    assert _message(lambda: MockExpect(fetch).was_called_once_with("/a")) == (
        "Expected fetch to have been called once with ('/a'), but was called with ('/b').\n"
        "  positional arguments:\n"
        "    first difference at index 0: '/b' instead of '/a'"
    )


def test_was_called_once_with_called_more_than_once_and_matching() -> None:
    """The bug ``unittest.mock`` conflates with the other two: the count is wrong."""
    fetch = _called((("/a",), {}), (("/b",), {}), (("/a",), {}))
    assert _message(lambda: MockExpect(fetch).was_called_once_with("/a")) == (
        "Expected fetch to have been called once with ('/a'),"
        " but it was called 3 times: [('/a'), ('/b'), ('/a')].\n"
        "  calls 1 and 3 were made with those arguments; it is the call count that is wrong"
    )


def test_was_called_once_with_called_more_than_once_and_never_matching() -> None:
    """Same count, entirely different bug -- and a different sentence."""
    fetch = _called((("/a",), {}), (("/b",), {}))
    assert _message(lambda: MockExpect(fetch).was_called_once_with("/z")) == (
        "Expected fetch to have been called once with ('/z'),"
        " but it was called 2 times: [('/a'), ('/b')].\n"
        "  none of those calls was made with those arguments"
    )


def test_the_three_failures_really_are_three_different_messages() -> None:
    """``unittest.mock`` renders the first and third of these identically."""
    never = Mock()
    wrong = _called((("/b",), {}))
    twice = _called((("/a",), {}), (("/a",), {}))
    messages = {
        _message(lambda: MockExpect(never).was_called_once_with("/a")),
        _message(lambda: MockExpect(wrong).was_called_once_with("/a")),
        _message(lambda: MockExpect(twice).was_called_once_with("/a")),
    }
    assert len(messages) == 3


# ---------------------------------------------------------------------------
# With what: any call, and no call
# ---------------------------------------------------------------------------
def test_was_ever_called_with_finds_a_call_anywhere() -> None:
    fetch = _called((("/a",), {}), (("/b",), {}), (("/c",), {}))
    MockExpect(fetch).was_ever_called_with("/b")


def test_was_ever_called_with_reports_the_absence() -> None:
    fetch = Mock()
    assert _message(lambda: MockExpect(fetch).was_ever_called_with("/a")) == (
        "Expected fetch to have been called with ('/a') at some point, but it was never called."
    )


def test_was_ever_called_with_explains_the_only_call() -> None:
    fetch = _called((("/b",), {}))
    assert _message(lambda: MockExpect(fetch).was_ever_called_with("/a")) == (
        "Expected fetch to have been called with ('/a') at some point,"
        " but its only call was ('/b').\n"
        "  positional arguments:\n"
        "    first difference at index 0: '/b' instead of '/a'"
    )


def test_was_ever_called_with_picks_the_nearest_of_several_to_explain() -> None:
    """ "none of these four matched" is a fact the reader already had."""
    fetch = _called(
        (("/other",), {}),
        (("/users",), {"timeout": 5}),
        ((), {}),
    )
    assert _message(lambda: MockExpect(fetch).was_ever_called_with("/users", timeout=3)) == (
        "Expected fetch to have been called with ('/users', timeout=3) at some point,"
        " but none of its 3 calls was: [('/other'), ('/users', timeout=5), ()].\n"
        "  the closest was call 2:\n"
        "    keyword arguments:\n"
        "      values differ at key 'timeout': 5 instead of 3"
    )


def test_the_nearest_call_is_a_choice_of_explanation_not_of_verdict() -> None:
    """A tie keeps the order the calls were made in, so the message is stable."""
    fetch = _called((("/x",), {}), (("/y",), {}))
    first = _message(lambda: MockExpect(fetch).was_ever_called_with("/z"))
    second = _message(lambda: MockExpect(fetch).was_ever_called_with("/z"))
    assert first == second
    assert "the closest was call 1:" in first


def test_was_never_called_with_has_no_counterpart_in_unittest_mock() -> None:
    fetch = _called((("/a",), {}), (("/b",), {}))
    MockExpect(fetch).was_never_called_with("/z")
    assert _message(lambda: MockExpect(fetch).was_never_called_with("/b")) == (
        "Expected fetch never to have been called with ('/b'), but call 2 was: [('/a'), ('/b')]."
    )


def test_was_never_called_with_names_every_offending_call() -> None:
    fetch = _called((("/a",), {}), (("/b",), {}), (("/a",), {}))
    assert _message(lambda: MockExpect(fetch).was_never_called_with("/a")) == (
        "Expected fetch never to have been called with ('/a'),"
        " but calls 1 and 3 were: [('/a'), ('/b'), ('/a')]."
    )


def test_was_never_called_with_passes_for_an_untouched_mock() -> None:
    MockExpect(Mock()).was_never_called_with("/a")


# ---------------------------------------------------------------------------
# Argument comparison
# ---------------------------------------------------------------------------
def test_positional_and_keyword_are_compared_where_they_were_written() -> None:
    """A deliberate divergence from ``assert_called_with`` on an autospec'd mock.

    ``unittest.mock`` normalises a call through the spec's signature first, so a
    recorded ``fn(1)`` matches an expected ``fn(x=1)``. This does not -- and the
    message says exactly what happened rather than quietly matching one form
    while printing another.
    """

    def fn(x: int) -> int:
        return x

    spied = create_autospec(fn)
    spied(1)
    spied.assert_called_with(x=1)  # unittest.mock: matched through the signature
    message = _message(lambda: MockExpect(spied).was_called_with(x=1))
    assert "positional arguments:" in message
    assert "keyword arguments:" in message
    MockExpect(spied).was_called_with(1)


def test_a_matching_call_is_never_handed_to_the_difference_engine() -> None:
    """``describe_difference`` is written for two values known to be unequal.

    Given two equal ones it reports, correctly for its own contract and absurdly
    here, that they render alike and are not equal. Only the half that actually
    differs is asked.
    """
    fetch = _called((("/a",), {"n": 1}))
    message = _message(lambda: MockExpect(fetch).was_called_with("/a", n=2))
    assert "positional arguments:" not in message
    assert "keyword arguments:" in message
    assert "not equal" not in message


def test_a_value_inside_a_call_goes_through_the_formatter_registry() -> None:
    """Arguments inside a recorded call are rendered through the formatter registry.

    A ``call`` object's own ``repr`` would go straight to each argument's
    ``__repr__``, which would silently ignore any registered formatter.
    """

    class Order:
        __slots__ = ("identifier",)

        def __init__(self, identifier: int) -> None:
            self.identifier = identifier

    class Terse:
        __slots__ = ()

        def can_handle(self, value: object, /) -> bool:
            return isinstance(value, Order)

        def format(self, value: object, /) -> str:
            return "#" + str(value.identifier) if isinstance(value, Order) else repr(value)

    fetch = _called(((Order(7),), {}))
    with soft_assertions(formatters=(Terse(),)) as scope:
        MockExpect(fetch).described_as("fetch").was_not_called()
        collected = scope.discard()
    assert collected == [
        "Expected fetch not to have been called, but it was called 1 time: [(#7)]."
    ]


class Uncomparable:
    """A value whose ``__eq__`` raises: a lazy proxy, an array, a detached ORM row.

    Nothing else about it is hostile -- it renders and hashes -- so a message that
    loses its detail block over one of these lost it to the comparison and to
    nothing else.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return "Uncomparable()"

    def __eq__(self, other: object) -> bool:
        message = "comparison exploded"
        raise RuntimeError(message)

    def __hash__(self) -> int:
        return 0


def test_a_positional_argument_that_cannot_be_compared_costs_detail_not_the_finding() -> None:
    """``describe_difference`` goes quiet rather than raising, and the failure stands.

    The two calls part company on the length of a list, so nothing compares the
    values inside it -- until the difference engine descends into that list and
    the comparison explodes. Its contract is to say nothing when it cannot say
    something; what it must never do is turn a failing test into a library error.
    """
    fetch = _called((([Uncomparable()],), {}))

    message = _message(lambda: MockExpect(fetch).was_called_with([Uncomparable(), 1]))

    assert message == (
        "Expected fetch to have been called with ([Uncomparable(), 1]),"
        " but was called with ([Uncomparable()])."
    )


def test_a_keyword_argument_that_cannot_be_compared_costs_detail_not_the_finding() -> None:
    """The same contract on the other half of the call."""
    fetch = _called(((), {"flag": Uncomparable()}))

    message = _message(lambda: MockExpect(fetch).was_called_with(flag=Uncomparable(), extra=1))

    assert message == (
        "Expected fetch to have been called with (flag=Uncomparable(), extra=1),"
        " but was called with (flag=Uncomparable())."
    )


def test_the_nearest_call_is_left_unexplained_when_nothing_can_be_said_about_it() -> None:
    """The closest-call note is an explanation, so an empty one is no note at all.

    Picking the nearest call is a heuristic about *which* call to explain. When
    the explanation comes back empty the line would read "the closest was call 1:"
    and then stop, pointing at a call it has nothing to say about.
    """
    fetch = _called((([Uncomparable()],), {}), (("/other",), {}))

    message = _message(lambda: MockExpect(fetch).was_ever_called_with([Uncomparable(), 1]))

    assert message == (
        "Expected fetch to have been called with ([Uncomparable(), 1]) at some point,"
        " but none of its 2 calls was: [([Uncomparable()]), ('/other')]."
    )


def test_an_unusual_value_does_not_break_the_message() -> None:
    fetch = _called(((None, b"raw", 1.5), {"flag": False}))
    assert _message(lambda: MockExpect(fetch).was_not_called()) == (
        "Expected fetch not to have been called,"
        " but it was called 1 time: [(None, b'raw', 1.5, flag=False)]."
    )


# ---------------------------------------------------------------------------
# Continuations
# ---------------------------------------------------------------------------
def test_calls_is_a_sequence_subject_over_the_recorded_calls() -> None:
    fetch = _called((("/a",), {}), (("/b",), {}))
    subject = MockExpect(fetch).calls
    assert isinstance(subject, SequenceExpect)
    assert list(subject.subject) == [call("/a"), call("/b")]


def test_calls_keeps_the_call_objects_users_already_write() -> None:
    """The whole argument for not converting them into something friendlier."""
    fetch = _called((("/a",), {}), (("/b",), {"n": 1}))
    MockExpect(fetch).calls.contains(call("/b", n=1))
    MockExpect(fetch).calls.contains_in_order(call("/a"), call("/b", n=1))
    MockExpect(fetch).calls.has_length(2)


def test_calls_subsumes_assert_has_calls_with_a_better_message() -> None:
    fetch = _called((("/a",), {}), (("/b",), {}))
    message = _message(lambda: MockExpect(fetch).calls.contains_in_order(call("/b"), call("/a")))
    assert "did not appear after" in message


def test_calls_of_an_untouched_mock_is_an_answer_not_a_failure() -> None:
    """Why it is a property: an empty recording is a fact, not a finding."""
    MockExpect(Mock()).calls.is_empty()


def test_calls_carries_an_explicit_name() -> None:
    fetch = _called((("/a",), {}))
    message = _message(lambda: MockExpect(fetch).described_as("the client").calls.has_length(2))
    assert message.startswith("Expected the client to have length 2")


def test_last_call_hands_back_the_most_recent_call() -> None:
    fetch = _called((("/a",), {}), (("/b",), {"n": 1}))
    subject = MockExpect(fetch)
    found = subject.last_call()
    assert found.subject == call("/b", n=1)
    assert found.and_ is subject
    assert found.which.subject == call("/b", n=1)


def test_last_call_fails_when_there_is_none() -> None:
    fetch = Mock()
    assert _message(lambda: MockExpect(fetch).last_call()) == (
        "Expected fetch to have been called, but it was never called."
    )


def test_last_call_is_a_method_because_it_asserts_something() -> None:
    """``calls`` is a property and cannot fail; this one can, so it takes ``because``.

    That asymmetry is the rule, not an inconsistency: every assertion carries a
    keyword-only ``because``, and a property has nowhere to put one.
    """
    assert isinstance(declared_by_the_subject(MockExpect)["calls"], property)
    assert not isinstance(declared_by_the_subject(MockExpect)["last_call"], property)


def test_and_underscore_returns_the_same_subject() -> None:
    fetch = _called((("/a",), {}))
    subject = MockExpect(fetch)
    assert subject.was_called().and_ is subject


# ---------------------------------------------------------------------------
# The public entry point
# ---------------------------------------------------------------------------
def test_the_explicit_form_works_without_any_dispatch_wiring() -> None:
    """``expect(value, as_=MockExpect)`` is the typed way in and needs no registration.

    A third-party subject class is usable through the public entry point whether or
    not anything has taught ``expect()`` to reach for it automatically.
    """
    fetch = _called((("/a",), {}))
    expect(fetch, as_=MockExpect).was_called_once_with("/a")
    assert _message(lambda: expect(fetch, as_=MockExpect).was_not_called()) == (
        "Expected fetch not to have been called, but it was called 1 time: [('/a')]."
    )


def test_an_explicit_name_survives_the_explicit_form() -> None:
    fetch = Mock()
    assert _message(lambda: expect(fetch, as_=MockExpect, name="the client").was_called()) == (
        "Expected the client to have been called, but it was never called."
    )


def test_the_name_is_recovered_from_the_source_line() -> None:
    """With no explicit name given, the message still says which mock.

    The name is read back off the source line that made the assertion.
    """
    the_publisher = Mock()
    assert _message(lambda: MockExpect(the_publisher).was_called()).startswith(
        "Expected the_publisher "
    )


# ---------------------------------------------------------------------------
# because
# ---------------------------------------------------------------------------
BECAUSE_CALLS: Final = [
    pytest.param(lambda: MockExpect(Mock()).was_called(because="R"), id="was_called"),
    pytest.param(
        lambda: MockExpect(_called(((1,), {}))).was_not_called(because="R"), id="was_not_called"
    ),
    pytest.param(lambda: MockExpect(Mock()).was_called_once(because="R"), id="was_called_once"),
    pytest.param(lambda: MockExpect(Mock()).has_call_count(2, because="R"), id="has_call_count"),
    pytest.param(lambda: MockExpect(Mock()).was_called_with(1, because="R"), id="was_called_with"),
    pytest.param(
        lambda: MockExpect(Mock()).was_called_once_with(1, because="R"),
        id="was_called_once_with",
    ),
    pytest.param(
        lambda: MockExpect(Mock()).was_ever_called_with(1, because="R"),
        id="was_ever_called_with",
    ),
    pytest.param(
        lambda: MockExpect(_called(((1,), {}))).was_never_called_with(1, because="R"),
        id="was_never_called_with",
    ),
    pytest.param(lambda: MockExpect(Mock()).last_call(because="R"), id="last_call"),
]

#: Public members that are **not** assertions: they make no claim, so they cannot
#: fail and have no ``because`` to carry, since ``because`` belongs to assertions.
#: ``calls`` is a property and is excluded from the enumeration below anyway; it is
#: named here so that the reason is written down rather than inferred from a
#: technicality.
NOT_ASSERTIONS: Final = frozenset({"calls"})


@pytest.mark.parametrize("call_it", BECAUSE_CALLS)
def test_because_reaches_every_assertion(call_it: object) -> None:
    with pytest.raises(AssertionFailure, match="because R"):
        call_it()  # type: ignore[operator]  # pyright: ignore[reportCallIssue]


def test_the_because_table_has_not_fallen_behind_the_catalogue() -> None:
    """A new assertion must arrive with its ``because`` case, or this fails."""
    covered = {parameters.id for parameters in BECAUSE_CALLS}
    declared = {
        name
        for name, attribute in declared_by_the_subject(MockExpect).items()
        if not name.startswith("_") and callable(attribute)
    } - NOT_ASSERTIONS
    assert covered == declared


def test_everything_excused_from_the_because_table_really_is_declared() -> None:
    assert set(declared_by_the_subject(MockExpect)) >= NOT_ASSERTIONS


def test_because_is_keyword_only_even_beside_star_args() -> None:
    with pytest.raises(TypeError):
        MockExpect(Mock()).has_call_count(1, "a reason")  # type: ignore[call-arg]  # pyright: ignore[reportCallIssue]


def test_because_shadows_a_keyword_argument_of_that_name() -> None:
    """The collision, pinned rather than left to be discovered in the wild.

    ``because`` is keyword-only on every assertion, which costs the
    argument-taking assertions the ability to name a keyword argument
    ``because``. ``calls`` is the way to say it instead.
    """
    audit = Mock()
    audit("/users", because="policy")
    # The obvious spelling asserts a call with no keyword arguments at all, and
    # attaches "policy" as the reason -- which is not what the reader meant.
    message = _message(lambda: MockExpect(audit).was_called_with("/users", because="policy"))
    sentence, _, block = message.partition("\n")
    assert sentence.endswith("because policy.")
    assert "extra keys: ['because']" in block
    # The escape hatch says it exactly.
    MockExpect(audit).calls.contains(call("/users", because="policy"))


# ---------------------------------------------------------------------------
# Empty calls, and why they are exempt from the no-arguments refusal
# ---------------------------------------------------------------------------
#: The four variadic assertions here. An empty call is **meaningful** for every
#: one of them -- it asks about a call made with no arguments, which is an
#: ordinary thing to assert -- so none of them raises ``ValueError``. This is the
#: ``contains_only_keys()`` case in ``tests/test_empty_arguments.py``, not the
#: ``contains_in_order()`` one.
_VARIADIC: Final = (
    "was_called_with",
    "was_called_once_with",
    "was_ever_called_with",
    "was_never_called_with",
)


@pytest.mark.parametrize("name", _VARIADIC)
def test_an_empty_call_asks_about_a_call_with_no_arguments(name: str) -> None:
    bare = Mock()
    bare()
    getattr(MockExpect(bare), name)() if name != "was_never_called_with" else None
    argued = _called((("/a",), {}))
    if name == "was_never_called_with":
        MockExpect(argued).was_never_called_with()
        with pytest.raises(AssertionFailure):
            MockExpect(bare).was_never_called_with()
        return
    with pytest.raises(AssertionFailure):
        getattr(MockExpect(argued), name)()


def test_no_variadic_assertion_here_raises_for_an_empty_call() -> None:
    """Every variadic assertion here answers an empty call rather than refusing it.

    ``tests/test_empty_arguments.py`` enumerates the assertions that must refuse
    when handed nothing; the exemption is stated here in one place so that
    enumeration can point at a reason instead of a special case.
    """
    bare = Mock()
    bare()
    for name in _VARIADIC:
        try:
            getattr(MockExpect(bare), name)()
        except AssertionFailure:
            continue
        except ValueError as error:  # pragma: no cover - a regression, not an outcome
            pytest.fail(f"{name}() refused an empty call, which is meaningful here: {error}")


# ---------------------------------------------------------------------------
# Soft assertions
# ---------------------------------------------------------------------------
def test_failures_aggregate_inside_a_soft_scope() -> None:
    fetch = Mock()
    with pytest.raises(AssertionFailure) as caught, soft_assertions("client"):
        MockExpect(fetch).described_as("fetch").was_called()
        MockExpect(fetch).described_as("fetch").was_called_once_with("/a")
    message = str(caught.value)
    assert "2 assertions failed:" in message
    assert message.count("client/fetch") == 2


def test_a_failed_last_call_absorbs_the_rest_of_its_chain() -> None:
    """One root cause, one message: the narrowed subject never existed."""
    fetch = Mock()
    with soft_assertions() as scope:
        MockExpect(fetch).described_as("fetch").last_call().which.is_not_none()
        collected = scope.discard()
    assert collected == ["Expected fetch to have been called, but it was never called."]


def test_a_soft_scope_keeps_chaining_past_a_failure() -> None:
    fetch = Mock()
    with soft_assertions() as scope:
        MockExpect(fetch).described_as("fetch").was_called().and_.has_call_count(2)
        collected = scope.discard()
    assert len(collected) == 2


# ---------------------------------------------------------------------------
# Rendering bounds (``_formatting.py``)
# ---------------------------------------------------------------------------
def test_a_long_recording_is_truncated_and_counted() -> None:
    fetch = Mock()
    for index in range(25):
        fetch(index)
    message = _message(lambda: MockExpect(fetch).was_not_called())
    assert "(0), (1), (2), (3), (4), (5), (6), (7), (8), (9), ... (15 more)]" in message


def test_a_long_argument_is_clipped_the_way_every_other_value_is() -> None:
    fetch = _called((("x" * 400,), {}))
    message = _message(lambda: MockExpect(fetch).was_not_called())
    assert "... (282 more characters)" in message, message


def test_a_call_with_very_many_arguments_is_bounded_too() -> None:
    fetch = Mock()
    fetch(*range(30))
    assert "... (20 more)" in _message(lambda: MockExpect(fetch).was_not_called())


def test_the_argument_bound_is_one_budget_for_positional_and_keyword_together() -> None:
    """The keywords are not a second allowance.

    Eight positional arguments leave room for two of the three keywords, and the
    count at the end is what was cut from the call as a whole. A per-half bound
    would show all three and claim nothing was elided.
    """
    fetch = Mock()

    fetch(1, 2, 3, 4, 5, 6, 7, 8, a=9, b=10, c=11)

    assert _message(lambda: MockExpect(fetch).was_not_called()) == (
        "Expected fetch not to have been called,"
        " but it was called 1 time: [(1, 2, 3, 4, 5, 6, 7, 8, a=9, b=10, ... (1 more))]."
    )


def test_a_long_list_of_matching_calls_is_bounded() -> None:
    fetch = Mock()
    for _ in range(15):
        fetch("/a")
    message = _message(lambda: MockExpect(fetch).was_never_called_with("/a"))
    assert "calls 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, ... (5 more) were" in message


def test_the_bounds_come_from_the_formatting_scope() -> None:
    """``_formatting.py`` exists to be read here, in a failure branch, and nowhere else."""
    fetch = Mock()
    for index in range(25):
        fetch(index)
    narrow = _message(lambda: MockExpect(fetch).was_not_called())
    assert "... (15 more)]" in narrow
    with formatting(max_items=30):
        wide = _message(lambda: MockExpect(fetch).was_not_called())
    assert "more)]" not in wide
    assert "(24)]" in wide


# ---------------------------------------------------------------------------
# Cost
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("no_failure_machinery")
def test_no_passing_assertion_touches_the_failure_path() -> None:
    """A passing assertion reaches nothing on the failure path.

    The formatting ``ContextVar`` is part of that path: a pass must not read it
    either, or every passing assertion in a suite pays for rendering it will never do.
    """
    fetch = _called((("/a",), {"n": 1}))
    subject = MockExpect(fetch)
    subject.was_called()
    subject.was_called_once()
    subject.has_call_count(1)
    subject.has_call_count(at_least(1))
    subject.was_called_with("/a", n=1)
    subject.was_called_once_with("/a", n=1)
    subject.was_ever_called_with("/a", n=1)
    subject.was_never_called_with("/z")
    subject.last_call()
    MockExpect(Mock()).was_not_called()


def test_no_assertion_retains_an_allocation() -> None:
    """No passing assertion leaves an allocation behind, measured rather than argued.

    ``*args`` and ``**kwargs`` build a tuple and a dict per call by construction;
    what must not happen is anything surviving the call."""
    baseline = blocks_allocated(lambda: None)
    fetch = _called((("/a",), {"n": 1}))
    subject = MockExpect(fetch)
    untouched = MockExpect(Mock())
    cases: list[tuple[str, Callable[[], object]]] = [
        ("was_called", subject.was_called),
        ("was_not_called", untouched.was_not_called),
        ("was_called_once", subject.was_called_once),
        ("has_call_count", lambda: subject.has_call_count(1)),
        ("has_call_count(occurrence)", lambda: subject.has_call_count(at_least(1))),
        ("was_called_with", lambda: subject.was_called_with("/a", n=1)),
        ("was_called_once_with", lambda: subject.was_called_once_with("/a", n=1)),
        ("was_ever_called_with", lambda: subject.was_ever_called_with("/a", n=1)),
        ("was_never_called_with", lambda: subject.was_never_called_with("/z")),
    ]
    for label, callback in cases:
        allocated = blocks_allocated(callback)
        assert allocated <= baseline, (
            f"{label} retained {allocated - baseline} blocks over many passing calls; "
            f"a passing assertion is a comparison and a `return self`."
        )


# ---------------------------------------------------------------------------
# Module hygiene
# ---------------------------------------------------------------------------
def test_unittest_mock_is_never_imported_anywhere_in_the_module() -> None:
    """Not at module level, and not lazily either -- the module never needs it.

    ``tests/test_packaging.py`` makes the module-level half of this claim for
    ``re`` and friends. This one is stronger, because the cost here is not a
    failure-path import but an import that a session with no mocks in it would
    pay for nothing.

    Reads every file the subject is made of rather than the one
    ``__file__`` names: were the subject ever a package, that one file would be
    its ``__init__``, and the claim would silently shrink to whichever imports
    happened to live there.
    """
    module_path = Path(mock_module.__file__)
    files = sources(module_path.parent) if module_path.name == "__init__.py" else [module_path]
    offenders: dict[str, list[str]] = {}
    for path in files:
        imported: set[str] = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)
        found = sorted(name for name in imported if name.partition(".")[0] == "unittest")
        if found:
            offenders[path.relative_to(module_path.parent).as_posix()] = found
    assert not offenders, f"the mock subject imports {offenders}; it does not need to"


def test_importing_the_library_does_not_pull_unittest_mock_in() -> None:
    """The static check above cannot see an import pulled in through a dependency."""
    probe = (
        "import sys;"
        "sys.path.insert(0, 'src');"
        "import lovely_assertions._mock;"
        "print('unittest.mock' in sys.modules)"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-S", "-c", probe],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    assert result.stdout.strip() == "False"


def test_the_public_surface_is_exported_and_sorted() -> None:
    assert mock_module.__all__ == ["MockExpect", "is_mock"]
    assert list(mock_module.__all__) == sorted(mock_module.__all__)
    for name in mock_module.__all__:
        assert hasattr(mock_module, name), f"__all__ advertises missing name {name!r}"


def test_this_modules_frames_fold_out_of_an_assertion_traceback() -> None:
    """This module's frames fold out of an assertion traceback, and only that one.

    ``__tracebackhide__`` is a callable rather than ``True``, so a genuine
    ``TypeError`` raised from here keeps the frames that explain it.
    """
    assert mock_module.__tracebackhide__ is hide_internal_frames
    assert hide_internal_frames(_Excinfo(AssertionFailure("x"))) is True
    assert hide_internal_frames(_Excinfo(TypeError("x"))) is False


class _Excinfo:
    """The shape pytest hands ``__tracebackhide__``: something with ``.value``."""

    __slots__ = ("value",)

    def __init__(self, value: BaseException) -> None:
        self.value = value


def test_the_subject_carries_no_instance_dictionary() -> None:
    """The subject has no instance dictionary, which is what refuses a misspelling.

    An empty ``__slots__`` leaves nowhere for an unknown name to land, so every
    misspelled assertion is an ``AttributeError`` rather than a silent pass.
    """
    assert MockExpect.__slots__ == ()
    with pytest.raises(AttributeError):
        MockExpect(Mock()).whatever = 1  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue]


def test_every_assertion_hands_back_the_same_subject() -> None:
    """Every assertion returns ``Self``, so a chain stays on the wrapper it started on."""
    fetch = _called((("/a",), {}))
    subject = MockExpect(fetch)
    assert subject.was_called() is subject
    assert subject.was_called_once() is subject
    assert subject.has_call_count(1) is subject
    assert subject.was_called_with("/a") is subject
    assert subject.was_called_once_with("/a") is subject
    assert subject.was_ever_called_with("/a") is subject
    assert subject.was_never_called_with("/z") is subject
    assert MockExpect(Mock()).was_not_called() is not subject
