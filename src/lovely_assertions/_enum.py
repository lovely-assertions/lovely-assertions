"""Enumeration members.

**One rule: an enum member is an enum before it is anything else.** ``IntEnum``
members are integers and ``StrEnum`` members are strings, so the dispatch could
plausibly route them to :class:`NumericExpect` and
:class:`~lovely_assertions.StringExpect` instead -- and that is the option this
module rejects. It would mean ``has_name`` and ``has_value`` were unavailable on
exactly the enums people write most, and that the subject a value gets depends on
which mixin its author chose, which is a rule nobody can hold in their head.
``is_equal_to``, ``is_in`` and ``is_one_of`` live on the generic subject and
remain available regardless; where the mixin's own catalogue is genuinely wanted,
``expect(Colour.RED.value)`` asks for it in one unambiguous move.

**Nothing here imports ``enum``.** The class is needed for typing and never at
runtime, so it arrives under ``TYPE_CHECKING`` and the module costs an importing
program nothing. ``_subjects.py`` finds the real type through ``sys.modules``.
The one exception is the flag guard, and it is not really one: see
:func:`_flag_is_present`.

**Names, not values, are what an alias resolves to.** ``Colour.CRIMSON`` where
``CRIMSON = 1`` and ``RED = 1`` *is* ``Colour.RED`` -- the alias is a second
spelling of one member, not a second member -- so ``.name`` is ``"RED"`` and
:meth:`~EnumExpect.has_name` says so. An assertion cannot recover which spelling
the caller typed, and pretending otherwise would mean ``has_name("CRIMSON")``
passing for a member that will print itself as ``Colour.RED`` for the rest of
the test.

**There is no ``is_defined``, because Python has no undefined member.**
FluentAssertions has one, and in .NET it earns its place: an enum is a struct
over an integer, ``(Colour)99`` is a legal value of type ``Colour``, and
asking whether it names a real member is a genuine question. Python has no such
value. ``Colour(99)`` raises ``ValueError`` rather than handing back an
undefined member, so by the time ``expect()`` is holding an enum member that
member is defined -- there is no subject the assertion could ever be false
about. An assertion that cannot fail is not an assertion, and one that quietly
answered a different question (does this *integer* name a member?) would be
worse than absent. Asking about the integer is
``expect(list(Colour)).contains(...)``, or ``pytest.raises(ValueError)`` around
the call, and both say plainly which question is being asked.
"""

import sys
from typing import TYPE_CHECKING, Self, TypeIs

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._ordered import is_nan
from lovely_assertions._ordered import rendered as rendered_value

if TYPE_CHECKING:
    from enum import Enum, Flag

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["EnumExpect", "rendered"]

#: Appended to a value failure whose operand was a NaN, where the message would
#: otherwise read as though the assertion had misfired -- ``to have value nan,
#: but had value nan`` is the whole message without it.
_NAN_VALUE_NOTE = " (a NaN is not equal to itself, so no value can match one)"


def _is_member(value: object, /) -> "TypeIs[Enum]":
    """Whether ``value`` really is an enum member. Failure path only.

    A duck test on ``.name`` is not good enough, and the difference shows up in
    somebody's failure message: ``threading.current_thread()`` has a string
    ``.name``, and rendering it the way a member is rendered prints
    ``_MainThread.MainThread`` -- an enumeration that does not exist and a
    member nobody wrote. :meth:`EnumExpect.has_value` types its operand
    ``object`` on purpose, so arbitrary values really do arrive here.

    Asked through ``sys.modules`` rather than by importing, which is the same
    move ``_subjects.py`` makes and for the same reason: a program that has
    never imported ``enum`` cannot be holding a member of one, so the miss *is*
    the answer, and no program pays for an ``enum`` import it never asked for.
    """
    module = sys.modules.get("enum")
    if module is None:
        return False
    base: type[Enum] = module.Enum
    return isinstance(value, base)


