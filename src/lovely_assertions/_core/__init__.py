"""The assertion primitive, the generic subject, and the soft-assertion scopes.

Two rules govern everything here.

**Deferred formatting.** An assertion tests, and formats *only* in its failure
branch. A message is never passed as an argument to a helper, because an f-string
argument is evaluated even when the assertion passes::

    def is_equal_to(self, expected: object, *, because: str = "") -> Self:
        if self._subject == expected:
            return self
        return self._fail(f"to equal {expected!r}, but was {self._subject!r}", because)

An f-string anywhere in this module but inside a ``_fail`` call is therefore a
bug: it charges every passing assertion for a message nobody will ever read.

**Zero-cost happy path.** A passing assertion performs the comparison and
``return self``: no frame inspection, no message construction, no ``ContextVar``
read, no allocation. Only the failure path may do any of those.

The subject is assembled here from one mixin per seam. Every mixin is a
``ExpectBase[T]`` with empty ``__slots__``, so the wrapper stays one allocation
and the assembled class carries no ``__dict__``; and every assertion still
returns ``Self``, so a chain that crosses three seams still has the concrete
subject's whole catalogue at the end of it.
"""

from lovely_assertions._core._base import ExpectBase
from lovely_assertions._core._coercion import CoercionAssertions
from lovely_assertions._core._composition import CompositionAssertions
from lovely_assertions._core._equality import EqualityAssertions
from lovely_assertions._core._found import Found
from lovely_assertions._core._identity import IdentityAssertions
from lovely_assertions._core._inspection import collect_failures, describe_predicate
from lovely_assertions._core._instance import InstanceAssertions
from lovely_assertions._core._membership import MembershipAssertions
from lovely_assertions._core._nullability import NullabilityAssertions
from lovely_assertions._core._predicates import PredicateAssertions
from lovely_assertions._core._scope import SoftScope
from lovely_assertions._core._shape import EquivalenceAssertions
from lovely_assertions._core._soft import soft_assertions
from lovely_assertions._core._truthiness import TruthinessAssertions
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = [
    "Expect",
    "Found",
    "SoftScope",
    "collect_failures",
    "describe_predicate",
    "soft_assertions",
]


class Expect[T](
    TruthinessAssertions[T],
    CompositionAssertions[T],
    EqualityAssertions[T],
    EquivalenceAssertions[T],
    IdentityAssertions[T],
    NullabilityAssertions[T],
    MembershipAssertions[T],
    PredicateAssertions[T],
    CoercionAssertions[T],
    InstanceAssertions[T],
    ExpectBase[T],
):
    """A disposable, typed wrapper around the value under test.

    Built by :func:`~lovely_assertions.expect`, chained on, and thrown away. ``T``
    is the subject's type; it is what ``.subject`` re-exposes after an assertion
    has narrowed it.

    One seam per base, in the order a reader meets them. The bases carry no state
    of their own -- the single attribute is declared on ``ExpectBase`` -- so this
    statement is the catalogue and nothing else.
    """

    __slots__ = ()
