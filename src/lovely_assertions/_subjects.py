"""``expect()``: the single entry point, and the dispatch that picks a subject.

Each subject lives in its own module -- ``_string.py``, ``_numeric.py`` and so on
-- because each carries a full assertion catalogue and one file holding all of
them would be unreviewable. This module is the façade: it re-exports the subjects
and owns the dispatch.

The static overload order and the runtime dispatch order are **one table seen
twice**: ``bool`` before ``int`` because ``bool`` is an ``int``, ``str`` before
``Sequence`` because a ``str`` is a ``Sequence[str]``, ``Mapping`` before
``Sequence``, bare ``T`` last. First match wins in both halves, and the two must
be edited together: if they drift, a checker promises one catalogue while the
runtime builds another, and a subject advertises methods it does not have.
"""

import sys
from abc import get_cache_token
from collections.abc import Callable, Collection, Mapping, Sequence
from types import BuiltinFunctionType, FunctionType, MethodType
from typing import TYPE_CHECKING, Any, overload

from lovely_assertions._bool import BoolExpect
from lovely_assertions._callable import CallableExpect, RaisedExpect, expect_raises
from lovely_assertions._collection import CollectionExpect
from lovely_assertions._core import Expect
from lovely_assertions._datetime import (
    DateExpect,
    DateTimeExpect,
    TimeDeltaExpect,
    TimeExpect,
    WithinDelta,
)
from lovely_assertions._enum import EnumExpect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._mapping import MappingExpect
from lovely_assertions._mock import (
    FIRST_MOCK_MARKER,
    MockExpect,
    answers_the_protocol,
    is_mock,
)
from lovely_assertions._numeric import NumericExpect
from lovely_assertions._ordered import OrderedExpect
from lovely_assertions._path import PathExpect, PurePathExpect
from lovely_assertions._sequence import SequenceExpect
from lovely_assertions._string import StringExpect
from lovely_assertions._type import TypeExpect

if TYPE_CHECKING:
    from datetime import date, datetime, time, timedelta
    from decimal import Decimal
    from enum import Enum
    from fractions import Fraction
    from pathlib import Path, PurePath

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = [
    "BoolExpect",
    "CallableExpect",
    "CollectionExpect",
    "DateExpect",
    "DateTimeExpect",
    "EnumExpect",
    "MappingExpect",
    "MockExpect",
    "NumericExpect",
    "OrderedExpect",
    "PathExpect",
    "PurePathExpect",
    "RaisedExpect",
    "SequenceExpect",
    "StringExpect",
    "TimeDeltaExpect",
    "TimeExpect",
    "TypeExpect",
    "WithinDelta",
    "expect",
    "expect_raises",
    "is_mock",
    "register",
]


