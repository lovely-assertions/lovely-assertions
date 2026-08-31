"""Every point where the engine touches a value it did not write, guarded.

Iterating a container, hashing a key, subscripting a mapping, reaching a field,
asking ``==``, putting members in some order: each of those is a call into
somebody else's code, and the objects being walked are precisely the ones a
reader has just found something wrong with. The guards sit here, one per
operation, rather than around the walk -- which is what makes a hostile member
cost that member and not the comparison.

Gathering them in one file also settles the vocabulary of a read that did not
come out. Nothing here answers a failed read with an exception, and nothing here
decides what the failure means: a value that would not be read comes back as
``None``, or as :data:`UNREADABLE` where ``None`` is itself an ordinary answer,
and the caller says whether that is a difference, an absence, or nothing worth
reporting at all.

The questions an option asks of a pair before its structure is taken apart --
which registered comparator claims it, whether both sides are enum members,
whether a mapping key carries a name that ``excluding`` could address -- are
inspection of the same foreign values, and sit here beside the reads.

All of it runs during the walk, which is a path a *passing* assertion takes,
since ``is_not_equivalent_to`` passes by finding differences. So nothing here
renders a value or reads ``current_formatting()``, and nothing here imports
another module of this engine: that is what keeps the file at the bottom of the
import graph, where a cycle cannot form through it.
"""

from typing import TYPE_CHECKING, Any, Final, cast

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Stands in for a field the object would not give up -- a ``__slots__`` entry
#: nobody assigned, a property that raised. A sentinel rather than ``None``,
#: because ``None`` is a perfectly ordinary field value and the two must not be
#: confused: one is a member that is absent, the other a member that is empty.
UNREADABLE: Final = object()


#: The two halves of "one side has this field and the other does not". Constants
#: rather than built at the point of use, because they are built during the walk.
NOT_ON_ACTUAL: Final = "this field could not be read on the actual value"


NOT_ON_EXPECTED: Final = "this field could not be read on the expected value"


# ---------------------------------------------------------------------------
# Reading, guarded
# ---------------------------------------------------------------------------
def safe_list(value: object, /) -> list[object] | None:
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


def has_key(mapping: "Mapping[object, object]", key: object, /) -> bool:
    """Whether a mapping holds a key, surviving a hostile ``__hash__``."""
    try:
        return key in mapping
    # an unanswerable key is an absent one
    except Exception:
        return False


def read_keys(
    actual: "Mapping[object, object]", expected: "Mapping[object, object]", key: object, /
) -> tuple[object, object] | None:
    """Both sides of one entry, or ``None`` when either would not be read."""
    try:
        return actual[key], expected[key]
    # one unreadable entry costs that entry
    except Exception:
        return None


def read_field(value: object, name: str, /) -> object:
    """One field, or :data:`UNREADABLE` when the object will not give it up."""
    try:
        return getattr(value, name)
    # a property that raises, or a slot nobody assigned
    except Exception:
        return UNREADABLE


def equal_or_unknown(actual: object, expected: object, /) -> bool | None:
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


def stably_ordered(items: list[object], /) -> list[object]:
    """Impose an order on members that have none, so two runs read the same.

    A set of strings iterates in an order that depends on the hash seed, which
    would make a failure message differ between runs of the same test, and a
    mapping hands over its keys in whatever order it happens to iterate. Mixed or
    unorderable members keep iteration order -- an arbitrary order beats an
    exception raised while rendering somebody else's failure.
    """
    try:
        return sorted(cast("list[Any]", items))
    # unorderable members keep the order they came in
    except Exception:
        return items


# ---------------------------------------------------------------------------
# Comparators and enums
# ---------------------------------------------------------------------------
def comparator_for(
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


def enum_names(actual: object, expected: object, /) -> tuple[str, str] | None:
    """Both members' names, or ``None`` when the pair is not two enum members.

    ``enum`` is imported here rather than at module level so that only the tests
    that ask for ``comparing_enums_by_name()`` pay for it -- the same reasoning
    that keeps ``re``, ``difflib`` and ``dataclasses`` off the import graph.
    """
    import enum  # noqa: PLC0415 (only callers of comparing_enums_by_name() pay for it)

    if not isinstance(actual, enum.Enum) or not isinstance(expected, enum.Enum):
        return None
    return actual.name, expected.name


def key_name(key: object, /) -> str | None:
    """The member name a mapping key carries, if it carries one.

    Only a string key has a name to exclude or include by. An integer key is
    addressable by path and by nothing else, which is what keeps one
    ``including("id")`` call from silently emptying every mapping in the graph.
    """
    if isinstance(key, str):
        return key
    return None
