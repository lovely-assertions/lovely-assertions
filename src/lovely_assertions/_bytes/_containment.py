"""What is in a byte string, asked the two ways Python itself allows.

``bytes`` answers ``in`` for an integer *and* for a byte string -- ``101 in
b"hello"`` and ``b"he" in b"hello"`` are both true -- and the inherited
collection catalogue offers only the first. Widening it here is following the
language rather than inventing something: the parameter grows, which is
contravariant and so leaves every existing call meaning exactly what it meant.
"""

from typing import TYPE_CHECKING, Self, overload, override

from lovely_assertions._bytes._base import BytesBase
from lovely_assertions._bytes._render import as_hex, clipped
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._text import count_of

if TYPE_CHECKING:
    from lovely_assertions._occurrence import Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class ByteContainmentAssertions(BytesBase):
    """Membership, widened to the run of bytes as well as the single one."""

    __slots__ = ()

    @overload
    def contains(
        self, item: int, /, *, occurrences: "Occurrence | None" = None, because: str = ""
    ) -> Self: ...
    @overload
    def contains(
        self, item: bytes, /, *, occurrences: "Occurrence | None" = None, because: str = ""
    ) -> Self: ...
    @override
    def contains(
        self, item: "int | bytes", /, *, occurrences: "Occurrence | None" = None, because: str = ""
    ) -> Self:
        """Assert the byte string holds ``item``: one byte, or a run of them.

            expect(payload).contains(b"HTTP/1.1")
            expect(payload).contains(0x0A, occurrences=exactly(3))

        An ``int`` asks about one byte and is the inherited reading, unchanged.
        A ``bytes`` asks about a **substring**, which is what ``in`` means for two
        byte strings and what a reader almost always wants; the sequence
        catalogue could only ever ask the first, which is why a checker used to
        refuse the second while the runtime answered it anyway.

        ``occurrences`` counts **non-overlapping** runs for a ``bytes`` item --
        ``bytes.count``, and the same rule the string subject applies -- and
        counts equal bytes for an ``int``.
        """
        if not isinstance(item, bytes):
            return super().contains(item, occurrences=occurrences, because=because)
        subject = self._subject
        if occurrences is None:
            # `find` rather than `in`, and the difference is measurable rather
            # than stylistic: `bytes.__contains__` with a `bytes` argument goes
            # through the buffer protocol and allocates a couple of hundred bytes
            # on every call, passing or failing, where `find` allocates nothing
            # at all. The two ask the same question of the same C routine.
            if subject.find(item) >= 0:
                return self
            return self._fail(f"to contain {clipped(item)}, but was {clipped(subject)}", because)
        count = subject.count(item)
        if occurrences.allows(count):
            return self
        return self._fail(
            f"to contain {clipped(item)} {occurrences.describe()},"
            f" but it appears {count} times in {clipped(subject)}",
            because,
        )

    @overload
    def does_not_contain(
        self, item: int, /, *, occurrences: "Occurrence | None" = None, because: str = ""
    ) -> Self: ...
    @overload
    def does_not_contain(
        self, item: bytes, /, *, occurrences: "Occurrence | None" = None, because: str = ""
    ) -> Self: ...
    @override
    def does_not_contain(
        self, item: "int | bytes", /, *, occurrences: "Occurrence | None" = None, because: str = ""
    ) -> Self:
        """Assert the byte string does not hold ``item``: one byte, or a run of them.

        The complement of :meth:`contains`, and widened the same way. Without a
        constraint the failure names where the run begins, because "it is in there
        somewhere" is the half a reader already knew; with one it says how many
        times it did appear.
        """
        if not isinstance(item, bytes):
            return super().does_not_contain(item, occurrences=occurrences, because=because)
        subject = self._subject
        if occurrences is not None:
            count = subject.count(item)
            if not occurrences.allows(count):
                return self
            return self._fail(
                f"not to contain {clipped(item)} {occurrences.describe()},"
                f" but it appears {count} times in {clipped(subject)}",
                because,
            )
        at = subject.find(item)
        if at < 0:
            return self
        return self._fail(
            f"not to contain {clipped(item)}, but it begins at byte {at} of {clipped(subject)}",
            because,
        )

    def has_byte_at(self, index: int, value: int, /, *, because: str = "") -> Self:
        """Assert the byte at ``index`` is ``value``.

            expect(header).has_byte_at(0, 0x1F)

        Thin on its own, and it earns its place on the message: a byte is read
        and written in hexadecimal everywhere except in Python's own ``repr``, so
        a failure that says ``0x1f instead of 0x8b`` is the one a reader can
        check against a specification. Negative indices count from the end, as
        they do everywhere in Python.

        Raises ``ValueError`` for a ``value`` outside ``0..255``: that is a
        mistake in the test rather than a finding about the subject, since no
        byte could ever equal it.
        """
        if not 0 <= value <= _MAX_BYTE:
            raise ValueError("a byte value is 0..255, not " + str(value))
        subject = self._subject
        size = len(subject)
        position = index + size if index < 0 else index
        if 0 <= position < size:
            if subject[position] == value:
                return self
            return self._fail(
                f"to have {as_hex(value)} at byte {index},"
                f" but had {as_hex(subject[position])}: {clipped(subject)}",
                because,
            )
        return self._fail(
            f"to have {as_hex(value)} at byte {index},"
            f" but it holds {count_of(size, 'byte')}: {clipped(subject)}",
            because,
        )


#: The largest value a byte can hold. Named because ``255`` on its own in a
#: bounds check reads as a magic number rather than as the definition of a byte.
_MAX_BYTE = 255
