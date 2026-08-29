"""The value-formatter registry.

The registry exists so that a failure message about a domain object says
something about the object. So these tests pin the **rendered text**: a test that
only asserted a formatter had been consulted would pass on a rendering that put
the wrong number next to the right label.

Three properties get their own section, because each is a promise something else
relies on.

*It never raises.* Formatters are user code. One that throws, or returns the
wrong type, costs the reader detail -- never an error raised in place of their
assertion failure.

*Scoping is per context.* A ``ContextVar``, so a scope in one thread or one
asyncio task cannot reach into another's messages. Same guarantee, and the same
tests, as the soft-assertion scopes in ``tests/test_soft_assertions.py``.

*Order is the contract.* Scoped before global, innermost scope first, first
registration before later ones, ``repr`` last. A scoped formatter overriding a
global one is the whole reason scoping exists, so it is asserted directly.
"""

import asyncio
import threading
from collections.abc import Generator, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any, Final, cast

import pytest

from lovely_assertions import _formatters
from lovely_assertions._formatters import (
    IterableFormatter,
    ObjectFormatter,
    ValueFormatter,
    format_value,
    pop_formatters,
    push_formatters,
    register_formatter,
)


# ---------------------------------------------------------------------------
# Subjects
# ---------------------------------------------------------------------------
class Order:
    """A domain object whose ``repr`` is legible and says nothing about its fields."""

    __slots__ = ("identifier", "total")

    def __init__(self, identifier: int, total: int) -> None:
        self.identifier = identifier
        self.total = total

    def __repr__(self) -> str:
        return "<Order>"


class RushOrder(Order):
    """A subclass, to pin which type name a rendering carries."""

    __slots__ = ()


class Opaque:
    """No ``repr`` of its own -- the ``<... object at 0x...>`` case, on purpose."""

    __slots__ = ("identifier",)

    def __init__(self, identifier: int) -> None:
        self.identifier = identifier