# `as_=` comes first: it is the only overload that takes a keyword, so nothing
# else can match a call that passes one, and putting it at the top says plainly
# that an explicit request wins over inference.
@overload
def expect[V, X: Expect[Any]](value: V, /, *, as_: "Callable[[V], X]", name: str = ...) -> X: ...
# A class is a class before it is anything else, matching `isinstance(value, type)`
# at the head of the runtime chain. The position is load-bearing rather than
# tidy: an `Enum` class is a `Collection` through `EnumMeta`, and a class whose
# metaclass implements the mapping protocol is a `Mapping`, so anywhere below
# `Collection` leaves the two halves disagreeing -- a checker answering
# `CollectionExpect` for `expect(Colour)` while the runtime builds a `TypeExpect`.
@overload
def expect(value: type[Any], /, *, name: str = ...) -> TypeExpect: ...
# Then the subjects whose value types live in modules the library refuses to
# import. They come first among the inferred overloads because one of them has to:
# an `IntEnum` member is an `int` and a `StrEnum` member is a `str`, so anything
# below would claim it. Their order here is `_LAZY_SUBJECTS` read aloud -- the two
# are one table seen twice, subclass before superclass throughout: `datetime`
# before `date` and `Path` before `PurePath`, because each is one.
@overload
def expect[E: "Enum"](value: E, /, *, name: str = ...) -> "EnumExpect[E]": ...
@overload
def expect(value: "datetime", /, *, name: str = ...) -> DateTimeExpect: ...
@overload
def expect[D: "date"](value: D, /, *, name: str = ...) -> "DateExpect[D]": ...
@overload
def expect(value: "time", /, *, name: str = ...) -> TimeExpect: ...
@overload
def expect(value: "timedelta", /, *, name: str = ...) -> TimeDeltaExpect: ...
@overload
def expect(value: "Path", /, *, name: str = ...) -> PathExpect: ...
@overload
def expect[P: "PurePath"](value: P, /, *, name: str = ...) -> "PurePathExpect[P]": ...
# `Decimal` and `Fraction` are ordered but are not `int | float`, so without an
# entry of their own they would fall through to the bare generic subject. They get
# the ordering half of the numeric family and keep their own type on `.subject`
# rather than being flattened into `int | float`.
@overload
def expect(value: "Decimal", /, *, name: str = ...) -> "OrderedExpect[Decimal]": ...
@overload
def expect(value: "Fraction", /, *, name: str = ...) -> "OrderedExpect[Fraction]": ...
# `bool` deliberately shadows `int | float`, and `str` deliberately shadows
# `Sequence[E]`. First-match-wins is the contract, so the overlap the checkers
# advise about is the intended behaviour, not an oversight, and the suppressions
# below are aimed at exactly that advice and nothing else.
@overload
def expect(value: bool, /, *, name: str = ...) -> BoolExpect: ...  # type: ignore[overload-overlap]  # pyright: ignore[reportOverlappingOverload]
@overload
def expect(value: str, /, *, name: str = ...) -> StringExpect: ...  # type: ignore[overload-overlap]  # pyright: ignore[reportOverlappingOverload]
@overload
def expect(value: int | float, /, *, name: str = ...) -> NumericExpect: ...
# `Mapping` deliberately shadows `Collection[E]` below, the way `str` shadows
# `Sequence[E]`: a mapping is a collection of its keys, and its own subject is
# the richer one. Same first-match-wins contract, same deliberate overlap, same
# targeted suppression.
#
# It sits *below* `bool`, `str` and `int | float` rather than above them, and that
# is reachable rather than tidy: `Mapping` has `ABCMeta` for its metaclass, so a
# class can inherit both it and a built-in, and `_resolve_shape` asks the same
# questions in this same order so that such a class gets one answer, not two.
@overload
def expect[K, V](value: Mapping[K, V], /, *, name: str = ...) -> MappingExpect[K, V]: ...  # type: ignore[overload-overlap]
@overload
def expect[E](value: Sequence[E], /, *, name: str = ...) -> SequenceExpect[E]: ...
# Everything left that has a length, an iterator and a membership test: sets,
# frozensets and the three dict views. After `Sequence` and `Mapping`, because
# each of those is a collection with more to offer.
@overload
def expect[E](value: Collection[E], /, *, name: str = ...) -> CollectionExpect[E]: ...
# A class is callable and has far more to say about itself than that, so it sits
# above the callable overload, in the same first-match-wins order the runtime
# walks.
#
# There is deliberately NO overload for a mock, though the runtime dispatches one
# to `MockExpect`. typeshed gives `NonCallableMock` an `Any` in its MRO, so a mock
# is statically assignable to *everything* -- `b: bool = Mock()` type-checks --
# and no position in this list can reach it: the first concrete overload always
# wins. That makes the static answer for a mock meaningless whatever we write, so
# the runtime is left to be right on its own. `expect(mock, as_=MockExpect)` is
# the typed route.
# A callable is a subject in its own right: `expect(parse).raises(ValueError)`.
# It sits second-to-last because everything above it is narrower. A class never
# reaches it -- the `type[Any]` overload at the top claims classes -- and loses
# nothing by that, since `TypeExpect` extends `CallableExpect`. What lands here is
# a function, a bound method, or an instance of a class defining `__call__`, and
# the only cost is that `.subject` widens to the callable type.
@overload
def expect(value: "Callable[..., object]", /, *, name: str = ...) -> CallableExpect: ...
@overload
def expect[T](value: T, /, *, name: str = ...) -> Expect[T]: ...
def expect(
    value: object, /, *, as_: "Callable[[Any], Expect[Any]] | None" = None, name: str | None = None
) -> Any:
    """Wrap ``value`` in the subject that knows how to assert on it.

        >>> expect("hello").starts_with("hell").and_.has_length(5).subject
        'hello'

    The subject is chosen from the type of ``value``, first match wins: ``bool``
    before ``int``, ``str`` and ``Mapping`` before ``Sequence``, and a generic
    :class:`Expect` for anything nothing claims. Dispatch never fails: every value
    has a subject. Returns it ready to assert on, and the assertions chain.

    Pass ``as_=`` to name the subject outright -- a factory taking the value and
    returning a subject. It overrides inference, it is the fully typed route to a
    custom subject, and it is the only way to reach :class:`MockExpect` with a
    checker's blessing. Pass ``name=`` to
    describe the subject in failure messages, exactly as ``described_as`` does; it
    is applied after the subject is built, so it composes with ``as_=``.

    The parameter is ``object`` rather than ``Any`` on purpose: narrowing an
    explicit ``Any`` with ``isinstance`` yields ``Unknown``, which pyright's
    strict mode rejects. Dispatch is one ``type()`` call and an O(1) lookup for
    exact built-ins, falling back to ``issubclass`` on the *type object* for
    subclasses and ABCs.

    **That first lookup is written here rather than called.** Reading it at the
    head of :func:`_dispatch` would be tidier and would cost a Python frame on the
    most-walked path in the library -- and the type it computed would be thrown
    away, so a value that fell through would pay for the same lookup twice. What
    is inlined is one dict lookup; what stays in :func:`_dispatch` is the whole
    chain that needs explaining, which is where the split earns its keep.
    """
    if as_ is None and name is None:
        subject_type = type(value)
        factory = _EXACT_SUBJECTS.get(subject_type)
        if factory is not None:
            return factory(value)
        return _dispatch(value, subject_type)
    # Inference on this path is the un-named call itself rather than a second
    # copy of it. Every overload declares `name=`, so a name must not change which
    # subject a value gets -- and entering `_dispatch` straight from here would
    # change it, because the exact table above is the only place `bool` is told
    # apart from `int`, and the chain behind that table answers `NumericExpect`
    # for one.
    subject = as_(value) if as_ is not None else expect(value)
    if name is not None:
        subject.described_as(name)
    return subject


