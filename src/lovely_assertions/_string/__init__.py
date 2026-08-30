"""Assertions for strings.

Five things are worth knowing before reading the rest.

**``matches`` is the regex one.** Every subject accepts ``matches(predicate)``;
on a string the same name also accepts a regular expression, the way
FluentAssertions' ``MatchRegex`` does, because in Python that is what ``matches``
means. Both forms live here, under overloads that *widen* the inherited parameter
rather than replace it, and the runtime tells them apart by asking whether the
argument is callable. FluentAssertions' wildcard ``Match`` becomes
:meth:`~StringExpect.matches_wildcard`.

**``re`` is imported inside the methods that need it.** Importing this package
must not drag in the regex engine, so only the regex and wildcard assertions pay
for ``re``, and only when they run. :meth:`~StringExpect.is_uuid` imports
``uuid`` the same way.

**Four assertions count instead of asking.** ``contains``, ``does_not_contain``,
``contains_ignoring_case`` and the regex form of ``matches`` take an
``occurrences=`` constraint, and every one of them counts **non-overlapping**
matches, because that is what ``str.count`` and ``re`` do and a reader checking
the answer by hand will reach for one of those. So ``"aaa"`` contains ``"aa"``
*once*. :meth:`~StringExpect.contains` documents the rule, the escape hatch and
the zero-width trap in full; the other three point at it.

**The rendering bounds are a scope, not a constant.** How long a rendered string
may be and how many of them a multi-value message lists are ``max_chars`` and
``max_items`` on :class:`~lovely_assertions.FormattingOptions`, read through
:func:`~lovely_assertions.current_formatting` at the point of use. Every one of
those reads sits inside a failure branch: a passing assertion must not pay for a
``ContextVar`` lookup, and this module's helpers are called from nowhere else.
The strings themselves leave through :func:`~lovely_assertions.format_value`,
so a registered ``str`` formatter renders them here exactly as it renders the
subject of an inherited ``is_equal_to`` -- one value cannot read two ways in one
report.

**The character-class family delegates, but does not merely repeat itself.**
:meth:`~StringExpect.is_alpha` and its siblings each call the ``str`` method of
the same name; the work is in the failure message, which names the first
offending character and its index instead of restating the assertion. Two Python
subtleties are answered there rather than left to the reader: an empty string
satisfies none of these classes except ``isascii`` and ``isprintable``, and
``isdigit`` is neither ``isdecimal`` nor ``isnumeric`` (see
:meth:`~StringExpect.is_digit`).

The catalogue is assembled from one mixin per seam, in the order a reader meets
them. Each is an ``Expect[str]`` with empty ``__slots__``, so a string subject is
still one allocation carrying one attribute.
"""

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._string._case import CaseAssertions
from lovely_assertions._string._caseless import CaselessEqualityAssertions
from lovely_assertions._string._classes_encoding import EncodingClassAssertions
from lovely_assertions._string._classes_letters import LetterClassAssertions
from lovely_assertions._string._containment import ContainmentAssertions
from lovely_assertions._string._containment_caseless import CaselessContainmentAssertions
from lovely_assertions._string._containment_many import MultipleContainmentAssertions
from lovely_assertions._string._edges import EdgeAssertions
from lovely_assertions._string._identifier import IdentifierAssertions
from lovely_assertions._string._regex import RegexAssertions
from lovely_assertions._string._size import SizeAssertions
from lovely_assertions._string._uuid import UuidAssertions
from lovely_assertions._string._wildcards import WildcardAssertions

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["StringExpect"]


class StringExpect(
    SizeAssertions,
    CaselessEqualityAssertions,
    ContainmentAssertions,
    MultipleContainmentAssertions,
    CaselessContainmentAssertions,
    EdgeAssertions,
    RegexAssertions,
    WildcardAssertions,
    CaseAssertions,
    LetterClassAssertions,
    EncodingClassAssertions,
    IdentifierAssertions,
    UuidAssertions,
    Expect[str],
):
    """Assertions for strings."""

    __slots__ = ()