def _claimed_by_a_formatter(value: object, /) -> str | None:
    """The registry's rendering of ``value``, or ``None`` if nothing claimed it.

    Failure path only. The question is "did a formatter take precedence?", and
    comparing against ``repr`` is how the other subjects ask it. The ``try`` is
    what makes the question survivable: ``repr`` is a method like any other and
    an enum whose own ``__repr__`` raises -- or whose value has more digits than
    CPython will convert to text -- would otherwise crash the message it is
    being written into. :func:`lovely_assertions._formatters.format_value` goes
    to the same trouble, and undoing it here would waste it. A ``repr`` that
    cannot answer has not claimed anything, so the member's name is used, which
    is the better rendering anyway.
    """
    text = format_value(value)
    try:
        plain = repr(value)
    except Exception:
        return None
    return text if text != plain else None


def rendered(value: object, /) -> str:
    """Render an enum member for a failure message. Failure path only.

    ``repr(Colour.RED)`` is ``<Colour.RED: 1>``; ``Colour.RED`` is what the
    reader wrote and what they want back. The formatter registry keeps
    precedence.

    ``str`` is not the shortcut it looks like: since 3.11 an ``IntEnum`` member
    stringifies as ``1`` and a ``StrEnum`` member as ``a``, so a message built
    with ``str`` would name neither the enumeration nor the member on exactly
    the two mixins this subject exists to keep.

    Two shapes have no single name. A composite flag has a compound one --
    ``(Perm.R | Perm.W).name`` is ``"R|W"``, which the name branch renders as
    ``Perm.R|W`` -- and the **empty** flag, ``Perm(0)``, has ``name`` of
    ``None``. That one is spelled the way it was built, ``Perm(0)``, rather than
    left to ``repr`` and its ``<Perm: 0>``.

    Anything that is not an enum member at all -- the operand of ``has_value``,
    typically -- is handed to :func:`lovely_assertions._ordered.rendered`
    *first*, and that order is the point rather than a detail. It clips an
    over-long rendering and refuses to ask an unprintably large integer for its
    digits, and asking whether the value looked member-shaped before delegating
    would mean asking a 5000-digit integer for a ``repr`` it cannot give -- so a
    failing assertion would raise ``ValueError`` about string conversion instead
    of reporting the verdict it already has.
    """
    if not _is_member(value):
        return rendered_value(value)
    claimed = _claimed_by_a_formatter(value)
    if claimed is not None:
        return claimed
    # `getattr` rather than `value.name`, and not for safety: typeshed promises
    # `Enum.name` is a `str`, the empty flag `Perm(0)` breaks that promise with a
    # `None`, and pyright rejects the check that catches it as unnecessary when
    # it can see the declared type. The lookup that cannot be narrowed away is
    # how the runtime truth gets to be tested at all.
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return type(value).__name__ + "." + name
    return type(value).__name__ + "(" + rendered(value.value) + ")"


def _nan_value_note(expected: object, /) -> str:
    """Explain a value failure the *operand* caused. Failure path only.

    ``Expected mode to have value nan, but Mode.UNKNOWN has value nan`` reads
    like a bug in the library. The note names the actual reason, exactly as
    :func:`lovely_assertions._ordered._nan_operand_note` does for an ordering.
    """
    return _NAN_VALUE_NOTE if is_nan(expected) else ""


#: ``enum.Flag``, fetched once. A one-element list so the module can fill it
#: without a ``global`` -- the same shape ``_subjects._SHAPE_TOKEN`` uses.
#:
#: ``from enum import Flag`` is a ``sys.modules`` probe and an attribute read even
#: when the module is already loaded, and a flag assertion that passes should pay
#: for neither. It stays out of the module body because this package never
#: imports ``enum`` at import time: a program holding a flag member has imported
#: it already, and this fills on the first flag assertion rather than on anyone
#: else's import.
_FLAG: "list[type[Flag]]" = []


def _remember_flag() -> "type[Flag]":
    """Fetch ``enum.Flag`` and keep it. Once per process."""
    from enum import Flag  # noqa: PLC0415  (only the flag assertions pay for this)

    _FLAG.append(Flag)
    return Flag


