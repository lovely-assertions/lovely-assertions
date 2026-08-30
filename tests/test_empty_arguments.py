"""A variadic assertion given nothing must not quietly pass.

``expect(items).contains_in_order(*expected)`` where ``expected`` came back empty
is the classic green test that asserted nothing. The whole discipline of this
project is aimed at tests that cannot fail, so the library must not ship the
mistake itself.

The rule: **a variadic assertion with no arguments raises ``ValueError``** wherever
the call would otherwise be vacuous — assert nothing, or assert something no
subject could satisfy. That is a bug in the test, not a finding about the subject,
so it is raised rather than reported through ``_fail``. ``StringExpect`` already
refuses; this pins the same rule on every subject.

Two variadic assertions are deliberately left alone, because an empty call means
something there rather than nothing: ``contains_only_keys()`` asserts the mapping
is empty, and ``satisfies_respectively()`` asserts the sequence is.
"""

import inspect
from collections.abc import Callable
from decimal import Decimal
from unittest.mock import Mock

import pytest

from _happy_calls import SUBJECT_CLASSES, declaring_class, owning_subject
from lovely_assertions import AssertionFailure, expect

_VACUOUS: list[tuple[str, Callable[[], object]]] = [
    ("Expect.is_one_of", lambda: expect(object()).is_one_of()),
    ("StringExpect.contains_all", lambda: expect("abc").contains_all()),
    ("StringExpect.contains_any", lambda: expect("abc").contains_any()),
    ("StringExpect.does_not_contain_all", lambda: expect("abc").does_not_contain_all()),
    ("StringExpect.does_not_contain_any", lambda: expect("abc").does_not_contain_any()),
    ("SequenceExpect.contains_in_order", lambda: expect([1, 2]).contains_in_order()),
    (
        "SequenceExpect.contains_in_consecutive_order",
        lambda: expect([1, 2]).contains_in_consecutive_order(),
    ),
    (
        "SequenceExpect.does_not_contain_in_order",
        lambda: expect([1, 2]).does_not_contain_in_order(),
    ),
    (
        "SequenceExpect.does_not_contain_in_consecutive_order",
        lambda: expect([1, 2]).does_not_contain_in_consecutive_order(),
    ),
    ("MappingExpect.contains_keys", lambda: expect({"a": 1}).contains_keys()),
    ("MappingExpect.does_not_contain_keys", lambda: expect({"a": 1}).does_not_contain_keys()),
    ("MappingExpect.contains_values", lambda: expect({"a": 1}).contains_values()),
    ("MappingExpect.does_not_contain_values", lambda: expect({"a": 1}).does_not_contain_values()),
]


@pytest.mark.parametrize(("label", "call"), _VACUOUS, ids=[label for label, _ in _VACUOUS])
def test_a_vacuous_call_is_a_caller_bug(label: str, call: Callable[[], object]) -> None:
    """``ValueError``, not ``AssertionFailure``: the test is wrong, not the subject."""
    with pytest.raises(ValueError, match="at least one") as caught:
        call()
    assert not isinstance(caught.value, AssertionFailure), (
        f"{label} reported a vacuous call as an assertion failure; "
        f"it is a bug in the test, and an AssertionFailure would let a runner "
        f"present it as a finding about the subject"
    )


def test_the_splat_that_motivates_the_rule() -> None:
    """The shape this actually takes in a real test suite."""
    expected: list[int] = []  # a fixture returned nothing
    with pytest.raises(ValueError, match="at least one"):
        expect([1, 2, 3]).contains_in_order(*expected)


# ---------------------------------------------------------------------------
# Where an empty call means something, it keeps meaning it
# ---------------------------------------------------------------------------
def test_contains_only_keys_with_no_keys_asserts_emptiness() -> None:
    empty: dict[str, int] = {}
    expect(empty).contains_only_keys()
    with pytest.raises(AssertionFailure):
        expect({"a": 1}).contains_only_keys()


def test_satisfies_respectively_with_no_assertions_asserts_emptiness() -> None:
    empty: list[int] = []
    expect(empty).satisfies_respectively()
    with pytest.raises(AssertionFailure):
        expect([1]).satisfies_respectively()


def test_a_populated_call_is_unaffected() -> None:
    """The guard must not change what these assertions do when given values."""
    expect([1, 2, 3]).contains_in_order(1, 3)
    expect({"a": 1, "b": 2}).contains_keys("a", "b")
    expect({"a": 1}).contains_values(1)
    expect({"a": 1}).does_not_contain_keys("z")
    expect("abc").contains_all("a", "b")
    expect(2).is_one_of(1, 2, 3)


