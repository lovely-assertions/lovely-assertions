"""Every marked line must be rejected by both checkers.

The extension API is the one place the caller supplies the subject class, so what
has to hold is that ``as_`` stays honest: it is named rather than positional, it
does not erase to the base subject, and the value it is given must be one the
subject can actually hold. Runtime registration is the one thing a checker cannot
follow, and that limit is pinned here too -- from the side where it must *not*
compile.
"""

from typing import Self, assert_type

from lovely_assertions import Expect, StringExpect, custom_assertion, expect


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


def as_must_be_keyword_only(amount: Money) -> None:
    expect(amount, MoneyExpect)  # expect-error: `as_` is keyword-only


def as_does_not_erase_to_the_base(amount: Money) -> None:
    assert_type(expect(amount, as_=MoneyExpect), Expect[Money])  # expect-error


def register_does_not_narrow(amount: Money) -> None:
    """Runtime registration changes dispatch, not types: a checker cannot see it."""
    expect(amount).is_positive()  # expect-error: runtime dispatch is invisible to a checker


def a_custom_assertion_keeps_its_signature(amount: Money) -> None:
    expect(amount, as_=MoneyExpect).is_positive("a reason")  # expect-error: keyword-only


def as_must_match_the_value_it_is_given(amount: Money) -> None:
    """``as_`` ties the value to the subject that is going to hold it.

    It takes a ``Callable[[V], X]``, so the subject has to accept what it is being
    handed. Declared ``(value: object, *, as_: type[X]) -> X`` instead, the value is
    untied from the subject's ``T`` entirely: an ``int`` could be built into an
    ``Expect[str]`` and ``.subject.upper()`` would propagate the lie into user code
    with both checkers green.
    """
    expect(3, as_=MoneyExpect)  # expect-error: an int is not a Money
    expect("500", as_=MoneyExpect)  # expect-error: nor is a str
    expect(amount, as_=StringExpect)  # expect-error: a Money is not a str


def as_still_has_to_build_a_subject(amount: Money) -> None:
    """``X`` is bound to ``Expect[Any]``: a factory that returns anything else is not one."""
    expect(amount, as_=lambda value: value.cents)  # expect-error: an int is not a subject