def _flag_is_present(subject: "Enum", other: "Enum", /) -> bool:
    """Whether every bit of ``other`` is set in ``subject``, or ``TypeError``.

    One function rather than a guard and a separate test, because the guard is
    what makes the test typecheck: ``Enum`` has no ``__contains__``, and
    ``Flag`` does, so narrowing both operands is how ``in`` becomes legal to
    write at all. It also keeps a passing assertion to a single call, which is
    the shape :func:`lovely_assertions._ordered._reject_unusable_range` already
    has.

    A caller bug, not an assertion failure: a plain ``Enum`` member supports
    neither ``in`` nor ``&``, so there is no flag to be present or absent and no
    verdict to give. Answering ``False`` would be worse than raising -- it would
    let ``does_not_have_flag`` pass on an enumeration that has no flags at all.
    Members of two *different* flag enumerations are refused for the same
    reason: ``Perm.R`` is not a bit of ``Bits``, and Python's own ``in`` raises
    on the pair rather than answering.

    **The ``enum`` import costs nothing after the first call**, which is why it
    is allowed to exist. A program holding an enum member has already imported
    ``enum`` to define it, so the statement is a ``sys.modules`` probe and an
    attribute read -- small, but paid on every flag assertion including the ones
    that pass, which is what :data:`_FLAG` holds the answer for. What it must not
    be is a module-level import, which would put ``enum`` on the import path of
    every program that touches this library.

    The messages are built by concatenation rather than f-strings, which this
    library reserves for the arguments of ``_fail`` -- and these are raised, not
    reported: a caller bug is not an assertion failure.
    """
    flag = _FLAG[0] if _FLAG else _remember_flag()
    if isinstance(subject, flag) and isinstance(other, flag) and type(other) is type(subject):
        # The whole of the passing case, in one condition. Everything below is a
        # message for a caller who got it wrong, and `type(other) is
        # type(subject)` is stricter than the `isinstance` check further down --
        # a member of a *subclass* of the subject's enumeration is still right,
        # and takes the long way round to the same answer.
        return other in subject

    if not isinstance(subject, flag):
        raise TypeError(
            "the flag assertions need enum.Flag members: "
            + rendered(subject)
            + " is a "
            + type(subject).__name__
            + ", which is not a Flag"
        )
    if not isinstance(other, flag):
        raise TypeError(
            "the flag assertions need enum.Flag members: "
            + rendered(other)
            + " is a "
            + type(other).__name__
            + ", which is not a Flag"
        )
    if not isinstance(other, type(subject)):
        raise TypeError(
            "a flag can only be looked for in its own enumeration: "
            + rendered(other)
            + " is a "
            + type(other).__name__
            + " and "
            + rendered(subject)
            + " is a "
            + type(subject).__name__
        )
    return other in subject


