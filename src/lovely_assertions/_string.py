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
"""

from typing import TYPE_CHECKING, Self, cast, overload, override

from lovely_assertions._core import Expect, Found
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting
from lovely_assertions._text import (
    count_of,
    holds_any,
    holds_every,
    length_note,
    matches_wildcard,
    pattern_text,
    regex_matcher,
)

if TYPE_CHECKING:
    import re
    from collections.abc import Callable, Sequence
    from uuid import UUID

    from lovely_assertions._occurrence import Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["StringExpect"]

# The two rendering bounds this module observes -- the longest string printed in
# full, and how many values a multi-value message lists -- are `max_chars` and
# `max_items` on `_formatting.FormattingOptions`, read at the point of use rather
# than pinned here. The defaults sit where they do because past a terminal line a
# message stops informing and starts dumping, and past ten values a list stops
# being readable; a reader who wants more for the one message they are debugging
# writes `formatting(max_chars=1000)` around it.

#: Guard message for the multi-value assertions. ``contains_all()`` with nothing
#: to look for would pass whatever the subject is, and ``contains_any()`` could
#: never pass. Both are bugs in the test rather than findings about the subject,
#: so they are raised, not reported.
_NEEDS_VALUES = "at least one value to look for is required"

#: ``matches`` takes either a predicate or a regular expression under one name,
#: and only one of the two has anything to count. The overloads refuse the
#: combination statically; this is what an untyped caller gets, and it names which
#: of the two arguments to drop rather than merely refusing both.
_OCCURRENCES_NEED_A_PATTERN = (
    "occurrences counts matches of a regular expression, and a predicate answers"
    " yes or no rather than how many; pass a pattern, or drop occurrences"
)


def _clipped(text: str, /) -> str:
    """Render a string for a failure message, eliding an over-long one.

    Failure path only, which is what makes the ``ContextVar`` read affordable: the
    budget is ``max_chars`` from :func:`current_formatting`, so a
    ``formatting(max_chars=...)`` block widens every string in every message this
    module builds without a bound being threaded through every assertion here.

    Rendered through :func:`format_value` rather than ``repr``, so a registered
    ``str`` formatter reaches these messages too; with none registered the two
    are the same call. The elision runs first, on the text, so the formatter is
    handed what will actually be shown: the ``...`` sits inside the rendering
    instead of dangling after it, and ``max_chars`` counts the subject's own
    characters rather than the quotes and escapes a rendering adds to them.

    Assembled by concatenation rather than an f-string, which throughout this
    library marks the one finished message handed to ``_fail`` rather than a
    fragment on its way into one.
    """
    limit = current_formatting().max_chars
    if len(text) <= limit:
        return format_value(text)
    return format_value(text[:limit] + "...") + length_note(len(text))


def _clipped_end(text: str, /) -> str:
    """:func:`_clipped`, but keeping the end of the string rather than its start.

    Used by the ``ends_with`` family: showing the first line of a long document
    to explain what its last characters are would answer a question nobody asked.
    """
    limit = current_formatting().max_chars
    if len(text) <= limit:
        return format_value(text)
    return format_value("..." + text[-limit:]) + length_note(len(text))


def _preview(values: "Sequence[str]", /) -> str:
    """Render the values a multi-value assertion was given, or found, or missed.

    Failure path only. Each value goes through :func:`_clipped` and the list
    itself is capped, because both dimensions run away: ``contains_all(*fields)``
    is routinely called with a computed list, and echoing a hundred of them --
    or one of them a page long -- back at the reader helps nobody.
    """
    limit = current_formatting().max_items
    shown = [_clipped(value) for value in values[:limit]]
    if len(values) <= limit:
        return "[" + ", ".join(shown) + "]"
    return "[" + ", ".join(shown) + ", ... " + str(len(values) - limit) + " more]"


def _lf(text: str, /) -> str:
    """``text`` with CRLF and lone-CR line endings rewritten to LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _equivalent(subject: str, expected: str, /, *, whitespace: bool, newline_style: bool) -> bool:
    """Whether two strings match once case -- and optionally more -- is set aside.

    ``casefold`` rather than ``lower``: it is the comparison Unicode defines for
    caseless matching, so ``"STRASSE"`` and ``"straße"`` come out equal.

    ``whitespace`` removes whitespace outright, which subsumes the newline-style
    normalisation, hence the early return: ``split()`` with no argument splits on
    runs of any whitespace and drops the empty pieces, so joining the pieces back
    together leaves the text with none.
    """
    if whitespace:
        return "".join(subject.split()).casefold() == "".join(expected.split()).casefold()
    if newline_style:
        return _lf(subject).casefold() == _lf(expected).casefold()
    return subject.casefold() == expected.casefold()


def _ignoring(*, whitespace: bool, newline_style: bool) -> str:
    """The ``ignoring ...`` clause naming what an equivalence comparison set aside."""
    parts = ["case"]
    if whitespace:
        parts.append("whitespace")
    if newline_style:
        parts.append("newline style")
    if len(parts) == 1:
        return " ignoring case"
    return " ignoring " + ", ".join(parts[:-1]) + " and " + parts[-1]


