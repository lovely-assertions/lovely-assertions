"""The class subject: ``TypeExpect``.

Four claims are pinned here.

*It is a ``CallableExpect``, statically as well as at runtime.* That is what keeps
``expect(SomeClass).raises(...)`` typed, and it is the whole argument for the
shape of the inheritance -- so the checker is made to agree with it rather than
asked to take it on trust.

*Every assertion hands back the subject it was called on*, a user's own subclass
included, and the two finders hand back a ``Found`` whose ``.which`` descends into
what they found.

*``.subject`` is a ``Callable[..., object]``.* Inherited from ``CallableExpect``
and deliberately not re-specialised to ``type[Any]``: re-annotating the subject
would narrow a mutable attribute in a subclass, and a ``type[Any]`` would trade an
honest type for an ``Any`` that silences the checker on everything reached through
it. Pinned so a change has to be argued for.

*The explicit entry point is typed.* ``expect(value, as_=TypeExpect)`` names the
subject outright, reaching it without going through the dispatch table at all.
"""

from collections.abc import Callable, Sized
from typing import Any, ClassVar, Protocol, assert_type, runtime_checkable

from lovely_assertions import CallableExpect, Expect, Found, RaisedExpect, expect
from lovely_assertions._type import TypeExpect


class Animal: ...


class Bird(Animal): ...


class Order:
    DEFAULTS: ClassVar[dict[str, int]] = {"retries": 3}

    def save(self) -> None: ...


@runtime_checkable
class Closeable(Protocol):
    def close(self) -> None: ...


# ---------------------------------------------------------------------------
# The addition is pure
# ---------------------------------------------------------------------------
def _accepts_a_callable_subject(subject: CallableExpect, /) -> CallableExpect:
    """Stands in for any code written against the callable subject."""
    return subject


def a_class_subject_is_a_callable_subject() -> None:
    """The inheritance is load-bearing: it is what keeps the next function typed.

    The claim is assignability, so it is made by *passing* one rather than by
    declaring one: pyright reports the narrowed type of a name, so
    ``subject: CallableExpect = TypeExpect(...)`` followed by an ``assert_type``
    would be testing how a checker reads a declaration rather than what the
    subject is.
    """
    assert_type(_accepts_a_callable_subject(TypeExpect(Order)), CallableExpect)


def the_exception_catalogue_survives() -> None:
    """``expect(SomeClass).raises(...)`` -- a constructor that must refuse its arguments."""
    assert_type(TypeExpect(Order).raises(TypeError), RaisedExpect[TypeError])
    assert_type(TypeExpect(Order).raises(TypeError).subject, TypeError)
    assert_type(TypeExpect(Order).does_not_raise(), TypeExpect)


def the_generic_catalogue_survives_too() -> None:
    assert_type(TypeExpect(Order).is_not_none(), Expect[Callable[..., object]])
    assert_type(TypeExpect(Order).is_instance_of(type), Found[TypeExpect, type])
    assert_type(TypeExpect(Order).and_, TypeExpect)


def the_subject_stays_the_callable_it_was() -> None:
    """The documented widening: ``CallableExpect`` fixes ``T``, and this inherits it."""
    assert_type(TypeExpect(Order).subject, Callable[..., object])


# ---------------------------------------------------------------------------
# Every assertion returns the subject it was called on
# ---------------------------------------------------------------------------
def the_catalogue_returns_self() -> None:
    subject = TypeExpect(Bird)
    assert_type(subject.is_subclass_of(Animal), TypeExpect)
    assert_type(subject.is_not_subclass_of(dict), TypeExpect)
    assert_type(subject.does_not_have_attribute("gone"), TypeExpect)
    assert_type(subject.is_abstract(), TypeExpect)
    assert_type(subject.is_not_abstract(), TypeExpect)
    assert_type(subject.implements(Closeable), TypeExpect)
    assert_type(subject.does_not_implement(Closeable), TypeExpect)


def an_abstract_base_class_is_a_valid_argument_too() -> None:
    """``implements`` takes anything with members to require, ABCs included."""
    assert_type(TypeExpect(Order).implements(Sized), TypeExpect)


def the_catalogue_chains() -> None:
    assert_type(
        TypeExpect(Bird).is_subclass_of(Animal).and_.is_not_abstract().and_.subject,
        Callable[..., object],
    )


# ---------------------------------------------------------------------------
# The finders
# ---------------------------------------------------------------------------
def has_attribute_finds_a_value_to_descend_into() -> None:
    found = TypeExpect(Order).has_attribute("DEFAULTS")
    assert_type(found, Found[TypeExpect, Any])
    assert_type(found.and_, TypeExpect)
    assert_type(found.which, Expect[Any])


def has_method_finds_one_too() -> None:
    found = TypeExpect(Order).has_method("save")
    assert_type(found, Found[TypeExpect, Any])
    assert_type(found.and_, TypeExpect)


# ---------------------------------------------------------------------------
# The explicit entry point
# ---------------------------------------------------------------------------
def as_reaches_the_class_subject_without_dispatch_wiring() -> None:
    assert_type(expect(Order, as_=TypeExpect), TypeExpect)
    assert_type(expect(Order, as_=TypeExpect).is_subclass_of(object), TypeExpect)


# ---------------------------------------------------------------------------
# Extension: a subclass gets its own type back
# ---------------------------------------------------------------------------
class ModelExpect(TypeExpect):
    """A user's own class subject, to pin what ``Self`` promises."""

    __slots__ = ()

    def has_table(self, expected: str, /, *, because: str = "") -> "ModelExpect":
        if getattr(self.subject, "__tablename__", None) == expected:
            return self
        return self._fail(f"to map to the table {expected!r}", because)


def a_subclass_keeps_its_own_type() -> None:
    assert_type(ModelExpect(Order).is_subclass_of(object), ModelExpect)
    assert_type(ModelExpect(Order).has_table("orders"), ModelExpect)
    assert_type(ModelExpect(Order).has_attribute("DEFAULTS").and_, ModelExpect)
    assert_type(ModelExpect(Order).is_abstract().and_.has_table("orders"), ModelExpect)
