"""Structural equivalence: two object graphs compared member by member.

``is_equal_to`` asks one question -- ``__eq__`` -- and a great many Python types
answer it by identity, by type, or not at all. Equivalence asks a different one:
*do these two graphs hold the same information?* A ``dict`` against a dataclass
member, a ``list`` against a ``tuple``, a record whose ``password`` field nobody
cares about, two timestamps a millisecond apart. FluentAssertions built its
reputation on that assertion; this is the engine behind the Python one.

The module has one entry point, :func:`compare`, and one configuration object,
:class:`Equivalency`. Everything else is private.

Seven rules shape it.

**"" means equivalent.** :func:`compare` returns an empty string when the two
graphs agree and a rendered block when they do not, so the caller branches on
emptiness and reports every finding in a single ``_fail``. That is the shape
``Expect.satisfies`` already uses, which is why soft-scope behaviour falls out of
it for free.

**It never raises because of a value.** A property that explodes, a ``__repr__``
that lies, an ``__eq__`` that throws, a structure that contains itself: each of
those costs the reader detail and never turns their test failure into an error
raised inside the assertion library. The guards are per member rather than around
the walk, so one hostile field of a twelve-field record costs that field and not
the other eleven. A *misconfigured call* is different and does raise, at the call,
where the mistake is.

**Failing is the safe direction.** ``_diff`` degrades to ``""`` because its block
is appended to a message that has already failed. Here ``""`` is a verdict, so
degrading to it would turn a broken comparison into a **passing test**. Every
degradation in this module therefore produces a *difference*, never silence.

**Equality settles equivalence.** Two values that are ``==`` hold the same
information, so the walk stops there and reports nothing. That is not only an
optimisation: it is what keeps equivalence from ever being *stricter* than
equality. ``Point(1, 2) == (1, 2)`` is true, so an engine that took the pair apart
and called a field ``x`` unmatched against index ``0`` would fail the weaker
assertion where the stronger one passes -- the one pair of answers a reader could
never make sense of. The exception is a hand-written comparator narrower than
``==``, which is not consulted for a pair equality has already settled; every
option in this module *widens* what counts as equivalent, so nothing else is
affected.

**Strict ordering is the default (a deliberate inversion of FluentAssertions).**
In Python a ``list`` is ordered by definition and ``set`` exists for the other
case, so a default under which ``[1, 2]`` matches ``[2, 1]`` writes tests that
pass when they should not. ``ignoring_order()`` opts in, and pays the quadratic
matching cost that opting in implies.

**The expectation drives, and a mapping is not a record.** ``is_equivalent_to``
compares the members the *expectation* names. A field only the subject carries is
not a difference -- asserting an ORM row, a pydantic model or a wire payload
against a small literal that names the three fields the test is about is the
commonest reason anyone reaches for structural equivalence, and a rule that
reported the other nine fields as surplus makes that unwritable. It is also the
asymmetry that gives ``BeEquivalentTo`` a reason to exist as something other than
``Be``. ``comparing_all_members()`` compares both member sets, for an expectation
meant to be exhaustive; ``excluding_missing()`` relaxes the other direction, so
that a member the expectation names and the subject lacks is skipped rather than
reported.

A **mapping is decided separately and the other way**: both directions are still
reported there, and neither option touches it. A record's fields are the shape its
author declared, and an expectation object is a *stand-in* for that shape -- what
it leaves out, it leaves out on purpose. A dictionary's keys are its data. The
expectation ``{"id": 1, "total": 5}`` is not a partial description of a payload,
it is a payload, and "the response carried a key I did not expect" is precisely
what a test written against one is asked to catch. FluentAssertions keeps
dictionary equivalency apart for the same reason. ``excluding()`` still reaches a
key by name, which is the escape when a payload carries a timestamp.

The consequence worth knowing is that an expectation naming *no* members is
satisfied by anything -- the same vacuity ``including()`` documents for a name
nothing carries, reached the same way and answered the same way, because saying so
would need a channel for reporting on the comparison itself rather than on the two
values, and this engine has none.

**It is bounded, and a bound it hits is never a verdict.** The engine stops
collecting differences at :data:`_MAX_DIFFERENCES`, which is a bound on *detail*:
two hundred findings already settle "not equivalent", so the report is truncated
and the answer stands. The two bounds on order-insensitive pairing --
:data:`_MAX_MATCHING` and :data:`_MAX_SCANNING` -- are different in kind: hitting
one means the items were never paired off, so neither answer was established.
Those raise :class:`ValueError` out of :func:`compare` rather than returning a
verdict, for the reason spelled out on :class:`_TruncatedError`. The *rendering*
bounds -- how many differences are shown, how long a value may be -- come from
:func:`~lovely_assertions.current_formatting` and are therefore read on the
reporting path only, never during the walk.

Two house rules show up in the shape of the code. A message is never built outside
the argument list of a ``_fail(...)`` call, and there is no ``_fail`` here, so
there are no f-strings either: every message is concatenated, exactly as in
``_diff``, ``_formatters.py`` and ``_formatting.py``. And nothing a passing
assertion would pay for is imported at module scope -- ``dataclasses`` is imported
inside the function that needs it, ``attrs`` is duck-typed through
``__attrs_attrs__`` with nothing imported at all, and pydantic v2 keeps its field
values in ``__dict__`` and needs nothing.

A note on the duplication with ``_diff``. Its clipping, counting and item
rendering are the conventions this module follows, and they live in modules that
package is entered past: only :func:`~lovely_assertions._diff.render_operand`,
:func:`~lovely_assertions._diff.describe_difference` and
:func:`~lovely_assertions._diff.stable_order` are exported, and reaching around
that for a leaf helper would tie this module to an arrangement the diff engine is
free to change. So ``render_operand`` is reused and the rest is reimplemented
here to the same behaviour. Field resolution is not duplicated: both modules read it from
``_reflection.py``, because two resolvers that drift produce a message that
contradicts the comparison behind it.
"""

from abc import get_cache_token
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Final, cast, override

from lovely_assertions._diff import render_operand
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting
from lovely_assertions._reflection import (
    attrs_field_names,
    dataclass_field_names,
    instance_dict_names,
    is_float_nan,
    is_mapping,
    is_set,
    named_tuple_field_names,
    qualified,
    remember,
    slot_names,
)
from lovely_assertions._text import count_of

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from datetime import timedelta

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["Equivalency", "close_within", "compare", "differs", "equivalency"]

#: Levels of structure the walk descends by default. FluentAssertions' number,
#: and it is chosen for the same reason: ten levels is deeper than any object
#: graph a test asserts on by hand, and shallow enough that a mistake -- a model
#: that reaches back into its session, a node with a parent pointer -- stops
#: rather than running until the interpreter does.
_DEFAULT_MAX_DEPTH: Final = 10

#: Differences collected before the walk gives up and says so. This bounds what
#: the *engine* may spend while comparing, which is why it is a constant here and
#: not an option: a caller who could raise it could hang a test run. Well past
#: anything a reader will look at, and small enough that two mismatched
#: ten-thousand-node graphs cost a few hundred small records rather than twenty
#: thousand.
_MAX_DIFFERENCES: Final = 200

#: Nodes the engine will visit while *deciding* how unordered items line up,
#: across one whole comparison. Structural pairing is quadratic in full recursive
#: comparisons, and every one of those may itself be a quadratic pairing one level
#: down -- two levels of a hundred unhashables against a hundred is a hundred
#: million comparisons and a test run that looks hung. Only matching spends it:
#: the caller's own walk is never cut short, and what keeps *it* finite is
#: :class:`_Memo` rather than an allowance.
#:
#: This is the *only* bound on structural pairing, and a per-level cap on unpaired
#: items is deliberately not a second one. Such a cap is not a bound at all, since
#: levels multiply -- which is exactly what this allowance is for -- and it clips
#: comparisons this allowance pays for comfortably: three hundred genuinely
#: unpaired items on each side is ninety thousand probes and an honest answer.
_MAX_MATCHING: Final = 100_000

#: ``==`` calls the *cheap* half of unordered pairing will spend on items that
#: nothing hashable can stand for, across one whole comparison. Those items are
#: paired by linear scan -- the treatment ``_diff._tally``/``_diff._take`` give the
#: same problem -- which is quadratic in ``==`` rather than in recursive walks. One
#: such call is two or three orders of magnitude cheaper than a node of
#: :data:`_MAX_MATCHING`'s currency, hence the far larger allowance: it pairs off
#: thousands of shuffled records against thousands, in a fraction of a second,
#: without the structural pass being asked for anything at all.
_MAX_SCANNING: Final = 5_000_000

#: Characters of one rendered mapping key inside a *path*. Paths are built during
#: the walk, which is the path a *passing* assertion takes, and reading
#: ``current_formatting()`` there is a ``ContextVar`` lookup nobody who is not
#: failing should pay for -- so this bound is a constant rather than an option. A
#: key long enough to hit it cannot be addressed with
#: :meth:`Equivalency.excluding_path` -- excluding it by name still works.
_MAX_PATH_KEY_CHARS: Final = 80

#: The two currencies :class:`_Budget` is spent in, named for the message a
#: :class:`_Truncated` carries. Constants because a message must not be assembled
#: on a path a passing comparison takes.
_MATCHING_NOUN: Final = "comparisons"
_SCANNING_NOUN: Final = "equality checks between items that cannot be hashed"

#: One level of the block. The whole thing is indented under a one-line message,
#: the way ``_diff``'s block is.
_INDENT: Final = "  "

#: Stands in for a field the object would not give up -- a ``__slots__`` entry
#: nobody assigned, a property that raised. A sentinel rather than ``None``,
#: because ``None`` is a perfectly ordinary field value and the two must not be
#: confused: one is a member that is absent, the other a member that is empty.
_UNREADABLE: Final = object()

#: Stands in for "this type has not been looked at yet" in the two caches below.
#: A sentinel rather than ``None`` for the same reason as :data:`_UNREADABLE`:
#: ``None`` is one of the answers being cached -- "this type declares no fields"
#: -- and a cache that could not tell it from a miss would re-derive it forever,
#: which is the one type the derivation is most expensive for.
_UNCACHED: Final = object()

#: Types whose values are compared whole, built once instead of at every call.
#: ``isinstance(value, str | bytes | ...)`` reads as the nicer spelling and is
#: not: the ``|`` builds a fresh ``UnionType`` on every evaluation, and
#: :func:`_is_opaque` runs twice for every pair the walk examines. A tuple is
#: what ``isinstance`` wants anyway.
_OPAQUE_TYPES: Final = (str, bytes, bytearray, memoryview, type)

#: The two halves of "one side has this field and the other does not". Constants
#: rather than built at the point of use, because they are built during the walk.
_NOT_ON_ACTUAL: Final = "this field could not be read on the actual value"
_NOT_ON_EXPECTED: Final = "this field could not be read on the expected value"

#: What a record whose every declared field turned out not to exist has to say
#: for itself. Reported alongside the two values, because with no member readable
#: on either side those reprs are the only account of the difference there is.
_UNRESOLVED: Final = "(none of the fields it declares could be read on either side)"

#: How the root of the two graphs reads. The root has no path -- there is no
#: member to name -- and "" would render as a line beginning with a colon.
_ROOT: Final = "the value itself"

#: The five kinds a value can be compared as. Two values of different kinds have
#: nothing to compare member by member, so the mismatch is itself the finding.
_KIND_LEAF: Final = "leaf"
_KIND_MAPPING: Final = "mapping"
_KIND_SET: Final = "set"
_KIND_SEQUENCE: Final = "sequence"
_KIND_RECORD: Final = "record"

#: What one difference has to show. Kept as tags on a single record rather than as
#: a class hierarchy: a difference is data gathered during the walk and rendered
#: afterwards, and the split is what keeps `current_formatting()` -- a ContextVar
#: read -- off the walk entirely.
_SHOWS_PAIR: Final = "pair"
_SHOWS_TYPES: Final = "types"
_SHOWS_NOTE: Final = "note"
_SHOWS_ITEMS: Final = "items"


