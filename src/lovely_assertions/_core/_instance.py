"""The type seam, and the head of the ``expect()`` overload table.

Asking what a value *is* hands back the subject that type deserves -- a ``str``
comes back as a ``StringExpect``, not as an ``Expect[str]`` -- because a
catalogue the object already has is a catalogue the reader should not have to
ask twice for. The overloads here mirror the dispatch, and the note below says
what they deliberately omit.
"""

from typing import TYPE_CHECKING, Any, Self, overload

from lovely_assertions._core._found import Found
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from enum import Enum

    from lovely_assertions._subjects import BoolExpect, EnumExpect, StringExpect
from lovely_assertions._core._base import ExpectBase

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.

__tracebackhide__ = hide_internal_frames


class InstanceAssertions[T](ExpectBase[T]):
    """The assertions of the type seam."""

    __slots__ = ()

    # The three narrowing methods below carry the head of the `expect()` overload
    # table, so that what you continue on is the subject `expect()` really builds.
    # Declaring `Expect[S]` instead would withhold a catalogue the object already
    # has: `expect(raw).as_type(str).starts_with(..)` would be a checker error
    # against a genuine `StringExpect` -- this library's whole claim, that the
    # checker knows which assertions a subject has, failing at the exact point it
    # is meant to pay off.
    #
    # `Enum` leads, as it does in `expect()` and for the same reason: a `StrEnum`
    # member's class *is* a `str` subclass, so `type[str]` would otherwise claim
    # `type[Colour]` and promise a catalogue the runtime does not build.
    #
    # **There is deliberately no `int` or `float` entry**, though it is the one a
    # reader will look for first. `bool` is a subclass of `int`, and `expect()`
    # sends a `bool` to `BoolExpect`, which is not a `NumericExpect` -- so
    # `is_instance_of(int)` on `True` really does hand back a `BoolExpect`, and
    # declaring `NumericExpect` would make `expect(flag).is_instance_of(int)
    # .which.is_positive()` type-check and then raise `AttributeError`. A checker
    # that green-lights a crash is worse than one that withholds a method, so
    # that call is declared `Expect[int]` and the numeric catalogue is reached by
    # asserting on `.subject` instead. The same objection rules out a
    # re-specialised `is_not_none`.
    #
    # What the entries that *are* here promise, exactly: the type **argument**
    # decides the subject. The value's own type decides nothing, so
    # `as_type(str)` on a value that happens to be a `StrEnum` member is declared
    # `StringExpect` and built as an `EnumExpect`. That gap belongs to the
    # dispatch rather than to this table: `expect(x)` for an `x: str` holding a
    # `StrEnum` member also answers `StringExpect` statically and builds an
    # `EnumExpect`. Closing it needs the dispatch to build from the named type
    # rather than from the value.
    #
    # The table also stops at the scalars: `date`, `Path`, `Decimal` and the rest
    # fall to the bare overload, which is unhelpful rather than wrong. Each entry
    # added here is another copy of the table `expect()` already declares, and so
    # one more place the two halves can drift apart.
    #
    # **A leading entry claims every argument that is not a named type.** A mock
    # is the case that shows up in real suites -- typeshed puts an `Any` in
    # `NonCallableMock`'s MRO, so `type[Mock]` satisfies `type[Enum]`, the same
    # divergence `expect()` has one level down. It is not the only case, and the
    # wider one matters more: an argument annotated `type[Any]`, or the bare
    # `type`, also satisfies `type[Enum]`, so a dynamically-typed call site reads
    # `EnumExpect` where it would otherwise read `Expect`. Measured, on this
    # table: pyright answers `EnumExpect[Any]` for `type[Any]` and
    # `EnumExpect[Unknown]` for `type`; mypy answers `Any` for the first and
    # `EnumExpect[Never]` for the second.
    #
    # That is a real cost and it is paid on purpose. No ordering avoids it --
    # whichever entry leads is the one a `type[Any]` lands on, and putting `bool`
    # or `str` first would be worse, since those flatten `V` to `bool` or `str`
    # where `Enum` at least leaves `.subject` alone. Nor can it be pinned by a
    # type-checking test: the two checkers disagree about the answer, so an
    # `assert_type` written for one fails the other.
    @overload
    def is_instance_of[S: "Enum"](
        self, expected_type: type[S], /, *, because: str = ...
    ) -> "Found[Self, S, EnumExpect[S]]": ...
    @overload
    def is_instance_of(
        self, expected_type: type[bool], /, *, because: str = ...
    ) -> "Found[Self, bool, BoolExpect]": ...
    @overload
    def is_instance_of(
        self, expected_type: type[str], /, *, because: str = ...
    ) -> "Found[Self, str, StringExpect]": ...
    @overload
    def is_instance_of[S](
        self, expected_type: type[S], /, *, because: str = ...
    ) -> "Found[Self, S]": ...
    def is_instance_of(self, expected_type: type[Any], /, *, because: str = "") -> Any:
        """Assert ``isinstance(subject, expected_type)``; continue with ``.which``.

        A subclass counts; use :meth:`is_exactly_instance_of` where it must not.
        Returns a :class:`Found`, so ``.and_`` goes on asserting about the
        original subject while ``.which`` continues on the same value re-typed --
        and re-dispatched, so ``.which`` after ``is_instance_of(str)`` carries the
        string catalogue. Inside a soft scope a failure here has no narrowed
        subject to hand back, so the rest of the chain is absorbed and one failure
        is reported rather than a second derived from it.
        """
        subject = self._subject
        if isinstance(subject, expected_type):
            return Found(self, subject, expected_type)
        return self._fail_narrowing(
            f"to be an instance of {expected_type.__name__}, but was {type(subject).__name__}",
            because,
        )

    def is_not_instance_of(self, unexpected_type: type[object], /, *, because: str = "") -> Self:
        """Assert the subject is not an instance of ``unexpected_type``.

        A subclass *is* an instance, so a subject of a subclass fails here. Use
        :meth:`is_not_exactly_instance_of` to rule out only the exact type. Does
        not narrow: there is nothing to continue on but the original subject, so
        it returns ``self``.
        """
        if not isinstance(self._subject, unexpected_type):
            return self
        return self._fail(
            f"not to be an instance of {unexpected_type.__name__},"
            f" but was {type(self._subject).__name__}",
            because,
        )

    @overload
    def is_exactly_instance_of[S: "Enum"](
        self, expected_type: type[S], /, *, because: str = ...
    ) -> "Found[Self, S, EnumExpect[S]]": ...
    @overload
    def is_exactly_instance_of(
        self, expected_type: type[bool], /, *, because: str = ...
    ) -> "Found[Self, bool, BoolExpect]": ...
    @overload
    def is_exactly_instance_of(
        self, expected_type: type[str], /, *, because: str = ...
    ) -> "Found[Self, str, StringExpect]": ...
    @overload
    def is_exactly_instance_of[S](
        self, expected_type: type[S], /, *, because: str = ...
    ) -> "Found[Self, S]": ...
    def is_exactly_instance_of(self, expected_type: type[Any], /, *, because: str = "") -> Any:
        """Assert ``type(subject) is expected_type`` -- a subclass does not count.

        Use :meth:`is_instance_of` where a subclass should pass. This is the one
        narrowing method whose declaration has no gap in it at all: an exact type
        leaves no room for a subclass with a subject of its own, so ``.which`` is
        the subject ``expect()`` builds, never a near relative.
        """
        subject = self._subject
        subject_type = type(subject)
        if subject_type is expected_type:
            return Found(self, subject)
        return self._fail_narrowing(
            f"to be exactly {expected_type.__name__}, but was {subject_type.__name__}",
            because,
        )

    def is_not_exactly_instance_of(
        self, unexpected_type: type[object], /, *, because: str = ""
    ) -> Self:
        """Assert ``type(subject) is not unexpected_type``.

        A subclass of ``unexpected_type`` passes, which is the whole difference
        from :meth:`is_not_instance_of`.
        """
        if type(self._subject) is not unexpected_type:
            return self
        return self._fail(f"not to be exactly {unexpected_type.__name__}", because)
