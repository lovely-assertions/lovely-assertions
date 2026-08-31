"""Everything a value can be asked purely because it compares.

Ordering, sign against zero, and ranges -- the assertions whose whole
requirement is that the comparison operators accept the subject. That
requirement is small enough to be worth naming, and it is:
:class:`Ordered`. Binding the subject by a protocol rather than by a
concrete type is what lets a ``Decimal`` and a ``Fraction`` have this
catalogue whole, without being flattened into ``int | float`` on the way in;
``.subject`` hands back the type that was put in, and a bound has to be that
type too.

What only a *machine* number needs is deliberately not here. A tolerance, and
the values arithmetic cannot reach, belong to
:mod:`lovely_assertions._numeric`, whose subject derives from this one and
specialises it. Keeping the two apart is what stops an exact type being
offered a relative band, and stops this package from importing anything to
talk about infinities.

The assertions are three mixins, one per heading the reference catalogue
already groups them under, so a reader arriving from that listing finds one
file per heading. Under them sit the two things a message needs and no
assertion should own: how a value is rendered inside a bound, and the refusal
of bounds no value could satisfy -- checked before the subject is looked at,
because bounds nothing could satisfy are a bug in the test rather than a
finding about the value.

Two of the four exported names are functions rather than assertions, and they
leave because a NaN and a rendered number are not this package's private
business. :func:`is_nan` is the bare self-comparison, which recognises a
``Decimal`` NaN as readily as a float one and needs no import to do it;
:func:`rendered` is the formatter lookup, the clip on an over-long value and
the refusal to ask an unprintably large integer for its digits, decided once.
Every package that has to put a number into a sentence borrows these rather
than restating them, so one value cannot read two ways depending on which
subject reported the failure. :class:`Ordered` leaves for the temporal
subjects, which need exactly this bound and cannot be written with the union
of the types they actually accept.

``math`` is not imported, nor ``decimal`` nor ``fractions``: a package holding
one of those numbers imported the module to make it, and nothing here has to
name the type to compare it.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._ordered._protocol import Ordered as Ordered
from lovely_assertions._ordered._rendering import is_nan as is_nan
from lovely_assertions._ordered._rendering import rendered as rendered
from lovely_assertions._ordered._subject import OrderedExpect as OrderedExpect

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["Ordered", "OrderedExpect", "is_nan", "rendered"]
