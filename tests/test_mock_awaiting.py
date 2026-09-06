"""``AsyncMockExpect`` -- the await side of a mock (``_mock._awaiting``).

Three things are pinned here, in this order of importance.

*The silent green is closed.* Calling an ``AsyncMock`` and never awaiting the
coroutine it returns satisfies every assertion on the call side, here and in
``unittest.mock`` both. The tests below show that state passing the call-side
catalogue, failing the await-side one, and -- the part that is the product --
saying which of the two bugs it is.

*The split is honest.* A synchronous ``Mock`` is never handed this subject, and
that is checked against every flavour ``unittest.mock`` ships: the ones that
really do record awaits however they were spelled at the call site
(``Mock(spec=async_fn)``, an autospecced async method) and the ones that do not.
The trap the recognition exists to avoid is pinned too -- a plain ``Mock``
answers ``await_args_list`` with a child mock, so an instance-level check would
hand every mock a catalogue it cannot answer.

*The messages are the product.* ``unittest.mock`` reports "never called" and
"called but never awaited" identically, as ``Awaited 0 times``, mentioning
neither that the mock was called nor with what. Each is pinned byte for byte
here, and so is the third state the call side has no way to reach: awaited fewer
times than it was called.
"""

import asyncio
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, Mock, create_autospec

import pytest

from lovely_assertions import (
    AssertionFailure,
    AsyncMockExpect,
    MockExpect,
    expect,
    is_async_mock,
    is_mock,
    soft_assertions,
)
from lovely_assertions._mock import _recognition
from lovely_assertions._occurrence import at_least, at_most, exactly

if TYPE_CHECKING:
    from collections.abc import Callable


def _message(callback: "Callable[[], object]") -> str:
    """The text of the failure ``callback`` produces."""
    with pytest.raises(AssertionFailure) as caught:
        callback()
    return str(caught.value)


def _awaited(*calls: tuple[tuple[Any, ...], dict[str, Any]]) -> AsyncMock:
    """A mock that has already been awaited, once per pair given."""
    made = AsyncMock()

    async def drive() -> None:
        for args, kwargs in calls:
            await made(*args, **kwargs)

    asyncio.run(drive())
    return made


def _called_never_awaited(*calls: tuple[tuple[Any, ...], dict[str, Any]]) -> AsyncMock:
    """A mock whose coroutines were built and dropped. The state under test.

    ``close()`` on each coroutine is what keeps the suite quiet: dropping one
    unclosed emits ``RuntimeWarning: coroutine was never awaited`` from the
    garbage collector, at whatever point it happens to run, which lands the
    warning on an unrelated test. Closing it changes nothing the mock recorded --
    the call is already in ``call_args_list`` and no await was ever made.
    """
    made = AsyncMock()
    for args, kwargs in calls:
        made(*args, **kwargs).close()
    return made


async def _async_service(url: str) -> str:
    return url


class Service:
    """A class with one async member and one synchronous one, for autospec."""

    async def fetch(self, url: str) -> str:
        return url

    def parse(self, body: str) -> str:
        return body


# ---------------------------------------------------------------------------
# Why this module exists
# ---------------------------------------------------------------------------
def test_the_call_side_passes_on_a_coroutine_nobody_awaited() -> None:
    """The claim in the module docstring, checked rather than asserted in prose.

    Both catalogues pass here -- ours and the standard library's -- because both
    are asking about calls. The mock was called. The work never ran.
    """
    publish = _called_never_awaited((("order.placed",), {}))

    MockExpect(publish).was_called_once_with("order.placed")
    publish.assert_called_once_with("order.placed")

    assert publish.call_count == 1
    assert publish.await_count == 0


def test_the_await_side_is_what_catches_it() -> None:
    publish = _called_never_awaited((("order.placed",), {}))

    assert _message(lambda: AsyncMockExpect(publish).was_awaited()) == (
        "Expected publish to have been awaited,"
        " but it was called once with ('order.placed') and never awaited."
    )


def test_the_standard_library_cannot_tell_the_two_bugs_apart() -> None:
    """Why the message earns its place, measured against what it replaces."""
    never_called = AsyncMock()
    called_not_awaited = _called_never_awaited((("order.placed",), {}))

    with pytest.raises(AssertionError) as first:
        never_called.assert_awaited_once()
    with pytest.raises(AssertionError) as second:
        called_not_awaited.assert_awaited_once()
    assert str(first.value) == str(second.value)

    ours_first = _message(lambda: AsyncMockExpect(never_called).was_awaited_once())
    ours_second = _message(lambda: AsyncMockExpect(called_not_awaited).was_awaited_once())
    assert ours_first != ours_second


