"""One value, and how many times it appears.

The counted form is the reason this is not a one-line assertion: "contains it"
and "contains it twice" are different claims, and a message that says which one
failed saves the reader a trip to the source.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._string._render import clipped

if TYPE_CHECKING:
    from lovely_assertions._occurrence import Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class ContainmentAssertions(Expect[str]):
    """Whether one value is in there, and how often."""

    __slots__ = ()

    def contains(
        self, value: str, /, *, occurrences: "Occurrence | None" = None, because: str = ""
    ) -> Self:
        r"""Assert ``value`` appears somewhere in the string.

        ``occurrences`` turns the question from *whether* into *how many*::

            expect(log).contains("retrying", occurrences=exactly(3))

        and the failure says which it found: ``Expected log to contain 'retrying'
        exactly 3 times, but found 2.`` The alternative --
        ``expect(log.count("retrying")).is_equal_to(3)`` -- asserts the same fact
        and reports almost none of it, because its subject is an integer.

        **Counting is non-overlapping.** This is ``str.count``, and ``str.count``
        resumes the scan *past* the match it just made rather than one character
        into it, so ``"aaa".count("aa")`` is **1**::

            expect("aaa").contains("aa", occurrences=exactly(1))   # passes
            expect("aaa").contains("aa", occurrences=exactly(2))   # fails: found 1

        That is the rule for every occurrence count on this subject, and it is
        deliberately the rule a reader gets when they check the answer by hand.
        When the overlapping count is what you meant, a lookahead counts them and
        :meth:`matches` will run it -- ``matches(r"(?=aa)", occurrences=exactly(2))``
        finds two, because a zero-width match consumes nothing and the scan
        advances by one instead.

        The empty needle follows ``str.count`` too: ``"abc".count("")`` is 4, one
        position before each character and one after the last.

        Without ``occurrences`` this is an ``in`` test and nothing else -- same
        message, same cost, and no counting.
        """
        subject = self._subject
        if occurrences is None:
            if value in subject:
                return self
            return self._fail(f"to contain {clipped(value)}, but was {clipped(subject)}", because)
        found = subject.count(value)
        if occurrences.allows(found):
            return self
        return self._fail(
            f"to contain {clipped(value)} {occurrences.describe()}, but found {found}", because
        )

    def does_not_contain(
        self, unexpected: str, /, *, occurrences: "Occurrence | None" = None, because: str = ""
    ) -> Self:
        """Assert ``unexpected`` appears nowhere in the string.

        ``occurrences`` negates the *count* rather than the presence, which is a
        different assertion and worth reading twice::

            expect(log).does_not_contain("retrying", occurrences=exactly(3))

        holds for a log that retried twice, and for one that retried four times,
        and fails only for one that retried exactly three. "It is not there at
        all" is this method with no ``occurrences``, or
        ``occurrences=exactly(0)`` said the long way round.

        Counting is non-overlapping; :meth:`contains` sets out the rule.
        """
        subject = self._subject
        if occurrences is None:
            if unexpected not in subject:
                return self
            return self._fail(
                f"not to contain {clipped(unexpected)}, but {clipped(subject)} does", because
            )
        found = subject.count(unexpected)
        if not occurrences.allows(found):
            return self
        return self._fail(
            f"not to contain {clipped(unexpected)} {occurrences.describe()}, but found {found}",
            because,
        )
