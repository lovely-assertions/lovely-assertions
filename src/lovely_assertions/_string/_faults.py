"""The clause that says *which* character broke the rule.

A whole-string predicate answers yes or no, and no is not a message. These find
the first character that fails and say where it is and what it is -- which is the
difference between "not alphabetic" and a reader who can see the tab they pasted.

Every one of them runs after the predicate has already said no.
"""

from typing import TYPE_CHECKING

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._string._render import at, clipped, clipped_around

if TYPE_CHECKING:
    from collections.abc import Callable

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Why an empty string fails ``is_alpha`` and its siblings. ``"".isalpha()`` is
#: ``False``, and a reader told only that an empty string "is not alphabetic" is
#: left to go and find that out. ``isascii`` and ``isprintable`` are the two
#: exceptions -- both answer ``True`` -- so neither ever reaches this note.
_EMPTY_CLASS_NOTE = " (an empty string satisfies no character class)"


def class_fault(subject: str, holds: "Callable[[str], bool]", /) -> str:
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
            return clipped_around(subject, index) + " has " + clipped(char) + at(index)
    # Unreachable for a genuine character class: if a non-empty string failed,
    # one of its characters did. Kept so the function is total rather than
    # falling off the end with `None` the day a caller passes something else.
    return "was " + clipped(subject)


def identifier_fault(subject: str, /) -> str:
    """The ``but ...`` clause of a failed :meth:`StringExpect.is_identifier`.

    An identifier is one opening character followed by continuation characters,
    and the two sets differ: ``"1st"`` fails on its first character where
    ``"my-var"`` fails in the middle. The two are told apart rather than merged,
    for the same reason :func:`title_fault` distinguishes its two halves.

    ``str.isidentifier`` on a single character answers the opening question, and
    prefixing an underscore answers the continuation one -- ``"_1"`` is an
    identifier where ``"1"`` is not.
    """
    if not subject:
        return "it was empty"
    if not subject[0].isidentifier():
        return clipped(subject) + " cannot start with " + clipped(subject[0])
    for index, char in enumerate(subject):
        if not ("_" + char).isidentifier():
            return clipped_around(subject, index) + " has " + clipped(char) + at(index)
    return "was " + clipped(subject)


def is_uncased(text: str, /) -> bool:
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


def _is_titlecase(char: str, /) -> bool:
    """Whether ``char`` is a title-case character (Unicode category ``Lt``).

    There is no direct test for the category without ``unicodedata``, but the
    pair of predicates pins it down: ``"ǅ".istitle()`` is true and
    ``"ǅ".isupper()`` is false, where for a plain ``"A"`` both are true.
    """
    return char.istitle() and not char.isupper()


def stays_upper(char: str, /) -> bool:
    """Whether ``char`` leaves an all-upper-case string all-upper-case.

    Mirrors ``str.isupper`` character by character: it is a lower-case or a
    title-case character that makes the whole-string answer ``False``.
    """
    return not (char.islower() or _is_titlecase(char))


def stays_lower(char: str, /) -> bool:
    """The mirror of :func:`stays_upper`."""
    return not (char.isupper() or _is_titlecase(char))


def title_fault(subject: str, /) -> str:
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
    if is_uncased(subject):
        return clipped(subject) + " has no cased characters"
    previous_is_cased = False
    for index, char in enumerate(subject):
        if char.isupper() or _is_titlecase(char):
            if previous_is_cased:
                return (
                    clipped_around(subject, index)
                    + " continues a word with upper-case "
                    + clipped(char)
                    + at(index)
                )
            previous_is_cased = True
        elif char.islower():
            if not previous_is_cased:
                return (
                    clipped_around(subject, index)
                    + " starts a word with lower-case "
                    + clipped(char)
                    + at(index)
                )
            previous_is_cased = True
        else:
            previous_is_cased = False
    return "was " + clipped(subject)