class Ticket:
    """Claimed by the one formatter this module registers globally, for real."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code

    def __repr__(self) -> str:
        return "<Ticket>"


class Feed:
    """An iterable with no length: a stream, not a collection."""

    __slots__ = ("_items",)

    def __init__(self, *items: int) -> None:
        self._items: tuple[int, ...] = items

    def __iter__(self) -> Iterator[int]:
        return iter(self._items)


class Basket(list[object]):
    """A ``list`` subclass, to pin which type name an iterable rendering carries."""

    __slots__ = ()


class Unmeasurable:
    """Long enough to truncate, and its ``__len__`` throws when asked how long."""

    __slots__ = ()

    def __iter__(self) -> Iterator[int]:
        return iter(range(20))

    def __len__(self) -> int:
        raise RuntimeError("len exploded")


class Sealed:
    """A type an ``IterableFormatter`` might be pointed at by mistake."""

    __slots__ = ()


class Hostile:
    """A subject whose ``repr`` explodes."""

    __slots__ = ()

    def __repr__(self) -> str:
        raise RuntimeError("repr exploded")


class Nameless(type):
    """A metaclass that refuses every attribute -- ``__name__`` included."""

    def __getattribute__(cls, name: str) -> Any:
        raise RuntimeError("nothing to see here")


class Unnameable(metaclass=Nameless):
    """Defeats ``repr`` and then defeats the fallback that names the type."""

    def __repr__(self) -> str:
        raise RuntimeError("repr exploded")


# ---------------------------------------------------------------------------
# Formatter doubles
# ---------------------------------------------------------------------------
class Fixed:
    """Claims one type, renders one fixed string. For testing order, not output."""

    __slots__ = ("_claimed", "_text")

    def __init__(self, claimed: type, text: str) -> None:
        self._claimed = claimed
        self._text = text

    def can_handle(self, value: object, /) -> bool:
        return isinstance(value, self._claimed)

    def format(self, value: object, /) -> str:
        return self._text


class ExplodesOnClaim:
    """A formatter with a bug in the half that decides."""

    __slots__ = ()

    def can_handle(self, value: object, /) -> bool:
        raise RuntimeError("can_handle exploded")

    def format(self, value: object, /) -> str:
        return "never reached"


class ExplodesOnFormat:
    """A formatter with a bug in the half that renders."""

    __slots__ = ()

    def can_handle(self, value: object, /) -> bool:
        return True

    def format(self, value: object, /) -> str:
        raise RuntimeError("format exploded")


class ReturnsANonString:
    """A formatter that breaks its own ``-> str`` contract."""

    __slots__ = ()

    def can_handle(self, value: object, /) -> bool:
        return True

    def format(self, value: object, /) -> int:
        return 42


class ClaimIsNotCallable:
    """Both names present; the one that decides is a truthy attribute, not a method.

    A shape check that only asks whether the attributes *exist* accepts this, and
    every later call raises ``TypeError`` -- which rendering reads as a decline.
    """

    __slots__ = ()

    can_handle = True

    def format(self, value: object, /) -> str:
        return "surely not"


class FormatIsNotCallable:
    """The other half, which has to be checked separately or it is not checked."""

    __slots__ = ()

    format = "surely not"

    def can_handle(self, value: object, /) -> bool:
        return True


class Abort(BaseException):
    """Deliberately not an ``Exception``: the safety net is not meant to catch it."""


class Interrupts:
    """A formatter that throws straight past the safety net."""

    __slots__ = ()

    def can_handle(self, value: object, /) -> bool:
        return True

    def format(self, value: object, /) -> str:
        raise Abort


#: The one real, permanent registration in this file. It claims ``Ticket`` and
#: nothing else, so the global registry it writes to stays honest for every other
#: test in the suite -- which is exactly the discipline the registry asks of a
#: user: configure once, at import, for your own types.
register_formatter(ObjectFormatter(Ticket, "code"))

ORDER_FORMATTER: Final = ObjectFormatter(Order, "identifier", "total")


@contextmanager
def scoped(*formatters: ValueFormatter) -> Generator[None]:
    """Push formatters for the body of a ``with``, the way ``SoftScope`` does."""
    token = push_formatters(formatters)
    try:
        yield
    finally:
        pop_formatters(token)


@pytest.fixture
def clean_registry(monkeypatch: pytest.MonkeyPatch) -> list[ValueFormatter]:
    """An empty global registry for one test.

    The shipped registry is write-once by design and offers no way to unregister,
    so a test that needs to watch registrations happen replaces the list rather
    than mutating the one the library is running on.
    """
    registry: list[ValueFormatter] = []
    monkeypatch.setattr(_formatters, "_GLOBAL", registry)
    return registry


# ---------------------------------------------------------------------------
# Nothing registered
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("clean_registry")
def test_a_value_nobody_claims_is_rendered_by_repr() -> None:
    assert format_value(3) == "3"
    assert format_value("x") == "'x'"
    assert format_value([1, 2]) == "[1, 2]"
    assert format_value(None) == "None"


def test_a_formatter_replaces_the_address_that_a_domain_object_prints() -> None:
    """The message this whole module exists to stop printing."""
    opaque = Opaque(7)
    assert "object at" in repr(opaque)
    with scoped(ObjectFormatter(Opaque, "identifier")):
        assert format_value(opaque) == "Opaque(identifier=7)"


# ---------------------------------------------------------------------------
# Scoped formatters
# ---------------------------------------------------------------------------
def test_a_scoped_formatter_renders_the_value() -> None:
    with scoped(ORDER_FORMATTER):
        assert format_value(Order(7, 42)) == "Order(identifier=7, total=42)"


def test_a_scoped_formatter_stops_at_the_end_of_its_scope() -> None:
    with scoped(ORDER_FORMATTER):
        assert format_value(Order(7, 42)) == "Order(identifier=7, total=42)"
    assert format_value(Order(7, 42)) == "<Order>"


def test_the_innermost_scope_wins() -> None:
    """Nested scopes push in front, so the closest one to the assertion decides."""
    with scoped(Fixed(Order, "outer")):
        assert format_value(Order(1, 2)) == "outer"
        with scoped(Fixed(Order, "inner")):
            assert format_value(Order(1, 2)) == "inner"
        assert format_value(Order(1, 2)) == "outer"


def test_the_first_formatter_to_claim_the_value_wins() -> None:
    with scoped(Fixed(Order, "first"), Fixed(Order, "second")):
        assert format_value(Order(1, 2)) == "first"


def test_a_formatter_that_declines_lets_the_next_one_answer() -> None:
    with scoped(Fixed(Ticket, "not this one"), Fixed(Order, "this one")):
        assert format_value(Order(1, 2)) == "this one"


def test_a_scoped_formatter_overrides_a_global_one(
    clean_registry: list[ValueFormatter],
) -> None:
    """The reason scoping exists: change a rendering without touching shared config."""
    register_formatter(Fixed(Order, "global"))
    assert format_value(Order(1, 2)) == "global"
    with scoped(Fixed(Order, "scoped")):
        assert format_value(Order(1, 2)) == "scoped"
    assert format_value(Order(1, 2)) == "global"
    assert len(clean_registry) == 1


def test_pushing_nothing_is_a_valid_pair() -> None:
    """``SoftScope`` opens with no formatters far more often than with some."""
    with scoped():
        assert format_value(Order(1, 2)) == "<Order>"


# ---------------------------------------------------------------------------
# The global registry
# ---------------------------------------------------------------------------
def test_a_globally_registered_formatter_renders_the_value() -> None:
    """Against the real registry, written once at this module's import."""
    assert format_value(Ticket("AB-1")) == "Ticket(code='AB-1')"