# ---------------------------------------------------------------------------
# Which subject a mock gets
# ---------------------------------------------------------------------------
#: Every spelling ``unittest.mock`` offers that really does record awaits. The
#: last two are the ones a reader would not predict: a ``spec`` of an async
#: callable makes ``NonCallableMock.__new__`` mix ``AsyncMockMixin`` into the
#: per-instance subclass it builds, whatever name was written at the call site.
_RECORDS_AWAITS: "list[tuple[str, Callable[[], object]]]" = [
    ("AsyncMock()", AsyncMock),
    ("Mock(spec=async_fn)", lambda: Mock(spec=_async_service)),
    ("MagicMock(spec=async_fn)", lambda: MagicMock(spec=_async_service)),
    ("create_autospec(async_fn)", lambda: create_autospec(_async_service)),
    ("create_autospec(Class).async_method", lambda: create_autospec(Service).fetch),
]

#: And every spelling that does not. ``create_autospec(Service).parse`` beside
#: ``.fetch`` above is the pair that matters: one class, two members, two
#: catalogues.
_RECORDS_NO_AWAITS: "list[tuple[str, Callable[[], object]]]" = [
    ("Mock()", Mock),
    ("MagicMock()", MagicMock),
    ("Mock(spec=SyncClass)", lambda: Mock(spec=Service)),
    ("create_autospec(Class).sync_method", lambda: create_autospec(Service).parse),
    # `unsafe=True` lifts `unittest.mock`'s own refusal of `assert*` names, so an
    # instance-level check would see every async marker answered by a child mock
    # and hand a synchronous mock the await catalogue. Asking the class is what
    # declines it, and this row is what holds the check to asking the class.
    ("Mock(unsafe=True)", lambda: Mock(unsafe=True)),
]


@pytest.mark.parametrize(("label", "build"), _RECORDS_AWAITS, ids=str)
def test_everything_that_records_awaits_gets_the_async_subject(
    label: str, build: "Callable[[], object]"
) -> None:
    made = build()

    assert is_async_mock(made), label
    assert is_mock(made), label
    assert type(expect(made)) is AsyncMockExpect, label


@pytest.mark.parametrize(("label", "build"), _RECORDS_NO_AWAITS, ids=str)
def test_everything_that_does_not_gets_the_plain_one(
    label: str, build: "Callable[[], object]"
) -> None:
    made = build()

    assert not is_async_mock(made), label
    assert is_mock(made), label
    assert type(expect(made)) is MockExpect, label


def test_every_async_marker_is_load_bearing() -> None:
    """``ASYNC_MOCK_MARKERS`` and the ``and`` chain inside it cannot drift apart.

    The twin of ``test_every_marker_is_load_bearing`` for the sync tuple, and it
    exists for a reason that is not symmetry: the chain is written out rather
    than looped over, so nothing but this holds the two in step, and a dropped
    conjunct leaves the whole suite green while the recognition quietly narrows.
    Both directions are checked -- dropping any one name from an otherwise
    complete impostor must be noticed, and the tuple must list nothing the
    function does not ask for.

    ``await_args_list`` is the one that matters most if it goes: every assertion
    in the await catalogue reads it, so a value admitted without it reaches an
    ``AttributeError`` rather than a sentence.
    """
    markers: tuple[str, ...] = _recognition.ASYNC_MOCK_MARKERS
    assert len(markers) == len(set(markers))

    for dropped in markers:
        namespace: dict[str, object] = {name: None for name in markers if name != dropped}
        impostor = type("Impostor", (), namespace)()
        assert is_async_mock(impostor) is False, (
            f"is_async_mock ignored the absence of {dropped!r}, which ASYNC_MOCK_MARKERS lists"
        )

    complete = type("Complete", (), dict.fromkeys(markers))()
    assert is_async_mock(complete) is True


def test_an_async_impostor_is_still_not_a_mock_without_the_sync_markers() -> None:
    """The async protocol is asked of a value already known to be a mock.

    Answering the await markers alone does not make something a mock, and
    ``expect()`` must not reach the async subject for it -- the await catalogue
    reads ``call_args_list`` too, through the shared message helper.
    """
    markers: tuple[str, ...] = _recognition.ASYNC_MOCK_MARKERS
    half = type("HalfAnImpostor", (), dict.fromkeys(markers))()

    assert is_async_mock(half) is True
    assert is_mock(half) is False
    assert type(expect(half)) is not AsyncMockExpect


