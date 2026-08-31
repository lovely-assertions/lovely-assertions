"""How an ordered value gets into a message, and how a NaN is recognised.

Whether a value is a NaN, how any value is spelled inside a bound, and the clause
an ordering failure adds when the operand it was handed was one. No assertion is
imported here and every file in the package that builds a sentence imports this,
which is what keeps a bound spelled the same way in a comparison failure, a range
failure and a refused range.

:func:`rendered` is the reason a bound never reaches a message as a raw ``repr``.
An integer has no size limit and a large enough one cannot be converted to text
at all, so an assertion that asked for the digits would raise on its way out and
replace the verdict it already had with an error about string conversion.
Settling that once also settles where the clip on an over-long rendering lives:
in the library, rather than in whichever assertion remembered to apply it. Both
matter beyond this package -- the enum renderer sends anything that is not a
member through here first, and the ``close_to`` matcher spells its tolerance with
it, so a band reads the same in a matcher's ``repr`` as in the failure of the
assertion that matcher stands in for.

:func:`is_nan` is the one thing here a *passing* assertion reaches, which is why
it is a single comparison and nothing else. Neither kind of NaN can be left to an
ordering to reveal -- a float one loses every comparison it enters, and a
``Decimal`` one signals ``InvalidOperation`` instead of answering -- so it has to
be recognised on the way to a verdict and not only while explaining one: it is
what the numeric subject's own ``is_nan`` asks, what the range guard refuses as a
bound, and what an approximate comparison settles before it measures anything. A
sortedness failure reads it on the explaining side, to name a pair with no order
between them.

The note is worded for an ordering alone. A NaN operand ruins an ordering, an
equality and a closeness in three unrelated ways, and each family writes the
sentence naming its own reason; one clause general enough to serve all three
would name none of them, which is exactly the vagueness the note exists to
repair.
"""

import sys

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._text import length_note

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Longest rendering shown in full in a failure message, matching the default the
#: string subject's own budget starts from: roughly one terminal line, which is
#: what a reader takes in at a glance. Past it the digits stop informing and start
#: dumping.
_MAX_RENDERED = 120


#: ``log10(2)``, scaled to five decimals so the digit count of a huge integer can
#: be estimated from ``int.bit_length()`` in integer arithmetic. Needed because on
#: the far side of CPython's conversion limit the digits cannot be produced at all,
#: and the size is the only thing left to report.
_LOG10_OF_2_SCALED = 30103


#: Appended to an ordering failure whose operand was a NaN, where the message
#: would otherwise read as though the assertion had misfired.
_NAN_OPERAND_NOTE = " (a NaN compares false against every ordering)"


def is_nan(value: object, /) -> bool:
    """``True`` when ``value`` is a NaN.

    A NaN is the only value not equal to itself, so the self-comparison *is* the
    definition rather than an accident -- and it answers the question without
    importing ``math``, for a ``Decimal`` NaN as readily as for a float one.
    """
    return value != value  # noqa: PLR0124  (that is what "not a number" means)


def rendered(value: object, /) -> str:
    """Render a value for a failure message. Failure path only.

    An integer has no size limit, and two thresholds sit above it. The lower one
    is legibility: past :data:`_MAX_RENDERED` characters the digits are a wall,
    so the rendering is clipped and its length reported, the way the string
    subject elides a long haystack. What is measured here is the rendering,
    quotes and escapes included, against a bound that is fixed -- where the
    string subject counts its own characters against one a ``formatting`` block
    can widen. The upper one is hard -- CPython raises ``ValueError`` rather than
    convert an integer of more than ``sys.get_int_max_str_digits()`` digits to
    text -- so past it the digits are never asked for at all, and the size is
    reported from ``bit_length`` instead. Without that, a failing assertion on a
    big integer would not report at all: it would blow up inside its own message
    with an error about string conversion.

    Everything else goes through the formatter registry, so a domain type with a
    registered formatter reads as itself here rather than as its address.

    Assembled by concatenation rather than an f-string, which throughout this
    library marks the one finished message handed to ``_fail`` rather than a
    fragment on its way into one.
    """
    if isinstance(value, int):
        digits = value.bit_length() * _LOG10_OF_2_SCALED // 100000 + 1
        # `sys.get_int_max_str_digits()` answers 0 when the limit is disabled.
        limit = sys.get_int_max_str_digits()
        if limit and digits >= limit:
            sign = "-" if value < 0 else ""
            return sign + "<integer of about " + str(digits) + " digits>"
    text = format_value(value)
    if len(text) <= _MAX_RENDERED:
        return text
    return text[:_MAX_RENDERED] + "..." + length_note(len(text))


def nan_operand_note(other: object, /) -> str:
    """Explain an ordering failure the *operand* caused. Failure path only.

    ``Expected 5 to be greater than nan, but was 5`` reads like a bug in the
    library; the subject is right there and nothing looks wrong with it. The note
    names the actual reason so the reader does not have to recall that every
    ordering against a NaN is false.
    """
    return _NAN_OPERAND_NOTE if is_nan(other) else ""