@pytest.mark.usefixtures("clean_registry")
def test_global_formatters_are_consulted_in_registration_order() -> None:
    """First registration wins; a later one does not displace it."""
    register_formatter(Fixed(Order, "first"))
    register_formatter(Fixed(Order, "second"))
    assert format_value(Order(1, 2)) == "first"


@pytest.mark.usefixtures("clean_registry")
def test_registering_the_same_formatter_twice_is_refused() -> None:
    """Write-once at import and never per test: nothing here can be unregistered."""
    formatter = Fixed(Order, "once")
    register_formatter(formatter)
    with pytest.raises(ValueError, match="already registered"):
        register_formatter(formatter)


@pytest.mark.usefixtures("clean_registry")
def test_two_formatters_of_the_same_class_are_not_a_duplicate() -> None:
    """The check is on identity: two ``ObjectFormatter``\\ s are two formatters."""
    register_formatter(ObjectFormatter(Order, "identifier"))
    register_formatter(ObjectFormatter(Opaque, "identifier"))
    assert format_value(Order(7, 42)) == "Order(identifier=7)"
    assert format_value(Opaque(3)) == "Opaque(identifier=3)"


@pytest.mark.usefixtures("clean_registry")
def test_registering_something_that_is_not_a_formatter_is_refused() -> None:
    """The only place a typo can be reported: rendering swallows it by design."""
    with pytest.raises(TypeError, match="can_handle"):
        register_formatter(cast("ValueFormatter", object()))


@pytest.mark.usefixtures("clean_registry")
def test_registering_a_formatter_whose_members_are_not_callable_is_refused() -> None:
    """Presence is not enough. ``can_handle = True`` has the right shape and no use.

    Left to rendering it would raise ``TypeError`` on every call, be read as a
    decline, and change nothing about any message -- forever, and silently.
    """
    with pytest.raises(TypeError, match="can_handle"):
        register_formatter(cast("ValueFormatter", ClaimIsNotCallable()))
    with pytest.raises(TypeError, match="can_handle"):
        register_formatter(cast("ValueFormatter", FormatIsNotCallable()))


def test_pushing_something_that_is_not_a_formatter_is_refused() -> None:
    with pytest.raises(TypeError, match="can_handle"):
        push_formatters((cast("ValueFormatter", object()),))


