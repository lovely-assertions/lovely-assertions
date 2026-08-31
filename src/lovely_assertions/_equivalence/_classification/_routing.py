"""Which kind a value is compared as, and the order that question is asked in.

Five kinds, and two values that land on different ones have no members to compare
at all -- the mismatch is itself the finding. Everything else in this file is the
order the branches are tried in, because ordering is where a mistake is silent. A
branch that fires later than it should does not give the reader a worse report; it
gives a comparison that takes both values apart on members they happen to agree
on and reports them equivalent. :func:`_resolve_classification` carries the case
for each position it puts a branch in.

The answer is remembered on ``type(value)``. Every question but the last is asked
of the class -- opacity, the declared-field resolvers, and the ``Mapping``,
``Set`` and ``Sequence`` memberships -- so none of them can differ between two
instances of it, while asking them unmemoised costs a string of ``isinstance``
calls that mostly run through ``abc.__instancecheck__``. The last question cannot
be cached and is not: an instance dictionary belongs to the instance, so a type
that reaches that branch is recorded as :data:`_ASK_THE_VALUE` and re-read every
time.

Because three of those memberships are ABC memberships, a registration really can
change an answer already remembered. :data:`ROUTE_TOKEN` is how that is noticed,
and the engine's entry points compare it once per comparison rather than this
module checking it once per node.
"""

from abc import get_cache_token
from collections.abc import Sequence
from typing import Final

from lovely_assertions._equivalence._classification._fields import (
    declared_field_names,
    stored_field_names,
)
from lovely_assertions._equivalence._classification._opacity import is_opaque
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._reflection import is_mapping, is_set, remember

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: The five kinds a value can be compared as. Two values of different kinds have
#: nothing to compare member by member, so the mismatch is itself the finding.
KIND_LEAF: Final = "leaf"


KIND_MAPPING: Final = "mapping"


KIND_SET: Final = "set"


KIND_SEQUENCE: Final = "sequence"


_KIND_RECORD: Final = "record"


#: What :func:`_resolve_classification` decided for a type, or
#: :data:`_ASK_THE_VALUE` when the answer depends on the instance rather than on
#: its class.
#:
#: Every question in the resolution order but one is asked of ``type(value)``:
#: ``str``/``bytes``/class/enum-member, the declared-field resolvers, and the
#: ``Mapping``/``Set``/``Sequence`` memberships. Only the *stored* branch reads an
#: instance, because ``__dict__`` is the instance's.
#:
#: Routing one node unmemoised asks a string of ``isinstance`` questions, most of
#: them through ``abc.__instancecheck__``, for an answer that cannot differ between
#: two values of the same class.
ROUTE_BY_TYPE: dict[type, "tuple[str, tuple[str, ...]] | None"] = {}


#: Recorded for a type whose kind depends on what the instance carries.
_ASK_THE_VALUE: Final = None


#: The ABC registry generation the routes above were worked out under.
#:
#: ``Mapping``, ``Set`` and ``Sequence`` take virtual subclasses, so
#: ``Sequence.register(X)`` really does change the answer after ``X`` exists.
#: Every such call bumps ``abc.get_cache_token()``, which is what the token is
#: for and what ``functools.singledispatch`` guards on. Same argument, same
#: mechanism and same one-element list as ``_subjects._SHAPE_TOKEN``.
ROUTE_TOKEN: list[object] = [get_cache_token()]


def classify(value: object, /) -> tuple[str, tuple[str, ...]]:
    """Route by type where the type decides, and remember the answer.

    See :data:`ROUTE_BY_TYPE`. The order this preserves is
    :func:`_resolve_classification`'s, which is where the wrong PASSes live.

    The ABC token is checked once per comparison rather than once per node, at
    the top of :func:`compare` and :func:`differs`. Per node it is a measurable
    slice of a small comparison, spent guarding against a registration nobody
    makes halfway through one.

    ``try``/``except`` rather than ``.get()`` and a sentinel, for the reason
    :func:`lovely_assertions._subjects._claimed_by_shape` gives -- ``None`` is a
    real answer here, so a miss has to be told apart from a remembered one. It is
    also what lets the value keep its declared type: a sentinel widens it to
    ``object`` and needs a ``typing.cast`` to get back, and ``cast`` is a genuine
    function call at runtime, on a function that runs once per node.
    """
    subject_type = type(value)
    try:
        cached = ROUTE_BY_TYPE[subject_type]
    except KeyError:
        cached = _resolve_classification(value)
        remember(ROUTE_BY_TYPE, subject_type, cached)
    if cached is None:
        # The one branch a type cannot answer: `__dict__` belongs to the instance.
        stored = stored_field_names(value)
        return (_KIND_RECORD if stored else KIND_LEAF), stored
    return cached


def _resolve_classification(value: object, /) -> "tuple[str, tuple[str, ...]] | None":
    """What this value is compared as, and -- for a record -- the fields to compare.

    The order is where the wrong PASSes live.

    The values with nothing inside them come first -- ``str`` and the buffers,
    class objects, enumeration members -- because the branches below would each
    claim one of them: a string is a sequence, and a member of an enum that
    assigns attributes looks like a record. :func:`is_opaque` carries the case for
    each.

    A **declared** record -- see :func:`declared_field_names` -- is resolved
    before every storage branch, because a ``NamedTuple`` *is* a tuple and a
    dataclass is free to subclass ``dict``. Left to the sequence branch,
    ``Point(1, 2)`` against ``Point(2, 1)`` would report "index 0" for a field the
    reader calls ``x`` -- and under ``ignoring_order`` it would compare equal,
    which is a silent, wrong pass on the one type the trap is easiest to fall
    into.

    A **stored** record -- one whose fields are only in ``__slots__`` or
    ``__dict__`` -- is resolved *after* the sequence branch, so that a list
    subclass which happens to carry an attribute is still compared as the list it
    is.

    And a dataclass leads the declared three: fall through from it and a
    ``field(compare=False)`` comes back in through ``vars`` and is reported as a
    difference that the ``==`` it was excluded from never looked at.
    """
    if is_opaque(value):
        return KIND_LEAF, ()
    declared = declared_field_names(value)
    if declared is not None:
        return _KIND_RECORD, declared
    if is_mapping(value):
        return KIND_MAPPING, ()
    if is_set(value):
        return KIND_SET, ()
    if isinstance(value, Sequence):
        return KIND_SEQUENCE, ()
    return _ASK_THE_VALUE
