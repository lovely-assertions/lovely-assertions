"""Asymmetric matchers: a placeholder that stands in for a value in an expectation.

The point of use is a value you cannot name and can describe::

    expect(row).is_equal_to({"id": any_instance_of(int), "name": "ada"})
    expect(payload).is_equal_to({"token": string_matching(r"^ey"), "ttl": close_to(60)})
    expect(sender).was_called_with(any_instance_of(Request), retries=one_of(0, 1))

and the thing it replaces is three assertions that have lost the shape of the
thing under test::

    expect(row["name"]).is_equal_to("ada")
    expect(row["id"]).is_instance_of(int)
    expect(row).has_length(2)

**The objection this trick usually attracts, and why it misses in Python.**
Jest's ``expect.any(Number)`` is type-erased: TypeScript sees ``any``, the object
slot it is dropped into stops being checked, and a typo in the *neighbouring* key
goes through. That is a true account of the trick in JavaScript and a false one
in Python, because a Python matcher can lie about its type in a way the checker
still enforces:

.. code-block:: python

    def any_instance_of[T](kind: type[T]) -> T: ...

    assert_type(any_instance_of(int), int)              # passes
    rows: dict[str, int] = {"a": any_instance_of(int)}  # accepted
    bad: list[int] = [any_instance_of(str)]             # rejected, as it must be

A function *declared* to return ``T`` is statically indistinguishable from a
``T``, so every slot the checker was already policing stays policed -- while at
runtime the object is a placeholder whose ``__eq__`` answers loosely.
``dirty-equals``, the closest thing Python has to this today, cannot do it: its
matchers are their own types, so ``list[int]`` has to be widened to
``list[int | IsInt]`` and the element type stops meaning anything.

**Where the checking actually bites, stated before anybody is disappointed by
it.** A matcher is refused where the *slot* it lands in has a declared type: an
annotated variable, a container element, an assertion parameter that carries the
element type -- ``expect(names).contains(any_instance_of(int))`` on a
``list[str]`` is an error, and so is ``rows: dict[str, int] = {"a":
any_instance_of(str)}``. It is **not** refused by ``is_equal_to``, whose
parameter is ``object`` on purpose so that any two values can be compared: an
unannotated ``{"id": any_instance_of(str)}`` written straight into that call has
no slot to be checked against, and neither checker will say anything. The
protection is real and it is the caller's annotations that switch it on, which is
one more reason to declare the expectation rather than inline it.

**No walker, at any depth.** Nothing in this library knows matchers exist. A
matcher works because Python's comparison protocol reaches it on its own:
``{"id": 7} == {"id": <any int>}`` compares the two values, ``int.__eq__``
answers ``NotImplemented``, and the reflected call lands on the matcher. That is
true at every depth of every structure ``==`` descends, which is why
``is_equal_to``, ``is_equivalent_to``, ``contains``, ``was_called_with`` and the
difference engine all support matchers without a line written for them.

**The lie is deliberate, and here is what it costs.** ``any_instance_of(str)`` is
annotated ``str`` and is not a ``str``. A reader who follows the annotation and
calls ``.upper()`` on one gets ``AttributeError``, and no checker will have
warned them. The trade is narrow and worth stating exactly:

* what it buys -- a placeholder that survives an *invariant* container slot
  (``dict[str, int]``, ``list[int]``), which no honestly-typed value can do,
  and which is the only reason to reach for a matcher at all;
* what it costs -- the annotation of a matcher is not the truth about the
  object, and a matcher used as anything other than an expectation misbehaves at
  runtime with no static warning.

So the rule is one sentence: **a matcher goes in an expectation and nowhere
else.** It is never the subject, never stored as application data, never
operated on. ``expect(any_instance_of(int))`` is refused with a ``TypeError``
that says so -- the refusal is registered through :func:`~lovely_assertions.register`,
so the dispatch pays nothing for it on any other value (see
:func:`_refuse_matcher_subject`).

**Where a matcher does not reach.** ``in`` against a ``set``, a ``frozenset`` or
a mapping's keys is a *hash* lookup, not a scan: Python computes the hash first
and only compares against the values in that bucket, so
``expect({1, 2}).contains(any_instance_of(int))`` finds nothing. A matcher
therefore cannot be hashed into agreement with the values it matches -- no object
can -- and the assertion to write there is one over the items rather than one
over containment. Sequences, mappings' *values* and call arguments are all
scans, so they work.

**Rendering.** Every matcher's ``repr`` is the phrase it stands for --
``<any int>``, ``<string matching '^ey'>`` -- because it is the text a reader
meets in a failure message ``Expected row to equal {'id': <any int>}, but was
{'id': 'oops'}``. That works through ``repr`` alone, since every rendering site
in this library falls back to it. :class:`_MatcherFormatter` is registered on top
of that for one narrower reason, given at the class.
"""

from collections.abc import Collection, Mapping, Sequence
from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING, Any, Final, Never, TypeIs, cast, override

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value, register_formatter

