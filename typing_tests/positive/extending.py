"""The extension model, statically.

The point of these is the *asymmetry*: `as_=` is fully typed, `register` is not.
Both halves are pinned, because a reader who only saw one would draw the wrong
conclusion about the other.
"""

from typing import Self, assert_type

from lovely_assertions import Expect, custom_assertion, expect


class Money:
    __slots__ = ("cents",)

    def __init__(self, cents: int) -> None:
        self.cents = cents


class MoneyExpect(Expect[Money]):
    __slots__ = ()

    @custom_assertion
    def is_positive(self, *, because: str = "") -> Self:
        if self._subject.cents > 0:
            return self
        return self._fail(f"to be positive, but was {self._subject.cents}", because)


def as_is_fully_typed(amount: Money) -> None:
    assert_type(expect(amount, as_=MoneyExpect), MoneyExpect)
    assert_type(expect(amount, as_=MoneyExpect).is_positive(), MoneyExpect)
    assert_type(expect(amount, as_=MoneyExpect).is_positive().and_.is_positive(), MoneyExpect)
    assert_type(expect(amount, as_=MoneyExpect).subject, Money)
    assert_type(expect(amount, as_=MoneyExpect).is_equal_to(amount), MoneyExpect)


def as_works_on_any_subject(text: str) -> None:
    """Not only for custom types: `as_` overrides inference wherever it is used."""

    class Slug(Expect[str]):
        __slots__ = ()

    assert_type(expect(text, as_=Slug), Slug)


def register_cannot_narrow(amount: Money) -> None:
    """The documented limitation, pinned so it cannot regress into a false promise.

    `register(Money, MoneyExpect)` makes this return a `MoneyExpect` at runtime.
    A checker still reads the declared overloads and says `Expect[Money]` — there
    is no way to express runtime dispatch in the type system, and pretending
    otherwise would be worse than saying so.
    """
    assert_type(expect(amount), Expect[Money])