def _dispatch(value: object, subject_type: type[Any], /) -> Any:  # noqa: ANN401  (any subject)
    """Everything after the exact table, which :func:`expect` has already tried.

    ``subject_type`` is handed in rather than recomputed, so a value that falls
    through here pays for one ``type()`` and one dict lookup in total rather than
    two of each.
    """
    # The exact table leads -- in `expect`, above -- and that ordering is
    # load-bearing in both directions.
    #
    # It is safe in front of the mock check because that table is keyed on
    # *identity of type*: a hit means `type(value) is int`, and no mock has ever
    # had that. Not `Mock(spec=int)`, not `create_autospec(int)`, not a `MagicMock`
    # subclass, and not the `m.__class__ = int` trick -- that one makes
    # `isinstance(m, int)` true while `type(m)` still reads `MagicMock`, because
    # `__class__` is an attribute and `type()` reads the object header. Asking the
    # mock question first would instead spend a large slice of the hottest path in
    # the library ruling out, on every `expect(3)`, a possibility an `int` cannot
    # represent.
    #
    # From here the order is correctness, not speed. A mock is a mock before it is
    # anything else: `MagicMock` defines `__len__`, `__iter__` and `__contains__`,
    # so the `Collection` branch below claims it otherwise -- and a mock is not a
    # collection in any sense the collection catalogue could act on. `_REGISTERED`
    # sits *after* the mock check, so a mock of a registered type is still a mock.
    #
    # The mock question is inlined here rather than called, and not weakened by
    # that. It is the most expensive single step of a fallthrough, and the two
    # Python frames a call would cost are the bulk of it, for a question whose
    # answer is almost always no. So the first marker attribute is tested before
    # any frame is entered, and the autospec arm is split off rather than reached
    # through a failed class check.
    #
    # `create_autospec(some_function)` is why that arm exists: it returns a real
    # function carrying the mock protocol as *instance* attributes, so its class
    # declares none of the markers. `_mock.is_mock` says the rest, and stays
    # exactly as it is -- it is public surface.
    if subject_type is FunctionType:
        if answers_the_protocol(value):
            return MockExpect(value)
    elif hasattr(subject_type, FIRST_MOCK_MARKER) and answers_the_protocol(subject_type):
        return MockExpect(value)
    factory = _REGISTERED.get(subject_type)
    if factory is None:
        factory = _claimed_by_shape(subject_type)
    if factory is not None:
        return factory(value)
    # The callable branch, asked of the value rather than of its type. It is the
    # one question `_claimed_by_shape` cannot answer cheaply: `callable()` is a
    # C-level slot test on the value, while reproducing it from a type alone means
    # walking the MRO -- an order of magnitude dearer, on every value that reaches
    # the end of the chain. `claimed_by` pays that price because `register()` has
    # no value to ask -- and it runs once, at import.
    if callable(value):
        return CallableExpect(value)
    return Expect(value)