class EnumExpect[T: "Enum"](Expect[T]):
    """Assertions for a member of an enumeration.

    ``T`` is the enumeration, not ``Enum``: ``expect(Colour.RED).subject`` is a
    ``Colour``, so the chain keeps whatever the caller put into it and
    ``has_same_name_as`` can still be handed a member of a different one.
    """

    __slots__ = ()

    # -- names --------------------------------------------------------------
    def has_name(self, name: str, /, *, because: str = "") -> Self:
        """Assert the member is the one called ``name``."""
        subject = self._subject
        if subject.name == name:
            return self
        return self._fail(
            f"to be named {name!r}, but {rendered(subject)} is named {subject.name!r}", because
        )

    def does_not_have_name(self, name: str, /, *, because: str = "") -> Self:
        """Assert the member is not the one called ``name``.

        An alias passes for its own spelling: ``Colour.CRIMSON`` is
        ``Colour.RED``, so it *does not* have the name ``"CRIMSON"``.
        """
        subject = self._subject
        if subject.name != name:
            return self
        return self._fail(f"not to be named {name!r}, but {rendered(subject)} is", because)

    def has_same_name_as(self, other: "Enum", /, *, because: str = "") -> Self:
        """Assert the member's name equals ``other``'s.

        The operand is any enum member, deliberately: comparing two
        enumerations by name is what this assertion is *for* -- the domain's
        ``Status.ACTIVE`` against the wire protocol's ``WireStatus.ACTIVE`` --
        and requiring the same class would leave it saying only what
        ``is_equal_to`` already says. ``comparing_enums_by_name()`` on
        :meth:`~lovely_assertions.Expect.is_equivalent_to` is the same idea for
        a whole object graph.
        """
        subject = self._subject
        if subject.name == other.name:
            return self
        return self._fail(
            f"to have the same name as {rendered(other)}, "
            f"but was named {subject.name!r} rather than {other.name!r}",
            because,
        )

    # -- values -------------------------------------------------------------
    def has_value(self, value: object, /, *, because: str = "") -> Self:
        """Assert the member's ``value`` equals ``value``.

        The comparison is ``==`` on the *value*, not on the member, so an
        ``IntEnum`` and a plain ``Enum`` holding ``1`` both have the value
        ``1``. A NaN value can never match, itself included, and the failure
        says so rather than printing ``nan`` twice.
        """
        subject = self._subject
        if subject.value == value:
            return self
        return self._fail(
            f"to have value {rendered(value)}, but {rendered(subject)} has value "
            f"{rendered(subject.value)}{_nan_value_note(value)}",
            because,
        )

    def does_not_have_value(self, value: object, /, *, because: str = "") -> Self:
        """Assert the member's ``value`` differs from ``value``.

        The exact complement of :meth:`has_value`, so a NaN passes it: a NaN
        value is not equal to the NaN it was compared against.
        """
        subject = self._subject
        if subject.value != value:
            return self
        return self._fail(
            f"not to have value {rendered(value)}, but {rendered(subject)} has it", because
        )

    def has_same_value_as(self, other: "Enum", /, *, because: str = "") -> Self:
        """Assert the member's ``value`` equals ``other``'s.

        Across enumerations too, and that is the decision: ``Colour.RED`` and
        ``Priority.LOW`` both carrying ``1`` **do** have the same value, because
        the assertion is named after the values and that is what the values are.
        The two members are still not equal -- ``is_equal_to`` is false for
        them, as it should be -- and the pair of answers is not a contradiction
        but the distinction the two assertions exist to draw. Where the
        enumeration is meant to be part of the claim, ``is_equal_to`` is the one
        that says so.
        """
        subject = self._subject
        if subject.value == other.value:
            return self
        return self._fail(
            f"to have the same value as {rendered(other)}, but had value "
            f"{rendered(subject.value)} rather than {rendered(other.value)}"
            f"{_nan_value_note(other.value)}",
            because,
        )

    # -- flags (enum.Flag and enum.IntFlag only) -----------------------------
    def has_flag(self, other: T, /, *, because: str = "") -> Self:
        """Assert ``other``'s bits are all set in the subject.

        The test is ``other in subject``, which is subset containment rather
        than equality: ``Perm.R | Perm.W`` has the flag ``Perm.R``, and has
        ``Perm.R | Perm.W`` as well.

        Two consequences of that are worth knowing before they surprise
        somebody. The **empty flag is a subset of everything**, so
        ``has_flag(Perm(0))`` passes for every member including ``Perm(0)``
        itself, and asserts nothing; ``Perm(0)`` conversely has no flag but the
        empty one. And a **composite operand is all-or-nothing** --
        ``expect(Perm.R).has_flag(Perm.R | Perm.W)`` fails, because ``W`` is not
        set. "Any of these" is a different claim and gets a different spelling:
        ``satisfies_any(lambda it: it.has_flag(Perm.R), ...)``, one branch per
        flag.

        Raises ``TypeError`` when either side is not an ``enum.Flag`` member, or
        when the two belong to different enumerations. Both are caller bugs (see
        :func:`_flag_is_present`). The operand is typed ``T`` -- the subject's
        *own* enumeration -- so the checkers refuse the cross-enumeration form
        before it can run; being a ``Flag`` at all is the half no signature can
        state, because ``T`` has already been fixed to whatever ``expect()`` was
        handed, and it is the half the guard exists for.
        """
        subject = self._subject
        if _flag_is_present(subject, other):
            return self
        return self._fail(f"to have flag {rendered(other)}, but was {rendered(subject)}", because)

    def does_not_have_flag(self, other: T, /, *, because: str = "") -> Self:
        """Assert at least one of ``other``'s bits is not set in the subject.

        The exact complement of :meth:`has_flag`, and it inherits both of that
        method's edges, negated. ``does_not_have_flag(Perm(0))`` can never pass,
        the empty flag being a subset of every member. And a composite operand
        passes as soon as *one* of its bits is missing -- so
        ``expect(Perm.R).does_not_have_flag(Perm.R | Perm.W)`` **passes**, on
        the strength of the absent ``W`` alone. Where "neither of these" is
        meant, one call per flag says it.
        """
        subject = self._subject
        if not _flag_is_present(subject, other):
            return self
        return self._fail(
            f"not to have flag {rendered(other)}, but {rendered(subject)} has it", because
        )