# ---------------------------------------------------------------------------
# Tolerance
# ---------------------------------------------------------------------------
def close_within(tolerance: "float | timedelta") -> "Callable[[Any, Any], bool]":
    """Build a comparator for :meth:`Equivalency.using` that allows ``tolerance``.

        >>> equivalency().using(float, close_within(0.01))
        equivalency().using(float, close_within)

    This is the vehicle for float and datetime tolerance, and it is one function
    for both because Python already makes them one problem: ``abs(a - b) <= t``
    reads a ``float`` against a ``float`` and a ``datetime`` against a
    ``timedelta`` without knowing which it has. Pass the tolerance in whatever
    type the values subtract to -- a ``float`` for numbers, a ``timedelta`` for
    datetimes -- and hand the result to :meth:`Equivalency.using`.

    Raises :class:`ValueError` here, at the call that builds the comparator,
    rather than at the first comparison that uses it. A negative tolerance means
    nothing is ever close and a NaN one means the same, so both would turn every
    value in the graph into a difference -- a failure a long way from the mistake
    that caused it. ``tolerance - tolerance`` is the zero of whatever type was
    passed, which is how one check covers both without importing ``datetime``.

    Subtracting two values that will not subtract raises, and that is left alone:
    the engine catches it and reports which member the comparator could not
    handle, which is the finding.
    """
    # Widened deliberately. Against the declared union the checker refuses the
    # arithmetic outright -- a `float` will not subtract a `timedelta` -- although
    # neither branch of the union ever meets the other. The widening is what lets
    # one expression cover both, and it is also what makes the check mean
    # something when a caller's declaration was wrong.
    bound: Any = tolerance
    if not bound >= bound - bound:
        message = "tolerance must be zero or more, not " + repr(tolerance)
        raise ValueError(message)

    def close_within(actual: Any, expected: Any, /) -> bool:  # noqa: ANN401 (a comparator takes whatever the graph holds)
        return bool(abs(actual - expected) <= tolerance)

    return close_within


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------
def _immutable(action: str, name: str, /) -> str:
    """The message behind a refused mutation."""
    return (
        "cannot "
        + action
        + " "
        + name
        + " on Equivalency: it is immutable."
        + " Every method returns a new one, so chain them instead."
    )


def _require_names(names: "tuple[object, ...]", owner: str, /) -> None:
    """Refuse a selection call that names something which is not a name.

    A call with *no* names at all is allowed, following :func:`formatting`, which
    documents an override-less call as "the honest result of
    ``formatting(max_items=configured)`` when nothing was configured". The same
    reading applies to ``excluding(*configured)``. This is a builder rather than
    an assertion, so the rule behind ``_NEEDS_VALUES`` -- an assertion given
    nothing to look for either passes whatever it is handed or can never pass --
    does not reach it: an empty selection decides nothing, and a name that went
    missing shows up in the configuration this engine prints on every failure.

    Takes ``object`` rather than ``str`` so that the type check means something:
    against the declared type it would be a tautology, and a call site is exactly
    where a caller's declaration might be wrong (``_formatters._check`` and
    ``_formatting._checked`` take the same line for the same reason).
    """
    for name in names:
        if not isinstance(name, str):
            message = owner + " needs names, not " + type(name).__name__
            raise TypeError(message)


def _require_class(candidate: object, owner: str, /) -> None:
    """Refuse something ``isinstance`` could not use as a class, for the same reason."""
    if isinstance(candidate, type):
        return
    message = owner + " needs a class to claim, not " + type(candidate).__name__
    raise TypeError(message)


def _require_callable(candidate: object, owner: str, /) -> None:
    """Refuse a comparator that is not callable.

    Worth reporting here rather than at the first comparison: the engine treats a
    comparator that raises as a finding about the *values*, so a non-callable one
    would quietly turn every value of its type into a difference and never say why.
    """
    if callable(candidate):
        return
    message = owner + " needs a callable comparator, not " + type(candidate).__name__
    raise TypeError(message)


def _require_options(candidate: object, /) -> None:
    """Refuse an ``options`` argument that is not an :class:`Equivalency`.

    The one thing that makes :func:`compare` raise. It is not a value being
    compared, it is the instruction for comparing them, and letting a wrong one
    through would produce a puzzling message about the graphs in place of a plain
    one about the call.
    """
    if isinstance(candidate, Equivalency):
        return
    message = "options must be an Equivalency, not " + type(candidate).__name__
    raise TypeError(message)


def _require_depth(candidate: object, /) -> int:
    """Validate a depth bound, or say which way it was wrong."""
    if not isinstance(candidate, int):
        message = "with_max_depth needs an integer, not " + type(candidate).__name__
        raise TypeError(message)
    if candidate < 0:
        message = "with_max_depth needs zero or more, not " + str(candidate)
        raise ValueError(message)
    return candidate


class Equivalency:
    """How two graphs are to be compared. Immutable; every method returns a new one.

        >>> equivalency().excluding("password").ignoring_order()
        equivalency().excluding('password').ignoring_order()

    Immutable for the reason :class:`~lovely_assertions.FormattingOptions` is: a
    configuration built in a fixture is shared by every test that uses it, and one
    that a test could edit would change what the others compare. Building on top
    of a shared one is what the methods are for.

    The fields are public and readable, because a reader debugging an equivalence
    failure is usually asking exactly what was in force -- which is also why
    :func:`compare` prints it into the failure message (a deliberate copy of
    FluentAssertions; it is what makes the assertion debuggable, and it is cheap).
    """

    __slots__ = (
        "all_members",
        "comparators",
        "enums_by_name",
        "excluded_missing",
        "excluded_names",
        "excluded_paths",
        "ignore_order",
        "included_names",
        "max_depth",
    )

    #: Member names skipped wherever they appear.
    excluded_names: frozenset[str]
    #: Paths skipped, together with everything beneath them.
    excluded_paths: frozenset[str]
    #: When non-empty, the only *named* members compared. Members with no name --
    #: a sequence index, a mapping key that is not a string -- are unaffected.
    included_names: frozenset[str]
    #: Whether a sequence's order is part of what is compared. ``False`` -- strict
    #: ordering -- is the default, inverting FluentAssertions on purpose.
    ignore_order: bool
    #: Custom comparators by type, in registration order; the last one that claims
    #: both sides of a pair wins.
    comparators: "tuple[tuple[type[Any], Callable[[Any, Any], bool]], ...]"
    #: Levels of structure the walk descends before falling back to ``==``.
    max_depth: int
    #: Whether two enum members are compared by name rather than by value.
    enums_by_name: bool
    #: Whether a *record* field only the subject carries is compared too. ``False``
    #: -- the expectation drives -- is the default. Mappings are unaffected; see
    #: the module docstring's sixth rule.
    all_members: bool
    #: Whether a *record* field the expectation names and the subject lacks is
    #: skipped instead of reported. Mappings are unaffected, for the same reason.
    excluded_missing: bool

    def __init__(self) -> None:
        """The default configuration. Prefer :func:`equivalency`, which reads better."""
        # Assigned through `object` because `__setattr__` below refuses -- the
        # hand-written half of a frozen dataclass, which cannot be a real one
        # because `dataclasses` may not be imported at module level.
        object.__setattr__(self, "excluded_names", frozenset())
        object.__setattr__(self, "excluded_paths", frozenset())
        object.__setattr__(self, "included_names", frozenset())
        object.__setattr__(self, "ignore_order", False)
        object.__setattr__(self, "comparators", ())
        object.__setattr__(self, "max_depth", _DEFAULT_MAX_DEPTH)
        object.__setattr__(self, "enums_by_name", False)
        object.__setattr__(self, "all_members", False)
        object.__setattr__(self, "excluded_missing", False)

    @override
    def __setattr__(self, name: str, _value: object, /) -> None:
        raise AttributeError(_immutable("set", name))

    @override
    def __delattr__(self, name: str, /) -> None:
        raise AttributeError(_immutable("delete", name))

    def _but(self, name: str, value: object, /) -> "Equivalency":
        """A copy of these options with one field replaced.

        One field, not several, and that is not a simplification: every method
        below changes exactly one, which is what makes a chain of them read as a
        sequence of independent decisions.
        """
        clone = Equivalency()
        for field in Equivalency.__slots__:
            object.__setattr__(clone, field, value if field == name else getattr(self, field))
        return clone

    # -- selection ----------------------------------------------------------
    def excluding(self, *names: str) -> "Equivalency":
        """Skip these member names wherever they appear.

            >>> equivalency().excluding("created_at", "id")
            equivalency().excluding('created_at', 'id')

        A name matches a record field and a string mapping key alike, because to
        the reader of ``{"password": ...}`` and ``User(password=...)`` those are
        the same member. Excluding a member also stops it being reported as
        missing or surplus: a member nobody is comparing cannot be absent.

        Returns a new configuration; this one is unchanged. A call naming nothing
        is allowed and changes nothing, so ``excluding(*configured)`` needs no
        guard. Anything that is not a string raises :class:`TypeError`.
        """
        _require_names(names, "excluding")
        return self._but("excluded_names", self.excluded_names.union(names))

    def excluding_path(self, *paths: str) -> "Equivalency":
        """Skip these exact paths, and everything beneath them.

            >>> equivalency().excluding_path("user.address.city", "items[0]")
            equivalency().excluding_path('items[0]', 'user.address.city')

        A path is written in the notation the failure message prints, so a path a
        reader can see is a path they can paste back in here. Excluding
        ``user.address`` excludes ``user.address.city`` with it -- a subtree, not
        a single member -- because that is what naming a branch of a graph means.

        Returns a new configuration; this one is unchanged. Anything that is not a
        string raises :class:`TypeError`, and the empty path raises
        :class:`ValueError`: it names the root, and a call that excluded everything
        would report two values equivalent without having compared any of them.

        An index only names something while order is being compared. Under
        :meth:`ignoring_order` there is no item at ``items[0]``, so a path through
        an index reaches nothing; exclude the sequence itself, or a field name
        inside its items, instead.
        """
        _require_names(paths, "excluding_path")
        for path in paths:
            if not path:
                message = "excluding_path needs a path; the empty path is the whole value"
                raise ValueError(message)
        return self._but("excluded_paths", self.excluded_paths.union(paths))

    def including(self, *names: str) -> "Equivalency":
        """Compare only these member names, and ignore every other *named* member.

            >>> equivalency().including("id", "total")
            equivalency().including('id', 'total')

        Members with no name are left alone: an item of a list is at an index
        rather than under a name, and a mapping keyed by dates has no names to
        select from. Without that rule, one ``including`` call would silently
        empty every collection in the graph and the comparison would pass by
        having compared nothing.

        ``excluding`` still wins where the two disagree, which is the order that
        lets a shared configuration be narrowed rather than fought with.

        A name **nothing carries** selects nothing, and two records with no
        selected member between them are equivalent -- a mistyped ``including``
        passes silently. That is the same answer ``excluding`` every field gives,
        and it is why the one vacuity that can be spotted at the call,
        ``excluding_path("")``, is refused there. FluentAssertions reports "no
        members were found for comparison" instead; saying so here would need a
        channel for reporting on the comparison itself rather than on the two
        values, which this engine does not have, and guessing at it would break the
        deliberate ``excluding`` case.

        Returns a new configuration; this one is unchanged. Anything that is not a
        string raises :class:`TypeError`.
        """
        _require_names(names, "including")
        return self._but("included_names", self.included_names.union(names))

    def comparing_all_members(self) -> "Equivalency":
        """Compare every member of both records, not only the ones the expectation names.

            >>> equivalency().comparing_all_members()
            equivalency().comparing_all_members()

        By default the expectation drives: a field only the subject carries is not
        a difference, which is what lets a forty-column ORM row be asserted against
        a three-field literal. This turns that off, so that a member the
        expectation never mentioned is reported as surplus.

        Reach for it when the expectation is meant to be *exhaustive* -- a golden
        record, a serialiser's whole output, a model asserted against a full copy
        of itself -- where a field appearing that nobody wrote a line for is the
        regression the test exists to catch.

        Mappings are unaffected, because they already compare both directions: a
        dictionary's keys are its data rather than a declared shape, and an extra
        key in a payload is always a difference. See the module docstring.
        """
        return self._but("all_members", True)

    def excluding_missing(self) -> "Equivalency":
        """Skip expectation members the subject does not carry, instead of reporting them.

            >>> equivalency().excluding_missing()
            equivalency().excluding_missing()

        FluentAssertions' ``ExcludingMissingMembers``. On top of the default it
        takes away the last report about member *sets*, so what is left is the
        members both sides carry, compared by value and nothing else said. Turned
        on together with :meth:`comparing_all_members` it inverts the asymmetry
        instead: the subject drives and the expectation may carry members it does
        not.

        The case it exists for is one expectation shared across versions of a
        model, where a field has been added on one side and the test is about the
        fields that were always there. It is a real hole in a test's cover --
        misspell a field name and the assertion stops looking at it silently -- so
        it is opt-in, and ``excluding`` a field by name is the narrower tool
        whenever the field is known.

        Mappings are unaffected, for the reason given on
        :meth:`comparing_all_members`.
        """
        return self._but("excluded_missing", True)

    # -- ordering -----------------------------------------------------------
    def ignoring_order(self) -> "Equivalency":
        """Compare sequences as bags: same items, any order.

            >>> equivalency().ignoring_order()
            equivalency().ignoring_order()

        Off by default, which is where this library parts company with
        FluentAssertions. C# has no cheap set literal, so ignoring order was the
        kinder default there; Python has ``set``, a ``list`` is ordered by
        definition, and a default under which ``[1, 2]`` matches ``[2, 1]``
        produces tests that pass when they should not.

        An index stops meaning anything here, so ``excluding_path("items[0]")``
        does not reach the items of a sequence whose order is ignored: there is no
        item the path names. Excluding the sequence itself still works, and so
        does ``excluding`` a field name inside the items -- both of those name
        something that survives the reordering.

        It is also the expensive option. Items that are simply equal are paired
        off by equality -- through a hash where there is one, by linear scan where
        there is not -- but whatever is left has to be matched by *comparing* each
        candidate against each remaining item, which is quadratic in full recursive
        comparisons. :data:`_MAX_MATCHING` and :data:`_MAX_SCANNING` bound the two
        halves across the whole comparison, and a comparison that exceeds either
        raises :class:`ValueError` rather than reporting a pairing it did not
        finish. Roughly: three hundred items on each side that nothing pairs by
        equality, or a few thousand unhashable ones, at which point comparing them
        in order is the cheaper question to ask.
        """
        return self._but("ignore_order", True)

    # -- semantics ----------------------------------------------------------
    def using[C](self, kind: type[C], comparator: "Callable[[C, C], bool]") -> "Equivalency":
        """Compare values of ``kind`` with ``comparator`` instead of structurally.

            >>> equivalency().using(float, close_within(0.001))
            equivalency().using(float, close_within)

        This is the vehicle for tolerance -- see :func:`close_within` -- and for
        any type whose members are not the thing being compared. The comparator is
        consulted wherever both sides of a pair are instances of ``kind``, at any
        depth.

        Registrations are consulted **last first**, so a later call narrows an
        earlier one rather than being shadowed by it: ``using(object, ...)``
        followed by ``using(float, ...)`` gives floats the second comparator and
        everything else the first.

        A comparator that raises is not a crash. The pair it could not handle is
        reported as a difference naming the exception, which is the finding: a
        comparator for ``datetime`` handed a ``date`` is a configuration mistake,
        and it should read as one.

        Returns a new configuration; this one is unchanged. A ``kind`` that is not
        a class, or a ``comparator`` that is not callable, raises
        :class:`TypeError` here rather than at the first pair it would have
        decided, where it would have looked like a difference in the values.
        """
        _require_class(kind, "using")
        _require_callable(comparator, "using")
        return self._but("comparators", (*self.comparators, (kind, comparator)))

    def with_max_depth(self, depth: int) -> "Equivalency":
        """Descend at most ``depth`` levels of structure.

            >>> equivalency().with_max_depth(3)
            equivalency().with_max_depth(3)

        At the bound the walk stops descending and compares with ``==`` instead,
        and says so in the message when that comparison fails. ``0`` is legal and
        means "compare the two values, do not take them apart" -- the same reading
        ``FormattingOptions.max_depth`` gives it.

        Returns a new configuration; this one is unchanged. A non-integer raises
        :class:`TypeError` and a negative depth raises :class:`ValueError`.
        """
        return self._but("max_depth", _require_depth(depth))

    def comparing_enums_by_name(self) -> "Equivalency":
        """Compare two enum members by their name rather than by their value.

            >>> equivalency().comparing_enums_by_name()
            equivalency().comparing_enums_by_name()

        The case this exists for is two enums that mean the same thing and are
        numbered differently -- one from a wire protocol, one from the domain
        model. Members of *different* enum classes therefore compare equivalent
        when their names match, which is the whole point and worth knowing.

        It cuts the other way too, and this is the one option in the set that can
        be **stricter** than ``==``. Two ``IntEnum`` members that share a value
        under different names are equal to Python and are not equivalent here,
        because asking for name semantics is asking for the value to stop
        deciding. Every other option only widens; this one replaces.
        """
        return self._but("enums_by_name", True)

    # -- value semantics ----------------------------------------------------
    @override
    def __eq__(self, other: object, /) -> bool:
        """Two configurations that would compare the same way are the same options."""
        if not isinstance(other, Equivalency):
            return NotImplemented
        return self._state() == other._state()

    @override
    def __hash__(self) -> int:
        return hash(self._state())

    def _state(self) -> tuple[object, ...]:
        """Every field, in one tuple, for equality and hashing."""
        return (
            self.excluded_names,
            self.excluded_paths,
            self.included_names,
            self.ignore_order,
            self.comparators,
            self.max_depth,
            self.enums_by_name,
            self.all_members,
            self.excluded_missing,
        )

    @override
    def __repr__(self) -> str:
        """The chain of calls that would build these options -- pasteable as it stands."""
        calls = ["equivalency()"]
        if self.excluded_names:
            calls.append(".excluding(" + _names_text(self.excluded_names) + ")")
        if self.excluded_paths:
            calls.append(".excluding_path(" + _names_text(self.excluded_paths) + ")")
        if self.included_names:
            calls.append(".including(" + _names_text(self.included_names) + ")")
        if self.all_members:
            calls.append(".comparing_all_members()")
        if self.excluded_missing:
            calls.append(".excluding_missing()")
        if self.ignore_order:
            calls.append(".ignoring_order()")
        for kind, comparator in self.comparators:
            calls.append(".using(" + kind.__name__ + ", " + _callable_name(comparator) + ")")
        if self.max_depth != _DEFAULT_MAX_DEPTH:
            calls.append(".with_max_depth(" + str(self.max_depth) + ")")
        if self.enums_by_name:
            calls.append(".comparing_enums_by_name()")
        return "".join(calls)


