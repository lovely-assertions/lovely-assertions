"""Regular expressions, and the one place this library takes the caller's own.

The pattern is theirs, so the failure quotes it back rather than describing it.
The occurrence forms need one: counting matches of a plain substring is what the
containment seam already does, and offering both would be two answers to one
question.
"""

from typing import TYPE_CHECKING, Self, overload, override

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._string._render import clipped
from lovely_assertions._text import pattern_text, regex_matcher

if TYPE_CHECKING:
    import re
    from collections.abc import Callable

    from lovely_assertions._occurrence import Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: ``matches`` takes either a predicate or a regular expression under one name,
#: and only one of the two has anything to count. The overloads refuse the
#: combination statically; this is what an untyped caller gets, and it names which
#: of the two arguments to drop rather than merely refusing both.
_OCCURRENCES_NEED_A_PATTERN = (
    "occurrences counts matches of a regular expression, and a predicate answers"
    " yes or no rather than how many; pass a pattern, or drop occurrences"
)


class RegexAssertions(Expect[str]):
    """Patterns the caller wrote."""

    __slots__ = ()

    @overload
    def matches(
        self,
        pattern: "str | re.Pattern[str]",
        /,
        *,
        occurrences: "Occurrence | None" = None,
        because: str = "",
    ) -> Self: ...
    @overload
    def matches(self, predicate: "Callable[[str], bool]", /, *, because: str = "") -> Self: ...
    @override
    def matches(
        self,
        pattern: "str | re.Pattern[str] | Callable[[str], bool]",
        /,
        *,
        occurrences: "Occurrence | None" = None,
        because: str = "",
    ) -> Self:
        r"""Assert the string matches a regular expression, or satisfies a predicate.

        The regex form is a **search**, not a full match: ``matches("wor")``
        passes for ``"hello world"``, mirroring FluentAssertions' ``MatchRegex``.
        Anchor the pattern yourself, or reach for :meth:`matches_wildcard`, when
        the whole string is meant.

        Both forms live under one name because both have a claim on it: a
        predicate is what ``matches`` means on any subject, and a regular
        expression is what it means on a string. The overloads widen the parameter
        inherited from ``Expect`` rather than replacing it, so a predicate still
        works on a string subject; the runtime tells the two apart by asking
        whether the argument is callable.

        ``occurrences`` counts matches instead of asking for one::

            expect(log).matches(r"ERROR \d+", occurrences=at_least(2))

        and counts them the way ``re`` does -- **non-overlapping**, each scan
        resuming past the match it just made, which is what ``re.finditer`` and
        ``re.findall`` both do. ``"aaa"`` therefore matches ``"aa"`` *once*, the
        same answer :meth:`contains` gives. A lookahead is how the other count is
        asked for: ``r"(?=aa)"`` matches at index 0 *and* at index 1, because a
        zero-width match consumes nothing and the scan advances by one.

        Which is also the trap. A pattern that *can* match nothing matches
        everywhere, so ``matches("x*", occurrences=exactly(1))`` against a
        three-character subject finds **four** -- one before each character and
        one at the end -- and no subject would ever satisfy it. Quantify or anchor
        the pattern when the count is the point.

        ``occurrences`` belongs to the regex form alone: a predicate answers yes
        or no and has nothing to count. The overloads refuse the pair statically,
        and an untyped caller gets a ``TypeError``.
        """
        if callable(pattern):
            if occurrences is not None:
                raise TypeError(_OCCURRENCES_NEED_A_PATTERN)
            return super().matches(pattern, because=because)

        matcher = regex_matcher(pattern)
        subject = self._subject
        if occurrences is None:
            if matcher.search(subject) is not None:
                return self
            return self._fail(
                f"to match the regular expression {pattern_text(pattern)!r}, "
                f"but was {clipped(subject)}",
                because,
            )
        # `finditer` rather than `findall`: the count is the same, and a pattern
        # with groups makes `findall` build a tuple per match to answer a question
        # about how many there were.
        found = sum(1 for _ in matcher.finditer(subject))
        if occurrences.allows(found):
            return self
        return self._fail(
            f"to match the regular expression {pattern_text(pattern)!r}"
            f" {occurrences.describe()}, but found {found}",
            because,
        )

    def does_not_match(self, pattern: "str | re.Pattern[str]", /, *, because: str = "") -> Self:
        """Assert no part of the string matches the regular expression ``pattern``.

        Regex only: the predicate form of :meth:`matches` needs no negation, a
        predicate being negatable where it is written.
        """
        subject = self._subject
        found = regex_matcher(pattern).search(subject)
        if found is None:
            return self
        matched = found.group()
        if not matched:
            # A pattern that can match nothing -- `x*`, `\b`, a lookahead -- matches
            # every string, so this assertion could never have passed. Saying it
            # "contains ''" would blame the subject for a bug in the pattern.
            return self._fail(
                f"not to match the regular expression {pattern_text(pattern)!r}, but it matches "
                f"the empty string at index {found.start()} of {clipped(subject)}",
                because,
            )
        if matched == subject:
            # Naming the match and the subject separately would print the same
            # text twice, and a greedy pattern makes that the common case.
            return self._fail(
                f"not to match the regular expression {pattern_text(pattern)!r}, "
                f"but {clipped(subject)} matches it in full",
                because,
            )
        return self._fail(
            f"not to match the regular expression {pattern_text(pattern)!r}, "
            f"but {clipped(subject)} contains {clipped(matched)} at index {found.start()}",
            because,
        )
