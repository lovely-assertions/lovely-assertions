"""Asserting about what an action did, rather than about a value.

Every other assertion in this library is about a value that already exists.
These two are about a *difference*: the value before an action, the action, the
value after it.

    with expect_change(Order.count).by(1):
        place(order)

Written by hand that is three statements, and their order is a discipline nobody
checks::

    before = Order.count()
    place(order)
    expect(Order.count() - before).is_equal_to(1)

Sample in the wrong order and the test passes for the wrong reason. The block
makes the ordering structural: there is no way to write the samples the wrong way
round.

**The message is the rest of the case.** The hand-written form prints
``Expected Order.count() - before to equal 1, but was 2`` -- which cannot say what
the value started at, and gives the same sentence to two different bugs. An
action that did nothing and an action that did twice too much are the two
failures a reader most needs separated:

    Expected Order.count to increase by 1, but it did not move from 3.
    Expected Order.count to increase by 1, but it went from 3 to 5 (a change of 2).

Three claims, in order of how much they say. ``with expect_change(probe):``
asserts the value moved at all; ``.to(value)`` asserts where it landed;
``.by(amount)`` asserts how far it went. ``expect_no_change(probe)`` is the
fourth and asserts the opposite of the first.

**The probe is a callable, always.** It is called twice, once either side of the
block, so a value would be sampled once and never re-read. ``Order.count`` and
``lambda: order.state`` are both probes; ``order.state`` is not, and the type
checker says so.

Two traps this family has that no other assertion does, both handled where they
arise rather than left for the reader: a probe that hands back the same mutable
object twice, so that nothing can be observed at all
(:meth:`~lovely_assertions._change._scope.Change._nothing_observable`), and a
scope that is built and never entered, which asserts nothing while reading as a
finished sentence (:meth:`~lovely_assertions._change._scope.Change.__del__`).

Two files: the scope and its verdict, and the amount half that only some probes
are offered.
"""

from typing import TYPE_CHECKING, Any, overload

from lovely_assertions._change._numeric import NumericChange
from lovely_assertions._change._scope import Change, NoChange
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime, timedelta
    from decimal import Decimal
    from fractions import Fraction

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["Change", "NoChange", "NumericChange", "expect_change", "expect_no_change"]


# The overload chain decides one thing: which probes are offered `.by(...)`.
#
# `bool` leads it, for the reason `bool` leads the dispatch table in
# `_subjects`: a `bool` is an `int`, so anything below would claim it, and a flag
# that went from False to True did not "increase by 1".
#
# It is also the only row either checker objects to. The concrete rows below do
# not overlap the generic one at the bottom, because the keyword argument keeps
# their signatures apart; only `bool` genuinely shadows `int` and `float`, and
# both checkers say so, so both suppressions sit on that row and nowhere else.
#
# `datetime` is the row worth reading twice: two instants differ by a
# `timedelta`, so its delta type is not its value type.
#
# `datetime`, `Decimal` and `Fraction` are named under `TYPE_CHECKING` and quoted
# here, so that importing this package imports none of the three -- the same
# arrangement, and the same reason, as the dispatch overloads.
@overload
# deliberate: `bool` leads the chain, and a `bool` is an `int`
def expect_change(  # type: ignore[overload-overlap]  # pyright: ignore[reportOverlappingOverload]
    probe: "Callable[[], bool]", /, *, because: str = ...
) -> "Change[bool]": ...
@overload
def expect_change(
    probe: "Callable[[], int]", /, *, because: str = ...
) -> "NumericChange[int, int]": ...
@overload
def expect_change(
    probe: "Callable[[], float]", /, *, because: str = ...
) -> "NumericChange[float, float]": ...
@overload
def expect_change(
    probe: "Callable[[], Decimal]", /, *, because: str = ...
) -> "NumericChange[Decimal, Decimal]": ...
@overload
def expect_change(
    probe: "Callable[[], Fraction]", /, *, because: str = ...
) -> "NumericChange[Fraction, Fraction]": ...
@overload
def expect_change(
    probe: "Callable[[], datetime]", /, *, because: str = ...
) -> "NumericChange[datetime, timedelta]": ...
@overload
def expect_change(
    probe: "Callable[[], timedelta]", /, *, because: str = ...
) -> "NumericChange[timedelta, timedelta]": ...
@overload
def expect_change[V](probe: "Callable[[], V]", /, *, because: str = ...) -> "Change[V]": ...
def expect_change[V](probe: "Callable[[], V]", /, *, because: str = "") -> "Change[V]":
    """Assert the block moves the value ``probe`` reads.

        with expect_change(Order.count).by(1):
            place(order)

        with expect_change(lambda: order.state).to("shipped"):
            ship(order)

    Complete on its own -- ``with expect_change(probe):`` asserts the value moved,
    whatever it moved to. Continue it with ``.to(...)`` for a destination, or with
    ``.by(...)`` for an amount where the probe returns something that subtracts.

    ``probe`` is called once before the block and once after, so it must be a
    callable and not a value. It is never called anywhere else, and a passing
    block costs those two calls and one comparison.

    Reports nothing when the block raises: that exception is the finding, and a
    second one about a block that never finished would bury it.
    """
    # Always the numeric scope at runtime: the delta type is a static question,
    # and one class means one code path to test. The overloads above are what
    # decide whether a caller is *offered* `.by(...)`. Annotated rather than
    # subscripted at the call site, which would allocate.
    scope: NumericChange[V, Any] = NumericChange(probe, because, must_move=True)
    return scope


def expect_no_change[V](probe: "Callable[[], V]", /, *, because: str = "") -> "NoChange[V]":
    """Assert the block leaves the value ``probe`` reads exactly where it was.

        with expect_no_change(lambda: account.balance, because="a retry must not charge twice"):
            charge(idempotency_key)

    The assertion a test means when the point is that work was *not* done. It has
    no ``.to`` and no ``.by``: there is no destination and no amount in "it did
    not move", and offering either would be offering a claim that contradicts the
    one already made.

    Takes the same probe as :func:`expect_change` and calls it the same twice.
    """
    return NoChange(probe, because, must_move=False)