#: The default configuration. One shared instance rather than a fresh one per
#: call: it is immutable, so sharing it across threads shares nothing that can
#: change, and every method builds a copy anyway.
_DEFAULT: Final = Equivalency()


def equivalency() -> Equivalency:
    """Return the default configuration: strict ordering, ten levels, nothing excluded.

        >>> equivalency().max_depth
        10

    The starting point for a chain of options, and what ``is_equivalent_to`` uses
    when it is given none. The instance is shared and immutable, so keeping it in
    a fixture and building on it in each test is safe.
    """
    return _DEFAULT


def _callable_name(comparator: object, /) -> str:
    """Name a comparator for a rendering; ``<comparator>`` when it will not say."""
    name = getattr(comparator, "__name__", None)
    if isinstance(name, str) and name != "<lambda>":
        return name
    return "<comparator>"


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------
class _Difference:
    """One finding: where it is, and what to say about it.

    Holds *values* rather than rendered text, and that is the load-bearing part.
    Rendering reads ``current_formatting()``, which is a ``ContextVar`` lookup and
    so must not happen on the path a passing assertion takes -- and the walk *is*
    that path, because ``is_not_equivalent_to`` passes by finding differences. So
    the walk gathers, and the reporting path renders.

    The notes that are built during the walk are made of constants, type names and
    counts. None of those reads a ``ContextVar`` or formats a value.
    """

    __slots__ = ("items", "note", "pair", "path", "shows")

    def __init__(
        self,
        path: str,
        shows: str,
        note: str,
        pair: tuple[object, object] | None,
        items: tuple[object, ...],
        /,
    ) -> None:
        self.path: str = path
        self.shows: str = shows
        self.note: str = note
        self.pair: tuple[object, object] | None = pair
        self.items: tuple[object, ...] = items

    @override
    def __repr__(self) -> str:
        return "_Difference(" + repr(self.path) + ", " + repr(self.shows) + ")"


def _pair_difference(path: str, actual: object, expected: object, note: str = "", /) -> _Difference:
    """Two values that disagree, rendered as ``actual instead of expected``."""
    return _Difference(path, _SHOWS_PAIR, note, (actual, expected), ())


def _types_difference(path: str, actual: object, expected: object, /) -> _Difference:
    """Two values with nothing structural in common."""
    return _Difference(path, _SHOWS_TYPES, "", (actual, expected), ())


def _note_difference(path: str, note: str, /) -> _Difference:
    """A finding that is a sentence rather than a pair of values."""
    return _Difference(path, _SHOWS_NOTE, note, None, ())


def _items_difference(path: str, note: str, items: "Sequence[object]", /) -> _Difference:
    """A finding about a set of members: keys, fields or items."""
    return _Difference(path, _SHOWS_ITEMS, note, None, tuple(items))


class _Findings:
    """The differences one comparison has collected, and whether it stopped early.

    The limit does double duty. For a real comparison it is
    :data:`_MAX_DIFFERENCES`, which bounds what the engine spends. For the probe
    that asks "do these two items match?" during order-insensitive pairing it is
    ``1``, which turns the same walk into a boolean that stops at the first
    disagreement instead of describing all of them.
    """

    __slots__ = ("items", "limit")

    def __init__(self, limit: int, /) -> None:
        self.limit: int = limit
        self.items: list[_Difference] = []

    @override
    def __repr__(self) -> str:
        return "_Findings(" + str(len(self.items)) + " of " + str(self.limit) + ")"

    @property
    def full(self) -> bool:
        """Whether this collector has taken everything it is going to take.

        Read at the head of every loop in the walk, which is what makes the bound
        a *stopping* rule rather than a filter: a comparison of two mismatched
        ten-thousand-node graphs stops at two hundred findings instead of
        producing ten thousand and discarding all but two hundred. It is also why
        the report says the comparison stopped rather than counting what it left
        out -- past the bound nothing was looked at, so there is no honest number
        to give.
        """
        return len(self.items) >= self.limit

    def add(self, difference: _Difference, /) -> None:
        """Record a finding, unless this collector has already taken its fill."""
        if self.full:
            return
        self.items.append(difference)


class _TruncatedError(Exception):
    """Raised, and never caught, when a bound stops the pairing of unordered items.

    The one thing this module must not do is hand back a *verdict* it did not
    establish, and pairing that ran out of allowance is exactly that. Reporting it
    as a difference is not symmetric between the two assertions built on top of
    :func:`compare`: a difference makes ``is_equivalent_to`` fail and makes
    ``is_not_equivalent_to`` **pass**, so the same truncation is a wrong failure in
    one direction and a silent wrong pass in the other. Returning ``""`` is worse
    still, and there is no third value a ``str`` can carry.

    So it leaves as an exception, which both directions see identically, and
    :func:`compare` turns it into a :class:`ValueError` -- the same class of answer
    the module already gives a call it cannot serve (see :func:`_require_options`).
    A caller who hits it has asked for an order-insensitive comparison of more
    items than the engine will pair up, and the message says so and says what to do
    instead.

    An ``Exception`` rather than a ``BaseException``: nothing in this module puts a
    ``try``/``except Exception`` between the two ``spend`` methods below and the one
    handler in :func:`compare` that is meant to see this, so no guard swallows it.
    """

    __slots__ = ()


def _out_of_stack(depth: int, /) -> str:
    """Why a comparison that ran out of stack is not a verdict. Failure path only."""
    return (
        "comparing these two graphs used up the interpreter's stack before the walk finished,"
        " so it was stopped rather than answered: an unfinished comparison is not a verdict,"
        " in either direction. The walk was allowed to descend "
        + str(depth)
        + " levels. Lower that with with_max_depth(), compare a smaller part of the graph, or"
        " raise the interpreter's own limit with sys.setrecursionlimit()."
    )


def _stopped(allowance: int, noun: str, /) -> str:
    """Why the comparison stopped, and what to do about it. Failure path only."""
    return (
        "matching the items of an unordered comparison needed more than "
        + str(allowance)
        + " "
        + noun
        + ", so it was stopped rather than answered: an unfinished pairing is not a"
        + " verdict, in either direction. Compare fewer items in one call. A sequence"
        + " is matched this way only under ignoring_order(); without it its items are"
        + " matched by position instead, which is linear. A set is matched this way"
        + " whatever the options say, so there fewer items is the only remedy."
    )


class _Budget:
    """What one comparison may still spend pairing unordered items up.

    Shared by every walk of that comparison, probes included, because the quantity
    worth bounding is the *total*: a hundred items against a hundred is ten
    thousand structural matches at one level, and each of those may itself be a
    hundred-against-a-hundred match one level down. A per-level cap does not bound
    that, and the shape it fails on -- shuffled rows of shuffled cells -- is an
    ordinary thing to write.

    Two meters rather than one, because pairing is spent in two currencies that
    differ by three orders of magnitude a call: :data:`_MAX_MATCHING` counts nodes
    visited inside a structural probe, :data:`_MAX_SCANNING` counts the ``==``
    calls the cheap pass spends on items that cannot be hashed. A single allowance
    covering both would either strangle the cheap pass or fail to bound the
    expensive one. They live on one object so that a walk carries one of these
    rather than two.

    The allowances are read from the module rather than passed in, because there is
    exactly one budget shape and a constructor that could be handed another would
    let a message name a bound that was not the one enforced.

    Spent by pairing alone, and this class is not what bounds the rest. Cutting
    the caller's own walk short would be a wrong failure on honest data, so what
    keeps that walk finite is :class:`_Memo`, which remembers the pairs it has
    already settled and so costs the *nodes* of the two graphs rather than the
    paths through them. That distinction is the whole bound: "linear in the graph"
    is not one, because a handful of objects whose every field points at a shared
    child have paths that multiply level by level, and the comparison that walks
    all of them takes minutes on default options while **passing**.
    """

    __slots__ = ("comparisons", "scans")

    def __init__(self) -> None:
        self.comparisons: int = _MAX_MATCHING
        self.scans: int = _MAX_SCANNING

    @override
    def __repr__(self) -> str:
        return (
            "_Budget(" + str(self.comparisons) + " comparisons, " + str(self.scans) + " scans left)"
        )

    def spend_comparison(self) -> None:
        """Charge one node of one structural probe.

        The subtraction is the whole of the happy path; the message is built on the
        way out, and never for a comparison that finishes.
        """
        self.comparisons -= 1
        if self.comparisons < 0:
            raise _TruncatedError(_stopped(_MAX_MATCHING, _MATCHING_NOUN))

    def spend_scans(self, cost: int, /) -> None:
        """Charge the ``==`` calls one linear scan over unhashable items just cost."""
        self.scans -= cost
        if self.scans < 0:
            raise _TruncatedError(_stopped(_MAX_SCANNING, _SCANNING_NOUN))


