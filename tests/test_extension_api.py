"""Adding your own domain assertions.

The extension model has two halves that trade off against each other, and the
tests below pin both including the trade-off.

``expect(x, as_=MyExpect)`` is **explicit and statically typed**: the checker knows
exactly what comes back, so autocompletion and narrowing work as they do for the
built-in subjects.

``register(MyType, MyExpect)`` is **automatic and not statically narrowable**:
``expect(x)`` returns your subject at runtime, but a type checker still reads the
declared overload set and says ``Expect[MyType]``. That is a limitation of the
language, not an oversight, and it is asserted here so nobody has to discover it.
"""

import importlib
from typing import Self

import pytest

from lovely_assertions import AssertionFailure, Expect, custom_assertion, expect, register
from lovely_assertions import _subjects as subjects


class Money:
    """A domain type with no useful ``repr`` of its own, on purpose."""

    __slots__ = ("cents",)

    def __init__(self, cents: int) -> None:
        self.cents = cents

    def __repr__(self) -> str:
        return f"Money({self.cents})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Money) and other.cents == self.cents

    def __hash__(self) -> int:
        return hash(self.cents)


class MoneyExpect(Expect[Money]):
    """A user-written subject, written exactly the way an author is taught to."""

    __slots__ = ()

    @custom_assertion
    def is_positive(self, *, because: str = "") -> Self:
        if self._subject.cents > 0:
            return self
        return self._fail(f"to be positive, but was {self._subject.cents} cents", because)

    @custom_assertion
    def is_at_least(self, minimum: Money, /, *, because: str = "") -> Self:
        if self._subject.cents >= minimum.cents:
            return self
        return self._fail(
            f"to be at least {minimum.cents} cents, but was {self._subject.cents}", because
        )


# ---------------------------------------------------------------------------
# expect(x, as_=...) — explicit, typed
# ---------------------------------------------------------------------------
def test_as_returns_the_requested_subject() -> None:
    subject = expect(Money(500), as_=MoneyExpect)
    assert isinstance(subject, MoneyExpect)
    assert subject.subject == Money(500)


def test_as_gives_the_custom_assertions() -> None:
    expect(Money(500), as_=MoneyExpect).is_positive().and_.is_at_least(Money(100))


def test_as_keeps_the_inherited_catalogue() -> None:
    expect(Money(500), as_=MoneyExpect).is_equal_to(Money(500)).and_.is_not_none()


def test_a_custom_assertion_names_the_callers_variable() -> None:
    """The whole point of ``@custom_assertion``: the extension's frame is skipped."""
    refund = Money(-250)
    with pytest.raises(AssertionFailure) as caught:
        expect(refund, as_=MoneyExpect).is_positive()
    assert str(caught.value) == "Expected refund to be positive, but was -250 cents."


def test_a_custom_assertion_takes_a_reason_like_any_other() -> None:
    refund = Money(-250)
    with pytest.raises(AssertionFailure, match="because refunds are settled separately"):
        expect(refund, as_=MoneyExpect).is_positive(because="refunds are settled separately")


def test_as_is_keyword_only() -> None:
    with pytest.raises(TypeError):
        expect(Money(1), MoneyExpect)  # type: ignore[call-overload]  # pyright: ignore[reportCallIssue]


def test_custom_subjects_take_part_in_soft_scopes() -> None:
    """The seam is in ``_fail``, so an extension gets soft scopes for free."""
    from lovely_assertions import soft_assertions

    with soft_assertions("ledger") as scope:
        refund = Money(-250)
        expect(refund, as_=MoneyExpect).is_positive()
        collected = scope.discard()
    assert collected == ["Expected ledger/refund to be positive, but was -250 cents."]


# ---------------------------------------------------------------------------
# register(type, factory) — automatic, not statically narrowable
# ---------------------------------------------------------------------------
class Temperature:
    __slots__ = ("celsius",)

    def __init__(self, celsius: float) -> None:
        self.celsius = celsius

    def __repr__(self) -> str:
        return f"Temperature({self.celsius})"


class TemperatureExpect(Expect[Temperature]):
    __slots__ = ()

    @custom_assertion
    def is_freezing(self, *, because: str = "") -> Self:
        if self._subject.celsius <= 0:
            return self
        return self._fail(f"to be freezing, but was {self._subject.celsius}C", because)


register(Temperature, TemperatureExpect)


def test_register_makes_plain_expect_return_the_custom_subject() -> None:
    assert isinstance(expect(Temperature(-5)), TemperatureExpect)


def test_a_registered_subject_carries_its_own_assertions() -> None:
    reading = Temperature(20)
    with pytest.raises(AssertionFailure) as caught:
        # Both suppressions ARE the limitation: `register` dispatches at runtime,
        # and no checker can see through that. The explicit `as_=` form has no
        # such problem, which is the point of offering both.
        expect(reading).is_freezing()  # type: ignore[attr-defined]  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
    assert str(caught.value) == "Expected reading to be freezing, but was 20C."


def test_registration_is_by_exact_type_not_by_subclass() -> None:
    """A subclass is a different type and may well want a different subject."""

    class Kelvin(Temperature):
        __slots__ = ()

    assert not isinstance(expect(Kelvin(1)), TemperatureExpect)


def test_registering_the_same_type_twice_is_refused() -> None:
    """The registry is write-once at import time, never mutated per test."""

    class Duration:
        __slots__ = ()

    class DurationExpect(Expect[Duration]):
        __slots__ = ()

    register(Duration, DurationExpect)
    with pytest.raises(ValueError, match="already registered"):
        register(Duration, DurationExpect)


def test_registering_over_a_built_in_is_refused() -> None:
    """It would put the runtime and the static overloads out of step."""

    class SneakyStringExpect(Expect[str]):
        __slots__ = ()

    with pytest.raises(ValueError, match="StringExpect"):
        register(str, SneakyStringExpect)


#: Every one of these is claimed by an ``expect()`` overload without being one of
#: the exact built-in types the subject table names. A guard that compared against
#: that list of names alone would let each of them be registered over, while the
#: checkers went on promising the overload's answer.
_CLAIMED_ELSEWHERE = [
    "datetime.datetime",
    "decimal.Decimal",
    "builtins.bytes",
    "builtins.range",
    "collections.OrderedDict",
]


@pytest.mark.parametrize("dotted", _CLAIMED_ELSEWHERE)
def test_registering_over_any_claimed_type_is_refused(dotted: str) -> None:
    """The guard asks the dispatch chain, not a hand-maintained list of names."""
    module_name, _, type_name = dotted.rpartition(".")
    claimed: type[object] = getattr(importlib.import_module(module_name), type_name)

    class Sneaky(Expect[object]):
        __slots__ = ()

    with pytest.raises(ValueError, match="already has a subject"):
        register(claimed, Sneaky)


def test_a_type_with_no_subject_of_its_own_still_registers() -> None:
    """The guard must refuse the collisions without refusing the feature."""

    class Invoice:
        __slots__ = ()

    class InvoiceExpect(Expect[Invoice]):
        __slots__ = ()

    register(Invoice, InvoiceExpect)
    try:
        assert type(expect(Invoice())) is InvoiceExpect
    finally:
        del vars(subjects)["_REGISTERED"][Invoice]
