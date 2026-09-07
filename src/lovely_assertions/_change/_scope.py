"""Sampling a value either side of a block, and saying what moved.

The block form exists because the claim is about an *action*: the value before,
the action, the value after. Written as three statements the ordering is a
discipline -- sample first, act, compare -- and a test that samples in the wrong
order passes for the wrong reason. ``with`` makes the ordering structural.

**What this buys over writing the subtraction by hand.** ``expect(count() -
before).is_equal_to(1)`` already names its subject and already prints a sentence.
What it cannot print is the *before* value, and it cannot tell apart the two
failures a reader most needs separated: an action that did nothing, and one that
did the wrong amount. Both come back as ``but was 2``. Here they are two
sentences.

Nothing is sampled and nothing is compared until the block ends, so a passing
block costs two calls to the caller's own probe and one comparison.
"""

from typing import TYPE_CHECKING, Any, Self, override

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Warned about when a scope is built and never entered. See :meth:`Change.__del__`.
_NEVER_ENTERED = (
    "expect_change(...) asserted nothing: it was never used as a `with` block. The probe was "
)


#: Which narrowing a scope was given, if any. A small string rather than a
#: rendered phrase, because the phrase is a message and a message built by ``to``
#: or ``by`` would be paid for by every block that passes.
NOT_NARROWED = ""
NARROWED_TO = "to"
NARROWED_BY = "by"


#: The ``but ...`` half for a probe that hands back the very object it handed back
#: before. Nothing could have been observed, and the honest answer is to say so
#: rather than to report one value standing in for both samples at once. Written
#: as the middle of the sentence, like every other expectation in the library.
_SAME_CONTAINER = (
    ", but the probe returned the same {kind} both times, so nothing could be observed"
    " -- sample a value instead, as in lambda: list(...) or lambda: len(...)"
)