#: :attr:`_Memo.leaned_on` when a frame has leaned on no open assumption at all.
#: Larger than any stack position the walk can reach, so that the ordinary
#: ``min``-style comparison against it needs no special case.
_NOTHING_OPEN: Final = 1 << 62


class _Memo:
    """What one comparison has settled, and what it is still assuming.

    Three fields, and they are one mechanism rather than three.

    ``open`` is the cycle stack: every pair currently being compared, mapped to
    its position in that stack. The position, not merely the membership, is what
    the conditional bookkeeping below needs.

    ``settled`` is what makes the walk affordable. Its entries are the pairs a
    *finished* walk found equivalent, keyed by ``(id(actual), id(expected),
    depth)``. Without it the walk costs the number of **paths** through the two
    graphs rather than the number of nodes, because ``open`` forgets a pair the
    moment its frame returns -- which is exactly right for a cycle memo and useless
    as a visited one. A handful of objects whose every field points at a shared
    child multiply their paths level by level, and the comparison takes minutes on
    default options and then **passes**: a hang, with no message, on a test that
    was about to go green. A parent backref plus a couple of shared configuration
    objects is the same shape and is not exotic.

    Only *equivalent* is remembered. A pair that produced findings is walked again
    wherever it is reached again, so the report still names every place the
    difference occurs; the bound on that direction is :data:`_MAX_DIFFERENCES`,
    which stops the whole walk once it has two hundred of them.

    ``depth`` is in the key because it is in the answer: the same pair taken apart
    at depth three may, at depth nine, reach :attr:`Equivalency.max_depth` and be
    reported as a pair the walk declined to open. Handing the shallow verdict to
    the deep reach would drop that report, and "I stopped here" is a finding.

    What the memo does to that bound is worth saying plainly, because it is a
    behaviour difference rather than a saving: the depth bound fires less often
    than the shape of the graph alone would suggest. A pair reached twice at the
    same depth is walked once, so a branch reached again by a second route is not
    descended again and cannot run into the bound there. The comparison answers
    "equivalent" where an unmemoised walk would answer "I ran out of levels", which
    is the better of the two answers and is still not the same one. Nothing moves
    in the other direction: a difference is never remembered, so no finding can be
    lost this way.

    **The id-reuse hazard, and what is done about it.** ``open`` may key on bare
    ids because every object in it is a local of a frame further up the stack and
    so cannot be collected. ``settled`` outlives those frames -- that is the whole
    point of it -- so a value built on the way past, a property that returns a
    fresh object each time, could be freed and have its id handed to something
    else, and a later unrelated pair would be declared equivalent without being
    looked at. That is a wrong *pass*, the one failure this module is written to
    avoid. So each entry's value is the pair itself: holding both objects keeps
    the ids that name them unusable by anything else for as long as the entry
    exists. Keying on something stable instead was the alternative and there is no
    such thing -- an unhashable subject has no identity to key on but ``id``.

    ``conditional`` is the part that is not obvious. A frame that took the cycle
    branch answered "equivalent" by *assuming* the pair further up the stack is
    equivalent, and an assumption is not a result. Recording it unconditionally
    would let a probe that later found a difference leave a wrong entry behind for
    a different probe to read. So a verdict reached while leaning on an assumption
    an enclosing frame has not yet discharged is recorded and its key remembered
    here; the enclosing frame promotes the lot when it finishes clean -- its own
    completion is what discharges its assumption -- and :meth:`forget` drops the
    lot when it does not. Keeping the entry rather than refusing to write one is
    what makes the parent-backref shape fast, since every field of a node that
    points back at its parent leans on that parent's assumption.
    """

    __slots__ = ("conditional", "leaned_on", "open", "settled")

    def __init__(self) -> None:
        self.open: dict[tuple[int, int], int] = {}
        self.settled: dict[tuple[int, int, int], tuple[object, object]] = {}
        self.conditional: list[tuple[int, int, int]] = []
        #: The shallowest still-open assumption the current frame has leaned on.
        self.leaned_on: int = _NOTHING_OPEN

    @override
    def __repr__(self) -> str:
        return "_Memo(" + str(len(self.open)) + " open, " + str(len(self.settled)) + " settled)"

    def lean_on(self, position: int, /) -> None:
        """Record that the assumption open at ``position`` was leaned on."""
        self.leaned_on = min(self.leaned_on, position)

    def forget(self, mark: int, /) -> None:
        """Drop every conditional verdict recorded since ``mark``.

        Called when a frame turns out *not* to be equivalent, which unmakes every
        answer beneath it that assumed it was. The spans nest, so a slice off the
        end is exactly the set to drop.
        """
        conditional = self.conditional
        settled = self.settled
        while len(conditional) > mark:
            del settled[conditional.pop()]


