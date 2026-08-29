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
"""

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING, Final, TypeIs, cast

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Iterable

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


def qualified(subject_type: type, /) -> str:
    """``package.module.Class``, for when the bare name does not tell them apart."""
    return subject_type.__module__ + "." + subject_type.__qualname__


def is_float_nan(value: object, /) -> bool:
    """Whether a value is a float NaN, without importing ``math``.

    Deliberately *not* :func:`lovely_assertions._ordered.is_nan`, which asks the
    same question of a wider world and gets a different answer. That one is the
    bare ``value != value``, so it recognises a ``Decimal("nan")`` -- which is
    what the ordering catalogue needs of it -- and so it also answers ``True`` for
    a ``Mock``, whose ``__eq__`` returns a new mock every time it is asked. A
    describer that called a mock a NaN would explain a failure with a fact about
    floating point that has nothing to do with it. Two questions, two names.
    """
    return isinstance(value, float) and value != value  # noqa: PLR0124  (that is what NaN means)


def is_mapping(value: object, /) -> TypeIs[Mapping[object, object]]:
    """Whether a value is a mapping, narrowed to what a caller needs to read.

    The two ``is_*`` predicates carry ``TypeIs`` rather than being written as bare
    ``isinstance`` calls at the call site: an un-parameterised ``isinstance``
    narrows ``object`` to ``Mapping[Unknown, Unknown]``, and the unknowns then leak
    into every branch after it. ``Mapping[object, object]`` is a supertype only for
    reading, which is all either caller ever does with them.
    """
    return isinstance(value, Mapping)


def is_set(value: object, /) -> TypeIs[AbstractSet[object]]:
    """Whether a value is a set, narrowed to what a caller needs to read."""
    return isinstance(value, AbstractSet)


def _is_reserved(name: str, /) -> bool:
    """Whether a name belongs to the machinery rather than to the object's state.

    No library's fields are called ``__like_this__``, and every runtime's
    bookkeeping is: the rule costs nothing and keeps a describer of *fields* from
    reporting one.

    ``_like_this_`` goes with it, because the ``enum`` module reserves that
    spelling outright. An ``IntEnum`` member carries ``_name_``, ``_value_`` and
    ``_sort_order_`` in its instance dictionary, so without this rule two members
    differ in an *ordinal nobody wrote* -- and differ in it only when the enum
    happens to mix in a type, since a plain ``Enum`` compares by identity and a
    ``StrEnum`` is routed to the text describer. Dropped, all three flavours say
    the same nothing about two members that their two reprs did not.
    """
    return len(name) > 1 and name.startswith("_") and name.endswith("_")


def _names_of(declared: object, /) -> tuple[str, ...]:
    """The string names in a ``__slots__`` or ``_fields`` declaration.

    ``__slots__`` may be a single string rather than a sequence of them, and
    either declaration is an ordinary class attribute that any class is free to
    set to anything at all, so this reads what it can and discards the rest.
    """
    if isinstance(declared, str):
        return (declared,)
    try:
        entries = tuple(cast("Iterable[object]", declared))
    except TypeError:
        return ()
    return tuple(entry for entry in entries if isinstance(entry, str))


def dataclass_field_names(value: object, /) -> tuple[str, ...]:
    """A dataclass's fields, minus the ones its ``__eq__`` was told to ignore.

    ``field(compare=False)`` is excluded because the generated ``__eq__``
    excludes it: a describer that reported it would contradict the very
    comparison that produced the failure. ``dataclasses.fields`` rather than a
    read of ``__dataclass_fields__`` for a second reason -- it drops the
    ``ClassVar`` and ``InitVar`` pseudo-fields, which are not state either.
    """
    import dataclasses  # noqa: PLC0415  (importing this package must not import dataclasses)

    if not dataclasses.is_dataclass(value) or isinstance(value, type):
        # Unreachable through either caller's race, which has already found
        # `__dataclass_fields__` on the *instance's* type. It is here to narrow
        # `object` down to something `fields()` accepts, and it costs two checks
        # on a path that is about to read every field it names.
        return ()
    return tuple(entry.name for entry in dataclasses.fields(value) if entry.compare)


def named_tuple_field_names(value: object, /) -> tuple[str, ...]:
    """A NamedTuple's own account of its fields; ``()`` for everything else.

    The ``isinstance`` is asked last and its answer is never carried forward, so
    that the narrowing it performs -- ``object`` becomes ``tuple[Unknown, ...]``,
    which pyright strict then refuses to pass on -- dies with the expression.
    """
    names = _names_of(getattr(type(value), "_fields", None))
    if not names or not isinstance(value, tuple):
        return ()
    return names


def attrs_field_names(value: object, /) -> tuple[str, ...]:
    """An ``attrs`` class's fields, minus the ones it excluded from ``__eq__``.

    Duck-typed through ``__attrs_attrs__`` with nothing imported, which is how a
    library with zero runtime dependencies supports one it does not depend on. The
    ``eq`` flag is honoured for the same reason ``compare`` is on a dataclass.
    """
    declared = getattr(type(value), "__attrs_attrs__", None)
    if declared is None:
        return ()
    try:
        entries = tuple(cast("Iterable[object]", declared))
    except TypeError:
        return ()
    names: list[str] = []
    for entry in entries:
        name = getattr(entry, "name", None)
        if isinstance(name, str) and getattr(entry, "eq", True):
            names.append(name)
    return tuple(names)


def slot_names(subject_type: type, /) -> tuple[str, ...]:
    """Every ``__slots__`` entry the type declares, base classes first.

    Walked over the whole MRO rather than read off the class: a subclass declares
    only the slots it adds, so reading one class would report its two fields and
    silently drop the four it inherited.

    Dunders are dropped, and that is what makes pydantic v2 work. ``BaseModel``
    declares ``__slots__ = '__dict__', '__pydantic_fields_set__', ...`` -- storage
    and bookkeeping, with the field values in the instance dictionary those slots
    ask for. Kept, they would resolve first and every model comparison would
    report a difference in ``__pydantic_fields_set__`` instead of in the fields
    the reader wrote. Dropped, the slot resolver declines and ``vars`` answers.

    Remembered per type, because the walk above reads a class attribute at every
    level of the MRO -- a real cost even for an ``int``, which declares no slots
    at all -- on a function the equivalence walk calls for every pair it examines.
    The answer is a property of the class, not of the instance, so there is
    nothing to go stale.
    """
    cached = _SLOTS_BY_TYPE.get(subject_type, _UNCACHED)
    if cached is not _UNCACHED:
        return cast("tuple[str, ...]", cached)
    names: list[str] = []
    for klass in reversed(subject_type.__mro__):
        declared: object = klass.__dict__.get("__slots__")
        for name in _names_of(declared):
            if not _is_reserved(name) and name not in names:
                names.append(name)
    resolved = tuple(names)
    remember(_SLOTS_BY_TYPE, subject_type, resolved)
    return resolved


def instance_dict_names(value: object, /) -> tuple[str, ...]:
    """The attributes an ordinary object actually carries.

    ``vars`` rather than ``dir``: the instance dictionary is the object's state,
    where ``dir`` would list every method of its class alongside it. A value with
    no instance dictionary at all -- an ``int``, anything written in C -- resolves
    to nothing, which is how those reach the describer and are declined by it.
    """
    try:
        members = vars(value)
    except TypeError:
        return ()
    return tuple(name for name in members if not _is_reserved(name))


#: Sentinel for a cache miss, so that a remembered ``None`` -- a real answer for
#: the callers that have one -- is told apart from nothing remembered at all.
_UNCACHED: Final = object()

#: Slot answers already worked out, keyed by the type asked about.
_SLOTS_BY_TYPE: dict[type, tuple[str, ...]] = {}

#: Types held in a cache before it is emptied. A cache keyed on class objects
#: keeps every class it has seen alive, and a suite that builds a class per test
#: would otherwise grow one entry per test for the length of the run. Cleared
#: wholesale rather than evicted one at a time: the answers are cheap to rebuild
#: and a policy that has to be right is worse than one that has to be bounded.
_MAX_CACHED_TYPES: Final = 4096


def remember[Answer](cache: dict[type, Answer], subject_type: type, answer: Answer, /) -> None:
    """Record one type's answer, keeping the cache bounded."""
    if len(cache) >= _MAX_CACHED_TYPES:
        cache.clear()
    cache[subject_type] = answer