# The tolerance machinery behind `NumericExpect.is_close_to`, borrowed rather
# than restated. `close_to` has to mean exactly what that assertion means -- a
# library that answers one question two ways is worse than one that answers it
# badly (`_text`'s docstring makes the same argument about wildcards) -- and
# these three are where the answer lives. They are private to `_numeric`, where
# `_ordered.is_nan` and `_ordered.rendered` are the same kind of cross-module
# helper with the underscore dropped.
from lovely_assertions._numeric import (
    effective_tolerance,
    reject_unusable_tolerance,
    within,
)
from lovely_assertions._ordered import rendered
from lovely_assertions._subjects import register

if TYPE_CHECKING:
    import re
    from collections.abc import Callable

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = [
    "any_instance_of",
    "anything",
    "close_to",
    "containing",
    "is_matcher",
    "matching",
    "one_of",
    "string_containing",
    "string_matching",
]

#: Operands a ``repr`` shows before it truncates. The same ten as
#: ``_formatters._MAX_ITEMS`` and ``_formatting._DEFAULT_MAX_ITEMS``, deliberately:
#: a matcher's rendering sits *inside* a message those two also bound, and two
#: different caps on one line would only make the reader wonder which was lying.
#:
#: It is a constant here rather than a ``current_formatting()`` read, unlike every
#: other bound in a message. ``__repr__`` is not confined to the failure path --
#: anybody may call it, at any time, from a debugger -- and a ``ContextVar`` read
#: is precisely what this library keeps out of anything a passing run can reach.
_MAX_SHOWN: Final = 10

#: Refused so that ``anything()`` -- which hands back one shared object -- cannot
#: be re-pointed by whichever test ran first. Same reasoning, and the same
#: wording, as ``_occurrence._IMMUTABLE``.
_IMMUTABLE: Final = "matchers are immutable values; cannot change "

#: A matcher that stands in for nothing can never match, so an assertion carrying
#: one could never pass. Same rule as the variadic assertions
#: (``_core._NEEDS_VALUES``) and the occurrence factories: a call that could
#: never succeed is a bug where it was written, not a finding about a subject.
_NEEDS_VALUES: Final = "one_of() needs at least one value; a choice between nothing matches nothing"

#: Its mirror. An empty spec is satisfied by every container there is, so the
#: assertion holding it asserts nothing -- the worst thing an assertion can be.
_NEEDS_A_SPEC: Final = (
    "containing() needs at least one entry; an empty one matches every container, "
    "so it asserts nothing"
)

#: ``containing`` is the only matcher that takes a structure rather than a value,
#: and the only one that can be handed something it cannot read.
_NOT_A_CONTAINER: Final = (
    "containing() takes a mapping, a sequence or a set to look for inside another one, not "
)

#: ``isinstance`` refuses anything that is not a class, and it refuses it with a
#: ``TypeError`` from inside a comparison -- a long way from the call that was
#: actually wrong.
_NOT_A_TYPE: Final = "any_instance_of() takes a class, not "

#: "a callable", not "a callable of one argument", because the second is a
#: promise this module does not keep: nothing checks the arity, and a predicate
#: of the wrong shape becomes a matcher that never matches rather than an error
#: at the call that was wrong. The `matching` docstring says so; a message that
#: implied otherwise would be the one place a reader looked for the guarantee.
_NOT_A_PREDICATE: Final = "matching() takes a callable, not "

#: A bytes pattern compiles perfectly well and then matches nothing, because
#: :meth:`_StringMatching.matches` asks for a ``str`` -- and it *has* to, since a
#: ``bytes`` pattern cannot be applied to one. The result is a matcher that can
#: never match, which is the same bug ``one_of()`` and ``containing({})`` are
#: refused for and is refused here for the same reason.
_NOT_A_TEXT_PATTERN: Final = (
    "string_matching() takes a str pattern, or one compiled from a str; a bytes pattern "
    "matches no string, so the assertion holding it could never pass. Pattern is "
)

#: Text that is a container in Python and never the container ``containing()``
#: means. ``containing("ab")`` would otherwise quietly mean "a sequence holding
#: the characters 'a' and 'b'", which nobody has ever wanted;
#: :func:`string_containing` is what that caller meant.
_TEXTUAL: Final = (str, bytes, bytearray)

#: The three membership tests below, hoisted out of the calls that make them.
#:
#: ``isinstance(value, int | float)`` builds the union object afresh on every
#: call -- an allocation whose size grows with the interpreter version -- where
#: the same test against a name bound once allocates nothing at all.
#: :meth:`_CloseTo.matches` runs inside ``==`` on an assertion that is about to
#: pass, and a passing assertion is meant to allocate nothing, so the union is
#: built once, here.
#:
#: Written as tuples rather than as ``Final`` unions for the reason :data:`_TEXTUAL`
#: already is one: both checkers narrow through a tuple of types, and a tuple has
#: no runtime construction left to hoist.
_NUMERIC: Final = (int, float)
_MAPPING_OR_TEXT: Final = (Mapping, str, bytes, bytearray)
_SCANNABLE: Final = (Sequence, AbstractSet)