# ---------------------------------------------------------------------------
# The walk
# ---------------------------------------------------------------------------
class _Walk:
    """One traversal of the two graphs: the options, the memo, the findings.

    Written as methods rather than free functions for a plain reason: the recursion
    threads five things through every level, and a free function taking options,
    memo, findings, path and depth alongside the two values is six arguments of
    plumbing around two of subject.

    The memo -- see :class:`_Memo` -- holds ``(id(actual), id(expected))`` for
    every pair currently being compared, which is ``_formatters._RENDERING``'s
    trick with a different carrier. That one has to be a ``ContextVar`` because it
    is re-entered through user code it did not call; this recursion is entirely
    its own, so the memo travels with it -- and a custom comparator that calls
    back into ``is_equivalent_to`` gets a fresh memo, which is the correct answer
    rather than a shared one.
    """

    __slots__ = ("budget", "findings", "matching", "memo", "options")

    def __init__(
        self,
        options: Equivalency,
        memo: _Memo,
        findings: _Findings,
        budget: _Budget,
        matching: bool,
        /,
    ) -> None:
        self.options: Equivalency = options
        self.memo: _Memo = memo
        self.findings: _Findings = findings
        self.budget: _Budget = budget
        #: Whether this walk is deciding a pairing rather than describing a graph.
        #: Only a walk that is spends the *comparison* meter -- the scanning one is
        #: charged wherever the cheap pass runs, matching or not, because that pass
        #: runs before the decision to probe is taken.
        self.matching: bool = matching

    @override
    def __repr__(self) -> str:
        return "_Walk(" + repr(self.options) + ")"

    def compare(self, actual: object, expected: object, path: str, depth: int, /) -> None:
        """Compare one pair, recording whatever it finds.

        The order of the four settling questions is the whole design. Identity
        first, because an object is equivalent to itself under any configuration
        and the check is free. Then a custom comparator, because a caller who
        registered one for this type said that its members are not what they want
        compared. Then enum names, for the same reason. Then ``==`` -- **equality
        settles equivalence**: two values that are equal hold the same information,
        and taking a graph apart to rediscover that would be work spent to reach
        the answer already in hand.
        """
        if actual is expected or self.findings.full:
            return
        if self.matching:
            self.budget.spend_comparison()
        options = self.options
        if options.comparators:
            comparator = _comparator_for(actual, expected, options.comparators)
            if comparator is not None:
                self._by_comparator(comparator, actual, expected, path)
                return
        if options.enums_by_name:
            names = _enum_names(actual, expected)
            if names is not None:
                if names[0] != names[1]:
                    self.findings.add(_pair_difference(path, actual, expected))
                return
        self._by_structure(actual, expected, path, depth)

    def _by_comparator(
        self,
        comparator: "Callable[[Any, Any], bool]",
        actual: object,
        expected: object,
        path: str,
        /,
    ) -> None:
        """Let a registered comparator settle one pair, and survive one that will not."""
        try:
            agreed = bool(comparator(actual, expected))
        # a comparator is user code; its failure is a finding, not a crash
        except Exception as error:
            self.findings.add(
                _note_difference(
                    path,
                    "the comparator for "
                    + type(actual).__name__
                    + " raised "
                    + type(error).__name__,
                )
            )
            return
        if not agreed:
            self.findings.add(_pair_difference(path, actual, expected))

    def _by_structure(self, actual: object, expected: object, path: str, depth: int, /) -> None:
        """Compare a pair nothing else settled: by kind, then member by member."""
        memo = self.memo
        left = id(actual)
        right = id(expected)
        key = (
            None if self.options.excluded_paths and self._path_bound(path) else (left, right, depth)
        )
        if key is not None and key in memo.settled:
            # Already shown equivalent, at this depth, in this comparison. This is
            # the check that makes the walk cost nodes instead of paths; the
            # reasoning, and the id-reuse hazard it has to survive, are on
            # :class:`_Memo`.
            return
        settled = _equal(actual, expected)
        if settled is True:
            return
        resolved = self._composite(actual, expected, settled, path, depth)
        if resolved is None:
            return
        marker = (left, right)
        opened = memo.open.get(marker)
        if opened is not None:
            # Both sides are already being compared further up this same stack, so
            # the structures agree exactly as far as they have been walked. Two
            # graphs that cycle in the same shape are equivalent; declaring a
            # difference here would fail every self-referential value there is.
            # It is an *assumption* rather than a result, so say which one was
            # leaned on, and see the closing bookkeeping below for what that costs.
            memo.lean_on(opened)
            return
        position = len(memo.open)
        memo.open[marker] = position
        enclosing = memo.leaned_on
        memo.leaned_on = _NOTHING_OPEN
        differences = len(self.findings.items)
        provisional = len(memo.conditional)
        try:
            self._members(actual, expected, resolved, path, depth)
        finally:
            # Discarded rather than left behind: a marker that outlived its frame
            # would make a *later* sibling with a recycled id look like a cycle.
            del memo.open[marker]
        # May this pair's verdict outlive the frame that reached it? Not if the
        # pair turned out to differ -- nothing is remembered in that direction, and
        # everything settled beneath it while assuming it did not has to go with
        # it. Unconditionally if the walk leaned on no open assumption but its own,
        # since finishing clean is what discharges a pair's own assumption, and at
        # that point every verdict recorded beneath is unconditional too.
        # Otherwise the verdict is real but provisional -- it rests on a pair
        # further up the stack that has not finished -- so it is recorded, which is
        # what makes the other five fields of a node whose child points back at it
        # cost nothing, and its key is remembered for that frame to promote or drop.
        #
        # A frame with **no key of its own** takes neither of those exits. It has
        # none because an exclusion reaches inside it (:meth:`_path_bound`), so
        # finishing clean is not a fact about the pair, it is a fact about the pair
        # *at this path* -- and anything settled below while assuming this frame
        # was equivalent inherited that. Dropping the lot is what keeps the
        # exclusion from leaking: a field excluded at ``a.tag`` lets the frame at
        # ``a`` finish clean, a descendant that points back at ``a`` takes the
        # cycle branch on the strength of it, and without this the verdict that
        # reached would go on to answer for the same pair at ``d.a``, where nothing
        # is excluded and the field disagrees. That is a silent wrong pass, and it
        # is not enough to drop only when this frame is the one discharging the
        # assumption: :meth:`_Memo.lean_on` keeps the *shallowest* position leaned
        # on, so a verdict that touched this frame and something above it travels
        # straight past here carrying the higher position. Hence one drop covering
        # both exits, written as the two questions rather than the three outcomes.
        leaned_on = memo.leaned_on
        memo.leaned_on = enclosing
        equivalent = len(self.findings.items) == differences
        outstanding = leaned_on < position
        if equivalent and outstanding:
            memo.lean_on(leaned_on)
        if key is None or not equivalent:
            memo.forget(provisional)
            return
        if outstanding:
            memo.settled[key] = (actual, expected)
            memo.conditional.append(key)
            return
        del memo.conditional[provisional:]
        memo.settled[key] = (actual, expected)

    def _composite(
        self, actual: object, expected: object, settled: bool | None, path: str, depth: int, /
    ) -> tuple[str, tuple[str, ...], tuple[str, ...]] | None:
        """The kind and names to walk this pair by, or ``None`` when there is nothing to walk.

        Three ways a pair that equality did not settle still has no members to walk:
        the two values are of different kinds, they are both leaves, or the walk has
        reached the depth bound. Each records its own finding, because in each case
        the reason there is nothing to take apart **is** the finding.

        Split out of :meth:`_by_structure` so that the memo bookkeeping around the
        descent reads as one thing rather than as the tail of a list of special
        cases. Called before the descent and returned from before it, so it costs no
        stack while the walk is deep -- and not called at all for the commonest node
        of a passing comparison, the pair ``==`` agrees on.
        """
        actual_kind, actual_names = _classify(actual)
        expected_kind, expected_names = _classify(expected)
        if actual_kind != expected_kind:
            self.findings.add(_types_difference(path, actual, expected))
            return None
        if actual_kind == _KIND_LEAF:
            self.findings.add(_leaf_difference(path, actual, expected, settled))
            return None
        if depth >= self.options.max_depth:
            self.findings.add(
                _pair_difference(
                    path,
                    actual,
                    expected,
                    "(not taken apart: the maximum depth of "
                    + str(self.options.max_depth)
                    + " stops here)",
                )
            )
            return None
        return (actual_kind, actual_names, expected_names)

    def _path_bound(self, path: str, /) -> bool:
        """Whether what is under this path depends on *where* this path is.

        A verdict may be remembered under a key that says nothing about where the
        pair was reached only if where it was reached cannot change it. One option
        makes it change: :meth:`Equivalency.excluding_path` names a branch, so the
        same two objects can be equivalent under one parent and not under another.

        The test is deliberately conservative and cheap. If no excluded path even
        starts with this one, nothing under here can be excluded and the verdict is
        about the pair alone. If one does, this subtree is walked afresh every time
        it is reached -- the slow answer, and the right one. Excluding a path
        therefore costs the memo only for the branch it names, rather than turning
        it off for the whole comparison, which would let one option bring back the
        shape that hangs.

        **A yes here has to reach further than this pair**, or it is a silent wrong
        pass. Withholding a key from *this* frame is not enough, because a frame an
        exclusion reaches into can finish clean **because** of the exclusion; a
        descendant that points back at it
        then takes the cycle branch on the strength of that, and the verdict it
        reaches is contingent on where it was reached from even though its own path
        is nowhere near an exclusion. So :meth:`_by_structure` also drops, rather
        than keeps, everything settled beneath a frame this returns ``True`` for.
        Conservative again: some of what it drops was sound.

        Asked only when there is an exclusion to ask about; the caller guards the
        call, so an ordinary comparison never makes it.
        """
        for candidate in self.options.excluded_paths:  # noqa: SIM110  (a generator expression would allocate)
            if candidate.startswith(path):
                return True
        return False

    def _members(
        self,
        actual: object,
        expected: object,
        resolved: tuple[str, tuple[str, ...], tuple[str, ...]],
        path: str,
        depth: int,
        /,
    ) -> None:
        """Route a composite pair of one kind to the branch that walks it.

        The kind and the field names are carried in rather than recovered:
        resolving a record's fields runs ``dataclasses.fields`` or walks an MRO,
        and doing it twice per node is work the caller has already done.
        """
        kind, actual_names, expected_names = resolved
        if kind == _KIND_MAPPING:
            self._mapping(actual, expected, path, depth)
        elif kind == _KIND_SET:
            self._set(actual, expected, path, depth)
        elif kind == _KIND_SEQUENCE:
            self._sequence(actual, expected, path, depth)
        else:
            self._record(actual, expected, (actual_names, expected_names), path, depth)

    # -- selection ----------------------------------------------------------
    def _selects(self, name: str | None, path: str, /) -> bool:
        """Whether a member with this name, at this path, is compared at all.

        ``name`` is ``None`` for a member that has none -- an index, a mapping key
        that is not a string. Those are unreachable by ``excluding``/``including``
        and are selected by path alone.
        """
        options = self.options
        if name is not None:
            if name in options.excluded_names:
                return False
            if options.included_names and name not in options.included_names:
                return False
        return not _path_excluded(path, options.excluded_paths)

    # -- mappings -----------------------------------------------------------
    def _mapping(self, actual: object, expected: object, path: str, depth: int, /) -> None:
        """Values under shared keys first, then keys only one side carries.

        The order is the mapping describer's, for the mapping describer's reason:
        a wrong value under a right key is what a mapping comparison usually fails
        on, and when it is a key that is absent there are no value lines in the way.
        """
        if not is_mapping(actual) or not is_mapping(expected):
            # A route is remembered against `type(value)`, but the question behind
            # it is asked of `__class__`, which a proxy or a lazy stand-in answers
            # per instance. So a pair can arrive here routed to a shape neither
            # side turns out to have. The kind was a guess about the type and the
            # guess missed, so the pair is reported the way a leaf is: equality
            # decides, which is the one answer that was not guessed. Returning in
            # silence would declare it *equivalent*. Equality is asked again rather
            # than carried down from the caller, so that an ordinary mapping node
            # pays nothing for a branch it never takes. The two checks also narrow
            # `object` down to something with keys, on a path that is about to read
            # every one of them.
            self.findings.add(_leaf_difference(path, actual, expected, _equal(actual, expected)))
            return
        actual_keys = _safe_list(actual)
        expected_keys = _safe_list(expected)
        if actual_keys is None or expected_keys is None:
            self.findings.add(_note_difference(path, "the keys of this mapping could not be read"))
            return
        missing = self._shared_keys(actual, expected, expected_keys, path, depth)
        extra = [
            key
            for key in actual_keys
            if not _has_key(expected, key) and self._selects(_key_name(key), _key_path(path, key))
        ]
        if missing:
            self.findings.add(_items_difference(path, "missing keys:", _sorted(missing)))
        if extra:
            self.findings.add(_items_difference(path, "extra keys:", _sorted(extra)))

    def _shared_keys(
        self,
        actual: "Mapping[object, object]",
        expected: "Mapping[object, object]",
        keys: list[object],
        path: str,
        depth: int,
        /,
    ) -> list[object]:
        """Walk every selected key of ``expected``; hand back the ones ``actual`` lacks."""
        missing: list[object] = []
        for key in keys:
            if self.findings.full:
                return missing
            child = _key_path(path, key)
            if not self._selects(_key_name(key), child):
                continue
            if not _has_key(actual, key):
                missing.append(key)
                continue
            pair = _read_keys(actual, expected, key)
            if pair is None:
                self.findings.add(_note_difference(child, "this entry could not be read"))
                continue
            self.compare(pair[0], pair[1], child, depth + 1)
        return missing

    # -- sets ---------------------------------------------------------------
    def _set(self, actual: object, expected: object, path: str, depth: int, /) -> None:
        """A set has no position to report, so it is matched the unordered way.

        Items that are simply equal pair off through the hash the set is built on,
        which is the comparison a set already makes; anything left is matched
        structurally, so a set of records still honours the options.
        """
        actual_items = _safe_list(actual)
        expected_items = _safe_list(expected)
        if actual_items is None or expected_items is None:
            self.findings.add(_note_difference(path, "the items of this set could not be read"))
            return
        self._unordered(actual_items, expected_items, path, depth)

    # -- sequences ----------------------------------------------------------
    def _sequence(self, actual: object, expected: object, path: str, depth: int, /) -> None:
        """Position by position, unless the caller opted out of order."""
        actual_items = _safe_list(actual)
        expected_items = _safe_list(expected)
        if actual_items is None or expected_items is None:
            self.findings.add(
                _note_difference(path, "the items of this sequence could not be read")
            )
            return
        if self.options.ignore_order:
            self._unordered(actual_items, expected_items, path, depth)
            return
        shared = min(len(actual_items), len(expected_items))
        for index in range(shared):
            if self.findings.full:
                return
            child = _index_path(path, index)
            if not self._selects(None, child):
                continue
            self.compare(actual_items[index], expected_items[index], child, depth + 1)
        if len(actual_items) == len(expected_items):
            return
        self.findings.add(
            _note_difference(
                path,
                "lengths differ: "
                + count_of(len(actual_items), "item")
                + ", expected "
                + str(len(expected_items)),
            )
        )
        # Reported at the first index with no counterpart rather than at the
        # sequence itself: a surplus item has a *where*, and every other finding
        # this engine produces names one. The length line above is the summary;
        # this is the location.
        tail = _index_path(path, shared)
        if len(actual_items) > shared:
            self.findings.add(_items_difference(tail, "extra items:", actual_items[shared:]))
        if len(expected_items) > shared:
            self.findings.add(_items_difference(tail, "missing items:", expected_items[shared:]))

    def _unordered(
        self, actual_items: list[object], expected_items: list[object], path: str, depth: int, /
    ) -> None:
        """Pair items up in any order: cheaply by equality, then by comparison.

        The two passes are not an optimisation on top of one algorithm, they are
        the algorithm. Structural pairing is quadratic *in full recursive
        comparisons*, so anything equality can settle has to be settled by equality
        first; what survives is the handful that genuinely needs comparing.

        The cheap pass pairs unhashable items too, which is what lets a shuffled
        list of JSON records come back equivalent at all: a ``dict`` has no hash,
        so without a surrogate for it (see :func:`_stand_in`) every record arrives
        at the structural pass unpaired and the whole comparison is spent there.
        """
        surplus, absent = _equality_leftovers(actual_items, expected_items, self.budget)
        if not surplus and not absent:
            return
        absent = self._pair_up(surplus, absent, depth)
        if absent:
            self.findings.add(_items_difference(path, "missing items:", _sorted(absent)))
        if surplus:
            self.findings.add(_items_difference(path, "extra items:", _sorted(surplus)))

    def _pair_up(self, surplus: list[object], absent: list[object], depth: int, /) -> list[object]:
        """Match each absent item against a surplus one, consuming as it goes.

        Greedy rather than optimal: finding the best overall pairing is an
        assignment problem, and the answer it would change is which of two equally
        unmatched items gets reported. ``surplus`` is edited in place, so what is
        left in it afterwards is what nothing matched.
        """
        unmatched: list[object] = []
        for item in absent:
            index = self._first_match(surplus, item, depth)
            if index is None:
                unmatched.append(item)
            else:
                del surplus[index]
        return unmatched

    def _first_match(self, candidates: list[object], item: object, depth: int, /) -> int | None:
        """Where in ``candidates`` an item equivalent to ``item`` sits, if anywhere."""
        for index, candidate in enumerate(candidates):
            if self._matches(candidate, item, depth):
                return index
        return None

    def _matches(self, actual: object, expected: object, depth: int, /) -> bool:
        """Whether two items are equivalent, without recording why they are not.

        The same walk with a collector that holds one finding: it stops at the
        first disagreement, which is all a pairing decision needs. The memo is
        shared, because this is still the same traversal -- so a pair a probe has
        already settled costs the next probe nothing -- and so are both budgets,
        because this is the work they exist to bound.

        There is no such thing here as a probe cut short. A budget that runs out
        raises out of the whole comparison (see :class:`_TruncatedError`), so every
        answer this returns is one a finished walk gave -- rather than a maybe that
        the caller above would have to read as a no.
        """
        findings = _Findings(1)
        _Walk(self.options, self.memo, findings, self.budget, True).compare(
            actual, expected, "", depth + 1
        )
        return not findings.items

    # -- records ------------------------------------------------------------
    def _record(
        self,
        actual: object,
        expected: object,
        names: tuple[tuple[str, ...], tuple[str, ...]],
        path: str,
        depth: int,
        /,
    ) -> None:
        """Field by field, by name, across types.

        Two records of *different* classes are compared here without complaint,
        and that is the point of the assertion: a wire model and a domain model
        that carry the same information are equivalent however their ``__eq__``
        feels about each other.

        **The expectation drives**, which is the module docstring's sixth rule and
        is enforced here, in the one branch it is about. The loop is over the
        expectation's fields; a field only the subject carries is not looked at and
        not reported. ``comparing_all_members()`` puts the second loop back, and
        ``excluding_missing()`` drops the first report. Neither of them reaches
        :meth:`_mapping`, which compares both directions whatever the options say.

        A symmetric comparison is what the asymmetry is chosen over, and the reason
        is the commonest use of the assertion there is:
        ``expect(row).is_equivalent_to(Expected(id=1, total=5))`` against a
        forty-column ORM row is unwritable if the thirty-eight columns the test is
        not about are reported as surplus. So naming a member is what asks for it
        to be compared, and asking for the other direction is a method.
        """
        options = self.options
        actual_names, expected_names = names
        on_actual = frozenset(actual_names)
        missing: list[object] = []
        looked_at = 0
        readable = 0
        for name in expected_names:
            if self.findings.full:
                return
            child = _attribute_path(path, name)
            if not self._selects(name, child):
                continue
            if name not in on_actual:
                if not options.excluded_missing:
                    missing.append(name)
                continue
            looked_at += 1
            readable += self._field(actual, expected, name, child, depth)
        if looked_at and not readable:
            # A declaration nothing backs is not a resolution. A tuple subclass is
            # free to set ``_fields`` to names it does not carry, and an engine
            # that trusts the declaration, reads nothing, and calls that "no
            # differences" turns a hostile class into a green test.
            self.findings.add(_pair_difference(path, actual, expected, _UNRESOLVED))
            return
        if missing:
            self.findings.add(_items_difference(path, "missing fields:", missing))
        if not options.all_members:
            return
        on_expected = frozenset(expected_names)
        extra = [
            name
            for name in actual_names
            if name not in on_expected and self._selects(name, _attribute_path(path, name))
        ]
        if extra:
            self.findings.add(_items_difference(path, "extra fields:", extra))

    def _field(
        self, actual: object, expected: object, name: str, child: str, depth: int, /
    ) -> bool:
        """Compare one field, and say whether either side gave it up at all.

        The answer feeds the resolver's own sanity check in :meth:`_record`, which
        is why it is returned rather than dropped.

        A declared member is not necessarily an assigned one: a ``__slots__``
        entry that was never written to raises ``AttributeError``, and so does a
        property that decides it has nothing to return. When *neither* side will
        give the field up, that is a member neither object has rather than a
        member they disagree about, and reporting it would fail an object against
        an identical one. When only one side will, the two objects genuinely
        differ and the finding says which side is holding the value.

        Guarded per field rather than around the loop on purpose: one hostile
        member of a twelve-field record must cost the reader that field, not the
        other eleven.
        """
        actual_value = _read_field(actual, name)
        expected_value = _read_field(expected, name)
        if actual_value is _UNREADABLE and expected_value is _UNREADABLE:
            return False
        if actual_value is _UNREADABLE:
            self.findings.add(_note_difference(child, _NOT_ON_ACTUAL))
            return True
        if expected_value is _UNREADABLE:
            self.findings.add(_note_difference(child, _NOT_ON_EXPECTED))
            return True
        self.compare(actual_value, expected_value, child, depth + 1)
        return True


