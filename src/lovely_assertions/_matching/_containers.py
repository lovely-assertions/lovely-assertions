"""The two placeholders that look inside a container.

One asks whether a mapping holds these entries; the other whether a sequence or
a set holds these items. Which of the two a caller gets is decided by what they
passed, not by which function they called, because the question they are asking
is the same one in both cases.

Text is refused outright. A string contains its substrings and its characters
and neither reading is more obviously right, so this refuses to guess and says
where to go instead.
"""

from collections.abc import Collection, Mapping, Sequence
from collections.abc import Set as AbstractSet
from typing import Any, Final, cast, override

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._matching._base import Matcher
from lovely_assertions._matching._comparison import equal, found_in, is_mapping, is_scannable
from lovely_assertions._matching._rendering import operands

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Its mirror. An empty spec is satisfied by every container there is, so the
#: assertion holding it asserts nothing -- the worst thing an assertion can be.
_NEEDS_A_SPEC: Final = (
    "containing() needs at least one entry; an empty one matches every container, "
    "so it asserts nothing"
)


#: ``containing`` is the only matcher that takes a structure rather than a value,
#: and the only one that can be handed something it cannot read.
_NOT_A_CONTAINER: Final = (
    "containing() takes a mapping, a sequence or a set to look for inside another one, not "
)


#: Text that is a container in Python and never the container ``containing()``
#: means. ``containing("ab")`` would otherwise quietly mean "a sequence holding
#: the characters 'a' and 'b'", which nobody has ever wanted;
#: :func:`string_containing` is what that caller meant.
_TEXTUAL: Final = (str, bytes, bytearray)


_SCANNABLE: Final = (Sequence, AbstractSet)


class MappingSubset(Matcher):
    """A mapping holding at least these entries."""

    __slots__ = ("_spec_",)

    _spec_: "Mapping[Any, Any]"

    def __init__(self, spec: "Mapping[Any, Any]", /) -> None:
        object.__setattr__(self, "_spec_", spec)

    @override
    def matches(self, value: object, /) -> bool:
        if not is_mapping(value):
            return False
        spec = self._spec_
        # Iterating the keys rather than `.items()`: a view is an allocation, and
        # this runs inside a comparison that a *passing* assertion makes.
        for key in spec:
            if key not in value:
                return False
            if not equal(spec[key], value[key]):
                return False
        return True

    @override
    def _spec_key(self) -> tuple[object, ...]:
        return (self._spec_,)

    @override
    def __repr__(self) -> str:
        return f"<containing {format_value(self._spec_)}>"


class ItemsPresent(Matcher):
    """A collection holding at least these items, in any order."""

    __slots__ = ("_items_",)

    _items_: tuple[object, ...]

    def __init__(self, items: tuple[object, ...], /) -> None:
        object.__setattr__(self, "_items_", items)

    @override
    def matches(self, value: object, /) -> bool:
        if not is_scannable(value):
            return False
        for wanted in self._items_:  # noqa: SIM110  (a generator expression would allocate)
            if not found_in(wanted, value):
                return False
        return True

    @override
    def _spec_key(self) -> tuple[object, ...]:
        return self._items_

    @override
    def __repr__(self) -> str:
        return f"<containing {operands(self._items_)}>"


def containing[T](spec: T, /) -> T:
    """A placeholder for a container holding at least what ``spec`` holds.

        >>> expect({"tags": ["a", "b"]}).is_equal_to({"tags": containing(["a"])})
        MappingExpect({'tags': ['a', 'b']})

    A **mapping** spec asks for those keys, with matching values, and says
    nothing about any other key -- Jest's ``objectContaining``. A **sequence or
    set** spec asks for those items, in any order and at any position, and says
    nothing about the rest -- Jest's ``arrayContaining``. Both compare their
    entries with ``==``, so matchers nest to any depth:
    ``containing({"user": containing({"id": any_instance_of(int)})})``.

    The signature is ``[T](spec: T) -> T`` rather than an overload per shape, and
    that is the load-bearing decision here. Declared ``Mapping[K, V]`` this would
    hand back a ``Mapping`` where the slot wants a ``dict`` and be rejected by
    both checkers; passed through, ``containing({"a": 1})`` is a ``dict[str, int]``
    to the checker and drops into a ``dict[str, int]`` slot -- which is the entire
    point. The cost is that the annotation accepts ``containing(3)``, which the
    runtime refuses with a ``TypeError``.

    Text is refused rather than read as a sequence of characters:
    ``containing("ab")`` would otherwise mean "holds 'a' and holds 'b'", which
    nobody wants and :func:`string_containing` already says properly. An empty
    spec raises ``ValueError`` -- it is satisfied by every container there is, so
    the assertion holding it asserts nothing.

    A set spec is read as items to find, not as a set to compare: the matcher
    holds the items and looks for each of them, which is why an unhashable item
    in the container it is checking is no obstacle.
    """
    if isinstance(spec, Mapping):
        mapping = cast("Mapping[Any, Any]", spec)
        if not mapping:
            raise ValueError(_NEEDS_A_SPEC)
        return cast("T", MappingSubset(mapping))
    if isinstance(spec, _SCANNABLE) and not isinstance(spec, _TEXTUAL):
        items = tuple(cast("Collection[object]", spec))
        if not items:
            raise ValueError(_NEEDS_A_SPEC)
        return cast("T", ItemsPresent(items))
    raise TypeError(_NOT_A_CONTAINER + type(spec).__name__)