def test_the_instance_level_trap_the_recognition_exists_to_avoid() -> None:
    """A plain ``Mock`` answers every await marker, and answers with a child mock.

    This is why the question is asked of the class. An instance-level check would
    call every mock async, and the await assertions would then compare against a
    child mock standing in for a list -- which is truthy, so ``was_awaited``
    would pass for a mock that cannot be awaited at all.
    """
    plain = Mock()

    assert hasattr(plain, "await_args_list")
    assert bool(plain.await_args_list)

    assert not hasattr(type(plain), "await_args_list")
    assert not is_async_mock(plain)


def test_the_async_subject_keeps_the_whole_call_side_catalogue() -> None:
    publish = _awaited((("order.placed",), {}))

    expect(publish, as_=AsyncMockExpect).was_called_once_with(
        "order.placed"
    ).and_.was_awaited_once_with("order.placed")


def test_a_plain_mock_has_no_await_assertions_at_all() -> None:
    """Claim one, at runtime: the catalogue a subject offers is the one it can answer.

    Reached through ``getattr`` rather than written as a call, because writing the
    call is a checker error -- which is the *static* half of this claim and is
    pinned in ``typing_tests/negative/``. This half is what a user without a
    checker sees.
    """
    with pytest.raises(AttributeError, match="was_awaited"):
        getattr(MockExpect(Mock()), "was_awaited")()  # noqa: B009  (the point is the lookup)


def test_naming_the_async_subject_for_a_sync_mock_does_not_pass_silently() -> None:
    """``as_=`` overrides inference, so a caller can point this subject anywhere.

    ``expect()`` never does it, and both checkers accept it -- the subject's value
    is ``Any``, so nothing static can refuse it. What must not happen is the one
    thing this package exists to prevent: a mock answers every attribute, so
    ``await_args_list`` on a plain ``Mock`` is a truthy child mock and a
    truth-testing assertion would pass having compared nothing.

    Reading a length instead refuses it. A ``Mock`` has no ``__len__`` at all and
    the misuse is a loud ``TypeError``; a ``MagicMock`` answers ``0``, so the
    assertion fails rather than passes. Neither is a silent green, which is the
    property under test.
    """
    with pytest.raises(TypeError, match="has no len"):
        expect(Mock(), as_=AsyncMockExpect).was_awaited()

    with pytest.raises(AssertionFailure):
        expect(MagicMock(), as_=AsyncMockExpect).was_awaited()


# ---------------------------------------------------------------------------
# How often it was awaited
# ---------------------------------------------------------------------------
def test_was_awaited_passes_for_any_number_of_awaits() -> None:
    publish = _awaited((("/a",), {}))
    AsyncMockExpect(publish).was_awaited()


def test_was_awaited_names_the_absence() -> None:
    publish = AsyncMock()
    assert _message(lambda: AsyncMockExpect(publish).was_awaited()) == (
        "Expected publish to have been awaited, but it was never called."
    )


def test_was_awaited_lists_the_calls_when_there_were_several() -> None:
    publish = _called_never_awaited((("/a",), {}), (("/b",), {"retry": True}))
    assert _message(lambda: AsyncMockExpect(publish).was_awaited()) == (
        "Expected publish to have been awaited,"
        " but it was called 2 times and never awaited: [('/a'), ('/b', retry=True)]."
    )


def test_was_not_awaited_passes_for_a_mock_that_was_only_called() -> None:
    publish = _called_never_awaited((("/a",), {}))
    AsyncMockExpect(publish).was_not_awaited()


def test_was_not_awaited_passes_for_an_untouched_mock() -> None:
    AsyncMockExpect(AsyncMock()).was_not_awaited()


def test_was_not_awaited_lists_what_was_there() -> None:
    publish = _awaited((("/a",), {}), (("/b",), {}))
    assert _message(lambda: AsyncMockExpect(publish).was_not_awaited()) == (
        "Expected publish not to have been awaited, but it was awaited 2 times: [('/a'), ('/b')]."
    )


def test_was_awaited_once_separates_none_from_several() -> None:
    never = AsyncMock()
    assert _message(lambda: AsyncMockExpect(never).was_awaited_once()) == (
        "Expected never to have been awaited once, but it was never called."
    )

    twice = _awaited((("/a",), {}), (("/b",), {}))
    assert _message(lambda: AsyncMockExpect(twice).was_awaited_once()) == (
        "Expected twice to have been awaited once, but it was awaited 2 times: [('/a'), ('/b')]."
    )