# ---------------------------------------------------------------------------
# It never raises
# ---------------------------------------------------------------------------
def test_a_formatter_whose_can_handle_raises_is_skipped() -> None:
    with scoped(ExplodesOnClaim()):
        assert format_value(Order(1, 2)) == "<Order>"


def test_a_formatter_whose_format_raises_is_skipped() -> None:
    with scoped(ExplodesOnFormat()):
        assert format_value(Order(1, 2)) == "<Order>"


def test_a_formatter_that_returns_a_non_string_is_skipped() -> None:
    """Not coerced: ``str()`` of the wrong object is a plausible-looking lie."""
    with scoped(cast("ValueFormatter", ReturnsANonString())):
        assert format_value(Order(1, 2)) == "<Order>"


def test_a_broken_formatter_lets_a_working_one_claim_the_value() -> None:
    """Skipped, not fatal: the rest of the registry still gets asked."""
    with scoped(ExplodesOnClaim(), ExplodesOnFormat(), Fixed(Order, "rendered")):
        assert format_value(Order(1, 2)) == "rendered"


def test_a_value_whose_repr_raises_is_named_by_its_type() -> None:
    assert format_value(Hostile()) == "<Hostile with an unusable __repr__>"


def test_a_value_whose_type_will_not_give_up_its_name_still_renders() -> None:
    """The last resort, and it is reachable: a metaclass can block ``__name__``."""
    assert format_value(Unnameable()) == "<unrenderable value>"


def test_a_formatter_that_explodes_leaves_no_marker_behind() -> None:
    """A leaked marker would make the *next* message claim a circular reference.

    Which is why the second call is the assertion: the same object, rendered
    again, has to come out the same way.
    """
    order = Order(1, 2)
    with scoped(ExplodesOnFormat()):
        assert format_value(order) == "<Order>"
        assert format_value(order) == "<Order>"


def test_a_formatter_that_throws_past_the_safety_net_releases_its_marker() -> None:
    """The net catches ``Exception``; anything else is somebody's shutdown signal.

    It goes through, which is the point -- and the ``finally`` is what stops it
    poisoning every later message with a circular reference that is not there.
    """
    order = Order(7, 42)
    with scoped(Interrupts()), pytest.raises(Abort):
        format_value(order)
    assert format_value(order) == "<Order>"


# ---------------------------------------------------------------------------
# Recursion
# ---------------------------------------------------------------------------
def test_a_formatter_can_render_its_parts_through_the_registry() -> None:
    """The reason recursion is supported at all."""
    with scoped(IterableFormatter(list), ORDER_FORMATTER):
        assert format_value([Order(7, 42)]) == "list[Order(identifier=7, total=42)]"


def test_a_self_referential_structure_renders_once() -> None:
    """``a = []; a.append(a)``: the case that would otherwise never come back."""
    looping: list[object] = []
    looping.append(looping)
    with scoped(IterableFormatter(list)):
        assert format_value(looping) == "list[<circular reference>]"
        # Again, to prove the marker is released rather than accumulated.
        assert format_value(looping) == "list[<circular reference>]"
    assert format_value(looping) == "[[...]]"


def test_nesting_stops_at_the_depth_cap() -> None:
    """Bounded like everything else in a message: five levels deep, four are shown."""
    with scoped(IterableFormatter(list)):
        assert format_value([[[[["x"]]]]]) == "list[list[list[list[...]]]]"


# ---------------------------------------------------------------------------
# IterableFormatter
# ---------------------------------------------------------------------------
def test_an_iterable_renders_as_its_items_under_its_type_name() -> None:
    with scoped(IterableFormatter(Feed)):
        assert format_value(Feed(1, 2, 3)) == "Feed[1, 2, 3]"


def test_a_long_iterable_is_truncated_with_a_count_of_what_was_left_out() -> None:
    with scoped(IterableFormatter(list)):
        assert format_value(list(range(13))) == ("list[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, ... (3 more)]")


