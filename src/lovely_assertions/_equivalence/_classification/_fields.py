"""What names can be read off a value, and where they were written down.

The other half of classification. Routing decides what a value *is*; this decides
what there is to compare once that is settled. It sits at the bottom of the
package because both of the others ask it and it asks neither.

Declared and stored are two different questions, not two attempts at one. A
declaration is the author stating what the object is, so the ways of writing one
down are raced and the first to answer wins. Storage is whatever the object turned
out to be holding, so ``__slots__`` and the instance dictionary are added rather
than raced: an object has both more often than it looks, and reading only the
winner compares the fields it found, ignores the fields it did not, and reports
the pair equivalent.

Of the two, only the declared answer is remembered here, and only on
``type(value)`` -- what a class declares is a property of the class, while what an
instance stores is the instance's and is re-read every time. That split is what
makes the cache sound rather than an approximation.

The enum-member test lives here for the same reason the rest does: it is a
question about what a class and a member carry, and it is answered by reading
those marks rather than by importing ``enum``, on a path a comparison that never
meets an enumeration should not pay for.
"""

from typing import Final, cast

from lovely_assertions._equivalence._memo import UNCACHED
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._reflection import (
    attrs_field_names,
    dataclass_field_names,
    instance_dict_names,
    named_tuple_field_names,
    remember,
    slot_names,
)

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: What a record whose every declared field turned out not to exist has to say
#: for itself. Reported alongside the two values, because with no member readable
#: on either side those reprs are the only account of the difference there is.
UNRESOLVED: Final = "(none of the fields it declares could be read on either side)"


# ---------------------------------------------------------------------------
# Kinds
# ---------------------------------------------------------------------------
#: What a type declares, worked out once. Keyed on the class object, and what it
#: holds is a property of that class: which fields the class declares, read from
#: the class and never from an instance. That is what makes caching it sound
#: rather than an approximation.
#:
#: A class rewritten after it has been compared -- a second ``@dataclass`` applied
#: to the same object -- would keep the answer taken the first time. That is
#: accepted rather than defended against: the shape does not occur outside a test
#: deliberately building one.
_DECLARED_BY_TYPE: dict[type, "tuple[str, ...] | None"] = {}


def declared_field_names(value: object, /) -> tuple[str, ...] | None:
    """The fields a type declares, remembered per type; ``None`` when it declares none.

    See :func:`_resolve_declared_field_names` for what the answer is and why it
    is asked where it is. This wrapper exists for what the answer *costs*.
    Resolving it runs ``dataclasses.fields()``, an MRO lookup for ``_fields`` and
    another for ``__attrs_attrs__``, and for a plain ``int`` most of that price is
    an exception raised and caught while reading a declaration that is not there.
    None of that can come out differently twice, because each of the three
    questions is asked of ``type(value)`` and never of the value, so the price is
    paid once for a class and then remembered.
    """
    subject_type = type(value)
    cached = _DECLARED_BY_TYPE.get(subject_type, UNCACHED)
    if cached is not UNCACHED:
        return cast("tuple[str, ...] | None", cached)
    resolved = _resolve_declared_field_names(value)
    remember(_DECLARED_BY_TYPE, subject_type, resolved)
    return resolved


def _resolve_declared_field_names(value: object, /) -> tuple[str, ...] | None:
    """The fields a type *declares*, or ``None`` when it declares none.

    Raced in the contract's order -- ``dataclasses.fields()``, then ``_fields``,
    then ``__attrs_attrs__`` -- and asked before the mapping, set and sequence
    branches, because a declaration is the author saying what the object *is*
    where those branches only see what it happens to be stored in. A dataclass
    that subclasses ``dict`` is the case that makes the difference: compared as a
    mapping, its declared fields are never looked at, and two instances carrying
    the same entries under different fields come back **equivalent** while ``==``
    -- which reads the fields and ignores the entries -- says they are not.

    ``None`` rather than ``()`` because "declares no fields" and "declares fields
    and they are empty" are different answers, and only the first one falls
    through.
    """
    if hasattr(type(value), "__dataclass_fields__"):
        return dataclass_field_names(value)
    named = named_tuple_field_names(value)
    if named:
        return named
    attributes = attrs_field_names(value)
    if attributes:
        return attributes
    return None


def is_enum_member(value: object, /) -> bool:
    """Whether a value is a member of an enumeration, without importing ``enum``.

    Duck-typed on the two marks the ``enum`` machinery leaves and nothing else
    does: ``_member_map_`` on the class, ``_value_`` on the member. Read rather
    than imported because the routing order asks this of every value it takes
    apart, and a comparison that never meets an enumeration should not pay for
    ``import enum``. The reader behind ``comparing_enums_by_name()`` does import
    it, and can afford to: it runs only for the callers who asked for that option.

    A class that sets ``_member_map_`` for its own reasons is compared as a leaf,
    which is the conservative answer: a leaf pair is settled by ``==``, so nothing
    is claimed about it that Python does not already claim.
    """
    return hasattr(type(value), "_member_map_") and hasattr(value, "_value_")


# ---------------------------------------------------------------------------
# Fields
# ---------------------------------------------------------------------------
def stored_field_names(value: object, /) -> tuple[str, ...]:
    """``__slots__`` together with the instance dictionary.

    Added rather than raced, and for an equivalence engine the reason is sharper
    than it is for a describer. An object has both storages more often than it
    looks -- a ``__slots__`` base whose subclass does not repeat the declaration
    keeps the base's fields in slots and every one the subclass adds in a
    ``__dict__`` -- and reading only the winner would compare the two fields it
    found, ignore the two it did not, and report the pair *equivalent*.

    Dunders are dropped, and that is what makes pydantic v2 work: ``BaseModel``
    declares ``__slots__`` for storage and bookkeeping and keeps the field values
    in the instance dictionary those slots ask for. Kept, every model comparison
    would be about ``__pydantic_fields_set__`` instead of about the fields
    somebody wrote.
    """
    slots = slot_names(type(value))
    members = instance_dict_names(value)
    if not slots:
        return members
    return slots + tuple(name for name in members if name not in slots)