class _Matcher:
    """Everything the matchers share -- which is not the match itself.

    :meth:`matches` lives on each subclass, because the match *is* the subclass.
    What is shared is the equality protocol, the hashing, the immutability and
    the refusal to be a subject.

    **``__eq__`` is total.** It is called by anything, from either side, against
    any value -- a ``dict`` comparison, a ``list.__contains__`` scan, a mock's
    call record, a difference engine rendering a failed assertion. It therefore
    never raises on account of the value it is handed: a match that blows up in
    somebody's ``__eq__`` or predicate is read as "no match", because the
    alternative is turning somebody's failing assertion into an error inside the
    assertion library while it is in the middle of explaining itself.
    (``_formatters._apply`` and ``_diff.describe_difference`` take the same line
    for the same reason.) The one thing it does let out is a subclass that never
    overrode :meth:`matches`, which is this library's own contract broken rather
    than a value misbehaving, and is not what the promise is here to absorb.

    **Two matchers do not match each other.** Comparing a matcher against another
    matcher of a *different* kind answers ``NotImplemented``, which hands the
    question to the other one, which declines it too -- so Python falls back to
    identity. The alternative is worse than it looks: if ``anything()`` matched
    ``any_instance_of(int)`` the way it matches everything else, then
    ``anything() == any_int`` would be ``True`` and ``any_int == anything()``
    would be ``False``, and ``==`` would depend on which side of the operator each
    was written. Two matchers of the *same* kind compare by what they were built
    from, exactly as ``_occurrence._Constraint`` does, so an expectation can be
    compared with another expectation.

    **Hashing is coarse on purpose.** ``__hash__`` answers from the class alone.
    Equal matchers hash equal, which is the contract; distinct matchers of one
    kind collide, which is legal and costs nothing because nobody keeps a
    thousand matchers in a set. The alternative -- hashing what the matcher was
    built from -- raises on an unhashable spec, and a ``__hash__`` that raises
    would make a matcher unusable as a dict key at all. What no hash can buy is
    hash-based *containment*: see the module docstring.

    **Every slot is spelled ``_like_this_``, and that is not a style choice.**
    ``_equivalence._classify`` reads an object's ``__slots__`` to decide whether
    it is a *record* -- a thing with fields, to be compared field by field -- or a
    *leaf*, and it drops the names its ``_is_reserved`` helper calls machinery:
    the ones that both start and end with an underscore. A matcher holding a
    plainly-named ``_kind`` is therefore a record, and ``is_equivalent_to``
    reports a failure against one as ``types differ: str instead of _AnyInstance``
    -- a private class name, and no account of what was expected. Spelled
    ``_kind_``, the matcher is a leaf, and the same failure reads
    ``'oops' instead of <any int>``.

    It really is machinery rather than state: a matcher has no fields anybody
    would want compared, and comparing two of them field by field is precisely
    the reading :meth:`__eq__` exists to override. The tidier fix lives one module
    over -- ``_equivalence._is_opaque`` naming matchers outright, the way it
    already names classes and enum members -- and this file cannot make it, so the
    naming convention here is load-bearing rather than decorative.
    """

    __slots__ = ()

    def matches(self, value: object, /) -> bool:
        """Whether this matcher stands in for ``value``. Every matcher overrides it.

        One that does not override it raises ``NotImplementedError``, through
        ``==`` as well as from a direct call: an incomplete matcher that quietly
        stood for nothing would pass every negative assertion it was written into,
        for ever.
        """
        raise NotImplementedError

    def _spec_key(self) -> tuple[object, ...]:
        """What this matcher was built from, for comparing two of the same kind."""
        return ()

    @override
    def __eq__(self, other: object) -> bool:
        if isinstance(other, _Matcher):
            if type(other) is not type(self):
                return NotImplemented
            try:
                same = self._spec_key() == other._spec_key()
            except Exception:
                return False
            return bool(same)
        try:
            verdict = self.matches(other)
        except NotImplementedError:
            # Let this out only when it came from the base method above -- a
            # subclass that never wrote its own. Reading that as "no match" buys a
            # matcher standing for nothing wherever it is placed, which in a
            # negative assertion is a test that can never fail; the totality this
            # class promises is to *somebody else's* code, and a half-written
            # subclass of it is not that. A `NotImplementedError` out of a
            # caller's predicate or a value's `__eq__` still reads as no match,
            # because that is exactly the code the promise was made to.
            if type(self).matches is _Matcher.matches:
                raise
            return False
        except Exception:
            return False
        return verdict

    @override
    def __hash__(self) -> int:
        return hash(type(self))

    @override
    def __setattr__(self, name: str, _value: object, /) -> Never:
        raise AttributeError(_IMMUTABLE + type(self).__name__ + "." + name)

    @override
    def __delattr__(self, name: str, /) -> Never:
        raise AttributeError(_IMMUTABLE + type(self).__name__ + "." + name)


def is_matcher(value: object, /) -> bool:
    """Whether ``value`` is one of this library's matchers.

        >>> is_matcher(any_instance_of(int))
        True
        >>> is_matcher(7)
        False

    Exported because the answer is otherwise unavailable: a matcher's whole
    design is to be indistinguishable from the type it stands in for, so code
    that has to tell the difference -- a custom assertion deciding whether to
    render an operand or assert on it -- cannot get there with ``isinstance``
    against a public name.
    """
    return isinstance(value, _Matcher)