# ---------------------------------------------------------------------------
# The entry point
# ---------------------------------------------------------------------------
def compare(actual: object, expected: object, options: Equivalency, /) -> str:
    """An account of how two graphs differ, or ``""`` when they are equivalent.

        >>> compare({"id": 1}, {"id": 1}, equivalency())
        ''

    ``""`` means equivalent, so the caller can branch on emptiness. Otherwise a
    block that starts with a newline and does not end with one, ready to be
    appended to a one-line failure message -- the same shape
    ``_diff.describe_difference`` returns.

    **No value makes this raise.** A property that raises, a hostile ``__repr__``,
    an ``__eq__`` that throws, a cycle: each costs detail, never the caller's test.
    Note which way the degradation runs, because it is the opposite of ``_diff``'s.
    There, ``""`` is a block nobody could build and the message stands without it;
    here ``""`` is the verdict *equivalent*, so a comparison that could not be
    completed reports a difference rather than falling silent. A broken engine
    fails a test that should have passed, which is loud; the alternative passes a
    test that should have failed, which is not.

    Two things that are *not* values do raise, at the call. A misconfigured
    ``options`` does, because the failure it prevents is otherwise a confusing
    message about the values rather than a clear one about the mistake. And an
    order-insensitive comparison of more items than :data:`_MAX_MATCHING` or
    :data:`_MAX_SCANNING` will pay for raises :class:`ValueError` naming the bound
    it stopped at -- not because a value misbehaved, but because the pairing never
    finished and neither answer was reached. See :class:`_TruncatedError` for why
    that cannot be reported as a difference instead.

    "Never raises" means never for an ``Exception``, which is where every guard in
    this module and in ``_diff`` is drawn. A ``BaseException`` -- a ``Ctrl-C``, an
    exiting interpreter -- goes through, because a value that raises one of those
    is not reporting a difference, it is asking everything to stop.
    """
    _require_options(options)
    # Forget every remembered route if the ABC registry has moved; see
    # `_ROUTE_TOKEN`. Written here rather than called, because a helper's frame
    # is half the cost of the check on a comparison that answers in a microsecond.
    token = get_cache_token()
    if token != _ROUTE_TOKEN[0]:
        _ROUTE_BY_TYPE.clear()
        _ROUTE_TOKEN[0] = token
    findings = _Findings(_MAX_DIFFERENCES)
    try:
        _Walk(options, _Memo(), findings, _Budget(), False).compare(actual, expected, "", 0)
    except _TruncatedError as stopped:
        # Caught before the blanket handler below, and deliberately not returned as
        # a difference: this is the one outcome that is neither verdict.
        raise ValueError(str(stopped)) from None
    except RecursionError:
        # The same rule, for the other way a walk can stop without finishing. A
        # `RecursionError` is not a statement about the values -- it is the walk
        # saying it never got to the end of them -- so it is caught here rather
        # than by the blanket handler below, which would turn it into "the two are
        # not equivalent", which `is_not_equivalent_to` reads as "they differ" and
        # **passes**. A graph a couple of hundred levels deep with a
        # `with_max_depth` to match is all it takes, and the green is silent.
        raise ValueError(_out_of_stack(options.max_depth)) from None
    # the contract: a value never turns into an error here
    except Exception:
        return (
            "\n" + _INDENT + "the comparison could not be completed, so the two are not equivalent"
        )
    if not findings.items:
        return ""
    try:
        return _render(findings, options)
    # same contract, one step later
    except Exception:
        return "\n" + _INDENT + "they are not equivalent, but the differences could not be rendered"


def differs(actual: object, expected: object, options: Equivalency, /) -> bool:
    """Whether two graphs differ, without saying how.

        >>> differs({"id": 1}, {"id": 1}, equivalency())
        False
        >>> differs({"id": 1}, {"id": 2}, equivalency())
        True

    :func:`compare`'s verdict without :func:`compare`'s report, for the two callers
    that are about to throw the report away. ``Expect.is_equivalent_to`` needs a
    boolean to decide whether to pass; ``Expect.is_not_equivalent_to`` is the
    sharper case, because the report it builds and drops is on the branch where it
    **passes**, and building it means gathering up to two hundred ``_Difference``
    records, rendering every one of them and reading
    :func:`~lovely_assertions.current_formatting` -- a ``ContextVar`` -- several
    times over. A passing assertion is meant to cost a comparison and a return.

    The saving is in the collector rather than in a second algorithm: this is the
    same walk with :class:`_Findings` bounded at one, which is what the pairing
    probes already use, so it stops at the first disagreement instead of
    describing all of them.

    **It answers the verdict and never the message, and the caller must keep that
    true.** A ``True`` here is a promise that :func:`compare` has something to
    report, not a substitute for it: the failure path has to call :func:`compare`
    and print the block, or the assertion loses the account of *what* differed,
    which is the whole product. So the fast path is the passing one, in both
    directions, and the report is built exactly where it is used.

    Raises what :func:`compare` raises and for the same reasons -- a misconfigured
    ``options``, a pairing that ran out of allowance, a walk that ran out of stack
    -- because those are not verdicts and a boolean has no room for a third answer
    either.
    """
    _require_options(options)
    # Forget every remembered route if the ABC registry has moved; see
    # `_ROUTE_TOKEN`. Written here rather than called, because a helper's frame
    # is half the cost of the check on a comparison that answers in a microsecond.
    token = get_cache_token()
    if token != _ROUTE_TOKEN[0]:
        _ROUTE_BY_TYPE.clear()
        _ROUTE_TOKEN[0] = token
    findings = _Findings(1)
    try:
        _Walk(options, _Memo(), findings, _Budget(), False).compare(actual, expected, "", 0)
    except _TruncatedError as stopped:
        raise ValueError(str(stopped)) from None
    except RecursionError:
        raise ValueError(_out_of_stack(options.max_depth)) from None
    # the contract: a comparison that broke is not an equivalence
    except Exception:
        return True
    return bool(findings.items)


# ---------------------------------------------------------------------------
# Rendering. Everything below here runs on the reporting path only, which is what
# licenses it to read `current_formatting()`.
# ---------------------------------------------------------------------------
def _render(findings: _Findings, options: Equivalency, /) -> str:
    """The block: the differences, what was left out, and what was in force."""
    max_items = current_formatting().max_items
    lines = [_INDENT + _render_difference(difference) for difference in findings.items[:max_items]]
    elided = len(findings.items) - max_items
    if elided > 0:
        lines.append(_INDENT + "... (" + count_of(elided, "more difference") + ")")
    if findings.full:
        # Said as well as the count, not instead of it: the count is how many
        # findings are being held back, and this is the separate fact that the
        # walk stopped looking. Two mismatched graphs of ten thousand nodes have
        # both to report, and neither says the other.
        lines.append(
            _INDENT
            + "... (the comparison stopped at "
            + count_of(findings.limit, "difference")
            + ")"
        )
    lines.append(_INDENT + "(compared with " + _configuration(options) + ")")
    return "\n" + "\n".join(lines)


def _render_difference(difference: _Difference, /) -> str:
    """One finding as one line: where it is, then what is wrong there."""
    where = _clip(difference.path or _ROOT)
    shows = difference.shows
    if shows == _SHOWS_NOTE:
        return where + ": " + difference.note
    if shows == _SHOWS_ITEMS:
        return where + ": " + difference.note + " " + _render_items(difference.items)
    pair = difference.pair
    if pair is None:
        # Unreachable: the two remaining shapes are built with a pair. Kept so
        # that the narrowing is done by the code rather than by a cast.
        return where + ": " + difference.note
    if shows == _SHOWS_TYPES:
        return where + ": " + _different_types_note(pair[0], pair[1])
    return where + ": " + _values_note(pair[0], pair[1], difference.note)


def _values_note(actual: object, expected: object, note: str, /) -> str:
    """``actual instead of expected``, and the one case where that says nothing.

    Compared unclipped: two values that part company past the clip would otherwise
    be declared identical-looking, which is a claim rather than a truncation.
    """
    rendered = format_value(actual)
    other = format_value(expected)
    if rendered == other:
        body = _look_alike_note(actual, expected, _clip(rendered))
    else:
        body = _clip(rendered) + " instead of " + _clip(other)
    if note:
        return body + " " + note
    return body


def _look_alike_note(actual: object, expected: object, rendered: str, /) -> str:
    """Why two values that render the same are still not equivalent.

    This is the failure that reads as a bug in the test runner, and it has a small
    number of causes worth naming outright. The last of them is particular to this
    assertion: a type with neither an ``__eq__`` nor any readable member gives the
    engine nothing at all to compare, and saying so is more use than repeating the
    ``repr`` twice.
    """
    if is_float_nan(actual) or is_float_nan(expected):
        return "both are " + rendered + ", and a NaN is equal to nothing, itself included"
    subject_type = type(actual)
    if subject_type is type(expected) and subject_type.__eq__ is object.__eq__:
        return (
            "both render as "
            + rendered
            + ", but "
            + subject_type.__name__
            + " has no __eq__ and no members to compare, so they compare by identity"
        )
    return "both render as " + rendered + ", but they are not equivalent"


def _different_types_note(actual: object, expected: object, /) -> str:
    """Name both types, in the vocabulary the rest of the block uses."""
    actual_type = type(actual)
    expected_type = type(expected)
    actual_name = actual_type.__name__
    expected_name = expected_type.__name__
    if actual_name == expected_name:
        # Two classes of one name is the case where the two reprs are of no help
        # whatsoever, so it is the one worth spelling out in full.
        actual_name = qualified(actual_type)
        expected_name = qualified(expected_type)
    if actual_name == expected_name:
        return (
            "types differ: both are called "
            + actual_name
            + ", but they are not the same class object"
        )
    return "types differ: " + actual_name + " instead of " + expected_name


def _leaf_difference(
    path: str, actual: object, expected: object, settled: bool | None, /
) -> _Difference:
    """A pair with no members to take apart, and the note when ``==`` would not answer."""
    if settled is None:
        return _pair_difference(
            path,
            actual,
            expected,
            "(comparing them raised " + _comparison_error(actual, expected) + ")",
        )
    return _pair_difference(path, actual, expected)


def _comparison_error(actual: object, expected: object, /) -> str:
    """Name the exception ``==`` raised, by asking it again on the reporting path.

    Asked a second time rather than carried out of the walk: an exception held in
    a difference record keeps a traceback, and with it every frame and local of
    the failing comparison, alive until the message is built. The second call
    costs one more failed comparison on a path that is already reporting.
    """
    try:
        _ = actual == expected
    # naming it is the whole point
    except Exception as error:
        return type(error).__name__
    return "an exception"