def subject_for(subject_type: type[Any], /) -> "Callable[[Any], Expect[Any]] | None":
    """The subject :func:`expect` builds for a value of this type, or ``None``.

    The whole answer, in the order :func:`_dispatch` walks it: the exact table
    first, then everything :func:`claimed_by` decides. Written once because two
    callers need it and they must not disagree -- :func:`register`, which refuses
    a type the overloads already claim, and ``Found.which``, which honours a type
    the caller named rather than re-dispatching the value.

    The exact table cannot be left out, and ``bool`` is why: the shape chain
    answers ``NumericExpect`` for it -- a ``bool`` is an ``int`` -- while
    ``expect(True)`` is a ``BoolExpect`` through the table that leads. Asking only
    :func:`claimed_by` would hand ``as_type(bool)`` the wrong catalogue.

    ``None`` for a type nothing claims, which is the generic subject's answer.
    """
    return _EXACT_SUBJECTS.get(subject_type) or claimed_by(subject_type)


def claimed_by(subject_type: type[Any], /) -> "Callable[[Any], Expect[Any]] | None":
    """The subject the built-in table builds for a type, or ``None`` for the generic one.

    The whole chain, including the callable branch that :func:`_dispatch` answers
    from the value instead. Used by :func:`register`, which is handed a type and no
    value, and which runs once at import where the MRO walk costs nothing.

    No leading underscore because other modules in the package reach it, and a
    name that announces itself as private and is then imported across a module
    boundary is worse than the plain name.
    """
    return _claimed_by_shape(subject_type) or (
        CallableExpect if _instances_are_callable(subject_type) else None
    )


#: The callable types, in a table of their own *behind* the mock check rather than
#: in `_EXACT_SUBJECTS` in front of it. Without it every callable spelling falls
#: through the whole `issubclass` chain, and `expect(lambda: parse(text))
#: .raises(ValueError)` is a common line that would then pay the most expensive
#: dispatch in the library.
#:
#: They cannot join the table that leads, and the reason is worth writing down:
#: `create_autospec(some_function)` produces an object whose `type()` really is
#: `function`, because autospec builds a genuine function wrapper carrying the
#: right signature. Put `FunctionType` in front of the mock check and every
#: autospecced function silently becomes a `CallableExpect` instead of a
#: `MockExpect`. Nothing in `_EXACT_SUBJECTS` has that problem -- no mock has ever
#: had `type() is int` -- which is exactly why the two tables are separate.
#:
#: `BuiltinMethodType is BuiltinFunctionType` in CPython, so `{}.keys` and `len`
#: are the same entry; a bound method of a Python class is `MethodType`.
_CALLABLE_TYPES: "dict[type[Any], Callable[[Any], Expect[Any]]]" = {
    FunctionType: CallableExpect,
    BuiltinFunctionType: CallableExpect,
    MethodType: CallableExpect,
}


