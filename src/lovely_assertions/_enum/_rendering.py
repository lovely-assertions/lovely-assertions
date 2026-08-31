"""The words every message about an enum member is assembled from.

A member spelled the way its author wrote it, anything that is not a member
handed to the library's shared value renderer, and the one note a value failure
needs when the operand it was given was a NaN. Nothing here settles anything:
the comparison has already come out false by the time any of it is asked, so a
passing assertion reaches none of it -- not the formatter registry, not the
``sys.modules`` probe, not a single allocation.

One module because the assertion mixins are independent, none of them calling
another, and a rendering copied into each is a standing invitation for one
member to read one way in a name failure and another in a value failure. It sits
below :mod:`lovely_assertions._enum._membership` as well, whose ``TypeError``
names the members it is refusing and wants them spelled the way the failures
spell them. That leaves the package layered one way: this file imports no
assertion, and everything that builds a sentence imports this file.

It is also the only file here that asks the formatter registry anything, or
calls :func:`lovely_assertions._ordered.rendered`. Formatter precedence over a
member's own name, the clip on an over-long rendering, the refusal to ask an
unprintably large integer for its digits -- each is a decision the mixins would
otherwise have to remember one at a time, and would each be free to remember
differently.

``enum`` is not imported, not even to ask whether a value is a member of one.
That question goes through ``sys.modules``, on the reasoning ``_subjects.py``
already uses for dispatch: a program holding a member imported ``enum`` to
define it, so a miss is a real answer rather than a reason to import. The
question does have to be asked, though. A value with a string ``.name`` is not a
member, and rendering one as though it were prints an enumeration nobody wrote.
"""

import sys
from typing import TYPE_CHECKING, TypeIs

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._ordered import is_nan
from lovely_assertions._ordered import rendered as rendered_value

if TYPE_CHECKING:
    from enum import Enum

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Appended to a value failure whose operand was a NaN, where the message would
#: otherwise read as though the assertion had misfired -- ``to have value nan,
#: but Mode.UNKNOWN has value nan`` is the whole message without it.
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
    *first*, and that order is the point rather than a detail. That renderer is
    what clips an over-long rendering, and what reports an integer past CPython's
    conversion limit by its size rather than asking for digits the interpreter
    refuses to produce. A bare ``repr`` in its place would turn a failing
    assertion into a ``ValueError`` about string conversion instead of the
    verdict it already has.
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


def nan_value_note(expected: object, /) -> str:
    """Explain a value failure the *operand* caused. Failure path only.

    ``Expected mode to have value nan, but Mode.UNKNOWN has value nan`` reads
    like a bug in the library. The note names the actual reason, exactly as
    :func:`lovely_assertions._ordered._nan_operand_note` does for an ordering.
    """
    return _NAN_VALUE_NOTE if is_nan(expected) else ""