def test_max_items_sets_the_cap() -> None:
    with scoped(IterableFormatter(list, max_items=2)):
        assert format_value([1, 2, 3, 4]) == "list[1, 2, ... (2 more)]"


def test_an_iterable_with_no_length_says_more_without_a_count() -> None:
    """Draining an iterator to produce a number would consume what is being shown."""
    with scoped(IterableFormatter(Feed, max_items=2)):
        assert format_value(Feed(1, 2, 3, 4)) == "Feed[1, 2, ... (more)]"


def test_an_iterable_subclass_is_claimed_and_named_as_itself() -> None:
    """The heading is the *runtime* type, exactly as for ``ObjectFormatter``."""
    with scoped(IterableFormatter(list)):
        assert format_value(Basket([1, 2])) == "Basket[1, 2]"


def test_a_broken_length_costs_the_count_and_not_the_rendering() -> None:
    """The count is a suffix. Losing it must not lose the items already rendered."""
    with scoped(IterableFormatter(Unmeasurable, max_items=2)):
        assert format_value(Unmeasurable()) == "Unmeasurable[0, 1, ... (more)]"


def test_a_claimed_type_that_is_not_iterable_is_declined() -> None:
    """A formatter that knows it cannot help says so, instead of raising."""
    formatter = IterableFormatter(Sealed)
    assert formatter.can_handle(Sealed()) is False
    with scoped(formatter):
        assert format_value(Sealed()).startswith("<")


def test_an_iterable_formatter_needs_a_type_and_a_usable_cap() -> None:
    with pytest.raises(ValueError, match="at least one type"):
        IterableFormatter()
    with pytest.raises(ValueError, match="max_items"):
        IterableFormatter(list, max_items=0)


def test_an_iterable_formatter_refuses_something_that_is_not_a_class() -> None:
    """``isinstance`` would raise, and rendering swallows that -- so it is caught here.

    It is worse than merely useless: ``isinstance`` walks the tuple left to right,
    so ``IterableFormatter(list, "tuple")`` works until the day it is handed
    something that is not a list.
    """
    with pytest.raises(TypeError, match="needs a class"):
        IterableFormatter(cast("type", "list"))
    with pytest.raises(TypeError, match="needs a class"):
        IterableFormatter(list, cast("type", "tuple"))


# ---------------------------------------------------------------------------
# ObjectFormatter
# ---------------------------------------------------------------------------
def test_an_object_renders_as_the_attributes_it_was_given() -> None:
    with scoped(ORDER_FORMATTER):
        assert format_value(Order(7, 42)) == "Order(identifier=7, total=42)"


def test_a_subclass_is_claimed_and_named_as_itself() -> None:
    """Unlike ``register``, which keys on the exact type; the registries differ."""
    with scoped(ORDER_FORMATTER):
        assert format_value(RushOrder(7, 42)) == "RushOrder(identifier=7, total=42)"


def test_an_unreadable_attribute_does_not_sink_the_rendering() -> None:
    """A failing test is often holding a half-built object; show the rest of it."""
    with scoped(ObjectFormatter(Order, "identifier", "missing")):
        assert format_value(Order(7, 42)) == "Order(identifier=7, missing=<unreadable>)"


def test_attribute_values_go_through_the_registry() -> None:
    with scoped(ObjectFormatter(Opaque, "identifier"), Fixed(int, "<a number>")):
        assert format_value(Opaque(7)) == "Opaque(identifier=<a number>)"


def test_an_object_formatter_needs_at_least_one_attribute() -> None:
    """``Order()`` would say less than ``repr`` does; report it at import."""
    with pytest.raises(ValueError, match="at least one attribute"):
        ObjectFormatter(Order)


def test_an_object_formatter_refuses_a_non_class_or_a_non_name() -> None:
    """Same silent death as above: ``getattr(value, 1)`` raises, rendering shrugs."""
    with pytest.raises(TypeError, match="needs a class"):
        ObjectFormatter(cast("type", "Order"), "identifier")
    with pytest.raises(TypeError, match="attribute names"):
        ObjectFormatter(Order, cast("str", 1))


