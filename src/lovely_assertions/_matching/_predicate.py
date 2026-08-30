"""The escape hatch, and the one place a broken predicate reads as "no match".

Everywhere else in this library a callable that raises is somebody's bug and is
reported as one. Here it cannot be: the predicate runs inside ``__eq__``, which
must be total, and a matcher that raises would turn every comparison it touches
into an error rather than a verdict.
"""

from typing import TYPE_CHECKING, Any, Final, cast, override

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._matching._base import Matcher
from lovely_assertions._matching._rendering import predicate_name

if TYPE_CHECKING:
    from collections.abc import Callable

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: "a callable", not "a callable of one argument", because the second is a
#: promise this module does not keep: nothing checks the arity, and a predicate
#: of the wrong shape becomes a matcher that never matches rather than an error
#: at the call that was wrong. The `matching` docstring says so; a message that
#: implied otherwise would be the one place a reader looked for the guarantee.
_NOT_A_PREDICATE: Final = "matching() takes a callable, not "


class Matching(Matcher):
    """Whatever a predicate says yes to."""

    __slots__ = ("_predicate_",)

    _predicate_: "Callable[[Any], bool]"

    def __init__(self, predicate: "Callable[[Any], bool]", /) -> None:
        object.__setattr__(self, "_predicate_", predicate)

    @override
    def matches(self, value: object, /) -> bool:
        return bool(self._predicate_(value))

    @override
    def _spec_key(self) -> tuple[object, ...]:
        return (self._predicate_,)

    @override
    def __repr__(self) -> str:
        return f"<matching {predicate_name(self._predicate_)}>"


def matching[T](predicate: "Callable[[T], bool]", /) -> T:
    """A placeholder for any value a predicate says yes to.

        >>> expect({"n": 4}).is_equal_to({"n": matching(lambda n: n % 2 == 0)})
        MappingExpect({'n': 4})

    The escape hatch, and the reason the rest of this module can stay small: a
    condition nobody anticipated is one lambda away, and it nests inside
    ``containing`` and ``one_of`` like any other matcher.

    A predicate that **raises** is read as "no match" rather than allowed to
    escape. ``__eq__`` has to be total -- it runs inside a ``dict`` comparison
    and inside the difference engine -- so the choice is between a wrong answer
    and an error raised in the middle of reporting somebody else's failure.

    That is the one place this module departs from the rest of the library, where
    a broken predicate propagates: ``expect([1]).only_contains(broken)`` raises
    the predicate's own error, and ``matching(broken)`` does not. **State the
    cost plainly rather than only its consolation.** In a *positive* assertion
    the damage is bounded, because the value that caused it is printed next to
    ``<matching ...>`` where the reader is already looking. In a *negative* one
    -- ``is_not_equal_to``, ``does_not_contain`` -- there is no message at all: a
    predicate that always raises never matches, so the assertion passes, every
    time, and the test can no longer fail. Nothing in this module detects that,
    including the wrong-arity case the ``TypeError`` above reads as though it
    ruled out; ``matching`` is checked for being callable and for nothing else.
    A predicate written to answer about one type and handed another is the way
    this happens in practice, so keep the predicate total -- ``isinstance``
    first, verdict second -- rather than relying on the failure message to
    confess.
    """
    if not callable(predicate):
        raise TypeError(_NOT_A_PREDICATE + type(predicate).__name__)
    return cast("T", Matching(predicate))
