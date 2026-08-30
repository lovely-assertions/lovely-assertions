"""What an object's fields are called, and the predicates that go with the question.

Two modules need this answer. ``_diff`` needs it to say which field made ``==``
say no, and ``_equivalence`` needs it to walk two graphs member by member. The
leaves live here so that there is one answer rather than two, because two
resolvers that are free to drift produce a failure nobody can spot from the
outside: report an ``attrs`` field declared ``eq=False`` and the reader is shown
a difference in a field the object's ``__eq__`` never looked at, under a heading
that says the objects are unequal. Which resolver is right is not visible in
either message, and nothing forces them to agree.

What is shared is the leaves; each caller keeps its own race over them, and that
division is the point rather than an accident. The two genuinely want different
orders, and only ``_equivalence`` needs "declares no fields" to be a distinct
answer from "declares none", so that a dataclass subclassing ``dict`` falls
through to its fields instead of to its entries. What neither needs is its own
idea of what a ``__slots__`` declaration contains.

The names here carry no leading underscore, by the rule the package follows
throughout: a name imported across a module boundary is that module's public
surface, and spelling it private only obliges its callers to lie.

**Importing this module imports nothing a user would not otherwise pay for.**
:func:`dataclass_field_names` imports ``dataclasses`` inside itself, so that only
the caller who actually resolves a dataclass's fields pays for it, and ``attrs``
is duck-typed through ``__attrs_attrs__`` with nothing imported at all.

The leaves are grouped by the question they answer: what a value *is*, what its
fields are *called*, and the bounded memo the slot answers are kept in.

The memo's cap and its table are deliberately not re-exported here. Both are
reached for by name from outside, and re-exporting one would put a second binding
on this module that the code reading it does not share -- so a reach aimed here
would find something, act on a copy, and leave the original untouched. Absent,
the same reach raises ``AttributeError`` at the line that made the mistake.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._reflection._cache import remember
from lovely_assertions._reflection._fields import (
    attrs_field_names,
    dataclass_field_names,
    instance_dict_names,
    named_tuple_field_names,
    slot_names,
)
from lovely_assertions._reflection._predicates import (
    is_float_nan,
    is_mapping,
    is_set,
    qualified,
)

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = [
    "attrs_field_names",
    "dataclass_field_names",
    "instance_dict_names",
    "is_float_nan",
    "is_mapping",
    "is_set",
    "named_tuple_field_names",
    "qualified",
    "remember",
    "slot_names",
]