# ---------------------------------------------------------------------------
# Scoping is per context
# ---------------------------------------------------------------------------
def test_scoped_formatters_are_isolated_between_threads() -> None:
    """ContextVar, not global state: one thread's rendering never reaches another's."""

    def scoped_worker() -> str:
        with scoped(Fixed(Order, "scoped")):
            return format_value(Order(1, 2))

    def plain_worker() -> str:
        return format_value(Order(1, 2))

    with ThreadPoolExecutor(max_workers=4) as pool:
        scoped_results = [pool.submit(scoped_worker) for _ in range(4)]
        plain_results = [pool.submit(plain_worker) for _ in range(4)]
        assert [future.result() for future in scoped_results] == ["scoped"] * 4
        assert [future.result() for future in plain_results] == ["<Order>"] * 4


def test_the_recursion_guard_is_isolated_between_threads() -> None:
    """Shared guard state would invent a cycle where there is none.

    Two threads render the *same* object at once. If the in-progress markers were
    a module global rather than a ``ContextVar``, the second thread would find the
    first thread's marker and print ``<circular reference>`` for a value that
    is not circular -- a wrong message, only under parallelism, in the middle of
    somebody else's failing test.
    """
    order = Order(7, 42)
    entered = threading.Event()
    release = threading.Event()

    class Holds:
        """Stays inside ``format`` -- and so inside the guard -- until released."""

        __slots__ = ()

        def can_handle(self, value: object, /) -> bool:
            return isinstance(value, Order)

        def format(self, value: object, /) -> str:
            entered.set()
            release.wait(timeout=5)
            return "held"

    def holder() -> str:
        with scoped(Holds()):
            return format_value(order)

    def bystander() -> str:
        assert entered.wait(timeout=5)
        with scoped(Fixed(Order, "bystander")):
            return format_value(order)

    with ThreadPoolExecutor(max_workers=2) as pool:
        held = pool.submit(holder)
        watching = pool.submit(bystander)
        try:
            seen = watching.result(timeout=5)
        finally:
            release.set()
        assert held.result(timeout=5) == "held"
    assert seen == "bystander"


def test_scoped_formatters_are_isolated_between_concurrent_tasks() -> None:
    """Same guarantee under asyncio, where a task copies the context."""

    async def scoped_task() -> str:
        with scoped(Fixed(Order, "scoped")):
            await asyncio.sleep(0)
            return format_value(Order(1, 2))

    async def plain_task() -> str:
        await asyncio.sleep(0)
        return format_value(Order(1, 2))

    async def main() -> list[str]:
        return list(await asyncio.gather(scoped_task(), plain_task(), scoped_task()))

    assert asyncio.run(main()) == ["scoped", "<Order>", "scoped"]


def test_the_global_registry_refuses_to_grow_without_bound() -> None:
    """The one piece of state a public call can grow forever.

    The identity check catches a module imported twice. It cannot catch a fixture
    building a fresh ``ObjectFormatter(Order, "id")`` per test, because two
    instances configured alike are genuinely two objects -- and that is exactly
    the shape ``register_formatter``'s docstring warns about.

    The cost is not only memory: every registration lengthens the list
    ``format_value`` walks for every value in every failure message.
    """
    registry: list[object] = getattr(_formatters, "_GLOBAL")  # noqa: B009
    bound: int = getattr(_formatters, "_MAX_GLOBAL")  # noqa: B009
    kept = list(registry)
    try:
        registry.clear()
        for _ in range(bound):
            register_formatter(ObjectFormatter(_Order, "identifier"))
        with pytest.raises(ValueError, match="running per test rather than once"):
            register_formatter(ObjectFormatter(_Order, "identifier"))
        assert len(registry) == bound
    finally:
        registry.clear()
        registry.extend(kept)


class _Order:
    """A subject for the registry test, and nothing else."""

    __slots__ = ("identifier",)

    def __init__(self, identifier: int) -> None:
        self.identifier = identifier
