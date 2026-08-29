"""Formatters have to reach the messages, or the registry is decoration.

``tests/test_formatters.py`` covers the registry itself. This file covers the
*reach*: which rendering sites consult it, and — just as importantly — which do
not, so the rule is written down rather than discovered.

The rule is: **a formatter applies wherever the library renders a value itself.**
Where a whole container is handed to ``repr``, the container's ``repr`` calls each
item's ``__repr__`` directly and no formatter is consulted. That is why
``_sequence._render`` builds its listing item by item instead of taking the short
route through ``repr``.
"""

import pytest

from lovely_assertions import (
    AssertionFailure,
    BoolExpect,
    ObjectFormatter,
    expect,
    register_formatter,
    soft_assertions,
)


class Order:
    """No ``__repr__`` on purpose: an address is what a message would show."""

    __slots__ = ("identifier", "total")

    def __init__(self, identifier: int, total: int) -> None:
        self.identifier = identifier
        self.total = total


class Terse:
    """A scoped formatter, distinguishable from the global one at a glance."""

    __slots__ = ()

    def can_handle(self, value: object, /) -> bool:
        return isinstance(value, Order)

    def format(self, value: object, /) -> str:
        return "#" + str(value.identifier) if isinstance(value, Order) else repr(value)


# Registered once, at import, for a type declared in this file — so it is real
# global registration without reaching into any other test's messages.
register_formatter(ObjectFormatter(Order, "identifier", "total"))


def _message(callback: object) -> str:
    with pytest.raises(AssertionFailure) as caught:
        callback()  # type: ignore[operator]  # pyright: ignore[reportCallIssue]
    return str(caught.value)


def test_the_subject_and_the_expected_value_are_formatted() -> None:
    order = Order(7, 4200)
    message = _message(lambda: expect(order).is_equal_to(Order(1, 10)))
    assert "Order(identifier=1, total=10)" in message
    assert "Order(identifier=7, total=4200)" in message
    assert "0x" not in message, "an address means the registry was bypassed"


def test_an_item_inside_a_sequence_is_formatted() -> None:
    """The case formatters are actually wanted in.

    A container's ``repr`` calls each item's ``__repr__`` directly, so rendering
    the collection through ``repr`` would leave a registered formatter invisible
    here — which is most of the reason to have one.
    """
    orders = [Order(1, 10), Order(2, 20)]
    message = _message(lambda: expect(orders).contains(Order(9, 90)))
    assert "Order(identifier=9, total=90)" in message
    assert "Order(identifier=1, total=10)" in message
    assert "0x" not in message


def test_a_value_inside_a_mapping_is_formatted() -> None:
    rows = {"first": Order(1, 10)}
    message = _message(lambda: expect(rows).contains_value(Order(9, 90)))
    assert "Order(identifier=9, total=90)" in message
    assert "Order(identifier=1, total=10)" in message


def test_the_alternatives_of_is_one_of_are_formatted() -> None:
    order = Order(7, 4200)
    message = _message(lambda: expect(order).is_one_of(Order(1, 1), Order(2, 2)))
    assert "Order(identifier=1, total=1)" in message
    assert "Order(identifier=2, total=2)" in message


def test_a_difference_block_is_formatted_too() -> None:
    message = _message(lambda: expect([Order(1, 10)]).is_equal_to([Order(2, 20)]))
    assert "Order(identifier=1, total=10)" in message
    assert "Order(identifier=2, total=20)" in message


# ---------------------------------------------------------------------------
# Rendering that must not change
# ---------------------------------------------------------------------------
def _triple() -> tuple[int, int, int]:
    return (1, 2, 3)


def _single() -> tuple[int]:
    return (1,)


def _empty() -> tuple[int, ...]:
    return ()


def test_a_container_keeps_its_own_brackets() -> None:
    """Items are rendered one at a time; the shape must survive that.

    The tuples come from functions rather than literals because pyright reads a
    tuple literal as a tuple of `Literal` types -- and then rejects
    `expect((1, 2, 3)).contains(9)` outright, since 9 is not among them. That is
    the checker being useful, and it is not what this test is about; a declared
    annotation does not help, because assignment re-narrows to the literal.
    """
    assert "[1, 2, 3]" in _message(lambda: expect([1, 2, 3]).contains(9))
    assert "(1, 2, 3)" in _message(lambda: expect(_triple()).contains(9))
    assert "(1,)" in _message(lambda: expect(_single()).contains(9))
    assert "()" in _message(lambda: expect(_empty()).contains(9))


