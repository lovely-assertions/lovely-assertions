"""The single requirement an ordering assertion has of a value.

Alone in a module because it is the floor of this package -- it imports no
sibling, so nothing about rendering or about refusing a range can drift into
the requirement itself -- and because the requirement is not this package's
alone. :mod:`lovely_assertions._datetime` binds the base its date, time and
datetime subjects share by the same protocol: what those assertions need is
that two values compare, not that either carries a year.

Nothing consults it at run time. It is not ``@runtime_checkable``, so an
``isinstance`` against it raises rather than answering, and dispatch never
asks -- ``expect()`` reaches a subject through concrete types. The protocol
exists so that both checkers can prove a ``Decimal`` belongs here, and its
cost to a program that never fails an assertion is one class body.

**The operands are ``Any`` and cannot be ``object``**, which looks like the
looser choice and is the only workable one. A protocol's parameters are
checked contravariantly, so an ``object`` operand demands an implementation
willing to be compared against anything -- and ``int``, ``str``, ``Decimal``
and ``Fraction`` every one of them declare something narrower. The protocol
would be satisfied by no ordered type in the language. ``Any`` asks only that
the operator exist, and leaves the real constraint where it can be stated
usefully: an assertion types its operand as the subject's own type, so a
``float`` bound on a ``Decimal`` subject is refused there rather than here.
"""

from typing import Any, Protocol

from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class Ordered(Protocol):
    """Anything the comparison operators accept -- the requirement this subject has.

    ``_typeshed.SupportsRichComparison`` is the obvious candidate and does not
    work: it is a *union* of two half-protocols, and neither checker will compare
    one member of that union against the other. This is the protocol written to
    solve that, and it is shared: ``_datetime`` binds the base of its temporal
    subjects by it. ``_sequence`` deliberately does not -- a sort key needs ``<``
    alone, so its ``key=`` callables promise ``Sortable``, which asks for that
    one operator and no more.

    All four operators are named, rather than the ``__lt__`` that sorting alone
    would need, because a NaN makes them genuinely independent: ``a >= b`` is
    *not* ``not (a < b)`` when either side is unordered, so
    :meth:`OrderedExpect.is_greater_than_or_equal_to` cannot be spelled with
    ``<`` and stay a true complement of :meth:`OrderedExpect.is_less_than`.
    """

    __slots__ = ()

    def __lt__(self, other: Any, /) -> bool:  # noqa: ANN401  (the operand is the caller's business)
        ...

    def __le__(self, other: Any, /) -> bool:  # noqa: ANN401  (the operand is the caller's)
        ...

    def __gt__(self, other: Any, /) -> bool:  # noqa: ANN401  (the operand is the caller's)
        ...

    def __ge__(self, other: Any, /) -> bool:  # noqa: ANN401  (the operand is the caller's)
        ...