class ChangeBase[V]:
    """The sampling, the verdict and the reporting -- everything both scopes share.

    A context manager, and complete on its own: entering and leaving it is the
    whole assertion. What the two scopes add on top is the narrowing each of them
    can honestly offer, which is why that lives on them and not here.

    Generic over what the probe returns, so a continuation added below takes the
    type the probe actually produces rather than ``object``.

    **The failure is reported through an ordinary subject**, built here and
    thrown away, rather than by rendering a message directly. That is what gives
    these assertions the subject's recovered name, the soft scope they were
    written inside, and the ``because`` clause -- none of which this class
    implements, and all of which live in the one place a failure is assembled.
    """

    __slots__ = ("_because", "_before", "_entered", "_must_move", "_narrowed", "_probe", "_wanted")

    def __init__(self, probe: "Callable[[], V]", because: str, *, must_move: bool) -> None:
        self._probe: Callable[[], V] = probe
        self._because: str = because
        #: Whether the value is required to move or required to hold still. The
        #: two entry points differ in this and in nothing else.
        self._must_move: bool = must_move
        #: What the block was asked for beyond "it moved": a destination from
        #: `to`, an amount from `by`. Unset until one of them is called, which is
        #: what tells the two apart from the plain form.
        self._wanted: object = _NOTHING_MORE
        #: Which narrowing was asked for, so the wording can be worked out on the
        #: failure path. A flag and not the rendered phrase: rendering it in
        #: `to` or `by` would build a message on the passing path, which is the
        #: one thing an assertion in this library may never do.
        self._narrowed: str = NOT_NARROWED
        self._entered: bool = False

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._probe!r})"

    def __del__(self) -> None:
        """Warn about a scope that was built and never entered.

        ``expect_change(count).by(1)`` without a ``with`` runs, returns and
        asserts nothing -- and unlike the other half-written chain in this library
        it reads as a *finished* sentence, so a reviewer's eye slides over it.
        That makes it worth reporting even though it can only be noticed late.

        The same shape, and the same reasoning, as the unfinished
        ``is_within(...)`` chain: raising is impossible at the moment the call
        returns, because at that moment it is a perfectly good scope about to be
        entered. So it is reported the way CPython reports an un-awaited
        coroutine -- a ``RuntimeWarning`` from the finaliser, arriving whenever
        the collector gets there, carrying the probe so the reader can tell which
        one it was. Late is enough: under ``-W error`` a silently-green test still
        goes red.
        """
        if self._entered:
            return
        import warnings  # noqa: PLC0415  (imported here, so only an unused scope pays)

        warnings.warn(_NEVER_ENTERED + repr(self._probe), RuntimeWarning, stacklevel=2)

    def __enter__(self) -> Self:
        """Take the *before* sample. No inspection of anything but the probe."""
        self._entered = True
        self._before: V = self._probe()
        return self

    def __exit__(
        self,
        exception_type: "type[BaseException] | None",
        exception: "BaseException | None",
        traceback: "TracebackType | None",
        /,
    ) -> None:
        """Take the *after* sample and report, unless the block is already failing.

        An exception on its way out of the block is the finding; sampling again
        and reporting a second one on top would bury it, and the second would be
        about a block that never finished.
        """
        if exception_type is not None:
            return
        after = self._probe()
        self._report(self._before, after)

    def _report(self, before: V, after: V, /) -> None:
        """Decide, and say what happened. **Failure path only** past the verdict."""
        if self._nothing_observable(before, after):
            self._fail(
                after,
                self._expectation() + _SAME_CONTAINER.format(kind=type(after).__name__),
            )
            return
        if self._holds(before, after):
            return
        self._fail(after, self._how_it_moved(before, after))

    def _holds(self, before: V, after: V, /) -> bool:
        """Whether the claim this scope was built with is true."""
        if self._narrowed:
            return self._satisfied(before, after)
        changed = bool(before != after)
        return changed is self._must_move

    def _satisfied(self, before: V, after: V, /) -> bool:
        """Whether the narrowed claim holds. Overridden where the claim is an amount."""
        del before
        return bool(after == self._wanted)

    def _nothing_observable(self, before: V, after: V, /) -> bool:
        """Whether the probe handed back one mutable object twice.

        The defect this exists for is quiet and reads as a bug in this library
        rather than in the test. A probe like ``lambda: order.items`` returns *the
        list itself*, so a block that appends to it holds one object as both
        samples. ``before != after`` is then ``False`` however much the block did,
        and ``expect_change`` reports ``but it stayed at ['widget']`` -- naming the
        changed value in the same breath as denying it changed.

        **Both entry points are refused, and that is deliberate.** The engine
        cannot see a change here; it also cannot see the absence of one. So
        ``expect_no_change`` is not passing because nothing happened, it is
        passing because it looked at one object twice -- an assertion that cannot
        fail, which is the outcome this library exists to refuse. The cost is
        that a correct ``expect_no_change(lambda: config.items)`` over a genuinely
        untouched list is now refused too; the message says exactly how to make it
        an assertion that checks something, and a claim nobody can verify is not
        worth keeping green.

        Identity alone would not do: two reads of an immutable value are
        legitimately one object, and a small ``int`` or an interned string always
        is. What separates them is mutability, and the cheapest honest proxy is
        hashability -- ``list``, ``dict`` and ``set`` are unhashable, and the
        values that are legitimately identical across two reads are not. A frozen
        or hashable container slips through, which is the safe direction: it
        cannot have been mutated in place.

        Nothing is imported and nothing is copied. ``hash`` allocates nothing and
        is reached only for a pair that is literally one object.
        """
        if before is not after:
            return False
        try:
            _ = hash(after)
        except TypeError:
            return True
        return False

    def _how_it_moved(self, before: V, after: V, /) -> str:
        """The ``but ...`` half. **Failure path only.**

        Two sentences rather than one, because the two failures behind them are
        different bugs: an action that did nothing, and an action that did the
        wrong thing. A single "but was X" would hide which.
        """
        if before is after or before == after:
            return self._expectation() + ", but it did not move from " + format_value(before)
        return (
            self._expectation()
            + ", but it went from "
            + format_value(before)
            + " to "
            + format_value(after)
            + self._distance(before, after)
        )

    def _distance(self, before: V, after: V, /) -> str:
        """How far it went, where that can be said. **Failure path only.**

        Empty here: a value that merely moved has no distance worth a number, and
        two strings do not subtract. :class:`~lovely_assertions.NumericChange`
        fills it in, which is the whole of what the amount half adds to a message.
        """
        del before, after
        return ""

    def _expectation(self) -> str:
        """The ``to ...`` half. **Failure path only.**

        Worked out here rather than stored by ``to`` or ``by``, because those run
        on the path where the block passes and a message built there is paid for
        by every test that never fails.
        """
        if self._narrowed:
            return self._narrowing()
        return "to change" if self._must_move else "not to change"

    def _narrowing(self) -> str:
        """The wording for the narrowed claim. **Failure path only.**

        Only ``to`` reaches this one; the amount half overrides it, because the
        wording for an amount reads the sign and this class knows nothing about
        arithmetic.
        """
        return "to change to " + format_value(self._wanted)

    def _fail(self, subject: V, expectation: str, /) -> None:
        """Report through an ordinary subject. **Failure path only.**

        The subject is built here and dropped: what is wanted from it is the one
        place a failure is rendered and routed, which is what carries the name
        recovered from the ``with`` header, the soft scope in force, and
        ``because``. Rendering a message here instead would put this family
        outside every one of them -- including the guard that watches assertions
        fail, which would then never see this one fail at all.
        """
        # Reported through a subject rather than by rendering here, so that this
        # family gets the one place a failure is assembled -- and with it the
        # recovered name, the soft scope and `because`. The same deliberate reach
        # across two cooperating objects that `WithinDelta` makes into its parent.
        Expect[Any](subject)._fail(expectation, self._because)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]


class _NothingMore:
    """The absence of a narrowed claim, told apart from ``None`` as a destination.

    ``None`` is a value a probe can legitimately return and a destination
    ``.to(None)`` can legitimately ask for, so it cannot double as "nothing was
    asked beyond movement".
    """

    __slots__ = ()

    @override
    def __repr__(self) -> str:
        return "<no further claim>"


#: The unset value of :attr:`Change._wanted`. One instance, compared by identity.
_NOTHING_MORE = _NothingMore()


class Change[V](ChangeBase[V]):
    """What :func:`~lovely_assertions.expect_change` hands back.

    The base, plus the one narrowing that makes sense for a value that moved:
    where it ended up.
    """

    __slots__ = ()

    def to(self, value: V, /) -> Self:
        """Narrow the claim to where the value ends up.

            with expect_change(lambda: order.state).to("shipped"):
                ship(order)

        Says both things: the value moved, *and* it moved to this. A value that
        was already ``"shipped"`` fails, which is the point -- an action that did
        nothing leaves the destination looking correct, and this is the reading
        that catches it.
        """
        self._wanted = value
        self._narrowed = NARROWED_TO
        return self


class NoChange[V](ChangeBase[V]):
    """What :func:`~lovely_assertions.expect_no_change` hands back.

    The base and nothing else, deliberately. ``.to(...)`` and ``.by(...)`` both
    narrow a claim that something *moved*, and this scope claims the opposite;
    offering either would put two contradictory readings of one block on one
    object. A separate type rather than a runtime refusal, so that a checker says
    so at the call site -- the same rule that keeps ``is_positive`` off a ``str``
    subject.
    """

    __slots__ = ()
