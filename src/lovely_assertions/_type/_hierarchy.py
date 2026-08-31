"""What a class inherits, and why ``issubclass`` answered as it did.

The MRO is read here and nowhere else in the package. Three callers with nothing else in common
need it -- the subclass assertions, the protocol ones, and the walk over class
dictionaries that recovers how a member was declared -- and each would otherwise
repeat the ``getattr`` that keeps a hand-built subject which is not a class from
turning a failure message into an error.

Asking ``issubclass`` is deliberately not this module's work. That call can refuse
a protocol outright, and explaining the refusal takes knowing what a protocol
requires, which is a different question living in a different file. Here the
verdict has already been given and only has to be accounted for, in both
directions: a class can be a subclass of another by being it, by inheriting from
it, or by having been registered as one without inheriting anything at all, and
only the first two are visible in the source the reader is staring at.

Nothing here runs for a passing assertion, the MRO walk included -- the lookup
that uses it is already building a message by the time it asks.
"""

from typing import Any

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._type._naming import listed, named

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def mro_of(subject: object, /) -> "tuple[type[Any], ...]":
    """A class's method resolution order, or an empty one for a non-class.

    The annotation is what ``type`` promises; the ``getattr`` is what actually
    holds, because this subject is only guaranteed to be a class by dispatch and
    a hand-built one need not be (see :class:`TypeExpect`).
    """
    mro: tuple[type[Any], ...] | None = getattr(subject, "__mro__", None)
    return mro if isinstance(mro, tuple) else ()


def bases_of(subject: object, /) -> str:
    """What a class inherits from, itself excluded. Failure path only.

    This is the "what was there" half of a failed subclass check: a reader who
    has just been told the class is not a subclass of something wants to know
    what it *is* derived from, and the MRO answers that in one line. A class
    registered as a virtual subclass with ``ABCMeta.register`` does not appear
    here, because nothing was inherited -- :func:`why_subclass` is what explains
    the opposite failure.
    """
    ancestors = [named(base) for base in mro_of(subject)[1:]]
    if not ancestors:
        return "nothing"
    return listed(ancestors)


def why_subclass(subject: object, other: type[object], /) -> str:
    """Why ``issubclass`` said yes, for a negated assertion. Failure path only.

    Three answers, because three genuinely different things happened.
    ``issubclass`` is reflexive, so a class is a subclass of itself and a reader
    who did not have that in mind needs telling. Ordinary inheritance puts the
    other class in the MRO. And neither of those explains a *virtual* subclass --
    ``ABCMeta.register``, or a ``__subclasshook__`` matching structurally -- where
    ``issubclass`` says yes and the MRO shows nothing, which is precisely the
    case a reader stares at without understanding.
    """
    name = named(other)
    if subject is other:
        return "it is " + name + " itself"
    if other in mro_of(subject):
        return name + " is one of its base classes"
    return "it counts as one without inheriting from it: " + name + " is not in its MRO"
