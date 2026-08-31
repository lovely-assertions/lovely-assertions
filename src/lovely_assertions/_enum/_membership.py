"""Whether one member's bits are set in another, and the class kept to ask it.

A plain ``Enum`` member supports neither ``in`` nor ``&``, and a ``Flag`` member
supports both. So the flag question is the one question in this package that
cannot be written as a comparison and left at that: ``enum.Flag`` has to exist at
runtime, both to narrow the two operands into something the test is legal to
write against and to turn away the operands that are not flags at all.
:func:`flag_is_present` is that narrowing and that test as a single call, and
:data:`_FLAG` is where the class stays once it has been fetched.

A file of its own because neither of those is an assertion. The flag mixin keeps
the shape every mixin in this library keeps -- compare, then ``self`` or
``_fail`` -- and the state the comparison needs has nowhere to live inside it: a
subject is allocated per assertion and slotted down to the value under test and
its name, so a class remembered for the life of the process cannot sit on one.
The import cannot sit at module scope either, which would put ``enum`` on the
import path of every program that touches this library; it is deferred to the
first flag assertion and then never paid again, which is what keeps a passing
one to the single call it is supposed to be.

This is also the one place in the package that raises rather than reports. A
plain enum member, or a flag out of a different enumeration, leaves no verdict
to give -- there is no bit that could be set or clear -- so answering ``False``
would quietly let ``does_not_have_flag`` pass over an enumeration with no flags
in it. That is a bug in the test rather than a finding about the subject, and a
``TypeError`` raised where the call was written says so, where an
``AssertionFailure`` would be counted as a result and, inside a soft scope,
collected as one.
"""

from typing import TYPE_CHECKING

from lovely_assertions._enum._rendering import rendered
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from enum import Enum, Flag

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


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


def flag_is_present(subject: "Enum", other: "Enum", /) -> bool:
    """Whether every bit of ``other`` is set in ``subject``, or ``TypeError``.

    One function rather than a guard and a separate test, because the guard is
    what makes the test typecheck: ``Enum`` has no ``__contains__``, and
    ``Flag`` does, so narrowing both operands is how ``in`` becomes legal to
    write at all. It also keeps a passing assertion to a single call, which is
    the shape :func:`lovely_assertions._ordered._validation.reject_unusable_range` already
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
        # type(subject)` is stricter than the `isinstance` check further down.
        # Python refuses to extend an enumeration that has members, so no member
        # can be written down that falls between the two -- but a metaclass that
        # widens `isinstance` puts one there, and it takes the long way round to
        # the same answer rather than to a refusal.
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