def test_has_await_count_takes_a_number() -> None:
    publish = _awaited((("/a",), {}))
    AsyncMockExpect(publish).has_await_count(1)
    assert _message(lambda: AsyncMockExpect(publish).has_await_count(2)) == (
        "Expected publish to have been awaited exactly 2 times,"
        " but it was awaited 1 time: [('/a')]."
    )


def test_has_await_count_takes_an_occurrence() -> None:
    publish = _awaited((("/a",), {}), (("/b",), {}))
    AsyncMockExpect(publish).has_await_count(at_least(2))
    AsyncMockExpect(publish).has_await_count(at_most(2))
    AsyncMockExpect(publish).has_await_count(exactly(2))
    assert _message(lambda: AsyncMockExpect(publish).has_await_count(at_least(3))) == (
        "Expected publish to have been awaited at least 3 times,"
        " but it was awaited 2 times: [('/a'), ('/b')]."
    )


def test_the_two_counts_can_disagree_and_only_the_await_side_sees_it() -> None:
    """The state the call side has no assertion for: one coroutine left unawaited."""
    publish = AsyncMock()

    async def drive() -> None:
        await publish("/a")
        await publish("/b")
        publish("/c").close()

    asyncio.run(drive())

    expect(publish, as_=AsyncMockExpect).has_call_count(3).and_.has_await_count(2)
    assert _message(lambda: AsyncMockExpect(publish).has_await_count(3)) == (
        "Expected publish to have been awaited exactly 3 times,"
        " but it was awaited 2 times: [('/a'), ('/b')]."
    )


# ---------------------------------------------------------------------------
# What it was awaited with
# ---------------------------------------------------------------------------
def test_was_awaited_with_checks_the_last_await_only() -> None:
    publish = _awaited((("/a",), {}), (("/b",), {}))
    AsyncMockExpect(publish).was_awaited_with("/b")
    assert _message(lambda: AsyncMockExpect(publish).was_awaited_with("/a")) == (
        "Expected publish to have been awaited with ('/a'),"
        " but was last awaited with ('/b')."
        "\n  positional arguments:"
        "\n    first difference at index 0: '/b' instead of '/a'"
        "\n  await 1 was made with those arguments; only the last await is checked"
    )


def test_was_awaited_with_says_so_when_nothing_was_awaited() -> None:
    publish = _called_never_awaited((("/a",), {}))
    assert _message(lambda: AsyncMockExpect(publish).was_awaited_with("/a")) == (
        "Expected publish to have been awaited with ('/a'),"
        " but it was called once with ('/a') and never awaited."
    )


def test_was_awaited_once_with_separates_its_four_failures() -> None:
    never = AsyncMock()
    assert _message(lambda: AsyncMockExpect(never).was_awaited_once_with("/a")) == (
        "Expected never to have been awaited once with ('/a'), but it was never called."
    )

    unawaited = _called_never_awaited((("/a",), {}))
    assert _message(lambda: AsyncMockExpect(unawaited).was_awaited_once_with("/a")) == (
        "Expected unawaited to have been awaited once with ('/a'),"
        " but it was called once with ('/a') and never awaited."
    )

    wrong = _awaited((("/b",), {}))
    assert _message(lambda: AsyncMockExpect(wrong).was_awaited_once_with("/a")) == (
        "Expected wrong to have been awaited once with ('/a'),"
        " but was awaited with ('/b')."
        "\n  positional arguments:"
        "\n    first difference at index 0: '/b' instead of '/a'"
    )

    twice = _awaited((("/a",), {}), (("/a",), {}))
    assert _message(lambda: AsyncMockExpect(twice).was_awaited_once_with("/a")) == (
        "Expected twice to have been awaited once with ('/a'),"
        " but it was awaited 2 times: [('/a'), ('/a')]."
        "\n  awaits 1 and 2 were made with those arguments;"
        " it is the await count that is wrong"
    )


def test_was_ever_awaited_with_ignores_position() -> None:
    publish = _awaited((("/a",), {}), (("/b",), {}))
    AsyncMockExpect(publish).was_ever_awaited_with("/a")
    assert _message(lambda: AsyncMockExpect(publish).was_ever_awaited_with("/z")) == (
        "Expected publish to have been awaited with ('/z') at some point,"
        " but none of its 2 awaits was: [('/a'), ('/b')]."
        "\n  the closest was await 1:"
        "\n    positional arguments:"
        "\n      first difference at index 0: '/a' instead of '/z'"
    )


