"""The numeric subject, assembled from the two seams a number adds to ordering.

The two have nothing in common. One is arithmetic against a tolerance -- how far
apart two values are, and whether that is near enough to pass. The other reaches
for the handful of values arithmetic cannot: a NaN, caught by the self-comparison
no other value fails, and the two infinities, by one membership test covering
both signs. So they are two mixins, one per group the catalogue already lists
these assertions under, and a reader who arrives from that listing finds one file
per heading.

Assembling them is all this module does: no assertion is written here, and the
class body is empty but for ``__slots__``. Every mixin carries empty slots too,
so the subject holds no ``__dict__`` however many seams it is made of. It sits
beside the package's ``__init__`` rather than in it so that the front door stays
a list of what leaves the package -- the subject, and the tolerance helpers the
matcher and the sequence subject borrow.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._numeric._approximation import ApproximationAssertions
from lovely_assertions._numeric._special_values import SpecialValueAssertions
from lovely_assertions._ordered import OrderedExpect

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class NumericExpect(ApproximationAssertions, SpecialValueAssertions, OrderedExpect[int | float]):
    """Assertions for numbers.

    ``expect()`` routes ``int``, ``float`` and their subclasses here; ``bool``
    goes to :class:`~lovely_assertions.BoolExpect`, which is the narrower
    overload and so is matched first. Because the subject is a union rather than
    a type parameter, every inherited member that names ``T`` sees
    ``int | float``: a predicate passed to ``matches`` or ``satisfies`` has to
    accept both, ``.subject`` hands the union back, and the comparisons and
    ranges inherited from :class:`~lovely_assertions.OrderedExpect` take a bound
    of either kind. ``is_equal_to`` and ``is_one_of`` are typed against ``object``
    and are indifferent to all of it.

    The class stays **non-generic** on purpose. ``expect(3)`` is a
    ``NumericExpect`` and not a ``NumericExpect[int]``, which keeps the subject
    the union that the built-ins really form -- an ``int`` bound on a ``float``
    subject and the reverse are both ordinary -- and keeps every chained
    assertion's static type one word long.
    """

    __slots__ = ()
