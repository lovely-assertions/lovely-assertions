"""The class subject, assembled from one mixin per family of question.

Every mixin derives from :class:`~lovely_assertions.CallableExpect` and none of
them touches another, so the base list decides nothing: no name is declared
twice and nothing is overridden here. It reads in the order a reader meets the
questions -- what the class is derived from, what it declares, what it leaves
abstract, what it conforms to -- and ``CallableExpect`` is named last because
the MRO admits a base only after the classes that already derive from it.

The assembly sits beside the mixins rather than in the package's ``__init__``,
which stays a front door: the exported name, and nothing to read past it.
"""

from lovely_assertions._callable import CallableExpect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._type._abstractness import AbstractnessAssertions
from lovely_assertions._type._attributes import AttributeAssertions
from lovely_assertions._type._conformance import ConformanceAssertions
from lovely_assertions._type._subclassing import SubclassAssertions

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class TypeExpect(
    SubclassAssertions,
    AttributeAssertions,
    AbstractnessAssertions,
    ConformanceAssertions,
    CallableExpect,
):
    """The subject ``expect()`` hands back for a class.

    It extends :class:`~lovely_assertions.CallableExpect`, so the whole callable
    catalogue is available on a class as well: ``expect(Order).raises(TypeError)``
    calls the constructor and asserts it refuses, which is a real assertion and
    the reason the inheritance is the right shape rather than a convenience.

    That inheritance fixes the subject's static type at
    ``Callable[..., object]``, so ``.subject`` hands a class back as a callable
    rather than as a ``type``. That is deliberate. Re-annotating the inherited
    ``_subject`` would be narrowing a mutable attribute in a subclass, which both
    checkers refuse and are right to; and a ``.subject`` typed ``type[Any]``
    would trade an honest type for an ``Any`` that silences the checker on every
    attribute reached through it. The caller already holds the class -- they
    wrote it in the ``expect(...)`` call -- so nothing is lost that they had.

    The subject *is* a class, because dispatch only routes one here. A
    hand-built ``TypeExpect(some_function)`` is not rejected on the way in, for
    the reason ``BoolExpect`` does not reject a hand-built ``BoolExpect(1)``: the
    assertions report the oddity instead of hiding it, and a constructor guard
    would cost every ordinary call to catch a mistake nobody makes twice.
    """

    __slots__ = ()