def _refuse_matcher_subject(value: object, /) -> Never:
    """Refuse ``expect(<a matcher>)``, and say why.

    Wired through :func:`~lovely_assertions.register` at the bottom of this
    module rather than as a branch in the dispatch chain, which is the whole
    reason it is worth doing: ``_subjects._dispatch`` already looks the subject's
    type up in the registry on its way past, so this check costs every *other*
    value in every other test exactly nothing. A branch at the head of the chain
    would have cost an ``isinstance`` on the hottest path in the library to catch
    a mistake that is made at most once per reader.

    The static side cannot help here and says so honestly:
    ``expect(any_instance_of(int))`` type-checks as ``NumericExpect``, because the
    matcher is *declared* to be an ``int``. That is the lie doing exactly what it
    was built to do, in the one place where it has nothing to offer -- so the
    runtime has to be the one to speak up.
    """
    raise TypeError(
        f"{value!r} is a matcher, so it belongs in an expectation rather than under "
        f"expect(). Its declared type is a deliberate fiction -- the object is a "
        f"placeholder, not a value of the type it claims -- so an assertion about it "
        f"would be an assertion about the placeholder. Put it in the expected value "
        f"instead: expect(row).is_equal_to({{'id': any_instance_of(int)}})."
    )


class _MatcherFormatter:
    """Renders a matcher through its own ``repr``, ahead of the registry.

    This looks redundant and nearly is: ``format_value`` already falls back to
    ``repr``, so every message in this library renders ``<any int>`` with nothing
    registered at all. What the registration buys is *priority*. The global
    registry is consulted in registration order and the first claim wins, so a
    user formatter written broadly -- ``ObjectFormatter(SomeBase, "id")`` over a
    hierarchy wider than its author meant -- can claim a matcher and render it as
    something it is not. Registering here, at import, puts this in front of
    anything a user's ``conftest`` can add later.

    A *scoped* formatter still overrides it, and that is right: scoping is how a
    block asks for a different rendering, and this is not a rendering worth
    refusing to give up.

    The one cost, stated because it is paid by suites that never touch a matcher:
    registering anything at all means ``format_value`` takes its general path
    rather than its "nothing is registered" shortcut, and this class is registered
    at import, so that shortcut is never taken in a program that imports the
    library. It costs one ``can_handle`` -- an ``isinstance`` -- per rendered
    value, and nothing beyond that.

    That is failure-path work only -- nothing in this class runs until an
    assertion has already failed -- so it is bought at the one moment the library
    is allowed to spend, and it buys a message that cannot be taken over by
    somebody else's formatter.
    """

    __slots__ = ()

    def can_handle(self, value: object, /) -> bool:
        return isinstance(value, _Matcher)

    def format(self, value: object, /) -> str:
        return repr(value)


# ---------------------------------------------------------------------------
# The matchers
# ---------------------------------------------------------------------------
class _AnyInstance(_Matcher):
    """``isinstance(value, kind)``."""

    __slots__ = ("_kind_",)

    _kind_: type[Any]

    def __init__(self, kind: type[Any], /) -> None:
        # Through `object`, because this class's own `__setattr__` refuses.
        object.__setattr__(self, "_kind_", kind)

    @override
    def matches(self, value: object, /) -> bool:
        return isinstance(value, self._kind_)

    @override
    def _spec_key(self) -> tuple[object, ...]:
        return (self._kind_,)

    @override
    def __repr__(self) -> str:
        return f"<any {_type_name(self._kind_)}>"


class _Anything(_Matcher):
    """Everything, ``None`` included."""

    __slots__ = ()

    @override
    def matches(self, value: object, /) -> bool:
        return True

    @override
    def __repr__(self) -> str:
        return "<anything>"


class _StringMatching(_Matcher):
    """A string in which a regular expression finds a match."""

    __slots__ = ("_pattern_",)

    _pattern_: "re.Pattern[str]"

    def __init__(self, pattern: "re.Pattern[str]", /) -> None:
        object.__setattr__(self, "_pattern_", pattern)

    @override
    def matches(self, value: object, /) -> bool:
        return isinstance(value, str) and self._pattern_.search(value) is not None

    @override
    def _spec_key(self) -> tuple[object, ...]:
        return (self._pattern_.pattern, self._pattern_.flags)

    @override
    def __repr__(self) -> str:
        return f"<string matching {format_value(self._pattern_.pattern)}>"


class _StringContaining(_Matcher):
    """A string holding a fragment."""

    __slots__ = ("_fragment_",)

    _fragment_: str

    def __init__(self, fragment: str, /) -> None:
        object.__setattr__(self, "_fragment_", fragment)

    @override
    def matches(self, value: object, /) -> bool:
        return isinstance(value, str) and self._fragment_ in value

    @override
    def _spec_key(self) -> tuple[object, ...]:
        return (self._fragment_,)

    @override
    def __repr__(self) -> str:
        return f"<string containing {format_value(self._fragment_)}>"


