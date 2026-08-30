"""The two string placeholders: a pattern, and a fragment.

Both compile or capture what they need once, at construction, because a matcher
is built in one place and compared in a loop -- and both refuse a value that is
not text rather than quietly never matching, which is the failure mode a reader
cannot tell apart from a wrong expectation.
"""

from typing import TYPE_CHECKING, Final, cast, override

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._matching._base import Matcher

if TYPE_CHECKING:
    import re

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: A bytes pattern compiles perfectly well and then matches nothing, because
#: :meth:`StringMatching.matches` asks for a ``str`` -- and it *has* to, since a
#: ``bytes`` pattern cannot be applied to one. The result is a matcher that can
#: never match, which is the same bug ``one_of()`` and ``containing({})`` are
#: refused for and is refused here for the same reason.
_NOT_A_TEXT_PATTERN: Final = (
    "string_matching() takes a str pattern, or one compiled from a str; a bytes pattern "
    "matches no string, so the assertion holding it could never pass. Pattern is "
)


class StringMatching(Matcher):
    """A string in which a regular expression finds a match."""

    __slots__ = ("_pattern_",)

    _pattern_: "re.Pattern[str]"

    def __init__(self, pattern: "re.Pattern[str]", /) -> None:
        object.__setattr__(self, "_pattern_", pattern)

    @override
    def matches(self, value: object, /) -> bool:
        return isinstance(value, str) and self._pattern_.search(value) is not None

    @override
    def _spec_key(self) -> tuple[object, ...]:
        return (self._pattern_.pattern, self._pattern_.flags)

    @override
    def __repr__(self) -> str:
        return f"<string matching {format_value(self._pattern_.pattern)}>"


class StringContaining(Matcher):
    """A string holding a fragment."""

    __slots__ = ("_fragment_",)

    _fragment_: str

    def __init__(self, fragment: str, /) -> None:
        object.__setattr__(self, "_fragment_", fragment)

    @override
    def matches(self, value: object, /) -> bool:
        return isinstance(value, str) and self._fragment_ in value

    @override
    def _spec_key(self) -> tuple[object, ...]:
        return (self._fragment_,)

    @override
    def __repr__(self) -> str:
        return f"<string containing {format_value(self._fragment_)}>"


def string_matching(pattern: "str | re.Pattern[str]", /) -> str:
    """A placeholder for any string a regular expression finds a match in.

        >>> expect({"t": "ey.J"}).is_equal_to({"t": string_matching(r"^ey")})
        MappingExpect({'t': 'ey.J'})

    A **search**, not a full match, mirroring ``StringExpect.matches`` and
    FluentAssertions' ``MatchRegex``: anchor the pattern yourself when the whole
    string is meant. An already-compiled pattern keeps its flags.

    The pattern is compiled here, once, rather than at each comparison -- which
    is also where this module's only ``import re`` lives, so importing this
    package does not import the regex engine and a suite that never writes a
    regex matcher never pays for it.

    A **bytes** pattern raises ``TypeError``. It compiles, and then matches
    nothing at all -- a matcher that can never match, which is what ``one_of()``
    and ``containing({})`` are refused for, and which is worse than a wrong
    answer: in a negative assertion it is a test that can never fail.
    """
    import re  # noqa: PLC0415  (kept off import time; only regex matchers need it)

    compiled = re.compile(pattern)
    # Widened past the declaration on purpose, the way `type_name` is: against
    # the declared `str | re.Pattern[str]` this test reads as redundant, and it is
    # exactly the caller whose declaration was wrong that it exists to catch.
    written = cast("object", compiled.pattern)
    if not isinstance(written, str):
        raise TypeError(_NOT_A_TEXT_PATTERN + type(written).__name__)
    return cast("str", StringMatching(compiled))


def string_containing(fragment: str, /) -> str:
    """A placeholder for any string holding ``fragment``.

        >>> expect({"m": "a b c"}).is_equal_to({"m": string_containing("b")})
        MappingExpect({'m': 'a b c'})

    The plain-substring half of :func:`string_matching`, worth its own name for
    the reason ``contains`` is worth having beside ``matches``: the commonest
    thing anyone wants to say about a string they only partly know should not
    have to be spelled as a regular expression, where every ``.`` and ``(`` in
    the fragment would then mean something else.
    """
    return cast("str", StringContaining(fragment))