def _is_uncased(text: str, /) -> bool:
    """Whether ``text`` holds no character that has a case at all.

    Failure path only, and the reason :meth:`StringExpect.is_upper` can tell
    ``"abc"`` from ``"123"``. The test is per character and is the one ``str``
    applies internally: a character is cased when it is lower case, upper case or
    title case. ``char.istitle()`` on a single character answers "upper case or
    title case", so the two predicates below cover all three.

    Case-mapping the whole string -- ``text.upper() == text.lower()`` -- looks
    like the same question and is not. A cased letter with no case mapping maps
    to itself both ways, and Unicode is full of them: ``"ª"`` -- the ordinal
    indicator in *1ª* -- is a lower-case letter, ``"ℾ"`` an upper-case one. Asked
    that way, ``is_upper("1ª")`` would report "no cased characters" about a
    string whose second character is the cased one the message should name.
    """
    return not any(char.islower() or char.istitle() for char in text)


#: The characters a UUID's body may be spelled with. A ``frozenset`` because the
#: check is a membership test over thirty-two characters, and the alternative --
#: a regular expression -- would drag ``re`` onto a path that does not need it.
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")

#: Length of a UUID's body -- what is left once dashes, braces and any
#: ``urn:uuid:`` prefix come off. Named so the check is not a bare number.
_UUID_DIGITS = 32

#: The versions this assertion can check -- the five RFC 4122 defines. RFC 9562
#: has since added 6, 7 and 8; they are not in the range yet. Anything outside it
#: is a bug in the test rather than a finding about the subject, so it is raised.
_UUID_VERSIONS = range(1, 6)

#: Said as a fact about *this assertion*, not about UUIDs. "A UUID version must
#: be 1, 2, 3, 4 or 5" would be false -- and would tell somebody holding a
#: perfectly good version 7 id that their id is malformed.
#:
#: The version that arrived is appended, because ``version=7`` and ``version=9``
#: are different mistakes -- 7 is a real version this range has not caught up
#: with, 9 is one nobody defines -- and a caller reading the traceback should not
#: have to go back to the call to see which number was refused. Through ``repr``,
#: so an untyped caller who passed the string ``"4"`` sees the quotes that
#: explain why a number that looks right was turned down.
_BAD_UUID_VERSION = (
    "this assertion checks UUID versions 1 to 5; RFC 9562 also defines 6, 7 and 8,"
    " and the version asked for was "
)

#: Why an empty string fails ``is_alpha`` and its siblings. ``"".isalpha()`` is
#: ``False``, and a reader told only that an empty string "is not alphabetic" is
#: left to go and find that out. ``isascii`` and ``isprintable`` are the two
#: exceptions -- both answer ``True`` -- so neither ever reaches this note.
_EMPTY_CLASS_NOTE = " (an empty string satisfies no character class)"