class _CloseTo(_Matcher):
    """A number within a tolerance of another.

    The tolerance is resolved once, at construction, into the single absolute
    band ``NumericExpect.is_close_to`` would have applied -- through that
    assertion's own helpers, so the two cannot answer the same question
    differently. A comparison then costs one ``isinstance`` and one subtraction.
    """

    __slots__ = ("_band_", "_rel_", "_tol_", "_value_")

    _value_: int | float
    _band_: int | float
    _tol_: int | float | None
    _rel_: int | float | None

    def __init__(
        self,
        value: int | float,
        band: int | float,
        tol: int | float | None,
        rel: int | float | None,
        /,
    ) -> None:
        object.__setattr__(self, "_value_", value)
        object.__setattr__(self, "_band_", band)
        object.__setattr__(self, "_tol_", tol)
        object.__setattr__(self, "_rel_", rel)

    @override
    def matches(self, value: object, /) -> bool:
        # `bool` is an `int` and passes: `True` really is within a whisker of 1.0,
        # and refusing it would mean this matcher disagreed with `==` about a
        # value `is_close_to` accepts. A `Decimal` is neither, so it does not
        # match -- the same boundary `NumericExpect.is_close_to` documents.
        if not isinstance(value, _NUMERIC):
            return False
        return within(value, self._value_, self._band_)

    @override
    def _spec_key(self) -> tuple[object, ...]:
        # The tolerances as the caller wrote them rather than the band they
        # resolved to, which loses nothing -- the band is a function of these
        # three -- and keeps `==` from contradicting the `repr` below. Around 60,
        # `tol=1` and `rel=1/60` admit exactly the same numbers and print as two
        # different phrases, and the phrase is what a reader meets in a failure
        # message, so the two are not one expectation. `_occurrence._Constraint`
        # draws the line in the same place, between `at_least(3)` and
        # `more_than(2)`.
        return (self._value_, self._tol_, self._rel_)

    @override
    def __repr__(self) -> str:
        return f"<close to {rendered(self._value_)}{_tolerance_phrase(self._tol_, self._rel_)}>"


class _OneOf(_Matcher):
    """Any one of a fixed set of values."""

    __slots__ = ("_values_",)

    _values_: tuple[object, ...]

    def __init__(self, values: tuple[object, ...], /) -> None:
        object.__setattr__(self, "_values_", values)

    @override
    def matches(self, value: object, /) -> bool:
        for candidate in self._values_:  # noqa: SIM110  (a generator expression would allocate)
            if _equal(candidate, value):
                return True
        return False

    @override
    def _spec_key(self) -> tuple[object, ...]:
        return self._values_

    @override
    def __repr__(self) -> str:
        return f"<one of {_operands(self._values_)}>"


class _MappingSubset(_Matcher):
    """A mapping holding at least these entries."""

    __slots__ = ("_spec_",)

    _spec_: "Mapping[Any, Any]"

    def __init__(self, spec: "Mapping[Any, Any]", /) -> None:
        object.__setattr__(self, "_spec_", spec)

    @override
    def matches(self, value: object, /) -> bool:
        if not _is_mapping(value):
            return False
        spec = self._spec_
        # Iterating the keys rather than `.items()`: a view is an allocation, and
        # this runs inside a comparison that a *passing* assertion makes.
        for key in spec:
            if key not in value:
                return False
            if not _equal(spec[key], value[key]):
                return False
        return True

    @override
    def _spec_key(self) -> tuple[object, ...]:
        return (self._spec_,)

    @override
    def __repr__(self) -> str:
        return f"<containing {format_value(self._spec_)}>"


class _ItemsPresent(_Matcher):
    """A collection holding at least these items, in any order."""

    __slots__ = ("_items_",)

    _items_: tuple[object, ...]

    def __init__(self, items: tuple[object, ...], /) -> None:
        object.__setattr__(self, "_items_", items)

    @override
    def matches(self, value: object, /) -> bool:
        if not _is_scannable(value):
            return False
        for wanted in self._items_:  # noqa: SIM110  (a generator expression would allocate)
            if not _found_in(wanted, value):
                return False
        return True

    @override
    def _spec_key(self) -> tuple[object, ...]:
        return self._items_

    @override
    def __repr__(self) -> str:
        return f"<containing {_operands(self._items_)}>"


class _Matching(_Matcher):
    """Whatever a predicate says yes to."""

    __slots__ = ("_predicate_",)

    _predicate_: "Callable[[Any], bool]"

    def __init__(self, predicate: "Callable[[Any], bool]", /) -> None:
        object.__setattr__(self, "_predicate_", predicate)

    @override
    def matches(self, value: object, /) -> bool:
        return bool(self._predicate_(value))

    @override
    def _spec_key(self) -> tuple[object, ...]:
        return (self._predicate_,)

    @override
    def __repr__(self) -> str:
        return f"<matching {_predicate_name(self._predicate_)}>"


# ---------------------------------------------------------------------------
# Shared machinery
# ---------------------------------------------------------------------------
def _is_mapping(value: object, /) -> "TypeIs[Mapping[Any, Any]]":
    """Whether a value is a mapping, in a shape a type checker can carry forward.

    A bare ``isinstance`` narrows to ``Mapping[Unknown, Unknown]`` under pyright's
    strict mode, and every key read out of it is then an unknown handed to
    something expecting a value. A ``TypeIs`` costs the same one call the ``cast``
    that would otherwise be needed costs, and says what it is doing.
    ``_equivalence._is_mapping`` is the same helper for the same reason.
    """
    return isinstance(value, Mapping)


def _is_scannable(value: object, /) -> "TypeIs[Collection[Any]]":
    """Whether a value is a collection ``containing()`` will look through.

    A **mapping** is excluded because iterating one yields its keys, so
    ``containing([1])`` against a dictionary would silently become a claim about
    that dictionary's keys -- a wrong pass, and the kind that reads as correct.
    **Text** is excluded for the reason :data:`_TEXTUAL` gives. Anything left with
    a length, an iterator and a membership test is scanned.
    """
    if isinstance(value, _MAPPING_OR_TEXT):
        return False
    return isinstance(value, Collection)