def _configuration(options: Equivalency, /) -> str:
    """The effective configuration, in one clause per decision.

    Printed on every failure, deliberately, and copied from FluentAssertions
    because it is what makes an equivalence failure debuggable: a reader who
    excluded the wrong field, or forgot ``ignoring_order()``, can see that they
    did without reading the test's fixtures. The two defaults are printed too --
    they are the two settings a surprising result is most often explained by.
    """
    clauses = [
        "order ignored" if options.ignore_order else "strict ordering",
        "maximum depth " + str(options.max_depth),
    ]
    if options.excluded_names:
        clauses.append("excluding members " + _render_names(options.excluded_names))
    if options.excluded_paths:
        clauses.append("excluding paths " + _render_names(options.excluded_paths))
    if options.included_names:
        clauses.append("comparing only members " + _render_names(options.included_names))
    if options.all_members:
        clauses.append("comparing every member of both")
    if options.excluded_missing:
        clauses.append("skipping members the subject does not carry")
    if options.enums_by_name:
        clauses.append("comparing enums by name")
    if options.comparators:
        claimed = [kind.__name__ for kind, _ in options.comparators]
        clauses.append("a custom comparator for " + ", ".join(claimed))
    return ", ".join(clauses)


def _render_names(names: "Iterable[str]", /) -> str:
    """A set of names for a *message*: sorted, so two runs read the same, and bounded."""
    ordered = sorted(names)
    max_items = current_formatting().max_items
    shown = [repr(name) for name in ordered[:max_items]]
    elided = len(ordered) - max_items
    if elided > 0:
        return ", ".join(shown) + ", ... (" + str(elided) + " more)"
    return ", ".join(shown)


def _names_text(names: "Iterable[str]", /) -> str:
    """The same names for a ``repr``: sorted, and never elided.

    A ``repr`` is a faithful account of an object, and Python's own reprs do not
    truncate. Eliding here would produce a line that reads like the call that
    built the options and is not it.
    """
    return ", ".join(repr(name) for name in sorted(names))


def _render_items(items: "tuple[object, ...]", /) -> str:
    """Render a computed list of members, truncated like every other collection."""
    max_items = current_formatting().max_items
    shown = [render_operand(item) for item in items[:max_items]]
    elided = len(items) - max_items
    if elided > 0:
        return "[" + ", ".join(shown) + ", ... (" + str(elided) + " more)]"
    return "[" + ", ".join(shown) + "]"


def _clip(text: str, /) -> str:
    """Cut an over-long rendering down, saying how much was cut."""
    max_chars = current_formatting().max_chars
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "... (" + str(len(text) - max_chars) + " more characters)"


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
def _attribute_path(parent: str, name: str, /) -> str:
    """``user.address.city``. The root is the empty path, so it grows no leading dot."""
    if not parent:
        return name
    return parent + "." + name


def _index_path(parent: str, index: int, /) -> str:
    """``items[3]``. An index has no name, so it is always bracketed."""
    return parent + "[" + str(index) + "]"


def _key_path(parent: str, key: object, /) -> str:
    """``rows.id`` for a key that could be written as a name, ``rows[3]`` otherwise.

    The dot for identifier-like string keys is not sugar. A path is printed so
    that it can be pasted into :meth:`Equivalency.excluding_path`, and a reader
    holding ``{"user": {"city": ...}}`` writes ``user.city`` -- the notation is
    worth nothing if it is not the one they would have reached for. Keys that are
    not names keep their ``repr`` inside brackets, which is likewise what they
    would type.

    The cost is that ``rows.id`` no longer says whether ``id`` was a key or an
    attribute. That ambiguity is real and is accepted: the two are the same member
    to the reader, and it is exactly the case where the two notations would
    otherwise disagree about the same graph.
    """
    if isinstance(key, str) and key.isidentifier():
        return _attribute_path(parent, key)
    return parent + "[" + _path_key_text(key) + "]"


def _path_key_text(key: object, /) -> str:
    """One key inside a path: its ``repr``, bounded by a constant.

    ``repr`` rather than ``format_value``, because this is text a user has to be
    able to type back: a registered formatter renders a key for a *reader*, and
    the two must not diverge in the one string the API matches against.
    """
    try:
        text = repr(key)
    # a hostile __repr__ costs the key's name, not the walk
    except Exception:
        return "<unreadable key>"
    if len(text) <= _MAX_PATH_KEY_CHARS:
        return text
    return text[:_MAX_PATH_KEY_CHARS] + "... (" + str(len(text) - _MAX_PATH_KEY_CHARS) + " more)"


def _path_excluded(path: str, excluded: frozenset[str], /) -> bool:
    """Whether a path, or a branch it hangs off, was excluded.

    A prefix rule rather than an equality one: ``excluding_path("user.address")``
    excludes ``user.address.city`` with it. The character after the prefix has to
    be a separator, or ``excluding_path("user")`` would take ``username`` with it
    -- a member the caller never named, silently dropped from the comparison, and
    the one way an exclusion can turn into a wrong pass. Index paths are already
    unambiguous, because the closing bracket keeps ``items[1]`` from being a prefix
    of ``items[10]`` at all; it is names that need the rule.
    """
    if not excluded or not path:
        return False
    for candidate in excluded:
        if path == candidate:
            return True
        if path.startswith(candidate) and path[len(candidate) : len(candidate) + 1] in (".", "["):
            return True
    return False


# ---------------------------------------------------------------------------
# Kinds
# ---------------------------------------------------------------------------
#: What a type declares, worked out once. Both caches below are keyed on the
#: class object and hold an answer that is a property of that class: which fields
#: it declares, and which ``__slots__`` entries its MRO carries. Neither reads
#: anything from an instance, which is what makes caching them sound rather than
#: an approximation.
#:
#: A class rewritten after it has been compared -- ``__slots__`` reassigned, a
#: second ``@dataclass`` applied to the same object -- would keep the answer taken
#: the first time. That is accepted rather than defended against: reassigning
#: ``__slots__`` does not move an instance's storage, and neither shape occurs
#: outside a test that is deliberately building one.
_DECLARED_BY_TYPE: dict[type, "tuple[str, ...] | None"] = {}


#: What :func:`_classify` decided for a type, or :data:`_ASK_THE_VALUE` when the
#: answer depends on the instance rather than on its class.
#:
#: Every question in the resolution order but one is asked of ``type(value)``:
#: ``str``/``bytes``/class/enum-member, the declared-field resolvers, and the
#: ``Mapping``/``Set``/``Sequence`` memberships. Only the *stored* branch reads an
#: instance, because ``__dict__`` is the instance's.
#:
#: Routing one node unmemoised asks a string of ``isinstance`` questions, most of
#: them through ``abc.__instancecheck__``, for an answer that cannot differ between
#: two values of the same class.
_ROUTE_BY_TYPE: dict[type, "tuple[str, tuple[str, ...]] | None"] = {}

#: Recorded for a type whose kind depends on what the instance carries.
_ASK_THE_VALUE: Final = None

#: The ABC registry generation the routes above were worked out under.
#:
#: ``Mapping``, ``Set`` and ``Sequence`` take virtual subclasses, so
#: ``Sequence.register(X)`` really does change the answer after ``X`` exists.
#: Every such call bumps ``abc.get_cache_token()``, which is what the token is
#: for and what ``functools.singledispatch`` guards on. Same argument, same
#: mechanism and same one-element list as ``_subjects._SHAPE_TOKEN``.
_ROUTE_TOKEN: list[object] = [get_cache_token()]


def _classify(value: object, /) -> tuple[str, tuple[str, ...]]:
    """Route by type where the type decides, and remember the answer.

    See :data:`_ROUTE_BY_TYPE`. The order this preserves is
    :func:`_resolve_classification`'s, which is where the wrong PASSes live.

    The ABC token is checked once per comparison rather than once per node, at
    the top of :func:`compare` and :func:`differs`. Per node it is a measurable
    slice of a small comparison, spent guarding against a registration nobody
    makes halfway through one.

    ``try``/``except`` rather than ``.get()`` and a sentinel, for the reason
    :func:`lovely_assertions._subjects._claimed_by_shape` gives -- ``None`` is a
    real answer here, so a miss has to be told apart from a remembered one. It is
    also what lets the value keep its declared type: a sentinel widens it to
    ``object`` and needs a ``typing.cast`` to get back, and ``cast`` is a genuine
    function call at runtime, on a function that runs once per node.
    """
    subject_type = type(value)
    try:
        cached = _ROUTE_BY_TYPE[subject_type]
    except KeyError:
        cached = _resolve_classification(value)
        remember(_ROUTE_BY_TYPE, subject_type, cached)
    if cached is None:
        # The one branch a type cannot answer: `__dict__` belongs to the instance.
        stored = _stored_field_names(value)
        return (_KIND_RECORD if stored else _KIND_LEAF), stored
    return cached


def _resolve_classification(value: object, /) -> "tuple[str, tuple[str, ...]] | None":
    """What this value is compared as, and -- for a record -- the fields to compare.

    The order is where the wrong PASSes live.

    ``str`` and ``bytes`` come first because both are sequences and neither is
    ever walked as one: iterating a string yields strings that iterate to
    themselves, and iterating ``bytes`` yields integers nobody indexed by hand.

    A **declared** record -- see :func:`_declared_field_names` -- is resolved
    before every storage branch, because a ``NamedTuple`` *is* a tuple and a
    dataclass is free to subclass ``dict``. Left to the sequence branch,
    ``Point(1, 2)`` against ``Point(2, 1)`` would report "index 0" for a field the
    reader calls ``x`` -- and under ``ignoring_order`` it would compare equal,
    which is a silent, wrong pass on the one type the trap is easiest to fall
    into.

    A **stored** record -- one whose fields are only in ``__slots__`` or
    ``__dict__`` -- is resolved *after* the sequence branch, so that a list
    subclass which happens to carry an attribute is still compared as the list it
    is.

    And a dataclass leads the declared three: fall through from it and a
    ``field(compare=False)`` comes back in through ``vars`` and is reported as a
    difference that the ``==`` it was excluded from never looked at.
    """
    if _is_opaque(value):
        return _KIND_LEAF, ()
    declared = _declared_field_names(value)
    if declared is not None:
        return _KIND_RECORD, declared
    if is_mapping(value):
        return _KIND_MAPPING, ()
    if is_set(value):
        return _KIND_SET, ()
    if isinstance(value, Sequence):
        return _KIND_SEQUENCE, ()
    return _ASK_THE_VALUE


def _is_opaque(value: object, /) -> bool:
    """Whether a value has no structure this engine will look inside.

    Three kinds, and each is a wrong pass if it falls through.

    ``str`` and ``bytes`` are sequences and neither is ever walked as one:
    iterating a string yields strings that iterate to themselves, and iterating
    ``bytes`` yields integers nobody indexed by hand.

    A class object's own dictionary holds the methods it defines, not the state an
    instance carries. A class is not a record.

    An **enumeration member** *is* its value; there is no state underneath to take
    apart. Left to the record branch, a member of an enum whose ``__init__``
    assigns attributes is compared on those attributes alone -- and two members
    that agree on them, under different values, come back **equivalent**.
    Stripping the runtime's own ``_name_`` and ``_value_`` (see
    :func:`_is_reserved`) does not cover it: that empties a plain member down to a
    leaf and leaves a mixed-in one a record.
    """
    return isinstance(value, _OPAQUE_TYPES) or _is_enum_member(value)


def _declared_field_names(value: object, /) -> tuple[str, ...] | None:
    """The fields a type declares, remembered per type; ``None`` when it declares none.

    See :func:`_resolve_declared_field_names` for what the answer is and why it
    is asked where it is. This wrapper exists for what the answer *costs*.
    Resolving it runs ``dataclasses.fields()``, an MRO lookup for ``_fields`` and
    another for ``__attrs_attrs__``, and for a plain ``int`` most of that price is
    an exception raised and caught while reading a declaration that is not there.
    That is a substantial cost on a function the walk calls twice for every pair it
    examines -- and all of it re-derives an answer that cannot change, because each
    of the three questions is asked of ``type(value)`` and never of the value.
    """
    subject_type = type(value)
    cached = _DECLARED_BY_TYPE.get(subject_type, _UNCACHED)
    if cached is not _UNCACHED:
        return cast("tuple[str, ...] | None", cached)
    resolved = _resolve_declared_field_names(value)
    remember(_DECLARED_BY_TYPE, subject_type, resolved)
    return resolved


def _resolve_declared_field_names(value: object, /) -> tuple[str, ...] | None:
    """The fields a type *declares*, or ``None`` when it declares none.

    Raced in the contract's order -- ``dataclasses.fields()``, then ``_fields``,
    then ``__attrs_attrs__`` -- and asked before the mapping, set and sequence
    branches, because a declaration is the author saying what the object *is*
    where those branches only see what it happens to be stored in. A dataclass
    that subclasses ``dict`` is the case that makes the difference: compared as a
    mapping, its declared fields are never looked at, and two instances carrying
    the same entries under different fields come back **equivalent** while ``==``
    -- which reads the fields and ignores the entries -- says they are not.

    ``None`` rather than ``()`` because "declares no fields" and "declares fields
    and they are empty" are different answers, and only the first one falls
    through.
    """
    if hasattr(type(value), "__dataclass_fields__"):
        return dataclass_field_names(value)
    named = named_tuple_field_names(value)
    if named:
        return named
    attributes = attrs_field_names(value)
    if attributes:
        return attributes
    return None