def test_values_with_no_formatter_still_use_repr() -> None:
    greeting = "hello"
    assert _message(lambda: expect(greeting).is_equal_to("bye")) == (
        "Expected greeting to equal 'bye', but was 'hello'."
    )


# ---------------------------------------------------------------------------
# Scoped formatters
# ---------------------------------------------------------------------------
def test_a_scoped_formatter_overrides_the_global_one() -> None:
    """The whole reason scoping exists: one block, a different rendering."""
    with soft_assertions(formatters=(Terse(),)) as scope:
        order = Order(7, 4200)
        expect(order).is_equal_to(Order(1, 1))
        collected = scope.discard()
    assert collected == ["Expected order to equal #1, but was #7."]


def test_the_global_formatter_is_back_after_the_scope() -> None:
    with soft_assertions(formatters=(Terse(),)) as scope:
        expect(Order(7, 4200)).is_equal_to(Order(1, 1))
        scope.discard()
    order = Order(7, 4200)
    assert "Order(identifier=7, total=4200)" in _message(
        lambda: expect(order).is_equal_to(Order(1, 1))
    )


def test_a_scope_without_formatters_leaves_rendering_alone() -> None:
    with soft_assertions() as scope:
        order = Order(7, 4200)
        expect(order).is_equal_to(Order(1, 1))
        collected = scope.discard()
    assert "Order(identifier=7, total=4200)" in collected[0]


def test_a_scope_can_be_re_entered() -> None:
    """The push token is cleared on exit; a spent one would raise on re-entry."""
    scope = soft_assertions(formatters=(Terse(),))
    for _ in range(2):
        with scope:
            order = Order(7, 4200)
            expect(order).is_equal_to(Order(1, 1))
            assert scope.discard() == ["Expected order to equal #1, but was #7."]


# ---------------------------------------------------------------------------
# Every rendering site on a subject, not just the ones equality goes through
# ---------------------------------------------------------------------------
class YesNo:
    """A formatter for ``bool``, so a subject's own catalogue can be checked.

    Scoped rather than registered globally: global registration is write-once and
    would rewrite every other test's booleans for the rest of the session.
    """

    __slots__ = ()

    def can_handle(self, value: object, /) -> bool:
        return type(value) is bool

    def format(self, value: object, /) -> str:
        return "yes" if value else "no"


def test_a_subjects_own_assertions_format_the_same_way_equality_does() -> None:
    """A formatter reaches every assertion on a subject, not the inherited ones only.

    The failure this pins is the quiet kind: ``is_equal_to`` is inherited and
    renders through the registry, so a formatter looks like it works. An
    assertion written on the subject itself that interpolates the value directly
    ignores it, and the same value then reads two ways in one report -- which is
    the one thing a formatter exists to stop.
    """
    with soft_assertions(formatters=(YesNo(),)) as scope:
        flag = False
        raised = True
        expect(flag).is_true()
        expect(raised).is_false()
        expect(raised).implies(False)
        expect(flag).is_equal_to(True)
        collected = scope.discard()

    assert collected == [
        "Expected flag to be True, but was no.",
        "Expected raised to be False, but was yes.",
        "Expected raised to imply the consequent, but was yes while the consequent was no.",
        "Expected flag to equal yes, but was no.",
    ]


def test_a_subject_that_is_not_really_a_bool_still_shows_what_it_was() -> None:
    """Routing through the registry must not hide the value a strict check rejected.

    ``is_true`` asks for ``True`` itself, and its whole worth is naming what
    turned up instead when a ``1`` or a NumPy scalar reaches the subject by hand.
    A formatter that claims only real booleans declines here, and the value falls
    through to its own rendering rather than being described as a boolean.
    """
    with soft_assertions(formatters=(YesNo(),)) as scope:
        truthy = 1
        BoolExpect(truthy).is_true()  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
        collected = scope.discard()
    assert collected == ["Expected truthy to be True, but was 1."]