def _equal(expected: object, actual: object, /) -> bool:
    """Python's own containment rule: identity first, then equality.

    Identity first is what lets a NaN be found where it actually sits, and it is
    the rule ``list.__contains__`` and ``_diff._equal`` already follow, so a
    matcher's idea of "holds this" is the language's.

    The *expected* side is compared on the left, which is the one place this
    module departs from what ``x in seq`` does. It has to: the expectation is the
    side a matcher is allowed to be on, and a value class that answers ``False``
    rather than ``NotImplemented`` to an unfamiliar operand -- an ordinary thing
    to write, and no error -- would otherwise shut a nested matcher out of the
    comparison entirely.
    """
    return expected is actual or bool(expected == actual)


def _found_in(wanted: object, container: "Collection[object]", /) -> bool:
    """Whether anything in ``container`` equals ``wanted``.

    A scan rather than ``wanted in container``, because ``in`` is a hash lookup
    on a ``set`` or a mapping and a nested matcher cannot be hashed into
    agreement with what it matches (see the module docstring). Quadratic in the
    two sizes, which is the price of the guarantee; the alternative is a matcher
    that works in a list and silently does not in a set.
    """
    for item in container:  # noqa: SIM110  (a generator expression would allocate)
        if _equal(wanted, item):
            return True
    return False


def _require_class(kind: object, /) -> None:
    """Refuse something ``isinstance`` could not use.

    Takes ``object`` rather than ``type[T]`` so the check means something: against
    the declared type it would be a tautology, and a factory call is exactly where
    a caller's declaration might be wrong (``_formatters._check_class`` takes the
    same line, one registry over). Reported here rather than left to
    ``isinstance`` inside a comparison, which would raise a ``TypeError`` from a
    ``__eq__`` that is required never to raise -- and would therefore be swallowed
    and read as "no match", silently, for the life of the matcher.
    """
    if isinstance(kind, type):
        return
    raise TypeError(_NOT_A_TYPE + type(kind).__name__)


def _type_name(kind: type[Any], /) -> str:
    """A class's name for a ``repr``, and something legible when it has none.

    ``__name__`` goes through the metaclass, and a class with a hostile
    ``__getattribute__`` makes even that raise. A ``repr`` that raises during a
    failure message costs the reader the message, so this cannot.
    """
    # Widened on purpose: `type.__name__` is declared `str`, so against that
    # declaration the check below reads as redundant -- and a metaclass is free to
    # hand back anything at all, which is the case this exists for
    # (`_formatters._apply` widens for the same reason).
    try:
        name = cast("object", kind.__name__)
    except Exception:
        return "<unnameable type>"
    return name if isinstance(name, str) else "<unnameable type>"


def _predicate_name(predicate: object, /) -> str:
    """Name a predicate for a ``repr``.

    A lambda's ``__name__`` is ``<lambda>``, which tells the reader nothing they
    could act on, so it reads as "a predicate" instead -- the same choice
    ``_core.describe_predicate`` makes, spelled again here rather than imported
    because that one is failure-path machinery and a ``repr`` is not.
    """
    name = getattr(predicate, "__name__", None)
    if isinstance(name, str) and name != "<lambda>":
        return name
    return "a predicate"


def _operands(values: tuple[object, ...], /) -> str:
    """Values inside a matcher's ``repr``, bounded the way every other list is.

    Rendered through ``format_value``, so a domain type with a registered
    formatter reads as itself inside a matcher exactly as it does outside one.
    """
    shown = [format_value(value) for value in values[:_MAX_SHOWN]]
    text = ", ".join(shown)
    left_out = len(values) - len(shown)
    if left_out:
        return text + ", ... (" + str(left_out) + " more)"
    return text


def _tolerance_phrase(tol: "int | float | None", rel: "int | float | None", /) -> str:
    """The tolerance half of ``close_to``'s ``repr``, or nothing when it defaulted.

    A default tolerance is ``pytest.approx``'s and is not worth a reader's
    attention; one the caller typed is the whole content of the assertion, so it
    is shown in the form they wrote it rather than as the single band the two
    resolve to. ``rendered`` keeps the digits the same as the ones the numeric
    subject prints.
    """
    if tol is None and rel is None:
        return ""
    if rel is None:
        return " ± " + rendered(tol)
    if tol is None:
        return " ± " + rendered(rel) + " relative"
    return " ± " + rendered(tol) + " or " + rendered(rel) + " relative"


# ---------------------------------------------------------------------------
# The factories -- and the lie lives in their return annotations
# ---------------------------------------------------------------------------
def any_instance_of[T](kind: type[T], /) -> T:
    """A placeholder for any instance of ``kind``.

        >>> expect({"id": 7}).is_equal_to({"id": any_instance_of(int)})
        MappingExpect({'id': 7})

    Declared to return ``T``, which is the trick and is not the truth: what comes
    back is a matcher, and the module docstring says plainly what that costs.

    Matching is ``isinstance``, with everything that implies -- a ``bool``
    matches ``any_instance_of(int)`` because a ``bool`` *is* an ``int``, and a
    subclass matches its base. Where the exact type is the claim,
    ``expect(value).is_exactly_instance_of(kind)`` is the assertion that makes it.

    Raises ``TypeError`` for something that is not a class, rather than letting
    ``isinstance`` raise it later from inside a comparison, a long way from the
    call that was wrong.
    """
    _require_class(kind)
    return cast("T", _AnyInstance(kind))