def _claimed_by_shape(subject_type: type[Any], /) -> "Callable[[Any], Expect[Any]] | None":
    """Everything :func:`claimed_by` can decide from the shape of a type alone.

    Remembered per type -- see :data:`_SHAPE_ANSWERS` for why that is sound, and
    what discards it. ``try``/``except`` rather than ``.get()`` because ``None`` is
    a real answer here and a miss has to be told apart from a remembered "no".
    """
    token = get_cache_token()
    if token != _SHAPE_TOKEN[0]:
        _SHAPE_ANSWERS.clear()
        _SHAPE_TOKEN[0] = token
    try:
        return _SHAPE_ANSWERS[subject_type]
    except KeyError:
        pass
    answer = _resolve_shape(subject_type)
    if len(_SHAPE_ANSWERS) >= _MAX_SHAPE_ANSWERS:
        _SHAPE_ANSWERS.clear()
    _SHAPE_ANSWERS[subject_type] = answer
    return answer


def _resolve_shape(subject_type: type[Any], /) -> "Callable[[Any], Expect[Any]] | None":
    """Work the shape answer out from scratch. Called once per type, then remembered.

    Read twice, which is the point. :func:`_dispatch` reads it to build a subject,
    and :func:`register` reads it to refuse a type the static overloads already
    claim. Both must consult the same chain: were ``register()`` to measure itself
    against only the exact entries in :data:`_EXACT_SUBJECTS` while the overloads
    claim a great deal more, ``register(datetime, ...)`` would be accepted and
    leave the runtime answering the caller's subject while both checkers went on
    promising ``DateTimeExpect``. One chain, read twice.
    """
    # Every class, not only the ones whose metaclass is `type` and which the exact
    # table already caught. It has to precede the `Collection` branch below: an
    # `Enum` class defines `__len__`, `__iter__` and `__contains__` through
    # `EnumMeta`, so that branch would claim it -- while the static side matches
    # `type[Any]` and answers `TypeExpect`. The two orders are one table seen
    # twice, so the runtime follows the overloads rather than the reverse.
    if issubclass(subject_type, type):
        return TypeExpect
    # Then the types from modules this one refuses to import. It has to precede
    # `str` and `int | float`: a `StrEnum` member is a `str` and an `IntEnum`
    # member is an `int`, and `_enum.py` explains why being an enum wins.
    lazy = _lazy_module_subject(subject_type)
    if lazy is not None:
        return lazy
    # `str` and `int | float` lead `Mapping` because the overloads put them there,
    # and the difference is reachable rather than theoretical: `Mapping` has
    # `ABCMeta` for its metaclass, so `class Config(str, Mapping[str, int])` is a
    # class anyone can write, and every overload above `Mapping` claims it. Only
    # this order answers what the checker promised its author.
    if issubclass(subject_type, str):
        return StringExpect
    if issubclass(subject_type, int | float):
        return NumericExpect
    # `Mapping` in turn leads the two below it: a mapping is a collection of its
    # keys, and its own subject is the richer one.
    if issubclass(subject_type, Mapping):
        return MappingExpect
    if issubclass(subject_type, Sequence):
        return SequenceExpect
    if issubclass(subject_type, Collection):
        return CollectionExpect
    return None


def _instances_are_callable(subject_type: type[Any], /) -> bool:
    """Whether ``callable()`` answers ``True`` for an instance of this type.

    Not ``hasattr(subject_type, "__call__")``: that finds ``type.__call__`` on the
    metaclass and so answers ``True`` for every class ever written. ``callable()``
    asks whether the *value's own type* fills the call slot, which is what walking
    the MRO reproduces.
    """
    return any("__call__" in base.__dict__ for base in subject_type.__mro__)


