"""What fields a value carries, and which of them disagree.

A declaration beats a dictionary, because a declaration is a statement of intent
and a dictionary is whatever happened to be assigned. So a dataclass, a
NamedTuple and an attrs class are each asked first and answer alone. ``__slots__``
and the instance dictionary are read *together* rather than raced: an object
often has both, and a slotted base under a subclass that carries a ``__dict__``
would otherwise report half of what it holds.

Every read of a field is guarded on its own. An object whose ``__getattr__``
raises is being described precisely because something about it is already wrong,
and one hostile field must cost that field rather than the whole report.
"""

from lovely_assertions._diff._primitives import clip, equal, indentation
from lovely_assertions._diff._render import membership_lines, pair_lines
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatting import current_formatting
from lovely_assertions._reflection import (
    attrs_field_names,
    dataclass_field_names,
    instance_dict_names,
    named_tuple_field_names,
    slot_names,
)

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def field_names(value: object, /) -> tuple[str, ...]:
    """The names that make this object what it is; the first to answer wins.

    ``dataclasses.fields`` leads because it is the only resolver that knows which
    fields the generated ``__eq__`` actually reads, and it is terminal for the
    same reason: fall through from it and a ``field(compare=False)`` comes back
    in through ``vars`` -- on the one type this was written for. Then a
    NamedTuple's own ``_fields``; then ``__attrs_attrs__``, for exactly the
    reason ``dataclasses.fields`` leads, since ``attrs`` spells the same
    exclusion ``eq=False``; then ``__slots__`` *together with* the instance
    dictionary, which is what answers for a plain class and for pydantic v2,
    neither of which is imported to be recognised.

    Skipping the ``attrs`` step is the mistake the order exists to prevent: an
    ``eq=False`` field would reach ``vars`` and be reported as a difference under
    a heading saying the objects are unequal, when the ``__eq__`` that said so
    never looked at it. Every resolver in the package reads its leaves from
    ``_reflection.py``, so no two of them can answer this differently.

    The last two are added rather than raced. An object has both storages more
    often than it looks: a ``__slots__`` base whose subclass does not repeat the
    declaration keeps the base's fields in slots and every one the subclass adds
    in a ``__dict__``, and reading only the winner would report the two fields it
    found and stay silent about the two it did not -- an incomplete answer that
    reads exactly like a complete one.
    """
    if isinstance(value, type):
        # A class's own ``__dict__`` holds the methods it defines, not the state
        # an instance carries; read as fields it would have two classes differ in
        # ``encode``. A class is not a record.
        return ()
    subject_type = type(value)
    if hasattr(subject_type, "__dataclass_fields__"):
        return dataclass_field_names(value)
    named = named_tuple_field_names(value)
    if named:
        return named
    attributes = attrs_field_names(value)
    if attributes:
        return attributes
    slots = slot_names(subject_type)
    members = instance_dict_names(value)
    if not slots:
        return members
    return slots + tuple(name for name in members if name not in slots)


def differing_field_lines(
    actual: object, expected: object, names: list[str], depth: int, /
) -> list[str]:
    """The shared fields that hold different values, capped and counted."""
    differing = _differing_fields(actual, expected, names)
    max_items = current_formatting().max_items
    lines: list[str] = []
    for name, actual_value, expected_value in differing[:max_items]:
        # Clipped like every other rendered label, for the same reason a mapping
        # key is: a name read off an instance dictionary is not always short.
        lines.extend(pair_lines("field " + clip(name), actual_value, expected_value, depth))
    elided = len(differing) - max_items
    if elided > 0:
        lines.append(indentation(depth) + _more_fields_note(elided))
    return lines


def _differing_fields(
    actual: object, expected: object, names: list[str], /
) -> list[tuple[str, object, object]]:
    """The fields that hold different values, with both values already read."""
    found: list[tuple[str, object, object]] = []
    for name in names:
        pair = _field_pair(actual, expected, name)
        if pair is not None:
            found.append((name, *pair))
    return found


def _field_pair(actual: object, expected: object, name: str, /) -> tuple[object, object] | None:
    """Both sides of one field, or ``None`` when there is nothing to report.

    ``None`` covers the equal case and every case this cannot answer: a property
    that raises, a ``__slots__`` entry that was never assigned, an ``__eq__``
    that blows up. Guarded per field rather than around the loop on purpose -- one
    hostile member of a twelve-field record must cost the reader that field, not
    the other eleven.
    """
    try:
        actual_value = getattr(actual, name)
        expected_value = getattr(expected, name)
        if equal(actual_value, expected_value):
            return None
    except Exception:
        return None
    return actual_value, expected_value


def _more_fields_note(elided: int, /) -> str:
    """``"... (5 more fields hold a different value)"``, and the singular of it."""
    if elided == 1:
        return "... (1 more field holds a different value)"
    return "... (" + str(elided) + " more fields hold a different value)"


def field_lines(
    actual: object,
    expected: object,
    actual_fields: tuple[str, ...],
    expected_fields: tuple[str, ...],
    depth: int,
    /,
) -> list[str]:
    """Fields that disagree first, then fields only one side carries.

    The same order, and the same vocabulary, as the mapping describer: a wrong
    value under a right name is what an object comparison usually fails on. The
    membership half only ever has anything to say for two objects read through
    their ``__dict__``, where the field set belongs to the instance rather than
    to the class.
    """
    on_actual = frozenset(actual_fields)
    on_expected = frozenset(expected_fields)
    shared = [name for name in expected_fields if name in on_actual]
    lines = differing_field_lines(actual, expected, shared, depth)
    missing: list[object] = [name for name in expected_fields if name not in on_actual]
    extra: list[object] = [name for name in actual_fields if name not in on_expected]
    lines.extend(membership_lines(indentation(depth), missing, extra, "fields"))
    return lines
