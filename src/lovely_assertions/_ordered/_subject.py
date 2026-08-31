"""The ordered subject, assembled from one mixin per heading of the catalogue.

Comparisons, sign against zero, and ranges. The three share the operators they
are built on and nothing else: none calls another, no name appears in two of
them, and none of them overrides anything the generic subject declares. So the
base list resolves no clash and is free to read in the order the reference
lists the groups in -- with ``Expect[T]`` last, because a base is admitted to
the order of resolution only after the classes that already derive from it.

Every mixin repeats the ``T: Ordered`` parameter rather than having it pinned
down here, and that is what makes a bound's typing work at all: a comparison
takes a ``T``, so ``T`` has to still be the caller's own type by the time the
signature is read, or a checker has nothing to refuse a mismatched bound
against. Specialising happens once, at the seam below this one: the numeric
subject's mixins derive from ``OrderedExpect[int | float]``, and from there
down every inherited bound is an ordinary number.

Assembling is the whole of what this module does. No assertion is written
here, and the class body is empty but for ``__slots__`` -- which the mixins
carry empty too, so a subject remains one allocation holding the value and its
name however many groups it was built from. It sits beside the mixins rather
than in the package's ``__init__``, which stays a list of what leaves.
"""

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._ordered._ordering import OrderingAssertions
from lovely_assertions._ordered._protocol import Ordered
from lovely_assertions._ordered._ranges import RangeAssertions
from lovely_assertions._ordered._sign import SignAssertions

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class OrderedExpect[T: Ordered](
    OrderingAssertions[T], SignAssertions[T], RangeAssertions[T], Expect[T]
):
    """Assertions for ordered values.

    ``expect()`` routes ``int``, ``float`` and their subclasses to
    :class:`~lovely_assertions.NumericExpect`, which is this class specialised to
    ``int | float`` and extended with the float-domain assertions; ``Decimal`` and
    ``Fraction`` land here directly, as ``OrderedExpect[Decimal]`` and
    ``OrderedExpect[Fraction]``.

    The operand of a comparison is typed ``T``, not "any number". On
    ``NumericExpect`` that resolves to ``int | float`` and reads as an ordinary
    numeric bound; on ``OrderedExpect[Decimal]`` it means a bound has to be a
    ``Decimal`` too. That is deliberate rather than incidental:
    ``Decimal("0.1") == 0.1`` is false, and an assertion library that let a float
    bound slip into a ``Decimal`` comparison would be undermining the reason the
    value is a ``Decimal``. Where a bound of zero is what was wanted,
    :meth:`is_positive` and its neighbours take no operand at all.
    """

    __slots__ = ()