def register[T](subject_type: type[T], factory: "Callable[[T], Expect[T]]", /) -> None:
    """Teach ``expect()`` to return a custom subject for ``subject_type``.

        >>> register(Money, MoneyExpect)          # doctest: +SKIP
        >>> expect(Money(500)).is_positive()      # doctest: +SKIP

    Matching is by **exact type**, not by subclass: a subclass is a different
    type and may well want a different subject.

    Two things this deliberately will not do.

    It will not let you register a type twice, or register over a built-in; both
    raise ``ValueError`` naming the subject already in place. Configuration is
    write-once at import and never mutated per test -- the lesson FluentAssertions
    learned when global assertion state stopped being safe under a parallel
    runner. Registering over ``str`` would also put the runtime out of step with
    the static overloads, which promise a ``StringExpect``.

    And it cannot narrow statically. A checker reads the declared overloads, so
    ``expect(Money(500))`` is ``Expect[Money]`` to pyright however the runtime
    dispatches. Where that matters, reach for the explicit form instead::

        expect(amount, as_=MoneyExpect).is_positive()

    which is fully typed. The trade-off is real and there is no way around it in
    today's Python: reach for :func:`register` when the call sites should stay
    plain and the extra assertions need not be visible to a checker, and for
    ``as_=`` wherever they must be.
    """
    if subject_type in _REGISTERED:
        message = subject_type.__name__ + " is already registered"
        raise ValueError(message)
    claimed = subject_for(subject_type)
    if claimed is not None:
        promised = getattr(claimed, "__name__", "a built-in subject")
        message = (
            subject_type.__name__ + " already has a subject; registering over it would "
            "put the runtime out of step with the static overloads of expect(), which "
            "go on answering " + promised + ". Use "
            "expect(value, as_=YourExpect) where you need your own, or subclass "
            + promised
            + " and register a type that has no subject yet"
        )
        raise ValueError(message)
    _REGISTERED[subject_type] = factory


#: User-registered subjects, consulted right after the mock check. Written at
#: import time by :func:`register` and never mutated afterwards.
#:
#: Seeded with :data:`_CALLABLE_TYPES` rather than kept beside it, because two
#: dictionaries consulted in order are one dictionary: keeping them apart spends
#: two bound-method loads and two calls where one would do, and the first of them
#: is empty in every program that never calls ``register()``.
#:
#: The merge cannot change an answer, and the reason is already enforced rather
#: than asserted: :func:`register` refuses any type :func:`claimed_by` answers
#: for, and ``claimed_by(FunctionType)`` is ``CallableExpect`` through
#: :func:`_instances_are_callable`. So a user can never own an entry that
#: collides with the three seeded ones.
_REGISTERED: dict[type[Any], "Callable[[Any], Expect[Any]]"] = dict(_CALLABLE_TYPES)

#: A throwaway mapping, purely to name the types of its views: ``dict_keys`` and
#: its siblings have no name in ``builtins``, and ``expect(rows.keys())`` is an
#: ordinary assertion that should not have to walk the ``issubclass`` chain.
_VIEW_SOURCE: dict[Any, Any] = {}

#: Exact built-in types, resolved without touching the ``issubclass`` chain.
#: The values are the plain classes, never ``SequenceExpect[Any]`` and friends:
#: calling a subscripted generic alias goes through ``_GenericAlias.__call__``, an
#: order of magnitude dearer than calling the class itself and more than the whole
#: rest of the dispatch put together, on the hottest path in the library.
_EXACT_SUBJECTS: dict[type[Any], Callable[[Any], Expect[Any]]] = {
    bool: BoolExpect,
    str: StringExpect,
    int: NumericExpect,
    float: NumericExpect,
    dict: MappingExpect,
    list: SequenceExpect,
    tuple: SequenceExpect,
    type: TypeExpect,
    set: CollectionExpect,
    frozenset: CollectionExpect,
    type(_VIEW_SOURCE.keys()): CollectionExpect,
    type(_VIEW_SOURCE.values()): CollectionExpect,
    type(_VIEW_SOURCE.items()): CollectionExpect,
}


