"""Assertions for sequences -- the half of the collection catalogue that order makes meaningful.

The richest catalogue in the library, and the one where the message engine earns
its keep. A collection assertion that only reports *false* leaves the reader to
diff two lists by eye, so every failure here names what was expected, what was
actually there, and -- wherever there is one -- the exact position of the
disagreement.

What lives here is what **order** makes meaningful: ordered equality, prefixes and
suffixes, indexing, "in this order", sortedness. Everything a collection can
answer without an order -- length, membership, set relations, per-item
inspections -- lives one class up in
:class:`~lovely_assertions._collection.CollectionExpect` and is inherited whole.
The two positional message hooks are overridden here, which is what keeps the
inherited half saying ``at index 3`` when the subject really has an index 3.

Four conventions run through the module.

**An assertion that cannot tell must not answer "no problem".** Both halves of
the catalogue compare, and both have a value that makes a comparison answer
false without meaning it: a NaN, which is equal to nothing and ordered against
nothing, and a type with a hostile ``__eq__``. Left alone, that silence reads as
agreement and the assertion passes vacuously -- the tell being an assertion and
its negation *both* passing on one subject. So equality here is Python's own
membership rule, ``x is y or x == y``, spelled inline at every comparison site
(the rule :func:`~lovely_assertions._collection._count_equal` states, so that
``contains`` and ``contains_in_order`` cannot disagree about what a list holds),
and sortedness asks whether a pair is definitely *in* order -- strictly ordered
or equal -- rather than definitely out of it, so an unordered neighbour is
reported at the index where it breaks the order instead of being waved through
by both ``is_sorted`` and ``is_sorted_descending``. The inclusive question is
built from ``<`` and ``==`` rather than ``<=``, so that an element or a ``key=``
result still needs no operator beyond the one ``sorted()`` needs. The one
deliberate exception is :meth:`SequenceExpect.equals_approximately`, where a NaN
is close to nothing -- itself included -- because that is the contract
``is_close_to`` states and it is a claim about distance, not about which items a
sequence holds.

**Collections in messages go through :func:`~lovely_assertions._collection.render_items`**,
which truncates long ones. A message that pastes ten thousand elements hides the
finding instead of explaining it.

**Comparisons are element-wise**, never ``==`` between the collections
themselves: the subject type is ``Sequence``, so a ``list`` is compared against
the ``tuple`` with the same contents on its merits.

**Element-valued parameters are typed ``E``**, not ``object``. ``expect(names)``
should refuse ``contains(3)`` when ``names`` is a ``Sequence[str]`` -- an
assertion that can only ever fail is a bug in the test, and catching it before
the suite runs is the point of the typed surface.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Protocol, Self, cast, override

from lovely_assertions._collection import CollectionExpect, render_items
from lovely_assertions._core import Found, collect_failures

# `collect_failures` lives in `_core` because `Expect.satisfies` needs it too, and
# `render_items` in `_collection` because both halves of the split render the same
# way. Neither carries a leading underscore, precisely so that these imports are
# ordinary ones rather than suppressions -- both modules are private, so nothing
# leaks to the public surface either way.
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._numeric import reject_unusable_tolerance
from lovely_assertions._ordered import is_nan
from lovely_assertions._text import count_of

if TYPE_CHECKING:
    from collections.abc import Callable, Sized

    from lovely_assertions._occurrence import Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["SequenceExpect"]


class _Ordered(Protocol):
    """Anything ``<`` accepts -- the requirement the ordering assertions have.

    ``_typeshed.SupportsRichComparison`` is the obvious candidate and does not
    work: it is a *union* of the two half-protocols, and neither checker will
    compare one member of that union against the other.

    ``<`` alone, and it stays that way: unlike
    :class:`lovely_assertions._ordered.Ordered`, which names all four operators
    because ``is_greater_than_or_equal_to`` is literally spelled ``>=``, nothing
    here needs more than the one operator ``sorted()`` itself needs.
    :func:`_first_out_of_order` asks its inclusive question out of ``<`` and
    ``==`` for exactly that reason. This protocol is part of the published
    surface -- it is what every ``key=`` parameter in the ordering assertions
    promises -- so widening it would start raising ``TypeError`` on a user type
    that defines only ``__lt__``, which is perfectly sortable.
    """

    __slots__ = ()

    def __lt__(self, other: Any, /) -> bool:  # noqa: ANN401  (the operand is the caller's business)
        ...


#: Guard for the variadic assertions. A call with nothing to look for either
#: passes whatever the subject is -- a test that asserts nothing -- or could never
#: pass at all. Both are bugs in the test rather than findings about the subject,
#: so they are raised, not reported. The variadics on
#: :class:`~lovely_assertions._string.StringExpect` raise for the same reason.
_NEEDS_VALUES = "at least one value to look for is required"


class SequenceExpect[E](CollectionExpect[E, Sequence[E]]):
    """Assertions for sequences, parameterised by element type.

    The subject is a ``Sequence``, not a ``list``: indexing, ``len`` and repeated
    iteration are fair game, mutation is not, and one subject class covers lists,
    tuples and anything else that behaves like a sequence.

    Everything an unordered collection can also answer is inherited from
    :class:`~lovely_assertions._collection.CollectionExpect`; what is declared
    here is what an order makes meaningful.
    """

    __slots__ = ()

    # -- message positions -------------------------------------------------
    #
    # The two hooks the inherited catalogue reports positions through. Failure
    # path only, and no f-strings: a failure message is assembled in exactly one
    # place, inside `_fail`, and these only hand it a fragment.
    @override
    def _position(self, index: int, /) -> str:
        """The `` at index N`` clause that follows a rendered item."""
        return " at index " + str(index)

    @override
    def _finding_tag(self, index: int, /) -> str:
        """The ``at index N: `` tag in front of one nested finding."""
        return "at index " + str(index) + ": "

    # -- ordered equality --------------------------------------------------
    def equals_sequence(self, other: "Sequence[E]", /, *, because: str = "") -> Self:
        """Assert the sequence holds the same items as ``other``, in the same order.

        Compared item by item rather than with ``==`` on the collections, so a
        list equals the tuple with the same contents. The failure names the first
        index that disagrees -- the one thing ``==`` cannot tell you -- and adds
        the lengths when those differ too.

        Two items count as the same when ``item is expected or item == expected``,
        Python's own membership rule, so a sequence holding a NaN equals itself
        while two sequences holding *different* NaNs do not. Lengths must match:
        a subject that merely opens with ``other`` fails here, and
        :meth:`starts_with_sequence` is the assertion for that claim.
        """
        subject = self._subject
        difference = _first_difference(subject, other)
        if difference is None:
            if len(subject) == len(other):
                return self
            return self._fail(
                f"to equal {render_items(other)},"
                f" but had {count_of(len(subject), 'item')}, not {len(other)}",
                because,
            )
        return self._fail(
            f"to equal {render_items(other)}, but differed at index {difference}"
            f" ({format_value(subject[difference])} instead of {format_value(other[difference])})"
            + _length_note(subject, other),
            because,
        )

    def does_not_equal_sequence(self, other: "Sequence[E]", /, *, because: str = "") -> Self:
        """Assert the sequence differs from ``other`` in length or in some item.

        The negation of :meth:`equals_sequence`, item comparison included, so the
        two can never both pass. A difference in length satisfies it on its own,
        as does a single item that does not match.
        """
        subject = self._subject
        if len(subject) != len(other) or _first_difference(subject, other) is not None:
            return self
        return self._fail(f"not to equal {render_items(other)}, but it did", because)

    def equals_approximately(
        self, other: "Sequence[float]", /, *, tol: float, because: str = ""
    ) -> Self:
        """Assert the sequence matches ``other`` item by item, each within ``tol``.

        The element type is deliberately not constrained: ``SequenceExpect[E]``
        is invariant in ``E``, so a self-type of ``SequenceExpect[float]`` would
        lock out ``SequenceExpect[int]`` -- the common case. The items have to
        support subtraction and ``abs``; anything else raises ``TypeError``,
        which is a bug in the test rather than a finding about the subject.

        ``tol`` is an absolute tolerance and the comparison is inclusive, the
        same contract ``NumericExpect.is_close_to`` states: equal items match at
        any tolerance (so two infinities do), a NaN matches nothing -- itself
        included -- and a negative or NaN ``tol`` raises ``ValueError`` instead
        of quietly making the assertion impossible or vacuous.
        """
        reject_unusable_tolerance(tol, "tolerance")
        subject = self._subject
        difference = _first_difference_beyond(subject, other, tol)
        if difference is None:
            if len(subject) == len(other):
                return self
            return self._fail(
                f"to equal {render_items(other)} within {tol},"
                f" but had {count_of(len(subject), 'item')}, not {len(other)}",
                because,
            )
        return self._fail(
            f"to equal {render_items(other)} within {tol}, but differed at index {difference}"
            f" ({format_value(subject[difference])} instead of {format_value(other[difference])})"
            + _nan_note(subject[difference], other[difference])
            + _length_note(subject, other),
            because,
        )

    def starts_with_sequence(self, prefix: "Sequence[E]", /, *, because: str = "") -> Self:
        """Assert the sequence opens with ``prefix``, item for item.

        Extra items after the prefix are fine -- that is the whole difference from
        :meth:`equals_sequence`. An empty ``prefix`` passes on any sequence, and a
        ``prefix`` longer than the subject fails even when every item they share
        matches; the message distinguishes the two, naming either the first
        differing index or the length that ran out. Items are compared with the
        same ``item is expected or item == expected`` rule
        :meth:`equals_sequence` uses.
        """
        subject = self._subject
        difference = _first_difference(subject, prefix)
        if difference is None:
            if len(prefix) <= len(subject):
                return self
            return self._fail(
                f"to start with {render_items(prefix)},"
                f" but only had {count_of(len(subject), 'item')}: {render_items(subject)}",
                because,
            )
        return self._fail(
            f"to start with {render_items(prefix)}, but differed at index {difference}"
            f" ({format_value(subject[difference])} instead of {format_value(prefix[difference])})",
            because,
        )

    def ends_with_sequence(self, suffix: "Sequence[E]", /, *, because: str = "") -> Self:
        """Assert the sequence closes with ``suffix``, item for item.

        The mirror of :meth:`starts_with_sequence`, walked from the other end:
        items before the suffix are fine, an empty ``suffix`` passes on any
        sequence, and a ``suffix`` longer than the subject fails. The failure
        reports the index *in the subject* where the two parted company, so it
        can be looked up directly rather than counted back from the end.
        """
        subject = self._subject
        offset = _first_difference_from_end(subject, suffix)
        if offset is None:
            if len(suffix) <= len(subject):
                return self
            return self._fail(
                f"to end with {render_items(suffix)},"
                f" but only had {count_of(len(subject), 'item')}: {render_items(subject)}",
                because,
            )
        return self._fail(
            f"to end with {render_items(suffix)}, but differed at index {len(subject) - offset}"
            f" ({format_value(subject[-offset])} instead of {format_value(suffix[-offset])})",
            because,
        )

    # -- element access ----------------------------------------------------
    def has_element_at(self, index: int, value: E, /, *, because: str = "") -> "Found[Self, E]":
        """Assert the item at ``index`` equals ``value``; continue with ``.which``.

        Negative indices count back from the end, as they do everywhere else in
        Python. An index outside the sequence is reported as a failure naming the
        length that was actually there, never raised as an ``IndexError`` -- an
        assertion answers, it does not blow up.

        ``found is value or found == value`` is Python's membership rule, applied
        here for the reason it is applied everywhere else in the module: the item
        the caller handed over is the item at that index even when it declines to
        equal itself.

        The continuation carries the item that was *stored*, so anything asserted
        through ``.which`` runs against the sequence's own object rather than the
        one passed in.
        """
        subject = self._subject
        count = len(subject)
        if -count <= index < count:
            found = subject[index]
            if found is value or found == value:
                return Found(self, found)
            return cast(
                "Found[Self, E]",
                self._fail_narrowing(
                    f"to have {format_value(value)} at index {index},"
                    f" but had {format_value(found)}: {render_items(subject)}",
                    because,
                ),
            )
        return cast(
            "Found[Self, E]",
            self._fail_narrowing(
                f"to have an item at index {index}, but only had {count}: {render_items(subject)}",
                because,
            ),
        )

    # -- containment -------------------------------------------------------
    @override
    def does_not_contain(
        self, item: E, /, *, occurrences: "Occurrence | None" = None, because: str = ""
    ) -> Self:
        """Assert the sequence does not hold ``item``, or not that many times.

        Overrides the inherited assertion for one word of the message: a sequence
        can say *where* it found the item, and ``.index`` is the one lookup an
        unordered collection cannot perform. The test itself is the inherited one,
        ``item in subject``, so the two cannot disagree about the answer.

        A count constraint has nothing to do with position, so that case is handed
        straight back to the collection subject rather than reimplemented here --
        two implementations of one rule is how they come to disagree.
        """
        if occurrences is not None:
            return super().does_not_contain(item, occurrences=occurrences, because=because)
        subject = self._subject
        if item not in subject:
            return self
        return self._fail(
            f"not to contain {format_value(item)}, but found it at index {subject.index(item)}:"
            f" {render_items(subject)}",
            because,
        )

    def contains_in_order(self, *items: E, because: str = "") -> Self:
        """Assert ``items`` all appear, in this order, not necessarily adjacent.

        A subsequence test: anything at all may sit between them, and each wanted
        item consumes a position of its own, so ``contains_in_order("a", "a")``
        needs two ``"a"`` in the subject. Matching is
        ``item is target or item == target``, the rule ``in`` itself applies, so
        this and :meth:`~lovely_assertions._collection.CollectionExpect.contains`
        cannot disagree about whether the sequence holds a value.

        The failure distinguishes an item that is missing entirely from one that
        is present but out of place. Raises ``ValueError`` when called with no
        items -- an assertion with nothing to look for cannot fail, which is a bug
        in the test rather than a finding. :meth:`contains_in_consecutive_order`
        is the strict form that forbids anything in between.
        """
        if not items:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        gap = _subsequence_gap(subject, items)
        if gap is None:
            return self
        if gap == 0:
            return self._fail(
                f"to contain {render_items(items)} in order,"
                f" but {format_value(items[0])} was missing from {render_items(subject)}",
                because,
            )
        return self._fail(
            f"to contain {render_items(items)} in order, but {format_value(items[gap])}"
            f" did not appear after {format_value(items[gap - 1])}: {render_items(subject)}",
            because,
        )

    def does_not_contain_in_order(self, *items: E, because: str = "") -> Self:
        """Assert ``items`` do not all appear in this order.

        The negation of :meth:`contains_in_order`, so one item missing or one
        arriving too early is enough; it does not ask for them to be absent.
        :meth:`does_not_contain_in_consecutive_order` is the weaker claim, which
        anything with a gap in it already satisfies. Raises ``ValueError`` when
        called with no items.
        """
        if not items:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if _subsequence_gap(subject, items) is not None:
            return self
        return self._fail(
            f"not to contain {render_items(items)} in order, but it did: {render_items(subject)}",
            because,
        )

    def contains_in_consecutive_order(self, *items: E, because: str = "") -> Self:
        """Assert ``items`` appear as an unbroken run, in this order.

        The run may start at any index; what it may not have is anything in
        between. That is the whole difference from :meth:`contains_in_order`, and
        the failure says which of the two happened -- the items were all there but
        interrupted, or they were not there in that order at all. Raises
        ``ValueError`` when called with no items.
        """
        if not items:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if _run_start(subject, items) is not None:
            return self
        gap = _subsequence_gap(subject, items)
        if gap is None:
            return self._fail(
                f"to contain {render_items(items)} in consecutive order,"
                f" but other items came between them: {render_items(subject)}",
                because,
            )
        return self._fail(
            f"to contain {render_items(items)} in consecutive order,"
            f" but {format_value(items[gap])} was not there in that order: {render_items(subject)}",
            because,
        )

    def does_not_contain_in_consecutive_order(self, *items: E, because: str = "") -> Self:
        """Assert ``items`` never appear as an unbroken run in this order.

        Items that all appear in order but with something between them satisfy
        this, which is exactly what separates it from
        :meth:`does_not_contain_in_order`. The failure names the index the run
        started at. Raises ``ValueError`` when called with no items.
        """
        if not items:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        start = _run_start(subject, items)
        if start is None:
            return self
        return self._fail(
            f"not to contain {render_items(items)} in consecutive order,"
            f" but they ran from index {start}: {render_items(subject)}",
            because,
        )

    # -- ordering ----------------------------------------------------------
    def is_sorted(self, *, key: "Callable[[E], _Ordered] | None" = None, because: str = "") -> Self:
        """Assert the items are in non-decreasing order.

        Equal neighbours are in order, and a sequence of fewer than two items is
        sorted -- it holds nothing that could be out of place. ``key`` maps each
        item to the value that is compared, exactly as it does for ``sorted()``,
        and only ``<`` is ever asked of an item or of a ``key`` result.

        A pair that cannot be ordered at all -- a NaN, in practice -- is a failure
        rather than a pass, reported at the index where it breaks the order and
        carrying a note that says why. :meth:`is_sorted_descending` reports the
        same pair, so a sequence holding one cannot satisfy both.
        """
        subject = self._subject
        index = _first_out_of_order(subject, key, descending=False)
        if index is None:
            return self
        return self._fail(
            f"to be sorted, but {format_value(subject[index])} at index {index}"
            f" came after {format_value(subject[index - 1])}"
            f"{_nan_ordering_note(subject, index, key)}: {render_items(subject)}",
            because,
        )

    def is_not_sorted(
        self, *, key: "Callable[[E], _Ordered] | None" = None, because: str = ""
    ) -> Self:
        """Assert some item comes before one it should follow.

        The negation of :meth:`is_sorted`: equal neighbours do not satisfy it, a
        sequence of fewer than two items always fails, and a pair that cannot be
        ordered -- a NaN -- does satisfy it, because it genuinely breaks the
        order. ``key`` behaves as it does there.
        """
        subject = self._subject
        if _first_out_of_order(subject, key, descending=False) is not None:
            return self
        return self._fail(f"not to be sorted, but it was: {render_items(subject)}", because)

    def is_sorted_descending(
        self, *, key: "Callable[[E], _Ordered] | None" = None, because: str = ""
    ) -> Self:
        """Assert the items are in non-increasing order.

        The mirror of :meth:`is_sorted`, with the same treatment of ``key``, of
        equal neighbours -- in order either way -- of a sequence too short to hold
        a violation, and of a pair that cannot be ordered, which fails here too
        rather than being waved through.
        """
        subject = self._subject
        index = _first_out_of_order(subject, key, descending=True)
        if index is None:
            return self
        return self._fail(
            f"to be sorted in descending order, but {format_value(subject[index])} at index {index}"
            f" came after {format_value(subject[index - 1])}"
            f"{_nan_ordering_note(subject, index, key)}: {render_items(subject)}",
            because,
        )

    def is_not_sorted_descending(
        self, *, key: "Callable[[E], _Ordered] | None" = None, because: str = ""
    ) -> Self:
        """Assert the items are not in non-increasing order.

        The negation of :meth:`is_sorted_descending`, which is not the same claim
        as :meth:`is_sorted`: ``[1, 3, 2]`` is neither ascending nor descending
        and so satisfies this *and* :meth:`is_not_sorted`.
        """
        subject = self._subject
        if _first_out_of_order(subject, key, descending=True) is not None:
            return self
        return self._fail(
            f"not to be sorted in descending order, but it was: {render_items(subject)}", because
        )

    # -- projection --------------------------------------------------------
    @override
    def extracting[R](self, selector: "Callable[[E], R]", /) -> "SequenceExpect[R]":
        """Assert about one field of every item, keeping the order they were in.

        ::

            expect(orders).extracting(lambda order: order.total).is_sorted()

        The override that re-earns the ordered catalogue. The base declaration on
        :class:`~lovely_assertions._collection.CollectionExpect` hands back an
        order-free subject, because the order of a list extracted from a ``set``
        is the set's iteration order and nothing worth asserting about. Here the
        source *is* ordered, extraction preserves that order item for item, so
        ``is_sorted`` on the result is the question it appears to be.

        Everything the base says still holds: the callable form only -- the string
        form assertpy is known for is untypeable -- no ``because``, because this
        makes no claim and cannot fail, and an explicit subject name carries over.
        """
        return self._carrying_name(SequenceExpect([selector(item) for item in self._subject]))

    # -- nested assertions -------------------------------------------------
    def satisfies_respectively(
        self, *assertions: "Callable[[E], object]", because: str = ""
    ) -> Self:
        """Assert each item satisfies its own inspection, paired by position.

        Ordered, so it belongs here rather than on the collection subject: the
        pairing is by position, and on a subject with no positions it would report
        findings that depend on iteration order. ``all_satisfy`` and
        ``satisfies_in_any_order`` are the order-free forms.

        The sequence has to be exactly as long as the list of inspections; a
        mismatch is reported as such rather than silently checking the shorter of
        the two.
        """
        subject = self._subject
        if len(subject) != len(assertions):
            return self._fail(
                f"to have one item for each of the {count_of(len(assertions), 'assertion')},"
                f" but had {len(subject)}: {render_items(subject)}",
                because,
            )
        collected: list[tuple[int, list[str]]] = []
        for index, item in enumerate(subject):
            failures = collect_failures(assertions[index], item, "satisfies_in_any_order")
            if failures:
                collected.append((index, failures))
        if not collected:
            return self
        return self._fail(
            f"to satisfy its assertions respectively\n{self._findings(collected)}",
            because,
        )


# ---------------------------------------------------------------------------
# Rendering helpers -- failure path only.
#
# None of them may use an f-string: an f-string is a message, and a message is
# built in exactly one place, inside `_fail`. They concatenate and join instead,
# so that a helper reached from an argument list cannot format eagerly.
# ---------------------------------------------------------------------------
#: Appended to an approximate-comparison failure a NaN caused, where the two
#: rendered values look identical and the message would otherwise read as though
#: the assertion had misfired.
_NAN_NOTE = " (a NaN is close to nothing, itself included)"

#: Appended to an ordering failure a NaN caused, where the message would
#: otherwise read as though the assertion had misfired. The wording is the one
#: :mod:`lovely_assertions._ordered` uses for the same finding on a scalar
#: subject -- one finding should not have two phrasings depending on which
#: subject reported it -- and is restated here rather than imported because that
#: name is private to its module. The two must be kept in step by hand.
_NAN_ORDERING_NOTE = " (a NaN compares false against every ordering)"


def _nan_note(left: object, right: object, /) -> str:
    """Trailing clause for a pair no tolerance could have brought together.

    Without it, an approximate comparison against a NaN reports "differed at
    index 0 (nan instead of nan)", which reads like a bug in the library rather
    than the finding it is.
    """
    if left != left or right != right:  # noqa: PLR0124  (that is what "not a number" means)
        return _NAN_NOTE
    return ""


def _nan_ordering_note(
    items: "Sequence[object]", index: int, key: "Callable[[Any], _Ordered] | None", /
) -> str:
    """Trailing clause for an ordering failure a NaN caused. Failure path only.

    ``to be sorted, but nan at index 1 came after 3.0`` reads like the library
    misfired -- both values are right there and neither looks out of place. The
    note names the actual reason, in the wording
    :mod:`lovely_assertions._ordered` already uses for the same finding.

    The two keys are recomputed rather than carried out of the scan: carrying
    them would make every *passing* ordering assertion pay for a value only a
    failure ever reads.
    """
    if is_nan(_sort_key(items[index], key)) or is_nan(_sort_key(items[index - 1], key)):
        return _NAN_ORDERING_NOTE
    return ""


def _length_note(left: "Sized", right: "Sized", /) -> str:
    """Trailing clause reporting a length mismatch, or ``""`` when they match."""
    if len(left) == len(right):
        return ""
    return ", and had " + str(len(left)) + " items, not " + str(len(right))


# ---------------------------------------------------------------------------
# Comparison helpers -- these run on the happy path, so they allocate nothing
# beyond what the question itself requires.
# ---------------------------------------------------------------------------
def _first_difference(left: "Sequence[object]", right: "Sequence[object]", /) -> int | None:
    """Index of the first item that differs, or ``None`` if the shared part matches.

    Says nothing about length -- the caller decides whether a matching prefix is
    a pass (``starts_with_sequence``) or a failure (``equals_sequence``).

    Two items count as the same when ``item is expected or item == expected``,
    Python's own membership rule (see the module docstring). Spelled inline,
    subscripts and all, rather than through a pair of locals: the identity test
    short-circuits whenever the two sides really are one object, and measured
    against locals it is the cheaper of the two.
    """
    for index in range(min(len(left), len(right))):
        if not (left[index] is right[index] or left[index] == right[index]):
            return index
    return None


def _first_difference_from_end(
    left: "Sequence[object]", right: "Sequence[object]", /
) -> int | None:
    """Offset back from the end of the first item that differs, 1 for the last one.

    Same equality rule as :func:`_first_difference`, walked from the other end.
    """
    for offset in range(1, min(len(left), len(right)) + 1):
        if not (left[-offset] is right[-offset] or left[-offset] == right[-offset]):
            return offset
    return None


def _first_difference_beyond(
    left: "Sequence[object]", right: "Sequence[float]", tol: float, /
) -> int | None:
    """Index of the first pair further apart than ``tol``.

    Equality is tested first, so two infinities count as equal -- their
    difference is a NaN, not zero -- and the tolerance comparison is written as
    ``not (distance <= tol)`` rather than ``distance > tol``, so a NaN distance
    counts as a difference. A NaN is close to nothing, itself included; the
    inverted spelling is what keeps it from passing every comparison instead.

    This is the one comparison in the module that deliberately does *not* apply
    the ``is``-then-``==`` rule. Everywhere else the question is which items a
    sequence holds, and a NaN is held where it sits; here the question is how far
    apart two numbers are, and that is the contract ``is_close_to`` states -- the
    same NaN, compared to itself, is still at no measurable distance from
    anything.

    The cast is where this assertion stops being type-safe and says so: the
    element type of the subject is unconstrained, and the arithmetic below is the
    contract the caller signed up to by asking for an approximate comparison.
    """
    for index in range(min(len(left), len(right))):
        item = cast("float", left[index])
        expected = right[index]
        if item == expected:
            continue
        if not abs(item - expected) <= tol:
            return index
    return None


def _subsequence_gap(items: "Sequence[object]", wanted: "Sequence[object]", /) -> int | None:
    """Index into ``wanted`` of the first item that breaks the ordered scan.

    ``None`` means every wanted item was found in order, though not necessarily
    adjacent.

    The scan matches on ``item is target or item == target``, the rule ``in``
    itself applies, so ``contains_in_order`` and ``does_not_contain`` cannot
    disagree about whether the sequence holds a NaN.
    """
    position = 0
    count = len(items)
    for index, target in enumerate(wanted):
        while position < count and not (items[position] is target or items[position] == target):
            position += 1
        if position == count:
            return index
        position += 1
    return None


def _run_start(items: "Sequence[object]", wanted: "Sequence[object]", /) -> int | None:
    """Index where ``wanted`` appears as an unbroken run, or ``None``.

    An empty ``wanted`` runs at index 0: every sequence contains nothing,
    consecutively.

    Same equality rule as :func:`_subsequence_gap`, so the consecutive form
    cannot disagree with the loose one about which items are present either.

    This is the one site that binds the pair to locals before comparing them,
    and the scan is why: every start that does *not* match is rejected by a
    comparison whose identity half fails, so the operands are read twice, and
    here reading one of them means an addition as well as a subscript. Measured,
    the locals pay for themselves here; at the other sites they do not.
    """
    span = len(wanted)
    for start in range(len(items) - span + 1):
        offset = 0
        while offset < span:
            item = items[start + offset]
            target = wanted[offset]
            if not (item is target or item == target):
                break
            offset += 1
        if offset == span:
            return start
    return None


def _sort_key(item: object, key: "Callable[[Any], _Ordered] | None", /) -> _Ordered:
    """The value ordering compares: the item itself, or what ``key`` makes of it."""
    if key is None:
        return cast("_Ordered", item)
    return key(item)


def _first_out_of_order(
    items: "Sequence[object]", key: "Callable[[Any], _Ordered] | None", /, *, descending: bool
) -> int | None:
    """Index of the first item that breaks the ordering, or ``None``.

    Equal neighbours are in order either way, so this reports strict violations
    only -- ``[1, 1, 2]`` is both sorted and not sorted descending.

    The question asked is "is this pair definitely *in* order?" -- strictly
    ordered, or equal -- and the loop returns on its negation. Asking the
    opposite, "is this pair definitely *out* of order?", is the whole difference
    between reporting a NaN and being silenced by one: every comparison involving
    a NaN is false, so the strict spelling gets ``False`` from a pair it cannot
    order at all and waves it through. That reading would let ``[3.0, nan, 1.0]``
    satisfy ``is_sorted`` *and* ``is_sorted_descending``, two assertions that are
    supposed to be opposites. Asked the answerable question, a pair that cannot
    answer is reported at the index where it breaks the order.

    The inclusive question is built out of ``<`` and ``==`` rather than spelled
    ``<=``, and that is deliberate rather than long-winded. ``<`` is the only
    ordering operator this module requires of an element or of a ``key=``
    result: it is what :class:`_Ordered` promises, what every ``key=`` signature
    in the module publishes, and all ``sorted()`` itself asks for. ``previous <=
    current`` would demand ``__le__`` and ``__ge__`` too, and a type defining
    only ``__lt__`` -- perfectly sortable, and the exact shape the protocol
    describes -- would then raise ``TypeError`` from every ordering assertion.

    The ``==`` is nearly free: it is reached only once the strict test has
    already said no, which on an ordered subject means at ties alone. The whole
    condition is written inline rather than through a local because that was
    measured, not assumed -- binding the pair to locals costs a few percent on an
    ordinary subject, while the inline form is at parity with the bare strict
    test, and only an all-ties subject, the one shape where ``==`` really is
    evaluated at every step, pays anything at all.

    Identity is deliberately *not* consulted here, unlike at the equality sites.
    Two references to one NaN are still an unordered pair: ``is`` answers a
    question about which item this is, not about how two of them compare.

    A ``Decimal`` NaN is not covered by this and is not meant to be: its
    orderings *signal* rather than return false, so the ``InvalidOperation`` it
    raises propagates instead of being turned into a verdict -- the scalar
    ordering subject in :mod:`lovely_assertions._ordered` makes the same choice,
    and for the same reason: a signal is the caller's configuration talking, not
    a finding about the sequence.
    """
    count = len(items)
    if count == 0:
        return None
    previous = _sort_key(items[0], key)
    for index in range(1, count):
        current = _sort_key(items[index], key)
        if not (current < previous if descending else previous < current) and previous != current:
            return index
        previous = current
    return None