def _is_enum_member(value: object, /) -> bool:
    """Whether a value is a member of an enumeration, without importing ``enum``.

    Duck-typed on the two marks the ``enum`` machinery leaves and nothing else
    does: ``_member_map_`` on the class, ``_value_`` on the member. Read rather
    than imported because this runs twice for every pair the walk examines, where
    :func:`_enum_names` runs only for callers who asked for
    ``comparing_enums_by_name()`` and can afford the import there.

    A class that sets ``_member_map_`` for its own reasons is compared as a leaf,
    which is the conservative answer: a leaf pair is settled by ``==``, so nothing
    is claimed about it that Python does not already claim.
    """
    return hasattr(type(value), "_member_map_") and hasattr(value, "_value_")


# ---------------------------------------------------------------------------
# Fields
# ---------------------------------------------------------------------------
def _stored_field_names(value: object, /) -> tuple[str, ...]:
    """``__slots__`` together with the instance dictionary.

    Added rather than raced, and for an equivalence engine the reason is sharper
    than it is for a describer. An object has both storages more often than it
    looks -- a ``__slots__`` base whose subclass does not repeat the declaration
    keeps the base's fields in slots and every one the subclass adds in a
    ``__dict__`` -- and reading only the winner would compare the two fields it
    found, ignore the two it did not, and report the pair *equivalent*.

    Dunders are dropped, and that is what makes pydantic v2 work: ``BaseModel``
    declares ``__slots__`` for storage and bookkeeping and keeps the field values
    in the instance dictionary those slots ask for. Kept, every model comparison
    would be about ``__pydantic_fields_set__`` instead of about the fields
    somebody wrote.
    """
    slots = slot_names(type(value))
    members = instance_dict_names(value)
    if not slots:
        return members
    return slots + tuple(name for name in members if name not in slots)


# ---------------------------------------------------------------------------
# Reading, guarded
# ---------------------------------------------------------------------------
def _safe_list(value: object, /) -> list[object] | None:
    """Materialise an iterable; ``None`` when iterating it would not come out.

    Materialised rather than iterated in place because a value is read more than
    once -- for its length, by position, and again while pairing -- and a
    one-shot or self-modifying iterable would answer differently each time.
    """
    try:
        return list(cast("Iterable[object]", value))
    # a hostile __iter__ costs this member, not the walk
    except Exception:
        return None


def _has_key(mapping: "Mapping[object, object]", key: object, /) -> bool:
    """Whether a mapping holds a key, surviving a hostile ``__hash__``."""
    try:
        return key in mapping
    # an unanswerable key is an absent one
    except Exception:
        return False


def _read_keys(
    actual: "Mapping[object, object]", expected: "Mapping[object, object]", key: object, /
) -> tuple[object, object] | None:
    """Both sides of one entry, or ``None`` when either would not be read."""
    try:
        return actual[key], expected[key]
    # one unreadable entry costs that entry
    except Exception:
        return None


def _read_field(value: object, name: str, /) -> object:
    """One field, or :data:`_UNREADABLE` when the object will not give it up."""
    try:
        return getattr(value, name)
    # a property that raises, or a slot nobody assigned
    except Exception:
        return _UNREADABLE


def _equal(actual: object, expected: object, /) -> bool | None:
    """Python's own containment rule, and ``None`` when the comparison raised.

    Identity first is what makes a ``float("nan")`` compare equal to itself, the
    same rule ``list.__eq__`` and ``dict.__eq__`` apply internally.
    """
    if actual is expected:
        return True
    try:
        return bool(actual == expected)
    # an __eq__ that throws is a finding, not a crash
    except Exception:
        return None


def _sorted(items: list[object], /) -> list[object]:
    """Impose an order on members that have none, so two runs read the same.

    Sets and dictionaries keyed by strings iterate in an order that depends on the
    hash seed, which would make a failure message differ between runs of the same
    test. Mixed or unorderable members keep iteration order -- an arbitrary order
    beats an exception raised while rendering somebody else's failure.
    """
    try:
        return sorted(cast("list[Any]", items))
    # unorderable members keep the order they came in
    except Exception:
        return items


# ---------------------------------------------------------------------------
# Comparators and enums
# ---------------------------------------------------------------------------
def _comparator_for(
    actual: object,
    expected: object,
    comparators: "tuple[tuple[type[Any], Callable[[Any, Any], bool]], ...]",
    /,
) -> "Callable[[Any, Any], bool] | None":
    """The registered comparator that claims this pair, or ``None``.

    Scanned last first, so that a later registration narrows an earlier one. Both
    sides have to be instances: a comparator for ``datetime`` handed a ``str`` on
    one side has no business deciding the pair, and the type difference the
    structural path reports is the better answer.
    """
    for index in range(len(comparators) - 1, -1, -1):
        kind, comparator = comparators[index]
        if _claims(kind, actual, expected):
            return comparator
    return None


def _claims(kind: "type[Any]", actual: object, expected: object, /) -> bool:
    """Whether both values are instances of ``kind``.

    A function rather than two ``isinstance`` calls at the call site so that the
    narrowing they perform -- ``object`` becomes ``Any`` through an unparameterised
    class object -- dies with the expression instead of leaking into the branch.
    """
    try:
        return isinstance(actual, kind) and isinstance(expected, kind)
    # a metaclass __instancecheck__ is user code too
    except Exception:
        return False


def _enum_names(actual: object, expected: object, /) -> tuple[str, str] | None:
    """Both members' names, or ``None`` when the pair is not two enum members.

    ``enum`` is imported here rather than at module level so that only the tests
    that ask for ``comparing_enums_by_name()`` pay for it -- the same reasoning
    that keeps ``re``, ``difflib`` and ``dataclasses`` off the import graph.
    """
    import enum  # noqa: PLC0415 (only callers of comparing_enums_by_name() pay for it)

    if not isinstance(actual, enum.Enum) or not isinstance(expected, enum.Enum):
        return None
    return actual.name, expected.name


def _key_name(key: object, /) -> str | None:
    """The member name a mapping key carries, if it carries one.

    Only a string key has a name to exclude or include by. An integer key is
    addressable by path and by nothing else, which is what keeps one
    ``including("id")`` call from silently emptying every mapping in the graph.
    """
    if isinstance(key, str):
        return key
    return None


#: Returned by :func:`_stand_in` for a value nothing hashable can stand for.
_NO_STAND_IN: Final = object()

#: How deep :func:`_stand_in` will canonicalise before giving up.
#:
#: A record nested past this keeps the linear scan instead: correct, just slower.
#: Four levels reaches the values inside a list of records holding a list of
#: records, which is as deep as the shape this is for usually goes.
_MAX_STAND_IN_DEPTH: Final = 4


def _frozen_parts(values: "Iterable[object]", depth: int, /) -> "tuple[object, ...] | None":
    """Each value's surrogate in order, or ``None`` if any of them has none."""
    parts: list[object] = []
    for held in values:
        surrogate = _stand_in(held, depth)
        if surrogate is _NO_STAND_IN:
            return None
        parts.append(surrogate)
    return tuple(parts)


def _stand_in(value: object, depth: int = 0, /) -> object:
    """A hashable surrogate, equal to another exactly when the values are.

    ``dict`` and ``list`` have no hash, so without this a shuffled list of JSON
    records -- which :func:`_equality_leftovers` calls "the ordinary shape of a
    JSON payload" -- pairs off by linear scan alone. That is quadratic in ``==``,
    and a few thousand records against a few thousand exhaust the scanning
    allowance before an answer is reached, so the comparison is refused outright.

    The surrogate makes them poolable. For a ``dict`` it is the frozen set of its
    items, which is equal for two dicts exactly when the dicts are, because a
    mapping's keys are unique and hashable by its own invariant. For a ``list`` it
    is the tuple of its items. Each carries a tag, so a list can never pair with
    the tuple holding the same items -- ``[1, 2] != (1, 2)``, and a surrogate that
    disagreed with ``==`` on one pair would not be sound on any.

    ``type(value) is`` rather than ``isinstance``: a ``dict`` subclass, an
    ``OrderedDict``, a ``list`` subclass keeps the scan. Canonicalising those would
    be correct on equality alone, but a subclass is free to narrow ``__eq__``, and
    this is the one place in the engine where a wrong pair is a wrong *verdict*
    rather than a slower one. They pair against each other by scan exactly as
    before, and against a plain ``dict`` in the structural pass, which is wider
    than ``==`` and is where an unpaired item goes anyway.

    :data:`_NO_STAND_IN` for everything else, including a value that turns out to
    hold something unhashable. That answer costs one failed attempt and then the
    linear scan, so nothing is worse off for the attempt having been made.
    """
    if depth > _MAX_STAND_IN_DEPTH:
        return _NO_STAND_IN
    kind = type(value)
    if kind is dict:
        mapping = cast("dict[object, object]", value)
        parts = _frozen_parts(mapping.values(), depth + 1)
        return _NO_STAND_IN if parts is None else ("d", frozenset(zip(mapping, parts, strict=True)))
    if kind is list:
        parts = _frozen_parts(cast("list[object]", value), depth + 1)
        return _NO_STAND_IN if parts is None else ("l", parts)
    try:
        hash(value)
    except Exception:
        return _NO_STAND_IN
    return ("v", value)


def _equality_leftovers(
    actual_items: list[object], expected_items: list[object], budget: _Budget, /
) -> tuple[list[object], list[object]]:
    """Pair off items that are simply equal; hand back what neither side matched.

    Equality is used as the cheap half of order-insensitive matching because it is
    sound in the direction that matters: two values that are equal hold the same
    information, so they are equivalent under any configuration that only ever
    *widens* what counts as equivalent -- which every option here does. The
    exception is a hand-written comparator narrower than ``==``, which is not
    consulted for a pair equality has already settled.

    Duplicates are counted: three copies on one side match three on the other and
    no more, which is what makes this a multiset comparison rather than a set one.

    **Two pools, because Python has two kinds of item.** Anything a hashable
    surrogate can stand for pairs through a dictionary in linear time -- which
    since :func:`_stand_in` includes ``dict`` and ``list``, and therefore the
    ordinary shape of a JSON payload. What is left has no hash and nothing that
    can stand for one: an object that defines ``__eq__`` and sets ``__hash__`` to
    ``None``, a ``dict`` subclass free to narrow its own equality. Those are kept
    in a second pool and matched by linear scan, exactly the treatment
    ``_diff._tally``/``_diff._take`` give the same problem. That is quadratic in
    ``==``, and it is charged to the budget's scanning meter so that it is bounded
    across the whole comparison rather than per level.

    Both pools matter to the *answer*, not only to the cost. An item this pass
    leaves unpaired goes to the structural pass, which is quadratic in full
    recursive comparisons and spends the matching allowance; a shuffled list long
    enough to exhaust that allowance would be refused rather than answered, on data
    that is plainly equivalent.
    """
    pool: dict[object, list[int]] = {}
    loose: list[int] = []
    for index, item in enumerate(actual_items):
        surrogate = _stand_in(item)
        if surrogate is _NO_STAND_IN:
            # nothing hashable stands for it; paired by scan
            loose.append(index)
        else:
            pool.setdefault(surrogate, []).append(index)
    taken: set[int] = set()
    absent: list[object] = []
    for item in expected_items:
        position = _take_index(pool, loose, actual_items, item, budget)
        if position is None:
            absent.append(item)
        else:
            taken.add(position)
    surplus = [item for index, item in enumerate(actual_items) if index not in taken]
    return surplus, absent


def _take_index(
    pool: dict[object, list[int]],
    loose: list[int],
    items: list[object],
    item: object,
    budget: _Budget,
    /,
) -> int | None:
    """Consume one position holding an item equal to this one; ``None`` when there is none.

    The scan is reached only when *this* item has no hash either, which is what
    keeps a list of ordinary hashables paying nothing for the second pool. A
    hashable item that is ``==`` to an unhashable one -- two classes written to
    compare across that line -- is missed here and picked up by the structural
    pass, which is wider than ``==`` and is where an unpaired item goes anyway.
    """
    surrogate = _stand_in(item)
    # nothing stands for it here either, so scan
    if surrogate is _NO_STAND_IN:
        return _take_loose(loose, items, item, budget)
    positions = pool.get(surrogate)
    if not positions:
        return None
    return positions.pop()


def _take_loose(
    loose: list[int], items: list[object], item: object, budget: _Budget, /
) -> int | None:
    """Consume one *unhashable* position equal to this item, by linear scan.

    ``loose`` holds positions rather than items so that the caller can tell which
    of ``items`` was consumed, which is what makes duplicates count on this side
    too. Charged for what the scan actually cost rather than for its worst case:
    over-charging would spend the allowance on comparisons that never happened, and
    the allowance decides whether an honest comparison gets an answer.
    """
    for offset, position in enumerate(loose):
        if _equal(items[position], item) is True:
            budget.spend_scans(offset + 1)
            del loose[offset]
            return position
    budget.spend_scans(len(loose))
    return None