#: The subjects whose value types live in modules this one refuses to import,
#: grouped by module so a program that never mentioned dates pays one dict miss
#: for the whole family. Within a module the order is subclass before superclass
#: -- `datetime` before `date`, `Path` before `PurePath` -- because each really is
#: one, and first match wins. The overload block above is this table read aloud.
#:
#: Refusing the imports is not a micro-optimisation. `pathlib` pulls `fnmatch` and
#: therefore `re`, and importing this package must not import `re`: only the
#: assertions that genuinely need it may pay for it. `import fractions` does the
#: same. The subject modules themselves take their types under `TYPE_CHECKING` for
#: the same reason, so importing them eagerly here costs nothing.
_LAZY_SUBJECTS: "tuple[tuple[str, tuple[tuple[str, Callable[[Any], Expect[Any]]], ...]], ...]" = (
    ("enum", (("Enum", EnumExpect),)),
    (
        "datetime",
        (
            ("datetime", DateTimeExpect),
            ("date", DateExpect),
            ("time", TimeExpect),
            ("timedelta", TimeDeltaExpect),
        ),
    ),
    ("pathlib", (("Path", PathExpect), ("PurePath", PurePathExpect))),
    ("decimal", (("Decimal", OrderedExpect),)),
    ("fractions", (("Fraction", OrderedExpect),)),
)

#: Answers already worked out for the whole shape chain, keyed by the type asked
#: about. `expect(some_domain_object())` -- the value that reaches the end of the
#: chain, and a common one -- otherwise pays the entire `issubclass` chain plus a
#: `sys.modules` lookup for every lazy module, where this is one integer compare
#: and one dict lookup.
#:
#: **Why the answer cannot go stale**, which is two arguments, not one:
#:
#: * Most of the chain reads a fixed MRO. `type`, `str`, `int | float` and every
#:   name in :data:`_LAZY_SUBJECTS` are plain classes, so `issubclass` cannot
#:   change its mind about them after the type exists. A `None` recorded because a
#:   module was absent cannot become wrong either: to build a subclass of
#:   `pathlib.Path` you must first import `pathlib`, so a type that exists while the
#:   module is unloaded is not a subclass of anything in it.
#: * The rest -- `Mapping`, `Sequence`, `Collection`, and `Fraction`, which inherits
#:   `ABCMeta` from `numbers.Rational` -- accept virtual subclasses, so
#:   `Sequence.register(X)` and `Fraction.register(X)` really do change the answer
#:   after the fact. Every one of those calls bumps `abc.get_cache_token()`, which
#:   is what the token exists for and what `functools.singledispatch` guards on.
#:   The guard below reads it and discards everything when it moves, so a virtual
#:   registration made mid-run is seen.
#:
#: The token is what lets `Fraction` live in the table above rather than in a
#: special case asked afresh every time: the first argument alone would not cover
#: it, and the second one does.
_SHAPE_ANSWERS: "dict[type[Any], Callable[[Any], Expect[Any]] | None]" = {}

#: The ABC registry generation the answers above were worked out under. When it
#: moves, every remembered answer is discarded rather than reasoned about.
#:
#: A one-element list rather than a bare name so the guard mutates instead of
#: rebinding: a module-level `global` would make this the only reassigned constant
#: in the package, and pyright is right to object to that. `get_cache_token` is
#: typed `object` in typeshed -- it is an opaque generation marker, and `!=` is all
#: anyone is meant to do with it.
_SHAPE_TOKEN: list[object] = [get_cache_token()]

#: Cleared wholesale past this many entries, the way `re` bounds its own pattern
#: cache. The keys are type objects and holding them forever would pin every class
#: a suite generates on the fly; clearing costs one rebuild of a table that is
#: only ever a few entries deep in practice.
_MAX_SHAPE_ANSWERS = 512


def _lazy_module_subject(subject_type: type[Any], /) -> "Callable[[Any], Expect[Any]] | None":
    """The subject for a type from a module the library will not import, if any.

    Asked through ``sys.modules`` rather than by importing: a program that has never
    mentioned a ``Decimal`` cannot be holding one, and the same argument covers
    every entry in :data:`_LAZY_SUBJECTS`.
    """
    return _scan(_LAZY_SUBJECTS, subject_type)


def _scan(
    table: "tuple[tuple[str, tuple[tuple[str, Callable[[Any], Expect[Any]]], ...]], ...]",
    subject_type: type[Any],
    /,
) -> "Callable[[Any], Expect[Any]] | None":
    """Work an answer out from scratch, first match wins."""
    for module_name, candidates in table:
        module = sys.modules.get(module_name)
        if module is None:
            continue
        for type_name, factory in candidates:
            if issubclass(subject_type, getattr(module, type_name)):
                return factory
    return None