def test_was_ever_awaited_with_explains_a_lone_await() -> None:
    publish = _awaited((("/a",), {}))
    assert _message(lambda: AsyncMockExpect(publish).was_ever_awaited_with("/z")) == (
        "Expected publish to have been awaited with ('/z') at some point,"
        " but its only await was ('/a')."
        "\n  positional arguments:"
        "\n    first difference at index 0: '/a' instead of '/z'"
    )


def test_was_never_awaited_with_passes_when_the_call_was_only_built() -> None:
    """The distinction this assertion has over its call-side twin.

    A dry run that constructs the forbidden request and never runs it fails
    ``was_never_called_with`` and passes here, which is the honest answer: no
    work was done.
    """
    publish = _called_never_awaited((("/danger",), {}))

    AsyncMockExpect(publish).was_never_awaited_with("/danger")
    with pytest.raises(AssertionFailure):
        MockExpect(publish).was_never_called_with("/danger")


def test_was_never_awaited_with_names_the_offending_awaits() -> None:
    publish = _awaited((("/a",), {}), (("/danger",), {}))
    assert _message(lambda: AsyncMockExpect(publish).was_never_awaited_with("/danger")) == (
        "Expected publish never to have been awaited with ('/danger'),"
        " but await 2 was: [('/a'), ('/danger')]."
    )


def test_keyword_arguments_go_through_the_same_difference_engine() -> None:
    publish = _awaited((("/a",), {"retry": True}))
    assert _message(lambda: AsyncMockExpect(publish).was_awaited_with("/a", retry=False)) == (
        "Expected publish to have been awaited with ('/a', retry=False),"
        " but was awaited with ('/a', retry=True)."
        "\n  keyword arguments:"
        "\n    values differ at key 'retry': True instead of False"
    )


# ---------------------------------------------------------------------------
# Continuations over awaits
# ---------------------------------------------------------------------------
def test_awaits_hands_the_recording_to_the_sequence_subject() -> None:
    publish = _awaited((("/a",), {}), (("/b",), {}))
    expect(publish, as_=AsyncMockExpect).awaits.has_length(2)


def test_awaits_is_empty_rather_than_failing_for_a_mock_that_was_only_called() -> None:
    publish = _called_never_awaited((("/a",), {}))
    expect(publish, as_=AsyncMockExpect).awaits.is_empty()


def test_awaits_carries_an_explicit_name() -> None:
    publish = _awaited((("/a",), {}))
    named = expect(publish, as_=AsyncMockExpect, name="the publisher")
    assert _message(lambda: named.awaits.has_length(2)) == (
        "Expected the publisher to have length 2, but had 1: [call('/a')]."
    )


def test_last_await_continues_on_the_most_recent_one() -> None:
    publish = _awaited((("/a",), {}), (("/b",), {}))
    found = AsyncMockExpect(publish).last_await()

    assert found.subject.args == ("/b",)
    found.and_.was_awaited_once_with  # noqa: B018  (the chain is the assertion)


def test_last_await_fails_when_nothing_was_awaited() -> None:
    publish = _called_never_awaited((("/a",), {}))
    assert _message(lambda: AsyncMockExpect(publish).last_await()) == (
        "Expected publish to have been awaited,"
        " but it was called once with ('/a') and never awaited."
    )


# ---------------------------------------------------------------------------
# Everything cross-cutting, which the subject gets for free
# ---------------------------------------------------------------------------
def test_because_attaches_to_the_await_sentence() -> None:
    publish = _called_never_awaited((("order.placed",), {}))
    assert _message(
        lambda: AsyncMockExpect(publish).was_awaited(because="the outbox drains on commit")
    ) == (
        "Expected publish to have been awaited,"
        " but it was called once with ('order.placed') and never awaited"
        " because the outbox drains on commit."
    )


def test_a_soft_scope_collects_await_failures_like_any_other() -> None:
    publish = _called_never_awaited((("/a",), {}))
    with soft_assertions() as scope:
        AsyncMockExpect(publish).described_as("publish").was_awaited()
        AsyncMockExpect(publish).described_as("publish").has_await_count(2)
        collected = scope.discard()

    assert collected == [
        (
            "Expected publish to have been awaited,"
            " but it was called once with ('/a') and never awaited."
        ),
        (
            "Expected publish to have been awaited exactly 2 times,"
            " but it was called once with ('/a') and never awaited."
        ),
    ]


def test_a_narrowing_failure_absorbs_the_rest_of_the_chain() -> None:
    publish = AsyncMock()
    with soft_assertions() as scope:
        AsyncMockExpect(publish).described_as("publish").last_await().which.is_equal_to(3)
        collected = scope.discard()

    assert collected == ["Expected publish to have been awaited, but it was never called."]