#: One shared instance. A matcher is immutable and this one carries no state at
#: all, so a new object per call would be an allocation that buys nothing.
_ANYTHING: Final = _Anything()


def anything() -> Any:  # noqa: ANN401  (the point is a placeholder that fits any slot)
    """A placeholder for any value at all, ``None`` included.

        >>> expect({"at": 1}).is_equal_to({"at": anything()})
        MappingExpect({'at': 1})

    ``Any``, because there is no narrower honest answer: this one really does go
    anywhere. It is the matcher to use for a field whose value is genuinely not
    the point -- a timestamp, a generated id -- and the one to reach for last,
    since ``any_instance_of`` says more and keeps the slot checked.
    """
    return _ANYTHING


def string_matching(pattern: "str | re.Pattern[str]", /) -> str:
    """A placeholder for any string a regular expression finds a match in.

        >>> expect({"t": "ey.J"}).is_equal_to({"t": string_matching(r"^ey")})
        MappingExpect({'t': 'ey.J'})

    A **search**, not a full match, mirroring ``StringExpect.matches`` and
    FluentAssertions' ``MatchRegex``: anchor the pattern yourself when the whole
    string is meant. An already-compiled pattern keeps its flags.

    The pattern is compiled here, once, rather than at each comparison -- which
    is also where this module's only ``import re`` lives, so importing this
    package does not import the regex engine and a suite that never writes a
    regex matcher never pays for it.

    A **bytes** pattern raises ``TypeError``. It compiles, and then matches
    nothing at all -- a matcher that can never match, which is what ``one_of()``
    and ``containing({})`` are refused for, and which is worse than a wrong
    answer: in a negative assertion it is a test that can never fail.
    """
    import re  # noqa: PLC0415  (kept off import time; only regex matchers need it)

    compiled = re.compile(pattern)
    # Widened past the declaration on purpose, the way `_type_name` is: against
    # the declared `str | re.Pattern[str]` this test reads as redundant, and it is
    # exactly the caller whose declaration was wrong that it exists to catch.
    written = cast("object", compiled.pattern)
    if not isinstance(written, str):
        raise TypeError(_NOT_A_TEXT_PATTERN + type(written).__name__)
    return cast("str", _StringMatching(compiled))


def string_containing(fragment: str, /) -> str:
    """A placeholder for any string holding ``fragment``.

        >>> expect({"m": "a b c"}).is_equal_to({"m": string_containing("b")})
        MappingExpect({'m': 'a b c'})

    The plain-substring half of :func:`string_matching`, worth its own name for
    the reason ``contains`` is worth having beside ``matches``: the commonest
    thing anyone wants to say about a string they only partly know should not
    have to be spelled as a regular expression, where every ``.`` and ``(`` in
    the fragment would then mean something else.
    """
    return cast("str", _StringContaining(fragment))


def close_to(
    value: int | float, /, *, tol: int | float | None = None, rel: int | float | None = None
) -> float:
    """A placeholder for any number within a tolerance of ``value``.

        >>> expect({"ttl": 59.7}).is_equal_to({"ttl": close_to(60, tol=1)})
        MappingExpect({'ttl': 59.7})

    ``tol`` is an absolute distance and ``rel`` a fraction of ``value``'s
    magnitude, and the four ways of calling this are the four
    ``NumericExpect.is_close_to`` documents -- the same helpers decide it, so the
    matcher and the assertion cannot drift apart on a NaN, an infinity, or an
    integer no float can hold. Neither tolerance means ``pytest.approx(x)``: one
    part in a million, floored near zero.

    Declared ``float`` rather than ``int | float``. The two are one slot in
    practice, because a ``float`` annotation accepts an ``int`` under the numeric
    tower every checker implements, and returning the union would fail in the
    direction that matters: ``dict[str, float]`` would refuse it.

    A negative or NaN tolerance raises ``ValueError``, exactly as it does on the
    assertion. A NaN **value** is refused here as well, and that one *is* a
    departure: ``expect(x).is_close_to(nan)`` is allowed to run and to fail, which
    is a true finding about ``x``. A matcher has no subject to make a finding
    about -- it would simply never match, anywhere it was placed, and report the
    mismatch as though the value were at fault. That is a bug in the test, and a
    bug in the test is raised where it was written rather than reported as a
    failure somewhere else.
    """
    reject_unusable_tolerance(tol, "tolerance")
    reject_unusable_tolerance(rel, "relative tolerance")
    if value != value:  # noqa: PLR0124  (that is what "not a number" means)
        raise ValueError("close_to(nan) matches nothing, itself included")
    band = effective_tolerance(value, tol, rel)
    return cast("float", _CloseTo(value, band, tol, rel))