def _clipped_around(text: str, index: int, /) -> str:
    """:func:`_clipped`, keeping the window around ``index`` rather than the start.

    Naming the character that broke a character-class assertion is only half an
    answer if the elision cut it out of the rendering: a stray tab at index 400
    of a document would otherwise be reported beside the document's first line.
    """
    limit = current_formatting().max_chars
    if len(text) <= limit:
        return format_value(text)
    start = max(0, min(index - limit // 2, len(text) - limit))
    window = text[start : start + limit]
    if start:
        window = "..." + window
    if start + limit < len(text):
        window += "..."
    return format_value(window) + length_note(len(text))


def _at(index: int, /) -> str:
    """The `` at index N`` tail that every offending-character clause ends with."""
    return " at index " + str(index)


def _class_fault(subject: str, holds: "Callable[[str], bool]", /) -> str:
    """The ``but ...`` clause of a failed character-class assertion.

    Failure path only. ``str.isalpha`` and its siblings answer for the whole
    string, so the message has to go back and find *which* character broke it.
    That character and its index are the difference between a message that helps
    and one that repeats the assertion back at the reader.

    The empty string gets a clause of its own. Every one of these methods except
    ``isascii`` and ``isprintable`` answers ``False`` for it, and "is not
    alphabetic" is not an explanation of why.
    """
    if not subject:
        return "it was empty" + _EMPTY_CLASS_NOTE
    for index, char in enumerate(subject):
        if not holds(char):
            return _clipped_around(subject, index) + " has " + _clipped(char) + _at(index)
    # Unreachable for a genuine character class: if a non-empty string failed,
    # one of its characters did. Kept so the function is total rather than
    # falling off the end with `None` the day a caller passes something else.
    return "was " + _clipped(subject)


def _is_titlecase(char: str, /) -> bool:
    """Whether ``char`` is a title-case character (Unicode category ``Lt``).

    There is no direct test for the category without ``unicodedata``, but the
    pair of predicates pins it down: ``"ǅ".istitle()`` is true and
    ``"ǅ".isupper()`` is false, where for a plain ``"A"`` both are true.
    """
    return char.istitle() and not char.isupper()


def _stays_upper(char: str, /) -> bool:
    """Whether ``char`` leaves an all-upper-case string all-upper-case.

    Mirrors ``str.isupper`` character by character: it is a lower-case or a
    title-case character that makes the whole-string answer ``False``.
    """
    return not (char.islower() or _is_titlecase(char))


def _stays_lower(char: str, /) -> bool:
    """The mirror of :func:`_stays_upper`."""
    return not (char.isupper() or _is_titlecase(char))


def _title_fault(subject: str, /) -> str:
    """The ``but ...`` clause of a failed :meth:`StringExpect.is_title`.

    ``str.istitle`` walks the string tracking whether the previous character was
    cased: an upper-case character may only follow an uncased one, a lower-case
    character may only follow a cased one, and a string holding no cased
    character at all is not title case however it is spelled. This is the same
    walk, stopped at the first character that broke the rule -- and it reports
    *which* half was broken, because "starts a word in lower case" and
    "continues a word in upper case" send the reader to different fixes.
    """
    if not subject:
        return "it was empty"
    if _is_uncased(subject):
        return _clipped(subject) + " has no cased characters"
    previous_is_cased = False
    for index, char in enumerate(subject):
        if char.isupper() or _is_titlecase(char):
            if previous_is_cased:
                return (
                    _clipped_around(subject, index)
                    + " continues a word with upper-case "
                    + _clipped(char)
                    + _at(index)
                )
            previous_is_cased = True
        elif char.islower():
            if not previous_is_cased:
                return (
                    _clipped_around(subject, index)
                    + " starts a word with lower-case "
                    + _clipped(char)
                    + _at(index)
                )
            previous_is_cased = True
        else:
            previous_is_cased = False
    return "was " + _clipped(subject)


def _identifier_fault(subject: str, /) -> str:
    """The ``but ...`` clause of a failed :meth:`StringExpect.is_identifier`.

    An identifier is one opening character followed by continuation characters,
    and the two sets differ: ``"1st"`` fails on its first character where
    ``"my-var"`` fails in the middle. The two are told apart rather than merged,
    for the same reason :func:`_title_fault` distinguishes its two halves.

    ``str.isidentifier`` on a single character answers the opening question, and
    prefixing an underscore answers the continuation one -- ``"_1"`` is an
    identifier where ``"1"`` is not.
    """
    if not subject:
        return "it was empty"
    if not subject[0].isidentifier():
        return _clipped(subject) + " cannot start with " + _clipped(subject[0])
    for index, char in enumerate(subject):
        if not ("_" + char).isidentifier():
            return _clipped_around(subject, index) + " has " + _clipped(char) + _at(index)
    return "was " + _clipped(subject)


def _uuid_digits(text: str, /) -> str:
    """The hexadecimal body of a UUID spelling: ``urn:uuid:``, braces and dashes off.

    The same normalisation ``uuid.UUID`` performs on its argument, so every
    spelling the standard library reads is read here too.
    """
    return text.replace("urn:", "").replace("uuid:", "").strip("{}").replace("-", "")


def _uuid_fault(subject: str, digits: str, /) -> str:
    """Why ``subject`` could not be read as a UUID. Failure path only.

    ``digits`` is the normalised *body*, and the message calls it that: dashes
    and braces are punctuation, so counting them would tell the reader that
    ``"not-a-uuid"`` is ten characters long when the eight that had to be
    hexadecimal are the ones the assertion is about.
    """
    if len(digits) != _UUID_DIGITS:
        return (
            _clipped(subject)
            + " has a body of "
            + count_of(len(digits), "character")
            + ", not 32 hexadecimal digits"
        )
    for index, char in enumerate(digits):
        if char not in _HEX_DIGITS:
            return (
                _clipped(subject)
                + " has "
                + _clipped(char)
                + " where a hexadecimal digit was expected, at digit "
                + str(index + 1)
                + " of 32"
            )
    # Unreachable: the caller only asks when one of the two checks above failed.
    # Kept so the function is total rather than returning `None` off the end.
    return _clipped(subject) + " could not be read as one"


def _version_note(parsed: "UUID", /) -> str:
    """How a parsed UUID answers the version question. Failure path only."""
    if parsed.version is None:
        return "carries no version, its variant not being RFC 4122"
    return "is version " + str(parsed.version)


class StringExpect(Expect[str]):
    """Assertions for strings."""

    __slots__ = ()

    # -- emptiness ---------------------------------------------------------
    def is_empty(self, *, because: str = "") -> Self:
        """Assert the string has no characters at all."""
        if not self._subject:
            return self
        return self._fail(f"to be empty, but was {_clipped(self._subject)}", because)

    def is_not_empty(self, *, because: str = "") -> Self:
        """Assert the string has at least one character."""
        if self._subject:
            return self
        return self._fail("not to be empty, but it was", because)

    def is_blank(self, *, because: str = "") -> Self:
        """Assert the string is empty or contains nothing but whitespace.

        The lenient neighbour of :meth:`is_empty`, which accepts a string of no
        characters and nothing else, and of :meth:`is_space`, which requires at
        least one whitespace character. Reach for this one when whitespace is not
        content.

        Written as ``not subject or subject.isspace()`` rather than the more
        obvious ``not subject.strip()``: same answer, without the stripped copy
        the tidier spelling allocates on every passing call, where a passing
        assertion is meant to cost a comparison and nothing more.
        """
        subject = self._subject
        if not subject or subject.isspace():
            return self
        return self._fail(f"to be blank, but was {_clipped(subject)}", because)

    def is_not_blank(self, *, because: str = "") -> Self:
        """Assert the string holds something other than whitespace."""
        subject = self._subject
        if subject and not subject.isspace():
            return self
        return self._fail(f"not to be blank, but was {_clipped(subject)}", because)

    # -- length ------------------------------------------------------------
    def has_length(self, expected: int, /, *, because: str = "") -> Self:
        """Assert the string is ``expected`` characters long."""
        subject = self._subject
        if len(subject) == expected:
            return self
        return self._fail(
            f"to have length {expected}, but {_clipped(subject)} has length {len(subject)}",
            because,
        )

    # -- caseless equality -------------------------------------------------
    def is_equal_ignoring_case(
        self,
        expected: str,
        /,
        *,
        ignoring_whitespace: bool = False,
        ignoring_newline_style: bool = False,
        because: str = "",
    ) -> Self:
        """Assert the string equals ``expected`` once case is set aside.

        ``ignoring_whitespace`` drops whitespace from both sides entirely, which
        covers indentation, wrapping and trailing newlines in one option rather
        than three. ``ignoring_newline_style`` is the narrower tool: it rewrites
        CRLF and CR to LF, so a file read on Windows compares equal to the same
        file read anywhere else, and nothing else moves.
        """
        subject = self._subject
        if _equivalent(
            subject,
            expected,
            whitespace=ignoring_whitespace,
            newline_style=ignoring_newline_style,
        ):
            return self
        clause = _ignoring(whitespace=ignoring_whitespace, newline_style=ignoring_newline_style)
        return self._fail(
            f"to equal {_clipped(expected)}{clause}, but was {_clipped(subject)}", because
        )

    def is_not_equal_ignoring_case(
        self,
        unexpected: str,
        /,
        *,
        ignoring_whitespace: bool = False,
        ignoring_newline_style: bool = False,
        because: str = "",
    ) -> Self:
        """Assert the string differs from ``unexpected`` by more than case."""
        subject = self._subject
        if not _equivalent(
            subject,
            unexpected,
            whitespace=ignoring_whitespace,
            newline_style=ignoring_newline_style,
        ):
            return self
        clause = _ignoring(whitespace=ignoring_whitespace, newline_style=ignoring_newline_style)
        return self._fail(
            f"not to equal {_clipped(unexpected)}{clause}, but was {_clipped(subject)}", because
        )

    # -- containment -------------------------------------------------------
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
            return self._fail(f"to contain {_clipped(value)}, but was {_clipped(subject)}", because)
        found = subject.count(value)
        if occurrences.allows(found):
            return self
        return self._fail(
            f"to contain {_clipped(value)} {occurrences.describe()}, but found {found}", because
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
                f"not to contain {_clipped(unexpected)}, but {_clipped(subject)} does", because
            )
        found = subject.count(unexpected)
        if not occurrences.allows(found):
            return self
        return self._fail(
            f"not to contain {_clipped(unexpected)} {occurrences.describe()}, but found {found}",
            because,
        )

    def contains_all(self, *values: str, because: str = "") -> Self:
        """Assert every one of ``values`` appears in the string.

        The failure names the values that were missing rather than reporting
        only that some were. Called with no values at all this raises
        ``ValueError``: an assertion that looks for nothing would pass whatever
        the subject is, which is a bug where it was written rather than a
        finding about the subject. :meth:`contains_any` asks for one of them
        instead of all.
        """
        if not values:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if holds_every(subject, values):
            return self
        missing = [value for value in values if value not in subject]
        return self._fail(
            f"to contain all of {_preview(values)}, "
            f"but {_clipped(subject)} is missing {_preview(missing)}",
            because,
        )

    def does_not_contain_all(self, *values: str, because: str = "") -> Self:
        """Assert at least one of ``values`` is absent from the string.

        The negation of :meth:`contains_all`, so it is satisfied by one missing
        value; :meth:`does_not_contain_any` is the one that demands all of them
        be absent. Raises ``ValueError`` when called with no values, for the
        reason :meth:`contains_all` gives.
        """
        if not values:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if not holds_every(subject, values):
            return self
        return self._fail(
            f"not to contain all of {_preview(values)}, "
            f"but {_clipped(subject)} contains every one of them",
            because,
        )

    def contains_any(self, *values: str, because: str = "") -> Self:
        """Assert at least one of ``values`` appears in the string.

        :meth:`contains_all` is the one that demands every value. The failure
        reports that none of them were found, and echoes the values it looked
        for. Raises ``ValueError`` when called with no values: a choice between
        nothing could never be satisfied by any subject.
        """
        if not values:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if holds_any(subject, values):
            return self
        return self._fail(
            f"to contain at least one of {_preview(values)}, "
            f"but {_clipped(subject)} contains none of them",
            because,
        )

    def does_not_contain_any(self, *values: str, because: str = "") -> Self:
        """Assert none of ``values`` appears in the string.

        Every one of them has to be absent, where :meth:`does_not_contain_all`
        is satisfied by a single missing value. The failure names the ones that
        were found. Raises ``ValueError`` when called with no values.
        """
        if not values:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if not holds_any(subject, values):
            return self
        present = [value for value in values if value in subject]
        return self._fail(
            f"not to contain any of {_preview(values)}, "
            f"but {_clipped(subject)} contains {_preview(present)}",
            because,
        )

    def contains_ignoring_case(
        self, value: str, /, *, occurrences: "Occurrence | None" = None, because: str = ""
    ) -> Self:
        """Assert ``value`` appears in the string, whatever the case of either.

        ``occurrences`` counts the casefolded needle in the casefolded subject,
        non-overlapping as everywhere else (:meth:`contains`). Both sides are
        folded before counting because casefolding can change a string's length --
        ``"ß"`` folds to ``"ss"`` -- so ``"ßß"`` contains ``"ss"`` twice, and
        counting against the unfolded text would answer about a string nobody
        wrote.
        """
        subject = self._subject
        if occurrences is None:
            if value.casefold() in subject.casefold():
                return self
            return self._fail(
                f"to contain {_clipped(value)} ignoring case, but was {_clipped(subject)}", because
            )
        found = subject.casefold().count(value.casefold())
        if occurrences.allows(found):
            return self
        return self._fail(
            f"to contain {_clipped(value)} ignoring case {occurrences.describe()},"
            f" but found {found}",
            because,
        )

    def does_not_contain_ignoring_case(self, unexpected: str, /, *, because: str = "") -> Self:
        """Assert ``unexpected`` appears nowhere in the string, in any case."""
        subject = self._subject
        if unexpected.casefold() not in subject.casefold():
            return self
        return self._fail(
            f"not to contain {_clipped(unexpected)} ignoring case, but {_clipped(subject)} does",
            because,
        )

    # -- edges -------------------------------------------------------------
    def starts_with(self, prefix: str, /, *, because: str = "") -> Self:
        """Assert the string begins with ``prefix``."""
        subject = self._subject
        if subject.startswith(prefix):
            return self
        return self._fail(f"to start with {_clipped(prefix)}, but was {_clipped(subject)}", because)

    def does_not_start_with(self, prefix: str, /, *, because: str = "") -> Self:
        """Assert the string does not begin with ``prefix``."""
        subject = self._subject
        if not subject.startswith(prefix):
            return self
        return self._fail(
            f"not to start with {_clipped(prefix)}, but was {_clipped(subject)}", because
        )

    def starts_with_ignoring_case(self, prefix: str, /, *, because: str = "") -> Self:
        """Assert the string begins with ``prefix``, whatever the case of either.

        Both sides are casefolded before the comparison, which is why this is not
        simply ``startswith`` on a folded prefix: casefolding can change a
        string's length -- ``"ß"`` folds to ``"ss"`` -- and the prefix has to be
        measured against the folded subject to stay honest.
        """
        subject = self._subject
        if subject.casefold().startswith(prefix.casefold()):
            return self
        return self._fail(
            f"to start with {_clipped(prefix)} ignoring case, but was {_clipped(subject)}",
            because,
        )

    def does_not_start_with_ignoring_case(self, prefix: str, /, *, because: str = "") -> Self:
        """Assert the string does not begin with ``prefix`` in any case."""
        subject = self._subject
        if not subject.casefold().startswith(prefix.casefold()):
            return self
        return self._fail(
            f"not to start with {_clipped(prefix)} ignoring case, but was {_clipped(subject)}",
            because,
        )

    def ends_with(self, suffix: str, /, *, because: str = "") -> Self:
        """Assert the string ends with ``suffix``."""
        subject = self._subject
        if subject.endswith(suffix):
            return self
        return self._fail(
            f"to end with {_clipped(suffix)}, but was {_clipped_end(subject)}", because
        )

    def does_not_end_with(self, suffix: str, /, *, because: str = "") -> Self:
        """Assert the string does not end with ``suffix``."""
        subject = self._subject
        if not subject.endswith(suffix):
            return self
        return self._fail(
            f"not to end with {_clipped(suffix)}, but was {_clipped_end(subject)}", because
        )

    def ends_with_ignoring_case(self, suffix: str, /, *, because: str = "") -> Self:
        """Assert the string ends with ``suffix``, whatever the case of either."""
        subject = self._subject
        if subject.casefold().endswith(suffix.casefold()):
            return self
        return self._fail(
            f"to end with {_clipped(suffix)} ignoring case, but was {_clipped_end(subject)}",
            because,
        )

    def does_not_end_with_ignoring_case(self, suffix: str, /, *, because: str = "") -> Self:
        """Assert the string does not end with ``suffix`` in any case."""
        subject = self._subject
        if not subject.casefold().endswith(suffix.casefold()):
            return self
        return self._fail(
            f"not to end with {_clipped(suffix)} ignoring case, but was {_clipped_end(subject)}",
            because,
        )

    # -- regular expressions -----------------------------------------------
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
                f"but was {_clipped(subject)}",
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
                f"the empty string at index {found.start()} of {_clipped(subject)}",
                because,
            )
        if matched == subject:
            # Naming the match and the subject separately would print the same
            # text twice, and a greedy pattern makes that the common case.
            return self._fail(
                f"not to match the regular expression {pattern_text(pattern)!r}, "
                f"but {_clipped(subject)} matches it in full",
                because,
            )
        return self._fail(
            f"not to match the regular expression {pattern_text(pattern)!r}, "
            f"but {_clipped(subject)} contains {_clipped(matched)} at index {found.start()}",
            because,
        )

    # -- wildcards ---------------------------------------------------------
    def matches_wildcard(self, pattern: str, /, *, because: str = "") -> Self:
        """Assert the whole string matches the wildcard ``pattern``.

        ``*`` matches any run of characters and ``?`` exactly one; everything
        else, punctuation included, is literal. Unlike :meth:`matches` this is a
        full match, which is what makes the wildcard form worth having.
        """
        subject = self._subject
        if matches_wildcard(subject, pattern, ignoring_case=False):
            return self
        return self._fail(
            f"to match the wildcard pattern {pattern!r}, but was {_clipped(subject)}", because
        )

    def does_not_match_wildcard(self, pattern: str, /, *, because: str = "") -> Self:
        """Assert the string does not match the wildcard ``pattern`` in full."""
        subject = self._subject
        if not matches_wildcard(subject, pattern, ignoring_case=False):
            return self
        return self._fail(
            f"not to match the wildcard pattern {pattern!r}, but was {_clipped(subject)}", because
        )

    def matches_wildcard_ignoring_case(self, pattern: str, /, *, because: str = "") -> Self:
        """Assert the whole string matches the wildcard ``pattern``, ignoring case."""
        subject = self._subject
        if matches_wildcard(subject, pattern, ignoring_case=True):
            return self
        return self._fail(
            f"to match the wildcard pattern {pattern!r} ignoring case, but was {_clipped(subject)}",
            because,
        )

    def does_not_match_wildcard_ignoring_case(self, pattern: str, /, *, because: str = "") -> Self:
        """Assert the string does not match the wildcard ``pattern``, in any case."""
        subject = self._subject
        if not matches_wildcard(subject, pattern, ignoring_case=True):
            return self
        return self._fail(
            f"not to match the wildcard pattern {pattern!r} ignoring case, "
            f"but was {_clipped(subject)}",
            because,
        )

    # -- case --------------------------------------------------------------
    def is_upper(self, *, because: str = "") -> Self:
        """Assert every cased character in the string is upper case.

        ``str.isupper`` is the test, so a string with no cased characters at all
        -- ``"123"``, ``""`` -- is neither upper nor lower and fails both this
        and :meth:`is_lower`. That failure gets its own message: a reader shown
        ``but was '123'`` would reasonably conclude the assertion was broken.

        Any other failure names the character that caused it and where it sits,
        the way the character-class family does. ``but 'Abc' has 'b' at index 1``
        beats ``but was 'Abc'`` on anything longer than three characters.
        """
        subject = self._subject
        if subject.isupper():
            return self
        if _is_uncased(subject):
            return self._fail(
                f"to be upper case, but {_clipped(subject)} has no cased characters", because
            )
        return self._fail(f"to be upper case, but {_class_fault(subject, _stays_upper)}", because)

    def is_not_upper(self, *, because: str = "") -> Self:
        """Assert the string is not entirely upper case."""
        subject = self._subject
        if not subject.isupper():
            return self
        return self._fail(f"not to be upper case, but was {_clipped(subject)}", because)

    def is_lower(self, *, because: str = "") -> Self:
        """Assert every cased character in the string is lower case.

        The mirror of :meth:`is_upper`, uncased strings included.
        """
        subject = self._subject
        if subject.islower():
            return self
        if _is_uncased(subject):
            return self._fail(
                f"to be lower case, but {_clipped(subject)} has no cased characters", because
            )
        return self._fail(f"to be lower case, but {_class_fault(subject, _stays_lower)}", because)

    def is_not_lower(self, *, because: str = "") -> Self:
        """Assert the string is not entirely lower case."""
        subject = self._subject
        if not subject.islower():
            return self
        return self._fail(f"not to be lower case, but was {_clipped(subject)}", because)

    def is_title(self, *, because: str = "") -> Self:
        """Assert the string is title case (``str.istitle``).

        Title case is a rule about words rather than about characters: an
        upper-case character may only follow an uncased one and a lower-case
        character may only follow a cased one, so ``"Hello World"`` passes while
        both ``"hello World"`` and ``"HELLO"`` fail. The message names the
        character that broke the rule and which half of it went.

        A string with no cased characters at all is not title case either -- the
        same trap :meth:`is_upper` documents, and it gets the same message.
        """
        subject = self._subject
        if subject.istitle():
            return self
        return self._fail(f"to be title case, but {_title_fault(subject)}", because)

    def is_not_title(self, *, because: str = "") -> Self:
        """Assert the string is not title case.

        True of the empty string, which ``str.istitle`` rejects for want of a
        cased character.
        """
        subject = self._subject
        if not subject.istitle():
            return self
        return self._fail(f"not to be title case, but {_clipped(subject)} is", because)

    # -- character classes -------------------------------------------------
    def is_alpha(self, *, because: str = "") -> Self:
        """Assert every character is a letter (``str.isalpha``).

        Letters as Unicode understands them, so ``"héllo"`` and ``"日本語"`` pass.
        The empty string does not: ``"".isalpha()`` is ``False``, and the message
        says as much rather than leaving the reader to work out why nothing is
        not alphabetic.
        """
        subject = self._subject
        if subject.isalpha():
            return self
        return self._fail(
            f"to contain only alphabetic characters, but {_class_fault(subject, str.isalpha)}",
            because,
        )

    def is_not_alpha(self, *, because: str = "") -> Self:
        """Assert the string is not made entirely of letters.

        Satisfied by the empty string, which belongs to no character class.
        """
        subject = self._subject
        if not subject.isalpha():
            return self
        return self._fail(
            f"not to contain only alphabetic characters, but {_clipped(subject)} does", because
        )

    def is_digit(self, *, because: str = "") -> Self:
        r"""Assert every character is a digit (``str.isdigit``).

        Python has three overlapping tests here and they are not interchangeable.
        ``isdecimal`` is the narrowest: the characters that spell a base-ten
        number, and exactly the ones ``int()`` will read. ``isdigit`` adds the
        digit-like characters that it will not -- ``"²".isdigit()`` is ``True``
        where ``"²".isdecimal()`` is ``False``, and ``int("²")`` raises.
        :meth:`is_numeric` is wider still.

        Two of the three are exposed and this is the middle one. **If what you
        mean is "this parses as an integer", this is not that assertion**: use
        ``matches(r"\A\d+\Z")``, whose ``\d`` is the decimal set, or assert on the
        parsed value. What this one is good for is rejecting the letters and
        punctuation in a code or an id, where ``"²"`` is not the failure anybody
        is hunting.

        An empty string fails, as it does for every class here.
        """
        subject = self._subject
        if subject.isdigit():
            return self
        return self._fail(
            f"to contain only digits, but {_class_fault(subject, str.isdigit)}", because
        )

    def is_not_digit(self, *, because: str = "") -> Self:
        """Assert the string is not made entirely of digits."""
        subject = self._subject
        if not subject.isdigit():
            return self
        return self._fail(f"not to contain only digits, but {_clipped(subject)} does", because)

    def is_numeric(self, *, because: str = "") -> Self:
        """Assert every character is numeric (``str.isnumeric``).

        The widest of the three tests :meth:`is_digit` sets out: on top of the
        digits it takes the characters that *mean* a number without spelling one,
        so the fraction ``"½"`` and the Roman numeral ``"Ⅷ"`` pass here and fail
        there. Right when the question is "does this text denote a quantity";
        misleading when the question is "will ``int()`` read it".
        """
        subject = self._subject
        if subject.isnumeric():
            return self
        return self._fail(
            f"to contain only numeric characters, but {_class_fault(subject, str.isnumeric)}",
            because,
        )

    def is_not_numeric(self, *, because: str = "") -> Self:
        """Assert the string is not made entirely of numeric characters."""
        subject = self._subject
        if not subject.isnumeric():
            return self
        return self._fail(
            f"not to contain only numeric characters, but {_clipped(subject)} does", because
        )

    def is_alnum(self, *, because: str = "") -> Self:
        """Assert every character is a letter or a number (``str.isalnum``).

        The union of :meth:`is_alpha`, :meth:`is_digit` and :meth:`is_numeric`,
        so it accepts ``"½"`` as readily as ``"a"``. Note what it does *not*
        accept: the underscore, which makes a Python name non-alphanumeric.
        :meth:`is_identifier` is that test.
        """
        subject = self._subject
        if subject.isalnum():
            return self
        return self._fail(
            f"to contain only letters and numbers, but {_class_fault(subject, str.isalnum)}",
            because,
        )

    def is_not_alnum(self, *, because: str = "") -> Self:
        """Assert the string is not made entirely of letters and numbers."""
        subject = self._subject
        if not subject.isalnum():
            return self
        return self._fail(
            f"not to contain only letters and numbers, but {_clipped(subject)} does", because
        )

    def is_ascii(self, *, because: str = "") -> Self:
        """Assert every character is ASCII (``str.isascii``).

        One of the two exceptions to the empty-string rule: ``"".isascii()`` is
        ``True``, every one of its zero characters being ASCII. The message names
        the first character that is not and where it sits, which is the whole
        question when a non-breaking space or a smart quote has come back from an
        editor.
        """
        subject = self._subject
        if subject.isascii():
            return self
        return self._fail(
            f"to contain only ASCII characters, but {_class_fault(subject, str.isascii)}", because
        )

    def is_not_ascii(self, *, because: str = "") -> Self:
        """Assert the string holds at least one character outside ASCII.

        Fails for the empty string, which ``str.isascii`` accepts.
        """
        subject = self._subject
        if not subject.isascii():
            return self
        return self._fail(
            f"not to contain only ASCII characters, but {_clipped(subject)} does", because
        )

    def is_printable(self, *, because: str = "") -> Self:
        r"""Assert every character is printable (``str.isprintable``).

        Printable means: not in an "Other" Unicode category, and not a separator
        other than the ASCII space -- so ``"\n"`` and ``"\x00"`` fail where ``" "``
        passes. The other exception to the empty-string rule:
        ``"".isprintable()`` is ``True``.

        ``repr`` escapes exactly the characters this rejects, so the offender
        shows up in the message as ``'\x07'`` rather than as nothing at all.
        """
        subject = self._subject
        if subject.isprintable():
            return self
        return self._fail(
            f"to contain only printable characters, but {_class_fault(subject, str.isprintable)}",
            because,
        )

    def is_not_printable(self, *, because: str = "") -> Self:
        """Assert the string holds at least one unprintable character.

        Fails for the empty string, which ``str.isprintable`` accepts.
        """
        subject = self._subject
        if not subject.isprintable():
            return self
        return self._fail(
            f"not to contain only printable characters, but {_clipped(subject)} does", because
        )

    def is_space(self, *, because: str = "") -> Self:
        """Assert the string is non-empty and made only of whitespace (``str.isspace``).

        The strict sibling of :meth:`is_blank`, which also accepts the empty
        string. ``str.isspace`` does not, and the message says so.
        """
        subject = self._subject
        if subject.isspace():
            return self
        return self._fail(
            f"to contain only whitespace, but {_class_fault(subject, str.isspace)}", because
        )

    def is_not_space(self, *, because: str = "") -> Self:
        """Assert the string is not made entirely of whitespace.

        Satisfied by the empty string, where :meth:`is_not_blank` is not.
        """
        subject = self._subject
        if not subject.isspace():
            return self
        return self._fail(f"not to contain only whitespace, but {_clipped(subject)} does", because)

    # -- identifiers -------------------------------------------------------
    def is_identifier(self, *, because: str = "") -> Self:
        """Assert the string is a valid Python identifier (``str.isidentifier``).

        The opening character and the continuation characters obey different
        rules, and the message says which one was broken: ``"1st"`` cannot
        *start* with ``"1"``, where ``"my-var"`` has a ``"-"`` at index 2.

        It answers the language's lexical question and nothing more, so a keyword
        passes -- ``"class".isidentifier()`` is ``True``. Chain
        ``.and_.is_not_in(keyword.kwlist)`` when a keyword has to be refused too.
        """
        subject = self._subject
        if subject.isidentifier():
            return self
        return self._fail(
            f"to be a valid Python identifier, but {_identifier_fault(subject)}", because
        )

    def is_not_identifier(self, *, because: str = "") -> Self:
        """Assert the string is not a valid Python identifier."""
        subject = self._subject
        if not subject.isidentifier():
            return self
        return self._fail(
            f"not to be a valid Python identifier, but {_clipped(subject)} is one", because
        )

    # -- UUIDs -------------------------------------------------------------
    def is_uuid(self, *, version: int | None = None, because: str = "") -> "Found[Self, UUID]":
        """Assert the string spells a UUID; continue on the parsed one with ``.which``.

        Worth more than a format check. ``UUID("...") == "..."`` is ``False``,
        silently and in both directions, so an id that has crossed a JSON
        boundary compares unequal to the same id that has not -- and
        :meth:`is_equal_to` on the two would fail for a reason that has nothing
        to do with the value. This is the join. It proves the text is a UUID and
        hands back the ``UUID``, which then compares the way the reader expects::

            expect(payload["id"]).is_uuid(version=4).which.is_equal_to(order.id)

        Every spelling ``uuid.UUID`` accepts is accepted: dashed or not, wrapped
        in braces, prefixed ``urn:uuid:``. **Two things it accepts are refused
        here on purpose.** ``uuid.UUID`` finishes with ``int(body, 16)``, which
        tolerates underscores and leading whitespace, so
        ``uuid.UUID("1_23...")`` succeeds and quietly returns a *different* id
        from the one that was written. Passing that would be the exact bug this
        assertion exists to catch, so the body is required to be thirty-two
        hexadecimal digits and nothing else.

        ``version`` narrows to one of the five versions RFC 4122 defines. RFC
        9562 has since added 6, 7 and 8, and this range has not caught up: a
        version 7 id passes ``is_uuid()`` itself, but ``version=7`` raises
        ``ValueError``, as any number outside the range does -- that is a bug in
        the test rather than a finding about the subject. A well-formed UUID
        string can also have *no* version -- the field lives in bits that only an
        RFC 4122 variant carries -- and the message says that rather than
        reporting a mismatch against ``None``.
        """
        if version is not None and version not in _UUID_VERSIONS:
            raise ValueError(_BAD_UUID_VERSION + repr(version))

        import uuid  # noqa: PLC0415  (kept off import time; only this assertion needs it)

        subject = self._subject
        digits = _uuid_digits(subject)
        if len(digits) != _UUID_DIGITS or not _HEX_DIGITS.issuperset(digits):
            return cast(
                "Found[Self, UUID]",
                self._fail_narrowing(f"to be a UUID, but {_uuid_fault(subject, digits)}", because),
            )
        parsed = uuid.UUID(hex=digits)
        if version is None or parsed.version == version:
            return Found(self, parsed)
        return cast(
            "Found[Self, UUID]",
            self._fail_narrowing(
                f"to be a version {version} UUID, but {_clipped(subject)} {_version_note(parsed)}",
                because,
            ),
        )
