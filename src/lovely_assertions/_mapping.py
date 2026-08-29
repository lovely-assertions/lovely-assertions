"""Assertions for mappings.

What a failed mapping assertion mostly has to say is *what was actually in
there*, so the messages here are built on two shared pieces: a capped preview of
the keys (or values) that were present, and -- when a lookup misses a key by what
looks like a typo -- a ``difflib`` suggestion naming the key that was probably
meant. Both run on the failure path only, and ``difflib`` is imported inside the
branch that needs it: importing this package must not drag in a module that only
a failing assertion has any use for. The cap is
``current_formatting().max_items``, read where the preview is built, so a
:func:`~lovely_assertions._formatting.formatting` block can widen the one failure
whose interesting key is the fiftieth.

**Containment is tested with ``x is y or x == y``**, Python's own rule -- what
``value in mapping.values()`` does, and what ``dict.__eq__`` does value by value.
Equality alone would report a value the mapping demonstrably holds as absent
whenever that value is not equal to itself (``float("nan")`` is the one everybody
meets), which would make ``contains_value`` contradict ``contains_values`` and
``contains_entry`` contradict the inherited ``is_equal_to``. The rule is written
out at each site rather than put in a helper: these are the comparisons the happy
path pays for, and a call per candidate is a cost a passing assertion should not
be charged.

**The keys and the values are subjects of their own.** ``.keys`` and ``.values``
hand back a :class:`~lovely_assertions._collection.CollectionExpect` over the
live view, so the whole order-free catalogue -- uniqueness, subset and superset,
element types, nested inspection -- applies to them without a second
implementation here. ``expect()`` already dispatches ``dict.keys()`` to that
subject; the properties only save the round trip.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Final, Self, cast

from lovely_assertions._collection import CollectionExpect
from lovely_assertions._core import Expect, Found, describe_predicate
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable, Sized

    from lovely_assertions._occurrence import Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["MappingExpect"]

# How many keys or values a message may list is `current_formatting().max_items`,
# read in the failure branch that is about to print them. The default, declared
# once in `_formatting`, is enough to recognise the mapping you meant and short
# enough to sit next to the rest of the message; `formatting(max_items=...)`
# widens it for the failure where the key that matters is the fiftieth.

#: Stands in for "no such key", so a lookup and the miss it may report are one
#: operation rather than a ``__contains__`` followed by a ``__getitem__``.
_MISSING: Final[object] = object()


def _preview(values: "Collection[object]", /) -> str:
    """Render ``values`` as a list, capped at ``current_formatting().max_items``.

    Failure path only -- which is what lets the cap be read from a ``ContextVar``
    at all, since a passing assertion must not touch one. Uses concatenation
    rather than an f-string on purpose: a message is assembled in exactly one
    place, inside ``_fail``, and a helper called from an argument list would
    format eagerly, on the passing path as well as the failing one.
    """
    limit = current_formatting().max_items
    total = len(values)
    if total <= limit:
        return "[" + ", ".join(format_value(value) for value in values) + "]"
    shown: list[str] = []
    for value in values:
        if len(shown) == limit:
            break
        shown.append(format_value(value))
    return "[" + ", ".join(shown) + ", ... " + str(total - limit) + " more]"


def _preview_entries[EK, EV](entries: Mapping[EK, EV], /) -> str:
    """Render ``entries`` as a mapping, capped at ``current_formatting().max_items``.

    Failure path only. ``contains_entries`` echoes what it was asked for, and a
    caller who passed a hundred pairs must not have them pasted back at them --
    unless they asked for that, which is what a ``formatting`` block is.
    """
    limit = current_formatting().max_items
    total = len(entries)
    shown: list[str] = []
    for key, value in entries.items():
        if len(shown) == limit:
            return "{" + ", ".join(shown) + ", ... " + str(total - limit) + " more}"
        shown.append(format_value(key) + ": " + format_value(value))
    return "{" + ", ".join(shown) + "}"


def _entries(count: int, /) -> str:
    """``"1 entry"`` or ``"4 entries"``. Failure path only."""
    if count == 1:
        return "1 entry"
    return str(count) + " entries"


def _did_you_mean(key: object, candidates: "Iterable[object]", /) -> str:
    """A parenthesised suggestion when a string key misses by a near-spelling.

    Returns ``""`` when nothing is close enough, and for non-string keys: a
    "did you mean" between values that were never spelled out is noise. When it
    does fire it is the single most useful thing the message can carry, which is
    why the cost of importing ``difflib`` is worth paying -- here, in the failure
    branch, and nowhere else.
    """
    if not isinstance(key, str):
        return ""
    import difflib  # noqa: PLC0415  (importing this package must not import difflib)

    names = [candidate for candidate in candidates if isinstance(candidate, str)]
    close = difflib.get_close_matches(key, names, n=1)
    if not close:
        return ""
    return " (did you mean " + repr(close[0]) + "?)"


def _entry_diff[EK, EV](subject: Mapping[EK, EV], entries: Mapping[EK, EV], /) -> str:
    """Say which of ``entries`` are absent and which hold something else.

    Failure path only. The two are different bugs -- a key never written, and a
    key written with the wrong value -- so they get separate clauses instead of
    one "did not contain" the reader has to investigate.
    """
    missing: list[EK] = []
    differing: list[str] = []
    for key, value in entries.items():
        actual = subject.get(key, _MISSING)
        if actual is _MISSING:
            missing.append(key)
        elif not (actual is value or actual == value):
            differing.append(
                format_value(key)
                + " held "
                + format_value(actual)
                + " instead of "
                + format_value(value)
            )
    clauses: list[str] = []
    if missing:
        clauses.append("was missing " + _preview(missing))
    if differing:
        limit = current_formatting().max_items
        shown = differing[:limit]
        if len(differing) > limit:
            shown.append("... " + str(len(differing) - limit) + " more")
        clauses.append(", ".join(shown))
    return " and ".join(clauses)


def _render_or_none(subject: "Mapping[Any, Any] | None", /) -> str:
    """Render a mapping, or ``None`` for a subject that turned out to be missing.

    Failure path only. Declared as an optional parameter for the reason
    :func:`_is_none_or_empty` is: the subject type excludes ``None``, so the
    comparison would be flagged as unreachable if it were written inline.
    """
    if subject is None:
        return "None"
    return _preview_entries(subject)


def _is_none_or_empty(subject: "Sized | None", /) -> bool:
    """Whether the subject is missing entirely or simply holds nothing.

    Runs on the happy path. Declared as an optional parameter so the ``None``
    branch is honest to both checkers: ``MappingExpect``'s subject type excludes
    ``None``, and a comparison against it inside the method would be flagged as
    unreachable. ``_collection`` carries the twin of this for the same reason.
    """
    return subject is None or len(subject) == 0


#: Guard for the variadic assertions. A call with nothing to look for either
#: passes whatever the subject is -- a test that asserts nothing -- or could never
#: pass at all. Both are bugs in the test rather than findings about the subject,
#: so they are raised, not reported. The variadics on
#: :class:`~lovely_assertions._string.StringExpect` raise for the same reason.
_NEEDS_VALUES = "at least one value to look for is required"


class MappingExpect[K, V](Expect[Mapping[K, V]]):
    """Assertions for mappings, parameterised by key and value type.

    The subject is a ``Mapping[K, V]``, so one subject class covers ``dict``,
    ``MappingProxyType``, ``ChainMap`` and anything else that implements the ABC.
    ``is_equal_to`` / ``is_not_equal_to`` are inherited: mapping equality is
    already the right comparison.
    """

    __slots__ = ()

    # -- size ---------------------------------------------------------------
    def is_empty(self, *, because: str = "") -> Self:
        """Assert the mapping has no entries."""
        subject = self._subject
        if not subject:
            return self
        return self._fail(
            f"to be empty, but had {_entries(len(subject))} with keys {_preview(subject.keys())}",
            because,
        )

    def is_not_empty(self, *, because: str = "") -> Self:
        """Assert the mapping has at least one entry."""
        if self._subject:
            return self
        return self._fail("not to be empty, but it was", because)

    def is_none_or_empty(self, *, because: str = "") -> Self:
        """Assert the mapping is ``None`` or has no entries.

        The subject type excludes ``None``, so a checker will say this can only
        ever be the empty case. The runtime check is real all the same: ``None``
        arrives here through a cast, from untyped code, or from a fixture that
        returned nothing, and absorbing exactly that is what the assertion is for.
        """
        subject = self._subject
        if _is_none_or_empty(subject):
            return self
        return self._fail(
            f"to be None or empty, but had {_entries(len(subject))}"
            f" with keys {_preview(subject.keys())}",
            because,
        )

    def is_not_none_or_empty(self, *, because: str = "") -> Self:
        """Assert the mapping is neither ``None`` nor empty."""
        if not _is_none_or_empty(self._subject):
            return self
        return self._fail(
            f"not to be None or empty, but was {_render_or_none(self._subject)}", because
        )

    def has_length(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the mapping has exactly ``expected`` entries."""
        subject = self._subject
        actual = len(subject)
        if actual == expected:
            return self
        return self._fail(
            f"to have {_entries(expected)}, but had {_entries(actual)} "
            f"with keys {_preview(subject.keys())}",
            because,
        )

    def does_not_have_length(self, unexpected: int, /, *, because: str = "") -> Self:
        """Assert the mapping has any number of entries other than ``unexpected``."""
        if len(self._subject) != unexpected:
            return self
        return self._fail(f"not to have {_entries(unexpected)}, but it did", because)

    def has_length_matching(
        self, predicate: "Callable[[int], bool]", /, *, because: str = ""
    ) -> Self:
        """Assert the number of entries satisfies ``predicate``."""
        subject = self._subject
        if predicate(len(subject)):
            return self
        return self._fail(
            f"to have a length matching {describe_predicate(predicate)},"
            f" but had {_entries(len(subject))} with keys {_preview(subject.keys())}",
            because,
        )

    def has_length_greater_than(self, other: int, /, *, because: str = "") -> Self:
        """Assert the mapping has more than ``other`` entries."""
        subject = self._subject
        if len(subject) > other:
            return self
        return self._fail(
            f"to have more than {_entries(other)},"
            f" but had {_entries(len(subject))} with keys {_preview(subject.keys())}",
            because,
        )

    def has_length_greater_than_or_equal_to(self, other: int, /, *, because: str = "") -> Self:
        """Assert the mapping has at least ``other`` entries."""
        subject = self._subject
        if len(subject) >= other:
            return self
        return self._fail(
            f"to have at least {_entries(other)},"
            f" but had {_entries(len(subject))} with keys {_preview(subject.keys())}",
            because,
        )

    def has_length_less_than(self, other: int, /, *, because: str = "") -> Self:
        """Assert the mapping has fewer than ``other`` entries."""
        subject = self._subject
        if len(subject) < other:
            return self
        return self._fail(
            f"to have fewer than {_entries(other)},"
            f" but had {_entries(len(subject))} with keys {_preview(subject.keys())}",
            because,
        )

    def has_length_less_than_or_equal_to(self, other: int, /, *, because: str = "") -> Self:
        """Assert the mapping has at most ``other`` entries."""
        subject = self._subject
        if len(subject) <= other:
            return self
        return self._fail(
            f"to have at most {_entries(other)},"
            f" but had {_entries(len(subject))} with keys {_preview(subject.keys())}",
            because,
        )

    def has_same_length_as(self, other: "Sized", /, *, because: str = "") -> Self:
        """Assert the mapping has as many entries as ``other`` has items.

        ``other`` is anything with a length -- a list, a set, another mapping --
        because comparing an entry count against an item count is a fair
        question and the element types are nobody's business here.
        """
        actual = len(self._subject)
        if actual == len(other):
            return self
        return self._fail(
            f"to have as many entries as {format_value(other)},"
            f" but had {_entries(actual)} against {len(other)}",
            because,
        )

    def does_not_have_same_length_as(self, other: "Sized", /, *, because: str = "") -> Self:
        """Assert the mapping and ``other`` differ in size.

        The negation of :meth:`has_same_length_as`, and it takes the same
        anything-with-a-length.
        """
        actual = len(self._subject)
        if actual != len(other):
            return self
        return self._fail(
            f"not to have as many entries as {format_value(other)},"
            f" but both had {_entries(actual)}",
            because,
        )

    # -- views --------------------------------------------------------------
    #
    # A mapping is a collection of its keys and a collection of its values, and
    # both of those already have a full catalogue one module over: uniqueness,
    # subset and superset, element types, wildcard matching, nested inspection.
    # Re-declaring any of it here would be a second implementation of an already
    # answered question, which is how one question comes to have two answers, so
    # the views hand back the collection subject instead. `expect()` dispatches
    # `dict.keys()` there already, which is what makes this a continuation
    # rather than new machinery.
    #
    # Properties, not methods, to match `.and_`, `.which` and `.whose_value`.
    # A continuation is a step sideways in the sentence, and
    # `expect(rows).keys()` would read as a call *on the mapping*.
    #
    # There is deliberately no `items` view. Every question the collection
    # catalogue could put to `(key, value)` pairs is either answered better here
    # -- `contains_entry` says *"but that key held 'ada'"* where
    # `items.contains(("name", "bob"))` could only reprint the pairs -- or
    # vacuous, since keys are unique and therefore so are pairs, which makes
    # `has_unique_items` on them a test that cannot fail. The one genuine use
    # left, comparing entries against another mapping's, is still one
    # `expect(rows.items())` away, and that already lands on `CollectionExpect`.
    def _view[E](self, items: "Collection[E]", /) -> "CollectionExpect[E]":
        """Wrap one of the mapping's views, carrying an explicit name across.

        Not the failure path -- this runs whenever a view is taken -- so it stays
        to the one allocation the wrapper itself is, plus one attribute read.
        ``_name`` is unset unless the caller named the subject, hence the
        default. A view that dropped the name would silently fall back to
        recovering one from the source, which is the answer ``described_as``
        was called to override in the first place.
        """
        view: CollectionExpect[E] = CollectionExpect(items)
        name = getattr(self, "_name", None)
        if isinstance(name, str):
            view.described_as(name)
        return view

    @property
    def keys(self) -> "CollectionExpect[K]":
        """Continue on the keys, as a collection.

            expect(rows).keys.is_subset_of(ALLOWED_FIELDS)

        Deliberately not ``has_unique_items``: keys cannot repeat, so that one
        is a test that cannot fail -- the very reason the block above gives for
        there being no ``items`` view. What the keys view is *for* is the
        questions the mapping catalogue does not answer at all: subset and
        superset, element types, wildcard matching, nested inspection.

        The wrapper holds the live view, so this copies nothing. Note that
        ``.and_`` on the result re-chains on the *keys*: the view is a subject in
        its own right, not a continuation that remembers the mapping.
        """
        return self._view(self._subject.keys())

    @property
    def values(self) -> "CollectionExpect[V]":
        """Continue on the values, as a collection.

            expect(rows).values.all_are_instance_of(int)

        Unlike the keys, values may repeat -- ``has_unique_items`` is a real
        question here, and the usual reason to reach for this view.
        """
        return self._view(self._subject.values())

    # -- keys ---------------------------------------------------------------
    def contains_key(self, key: K, /, *, because: str = "") -> "Found[Self, V]":
        """Assert the mapping has ``key``; continue on its value with ``.whose_value``.

        On failure the message lists the keys that *are* present, and names the
        closest spelling among them when there is one -- a mistyped key is the
        common case, and the diff is the answer rather than a hint towards it.
        """
        subject = self._subject
        if key in subject:
            return Found(self, subject[key])
        return cast(
            "Found[Self, V]",
            self._fail_narrowing(
                f"to contain key {format_value(key)}{_did_you_mean(key, subject)}, "
                f"but the keys were {_preview(subject.keys())}",
                because,
            ),
        )

    def does_not_contain_key(self, key: K, /, *, because: str = "") -> Self:
        """Assert the mapping has no such key.

        A key mapped to ``None`` is still present and still fails this. The
        message reports the value that key held, which is usually the next thing
        wanted; :meth:`does_not_contain_entry` is the assertion for "not with
        *that* value".
        """
        subject = self._subject
        if key not in subject:
            return self
        return self._fail(
            f"not to contain key {format_value(key)}, but it held {format_value(subject[key])}",
            because,
        )

    def contains_keys(self, *keys: K, because: str = "") -> Self:
        """Assert every one of ``keys`` is present.

        Extra keys in the mapping are fine: this asks what it must have, not what
        it may not, and :meth:`contains_only_keys` is what closes the other
        direction. Repeats among ``keys`` change nothing. The failure lists the
        missing keys separately from the keys that were actually there, so the
        two do not have to be diffed by eye. Raises ``ValueError`` when called
        with no keys, since an assertion with nothing to look for cannot fail.
        """
        if not keys:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        for key in keys:
            if key not in subject:
                break
        else:
            return self
        missing = [key for key in keys if key not in subject]
        return self._fail(
            f"to contain keys {_preview(keys)}, but was missing {_preview(missing)}; "
            f"the keys were {_preview(subject.keys())}",
            because,
        )

    def does_not_contain_keys(self, *keys: K, because: str = "") -> Self:
        """Assert none of ``keys`` is present.

        Every one of them has to be absent -- one that is present fails the whole
        call -- and the failure names the ones that were found. Raises
        ``ValueError`` when called with no keys.
        """
        if not keys:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        for key in keys:
            if key in subject:
                break
        else:
            return self
        present = [key for key in keys if key in subject]
        return self._fail(
            f"not to contain keys {_preview(keys)}, but found {_preview(present)}", because
        )

    def contains_only_keys(self, *keys: K, because: str = "") -> Self:
        """Assert the keys are exactly ``keys`` -- no more, no fewer, order ignored.

        Both directions are checked, and the failure says which one gave way:
        keys that were missing, keys that were surplus, or both. Repeats among
        ``keys`` are ignored; a mapping cannot hold a key twice, so reading them
        as a set is the only interpretation that means anything.

        A call with no keys asserts the mapping is *empty*, which is a real claim
        rather than a vacuous one -- so, unlike the other variadics here, it is
        allowed rather than rejected.
        """
        subject = self._subject
        expected = set(keys)
        if set(subject) == expected:
            return self
        missing = [key for key in keys if key not in subject]
        surplus = [key for key in subject if key not in expected]
        if not missing:
            return self._fail(
                f"to contain only the keys {_preview(keys)}, but also had {_preview(surplus)}",
                because,
            )
        if not surplus:
            return self._fail(
                f"to contain only the keys {_preview(keys)}, but was missing {_preview(missing)}",
                because,
            )
        return self._fail(
            f"to contain only the keys {_preview(keys)}, but was missing {_preview(missing)} "
            f"and also had {_preview(surplus)}",
            because,
        )

    def contains_key_matching(
        self, predicate: "Callable[[K], bool]", /, *, because: str = ""
    ) -> "Found[Self, K]":
        """Assert some key satisfies ``predicate``; continue on that key with ``.which``.

        This is where a ``Found`` earns its place, and ``contains_key`` is where
        it would not: there the caller already holds the key they searched for,
        and what they want next is the value behind it. Here the caller does not
        know *which* key matched, so the key is the thing worth handing back.

        The **first** matching key in iteration order is the one handed on, as
        in the two forms beside it.
        """
        for key in self._subject:
            if predicate(key):
                return Found(self, key)
        return cast(
            "Found[Self, K]",
            self._fail_narrowing(
                f"to contain a key matching {describe_predicate(predicate)}, "
                f"but the keys were {_preview(self._subject.keys())}",
                because,
            ),
        )

    # -- values -------------------------------------------------------------
    def contains_value(
        self, value: V, /, *, occurrences: "Occurrence | None" = None, because: str = ""
    ) -> "Found[Self, V]":
        """Assert some key holds ``value``; continue on it with ``.which``.

        The value handed on is the one *stored*, not the one passed in. They
        compare equal, and when they are not the same object the stored one is
        the one worth asserting against.

        ``occurrences`` turns the question into **how many keys hold it**::

            expect(statuses).contains_value("failed", occurrences=at_most(2))

        Counting stops at nothing: every value is compared, by the same
        ``x is y or x == y`` this class applies everywhere (see the module
        docstring), so the count and the plain form can never disagree about
        whether the value is in there. Distinct keys holding equal values each
        count -- ``{"a": 1, "b": 1.0}`` holds ``1`` twice -- and a NaN counts the
        keys holding *that* NaN, since identity is tested first and a NaN is
        equal to nothing, itself included.

        One consequence of keeping the return type (a constraint may be satisfied
        by **no** matches at all, as ``at_most(0)`` is): there is then nothing
        stored to continue on, and ``.which`` gets the value that was passed in.
        A continuation onto a value the mapping does not hold is a strange thing
        to write, and the alternative -- a ``Found`` over a sentinel, or a second
        return type for one assertion -- would be worse than strange.
        """
        subject = self._subject
        if occurrences is None:
            for candidate in subject.values():
                if candidate is value or candidate == value:
                    return Found(self, candidate)
            return cast(
                "Found[Self, V]",
                self._fail_narrowing(
                    f"to contain value {format_value(value)}, "
                    f"but the values were {_preview(subject.values())}",
                    because,
                ),
            )
        count = 0
        # Seeded with what was asked for, which is also the answer when the
        # constraint is satisfied by no match at all; the first stored match
        # replaces it. One pass, and no sentinel to cast away afterwards.
        stored = value
        for candidate in subject.values():
            if candidate is value or candidate == value:
                if count == 0:
                    stored = candidate
                count += 1
        if occurrences.allows(count):
            return Found(self, stored)
        return cast(
            "Found[Self, V]",
            self._fail_narrowing(
                f"to contain value {format_value(value)} {occurrences.describe()}, "
                f"but found {count}: {_preview(subject.values())}",
                because,
            ),
        )

    def does_not_contain_value(self, value: V, /, *, because: str = "") -> Self:
        """Assert no key holds ``value``.

        Compared with ``x is y or x == y``, so a mapping is reported as holding
        *the* NaN it stores and no other one, and this can never contradict
        :meth:`contains_value`. The failure names the key that held it, which is
        the half of the entry worth reporting. :meth:`does_not_contain_values` is
        the variadic form.
        """
        for key, candidate in self._subject.items():
            if candidate is value or candidate == value:
                return self._fail(
                    f"not to contain value {format_value(value)},"
                    f" but key {format_value(key)} held it",
                    because,
                )
        return self

    def contains_values(self, *values: V, because: str = "") -> Self:
        """Assert every one of ``values`` is held by some key.

        Which key holds what is not asked, and each value is looked up on its
        own, so passing the same value twice asks one question twice rather than
        demanding two entries hold it -- ``contains_value(v, occurrences=...)``
        is where counting lives. The lookup goes through the mapping's values
        view, so the comparison is the ``x is y or x == y`` this class applies
        everywhere. Raises ``ValueError`` when called with no values.
        """
        if not values:
            raise ValueError(_NEEDS_VALUES)
        present = self._subject.values()
        for value in values:
            if value not in present:
                break
        else:
            return self
        missing = [value for value in values if value not in present]
        return self._fail(
            f"to contain values {_preview(values)}, but was missing {_preview(missing)}; "
            f"the values were {_preview(present)}",
            because,
        )

    def does_not_contain_values(self, *values: V, because: str = "") -> Self:
        """Assert none of ``values`` is held by any key.

        Every one of them has to be absent, and the failure names the ones that
        were found. Same comparison as :meth:`contains_values`, so the two can
        never disagree. Raises ``ValueError`` when called with no values.
        """
        if not values:
            raise ValueError(_NEEDS_VALUES)
        present = self._subject.values()
        for value in values:
            if value in present:
                break
        else:
            return self
        found = [value for value in values if value in present]
        return self._fail(
            f"not to contain values {_preview(values)}, but found {_preview(found)}", because
        )

    def contains_value_matching(
        self, predicate: "Callable[[V], bool]", /, *, because: str = ""
    ) -> "Found[Self, V]":
        """Assert some key holds a value satisfying ``predicate``; continue with ``.which``.

        The first matching value in iteration order is the one handed on. A
        mapping with several matches is answering "is there one", and picking the
        first is the only answer that costs nothing.
        """
        for value in self._subject.values():
            if predicate(value):
                return Found(self, value)
        return cast(
            "Found[Self, V]",
            self._fail_narrowing(
                f"to contain a value matching {describe_predicate(predicate)}, "
                f"but the values were {_preview(self._subject.values())}",
                because,
            ),
        )

    # -- entries ------------------------------------------------------------
    def contains_entry(self, key: K, value: V, /, *, because: str = "") -> Self:
        """Assert the mapping maps ``key`` to ``value``.

        A key that is absent and a key that holds something else are different
        bugs, and the message says which one happened rather than leaving the
        reader to check.
        """
        actual = self._subject.get(key, _MISSING)
        if actual is value or actual == value:
            return self
        if actual is _MISSING:
            return self._fail(
                f"to contain entry {format_value(key)}: {format_value(value)},"
                f" but the key was missing"
                f"{_did_you_mean(key, self._subject)}; "
                f"the keys were {_preview(self._subject.keys())}",
                because,
            )
        return self._fail(
            f"to contain entry {format_value(key)}: {format_value(value)},"
            f" but that key held {format_value(actual)}",
            because,
        )

    def does_not_contain_entry(self, key: K, value: V, /, *, because: str = "") -> Self:
        """Assert the mapping does not map ``key`` to ``value``.

        A missing key satisfies this: the entry is not there either way.
        """
        actual = self._subject.get(key, _MISSING)
        if actual is value or actual == value:
            return self._fail(
                f"not to contain entry {format_value(key)}: {format_value(value)},"
                f" but it was there",
                because,
            )
        return self

    def contains_entries(self, entries: Mapping[K, V], /, *, because: str = "") -> Self:
        """Assert every entry of ``entries`` is present with that exact value.

        A superset is fine -- this asks what the mapping must contain, not what it
        may not. Values are compared with ``x is y or x == y``, the rule this
        class applies everywhere, and the failure keeps the keys that were absent
        apart from the keys that held something else, because those are different
        bugs. Raises ``ValueError`` when ``entries`` is empty.
        """
        if not entries:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        for key, value in entries.items():
            actual = subject.get(key, _MISSING)
            if not (actual is value or actual == value):
                break
        else:
            return self
        return self._fail(
            f"to contain entries {_preview_entries(entries)}, but {_entry_diff(subject, entries)}",
            because,
        )

    def contains_entry_matching(
        self, predicate: "Callable[[K, V], bool]", /, *, because: str = ""
    ) -> "Found[Self, tuple[K, V]]":
        """Assert some entry satisfies ``predicate(key, value)``; continue with ``.which``.

        The predicate takes the key and the value as **two arguments**, not one
        pair. Three reasons, in order of weight. This class already spells an
        entry as two positional arguments -- ``contains_entry(key, value)``,
        ``does_not_contain_entry(key, value)`` -- and one concept must not read
        two ways in one catalogue. Python 3 removed tuple parameter unpacking, so
        the pair form's only spelling in a lambda is ``entry[0]`` and
        ``entry[1]``, which is precisely the unreadable test this library exists
        to replace. And a named predicate written for it, ``def is_stale(key,
        value)``, is then an ordinary two-parameter function rather than one
        contorted for the call site.

        What comes back is the whole entry, because that is what was searched
        for: ``.subject`` is the ``(key, value)`` pair, and the key half is
        usually the half worth reporting. Assert on the value with
        ``.subject[1]`` or re-enter through ``expect()``. The **first** matching
        entry in iteration order is the one handed on, as in the two forms
        beside it.
        """
        for key, value in self._subject.items():
            if predicate(key, value):
                return Found(self, (key, value))
        return cast(
            "Found[Self, tuple[K, V]]",
            self._fail_narrowing(
                f"to contain an entry matching {describe_predicate(predicate)}, "
                f"but the entries were {_preview_entries(self._subject)}",
                because,
            ),
        )
