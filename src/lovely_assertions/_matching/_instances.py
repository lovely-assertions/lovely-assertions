"""The two placeholders that judge a value by what it is, not what it holds.

One accepts any instance of a class; the other accepts anything at all. The
second is a singleton because it carries no state and a reader who writes
``anything()`` twice means the same thing both times.

The class is checked when the matcher is *built*. A placeholder constructed with
something that is not a class would otherwise fail inside the assertion that used
it, which is a message about the wrong thing entirely.
"""

from typing import Any, Final, cast, override

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._matching._base import Matcher
from lovely_assertions._matching._rendering import type_name

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: ``isinstance`` refuses anything that is not a class, and it refuses it with a
#: ``TypeError`` from inside a comparison -- a long way from the call that was
#: actually wrong.
_NOT_A_TYPE: Final = "any_instance_of() takes a class, not "


def _require_class(kind: object, /) -> None:
    """Refuse something ``isinstance`` could not use.

    Takes ``object`` rather than ``type[T]`` so the check means something: against
    the declared type it would be a tautology, and a factory call is exactly where
    a caller's declaration might be wrong (``_formatters._check_class`` takes the
    same line, one registry over). Reported here rather than left to
    ``isinstance`` inside a comparison, which would raise a ``TypeError`` from a
    ``__eq__`` that is required never to raise -- and would therefore be swallowed
    and read as "no match", silently, for the life of the matcher.
    """
    if isinstance(kind, type):
        return
    raise TypeError(_NOT_A_TYPE + type(kind).__name__)


# ---------------------------------------------------------------------------
# The matchers
# ---------------------------------------------------------------------------
class AnyInstance(Matcher):
    """``isinstance(value, kind)``."""

    __slots__ = ("_kind_",)

    _kind_: type[Any]

    def __init__(self, kind: type[Any], /) -> None:
        # Through `object`, because this class's own `__setattr__` refuses.
        object.__setattr__(self, "_kind_", kind)

    @override
    def matches(self, value: object, /) -> bool:
        return isinstance(value, self._kind_)

    @override
    def _spec_key(self) -> tuple[object, ...]:
        return (self._kind_,)

    @override
    def __repr__(self) -> str:
        return f"<any {type_name(self._kind_)}>"


class Anything(Matcher):
    """Everything, ``None`` included."""

    __slots__ = ()

    @override
    def matches(self, value: object, /) -> bool:
        return True

    @override
    def __repr__(self) -> str:
        return "<anything>"


#: One shared instance. A matcher is immutable and this one carries no state at
#: all, so a new object per call would be an allocation that buys nothing.
_ANYTHING: Final = Anything()


# ---------------------------------------------------------------------------
# The factories -- and the lie lives in their return annotations
# ---------------------------------------------------------------------------
def any_instance_of[T](kind: type[T], /) -> T:
    """A placeholder for any instance of ``kind``.

        >>> expect({"id": 7}).is_equal_to({"id": any_instance_of(int)})
        MappingExpect({'id': 7})

    Declared to return ``T``, which is the trick and is not the truth: what comes
    back is a matcher, and the module docstring says plainly what that costs.

    Matching is ``isinstance``, with everything that implies -- a ``bool``
    matches ``any_instance_of(int)`` because a ``bool`` *is* an ``int``, and a
    subclass matches its base. Where the exact type is the claim,
    ``expect(value).is_exactly_instance_of(kind)`` is the assertion that makes it.

    Raises ``TypeError`` for something that is not a class, rather than letting
    ``isinstance`` raise it later from inside a comparison, a long way from the
    call that was wrong.
    """
    _require_class(kind)
    return cast("T", AnyInstance(kind))


def anything() -> Any:  # noqa: ANN401  (the point is a placeholder that fits any slot)
    """A placeholder for any value at all, ``None`` included.

        >>> expect({"at": 1}).is_equal_to({"at": anything()})
        MappingExpect({'at': 1})

    ``Any``, because there is no narrower honest answer: this one really does go
    anywhere. It is the matcher to use for a field whose value is genuinely not
    the point -- a timestamp, a generated id -- and the one to reach for last,
    since ``any_instance_of`` says more and keeps the slot checked.
    """
    return _ANYTHING
