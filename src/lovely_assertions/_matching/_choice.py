"""A value from a fixed set: equality against each option in turn.

Identity first, so an option whose ``__eq__`` misbehaves cannot stop the matcher
from recognising the very value it was given. An empty set of options is refused
where it is written: a matcher nothing can satisfy is a mistake in the test, and
one that silently never matches is a mistake nobody finds.
"""

from typing import Final, cast, override

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._matching._base import Matcher
from lovely_assertions._matching._comparison import equal
from lovely_assertions._matching._rendering import operands

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: A matcher that stands in for nothing can never match, so an assertion carrying
#: one could never pass. Same rule as the variadic assertions
#: (``_core._NEEDS_VALUES``) and the occurrence factories: a call that could
#: never succeed is a bug where it was written, not a finding about a subject.
_NEEDS_VALUES: Final = "one_of() needs at least one value; a choice between nothing matches nothing"


class OneOf(Matcher):
    """Any one of a fixed set of values."""

    __slots__ = ("_values_",)

    _values_: tuple[object, ...]

    def __init__(self, values: tuple[object, ...], /) -> None:
        object.__setattr__(self, "_values_", values)

    @override
    def matches(self, value: object, /) -> bool:
        for candidate in self._values_:  # noqa: SIM110  (a generator expression would allocate)
            if equal(candidate, value):
                return True
        return False

    @override
    def _spec_key(self) -> tuple[object, ...]:
        return self._values_

    @override
    def __repr__(self) -> str:
        return f"<one of {operands(self._values_)}>"


def one_of[T](*values: T) -> T:
    """A placeholder for any one of ``values``.

        >>> expect({"n": 1}).is_equal_to({"n": one_of(0, 1)})
        MappingExpect({'n': 1})

    Equality against each in turn, identity first, so a NaN among the values is
    found where it sits. Nested matchers work: ``one_of(None, any_instance_of(int))``
    is how "an int, or nothing" is spelled, and it is the shape that makes this
    matcher worth having next to :func:`any_instance_of`.

    ``one_of()`` raises ``ValueError``. A choice between nothing matches nothing,
    so the assertion carrying it could never pass -- the same rule the variadic
    assertions keep, and for the same reason: it is a bug where it was written.
    """
    if not values:
        raise ValueError(_NEEDS_VALUES)
    return cast("T", OneOf(values))
