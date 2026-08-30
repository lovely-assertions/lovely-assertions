"""The one string assertion that hands back something else.

A string that is a UUID is more usefully a ``UUID``, so this narrows. The version
guard is separate from the shape guard because the two fail for different reasons
and a reader debugging one does not want to be told about the other.

``uuid`` is imported inside the failure branch. A library that parses UUIDs on
import would charge every program that never mentions one.
"""

from typing import TYPE_CHECKING, Self, cast

from lovely_assertions._core import Expect, Found
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._string._render import clipped
from lovely_assertions._text import count_of

if TYPE_CHECKING:
    from uuid import UUID

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


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


def _uuid_digits(text: str, /) -> str:
    """The hexadecimal body of a UUID spelling: ``urn:uuid:``, braces and dashes off.

    The same normalisation ``uuid.UUID`` performs on its argument, so every
    spelling the standard library reads is read here too.
    """
    return text.replace("urn:", "").replace("uuid:", "").strip("{}").replace("-", "")


def uuid_fault(subject: str, digits: str, /) -> str:
    """Why ``subject`` could not be read as a UUID. Failure path only.

    ``digits`` is the normalised *body*, and the message calls it that: dashes
    and braces are punctuation, so counting them would tell the reader that
    ``"not-a-uuid"`` is ten characters long when the eight that had to be
    hexadecimal are the ones the assertion is about.
    """
    if len(digits) != _UUID_DIGITS:
        return (
            clipped(subject)
            + " has a body of "
            + count_of(len(digits), "character")
            + ", not 32 hexadecimal digits"
        )
    for index, char in enumerate(digits):
        if char not in _HEX_DIGITS:
            return (
                clipped(subject)
                + " has "
                + clipped(char)
                + " where a hexadecimal digit was expected, at digit "
                + str(index + 1)
                + " of 32"
            )
    # Unreachable: the caller only asks when one of the two checks above failed.
    # Kept so the function is total rather than returning `None` off the end.
    return clipped(subject) + " could not be read as one"


def _version_note(parsed: "UUID", /) -> str:
    """How a parsed UUID answers the version question. Failure path only."""
    if parsed.version is None:
        return "carries no version, its variant not being RFC 4122"
    return "is version " + str(parsed.version)


class UuidAssertions(Expect[str]):
    """A UUID, and the narrowing that follows one."""

    __slots__ = ()

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
                self._fail_narrowing(f"to be a UUID, but {uuid_fault(subject, digits)}", because),
            )
        parsed = uuid.UUID(hex=digits)
        if version is None or parsed.version == version:
            return Found(self, parsed)
        return cast(
            "Found[Self, UUID]",
            self._fail_narrowing(
                f"to be a version {version} UUID, but {clipped(subject)} {_version_note(parsed)}",
                because,
            ),
        )