# ---------------------------------------------------------------------------
# The rule, enforced by enumeration rather than by a list
# ---------------------------------------------------------------------------
#: The variadic assertions an empty call says something with, rather than nothing.
#: ``contains_only_keys()`` and ``satisfies_respectively()`` assert the subject is
#: empty.
#:
#: The four ``MockExpect`` rows are the clearest case in the set:
#: ``was_called_with()`` asserts the mock was called **with no arguments**, and
#: reports "expected to have been called with no arguments, but was called with
#: (1)" when it was not. Refusing the empty call would remove the only way to say
#: that.
_MEANINGFUL_WHEN_EMPTY = frozenset(
    {
        ("MappingExpect", "contains_only_keys"),
        ("SequenceExpect", "satisfies_respectively"),
        ("CollectionExpect", "satisfies_respectively"),
        ("MockExpect", "was_called_with"),
        ("MockExpect", "was_called_once_with"),
        ("MockExpect", "was_ever_called_with"),
        ("MockExpect", "was_never_called_with"),
    }
)


def _specimens() -> dict[str, object]:
    """One live subject per class that defines a variadic assertion.

    Hand-written, because a subject cannot be synthesised from its class: a
    ``MockExpect`` needs a mock that has been called, a ``PathExpect`` needs a
    path that exists. What is *not* hand-written is which classes need to be here
    -- :func:`test_every_variadic_owner_has_a_specimen` reads that off the
    package, so a new subject with a variadic assertion and no specimen fails by
    name instead of being skipped.
    """
    called = Mock()
    called(1, key="v")
    return {
        "Expect": expect(object()),
        "BoolExpect": expect(True),
        "StringExpect": expect("abc"),
        "NumericExpect": expect(5),
        "OrderedExpect": expect(Decimal("1")),
        "CollectionExpect": expect({1, 2}),
        "SequenceExpect": expect([1, 2]),
        "MappingExpect": expect({"a": 1}),
        "MockExpect": expect(called),
        "CallableExpect": expect(len),
        "TypeExpect": expect(int),
    }


def _variadic_assertions() -> list[tuple[str, str, object]]:
    """Every public variadic assertion in the package, found by introspection.

    Listing them by hand is how a guard like this drifts: a variadic assertion is
    added, the list is not, and nothing notices. Enumerating cannot drift.

    The same applies one level up, to the *classes*: hand-list those and a whole
    subject's worth of assertions goes unchecked. They are read off
    ``SUBJECT_CLASSES``, the table ``tests/_happy_calls.py`` already derives for
    the other guards, so this file walks whatever the package has rather than
    whatever someone remembered.

    Keyed on the subject that *carries* each assertion, so an inherited one is
    exercised once rather than once per subclass. A subject is assembled from one
    mixin per seam, so the class a method is declared on is usually not a subject
    at all and has no specimen -- keying on it drops the assertion instead.
    """
    specimens = _specimens()
    found: dict[tuple[str, str], tuple[str, str, object]] = {}
    for cls in SUBJECT_CLASSES:
        for name, member in inspect.getmembers(cls, inspect.isfunction):
            if name.startswith("_"):
                continue
            parameters = inspect.signature(member).parameters.values()
            if not any(p.kind is inspect.Parameter.VAR_POSITIONAL for p in parameters):
                continue
            owner = owning_subject(declaring_class(cls, name))
            subject = specimens.get(owner)
            if subject is not None:
                found[(owner, name)] = (owner, name, subject)
    return sorted(found.values(), key=lambda entry: entry[:2])


def _variadic_owners() -> set[str]:
    """The classes that define a variadic assertion, whether or not one is here."""
    owners: set[str] = set()
    for cls in SUBJECT_CLASSES:
        for name, member in inspect.getmembers(cls, inspect.isfunction):
            if name.startswith("_"):
                continue
            parameters = inspect.signature(member).parameters.values()
            if any(p.kind is inspect.Parameter.VAR_POSITIONAL for p in parameters):
                owners.add(owning_subject(declaring_class(cls, name)))
    return owners


def test_every_variadic_owner_has_a_specimen() -> None:
    """A class with no specimen is a class this file silently skips.

    The enumeration cannot call an assertion without a subject to call it on, so
    a missing specimen would drop that class's assertions from the guard and
    leave every test green. This is what turns that into a failure.
    """
    missing = sorted(_variadic_owners() - set(_specimens()))
    assert not missing, (
        f"these classes define a variadic assertion and have no specimen in "
        f"`_specimens()`, so this file does not check them: {missing}"
    )


def test_no_variadic_assertion_passes_on_an_empty_call() -> None:
    """Enumerated rather than listed, so a new variadic assertion cannot escape it."""
    offenders: list[str] = []
    for owner, name, subject in _variadic_assertions():
        if (owner, name) in _MEANINGFUL_WHEN_EMPTY:
            continue
        try:
            getattr(subject, name)()
        except (AssertionFailure, ValueError, TypeError):
            continue
        offenders.append(f"{owner}.{name}")
    assert not offenders, (
        f"these pass with no arguments, asserting nothing: {sorted(set(offenders))}. "
        f"Guard them with `raise ValueError(_NEEDS_VALUES)`, or add them to "
        f"_MEANINGFUL_WHEN_EMPTY if an empty call genuinely asserts emptiness."
    )


def test_the_enumeration_finds_something() -> None:
    """A guard over an empty enumeration would pass for the wrong reason."""
    assert len(_variadic_assertions()) > 15