def one_of[T](*values: T) -> T:
    """A placeholder for any one of ``values``.

        >>> expect({"n": 1}).is_equal_to({"n": one_of(0, 1)})
        MappingExpect({'n': 1})

    Equality against each in turn, identity first, so a NaN among the values is
    found where it sits. Nested matchers work: ``one_of(None, any_instance_of(int))``
    is how "an int, or nothing" is spelled, and it is the shape that makes this
    matcher worth having next to :func:`any_instance_of`.

    ``one_of()`` raises ``ValueError``. A choice between nothing matches nothing,
    so the assertion carrying it could never pass -- the same rule the variadic
    assertions keep, and for the same reason: it is a bug where it was written.
    """
    if not values:
        raise ValueError(_NEEDS_VALUES)
    return cast("T", _OneOf(values))


def containing[T](spec: T, /) -> T:
    """A placeholder for a container holding at least what ``spec`` holds.

        >>> expect({"tags": ["a", "b"]}).is_equal_to({"tags": containing(["a"])})
        MappingExpect({'tags': ['a', 'b']})

    A **mapping** spec asks for those keys, with matching values, and says
    nothing about any other key -- Jest's ``objectContaining``. A **sequence or
    set** spec asks for those items, in any order and at any position, and says
    nothing about the rest -- Jest's ``arrayContaining``. Both compare their
    entries with ``==``, so matchers nest to any depth:
    ``containing({"user": containing({"id": any_instance_of(int)})})``.

    The signature is ``[T](spec: T) -> T`` rather than an overload per shape, and
    that is the load-bearing decision here. Declared ``Mapping[K, V]`` this would
    hand back a ``Mapping`` where the slot wants a ``dict`` and be rejected by
    both checkers; passed through, ``containing({"a": 1})`` is a ``dict[str, int]``
    to the checker and drops into a ``dict[str, int]`` slot -- which is the entire
    point. The cost is that the annotation accepts ``containing(3)``, which the
    runtime refuses with a ``TypeError``.

    Text is refused rather than read as a sequence of characters:
    ``containing("ab")`` would otherwise mean "holds 'a' and holds 'b'", which
    nobody wants and :func:`string_containing` already says properly. An empty
    spec raises ``ValueError`` -- it is satisfied by every container there is, so
    the assertion holding it asserts nothing.

    A set spec is read as items to find, not as a set to compare: the matcher
    holds the items and looks for each of them, which is why an unhashable item
    in the container it is checking is no obstacle.
    """
    if isinstance(spec, Mapping):
        mapping = cast("Mapping[Any, Any]", spec)
        if not mapping:
            raise ValueError(_NEEDS_A_SPEC)
        return cast("T", _MappingSubset(mapping))
    if isinstance(spec, _SCANNABLE) and not isinstance(spec, _TEXTUAL):
        items = tuple(cast("Collection[object]", spec))
        if not items:
            raise ValueError(_NEEDS_A_SPEC)
        return cast("T", _ItemsPresent(items))
    raise TypeError(_NOT_A_CONTAINER + type(spec).__name__)


def matching[T](predicate: "Callable[[T], bool]", /) -> T:
    """A placeholder for any value a predicate says yes to.

        >>> expect({"n": 4}).is_equal_to({"n": matching(lambda n: n % 2 == 0)})
        MappingExpect({'n': 4})

    The escape hatch, and the reason the rest of this module can stay small: a
    condition nobody anticipated is one lambda away, and it nests inside
    ``containing`` and ``one_of`` like any other matcher.

    A predicate that **raises** is read as "no match" rather than allowed to
    escape. ``__eq__`` has to be total -- it runs inside a ``dict`` comparison
    and inside the difference engine -- so the choice is between a wrong answer
    and an error raised in the middle of reporting somebody else's failure.

    That is the one place this module departs from the rest of the library, where
    a broken predicate propagates: ``expect([1]).only_contains(broken)`` raises
    the predicate's own error, and ``matching(broken)`` does not. **State the
    cost plainly rather than only its consolation.** In a *positive* assertion
    the damage is bounded, because the value that caused it is printed next to
    ``<matching ...>`` where the reader is already looking. In a *negative* one
    -- ``is_not_equal_to``, ``does_not_contain`` -- there is no message at all: a
    predicate that always raises never matches, so the assertion passes, every
    time, and the test can no longer fail. Nothing in this module detects that,
    including the wrong-arity case the ``TypeError`` above reads as though it
    ruled out; ``matching`` is checked for being callable and for nothing else.
    A predicate written to answer about one type and handed another is the way
    this happens in practice, so keep the predicate total -- ``isinstance``
    first, verdict second -- rather than relying on the failure message to
    confess.
    """
    if not callable(predicate):
        raise TypeError(_NOT_A_PREDICATE + type(predicate).__name__)
    return cast("T", _Matching(predicate))


# ---------------------------------------------------------------------------
# Wiring, once, at import
# ---------------------------------------------------------------------------
#: Every matcher class, so the two registrations below stay one list.
_MATCHER_TYPES: Final[tuple[type[_Matcher], ...]] = (
    _AnyInstance,
    _Anything,
    _CloseTo,
    _ItemsPresent,
    _MappingSubset,
    _Matching,
    _OneOf,
    _StringContaining,
    _StringMatching,
)

for _matcher_type in _MATCHER_TYPES:
    register(_matcher_type, _refuse_matcher_subject)

register_formatter(_MatcherFormatter())
