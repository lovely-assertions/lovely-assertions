"""Classes as subjects -- ``TypeExpect``.

Three things are pinned here beyond the ordinary pass/fail/message rounds.

*The addition is pure.* ``TypeExpect`` specialises ``CallableExpect``, and a class
is a callable: asserting on a constructor -- ``expect(Order).raises(TypeError)``
-- is a real thing to do. Nothing a callable subject could say about a class may
be lost by narrowing to this one, so it is tested rather than assumed.

*The definition of "abstract" is a decision, not an accident.* A class is abstract
here when ``__abstractmethods__`` is non-empty, whatever its metaclass. Three
classes disagree with the alternatives, and all three are pinned so a future
change has to be deliberate.

*The four shapes of a callable member are all tested.* ``getattr`` on a class
turns a ``classmethod`` into a bound method, a ``staticmethod`` into a plain
function and a ``property`` into the descriptor. Three of those are methods and
one is not, and the failure has to say which it found.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Sized
from dataclasses import dataclass
from typing import Any, ClassVar, NoReturn, Protocol, cast, runtime_checkable

import pytest
from benchmarks import blocks_allocated

from lovely_assertions import (
    AssertionFailure,
    CallableExpect,
    Found,
    expect,
    soft_assertions,
)
from lovely_assertions._formatting import formatting
from lovely_assertions._reflection import dataclass_field_names
from lovely_assertions._type import TypeExpect

#: Read with ``setattr`` rather than written as an attribute so that the class it
#: is put on is plainly a class that never declared it.
_ABSTRACT_METHODS = "__abstractmethods__"


# ---------------------------------------------------------------------------
# The cast of classes
# ---------------------------------------------------------------------------
class Animal:
    """The root of an ordinary three-deep hierarchy."""


class Bird(Animal): ...


class Duck(Bird): ...


class Repo(ABC):
    """Two abstract methods, so the failure has a list to sort."""

    @abstractmethod
    def save(self) -> None: ...

    @abstractmethod
    def load(self) -> None: ...


class Impl(Repo):
    """``Repo``, finished."""

    def save(self) -> None: ...

    def load(self) -> None: ...


class Bare(ABC):  # noqa: B024  (an ABC with nothing abstract is the case under test)
    """An ABC that declares nothing abstract -- and therefore constructs."""


class DeclaredAbstract:
    """A plain class that merely *says* it is abstract, and still constructs.

    The case where "non-empty ``__abstractmethods__``" and "cannot be
    instantiated" come apart: CPython sets its abstract flag when the attribute
    is *assigned* on an existing class, not when a class body happens to contain
    the name.
    """

    __abstractmethods__ = frozenset({"handle"})


class Order:
    """One class carrying every shape a class member can take."""

    DEFAULTS: ClassVar[dict[str, int]] = {"retries": 3}
    legacy_id = 3
    nothing = None

    class Row:
        """A nested class: callable, and not a method."""

    def save(self) -> None: ...

    @classmethod
    def build(cls) -> "Order":
        return cls()

    @staticmethod
    def helper() -> int:
        return 1

    @property
    def total(self) -> int:
        return 0


@runtime_checkable
class Closeable(Protocol):
    """The ordinary case: runtime-checkable, methods only."""

    def close(self) -> None: ...


class Unchecked(Protocol):
    """Deliberately not ``@runtime_checkable``."""

    def close(self) -> None: ...


@runtime_checkable
class HasName(Protocol):
    """Runtime-checkable and a *data* protocol, which ``issubclass`` refuses."""

    name: str


class Session:
    def close(self) -> None: ...


def test_the_module_hides_its_frames() -> None:
    """One ``__tracebackhide__`` per module folds its frames out of a failure traceback."""
    from lovely_assertions import _exceptions, _type

    assert _type.__tracebackhide__ is _exceptions.hide_internal_frames


def test_the_subject_carries_no_instance_dictionary() -> None:
    """``__slots__ = ()`` on the subject, so no wrapper carries an instance dictionary."""
    assert TypeExpect.__slots__ == ()
    assert not hasattr(TypeExpect(Duck), "__dict__")


# ---------------------------------------------------------------------------
# The addition is pure: everything a class subject could do, it still does
# ---------------------------------------------------------------------------
def test_the_subject_is_a_callable_subject() -> None:
    """The inheritance is the mechanism, so it is asserted rather than assumed."""
    assert issubclass(TypeExpect, CallableExpect)
    assert isinstance(TypeExpect(Duck), CallableExpect)


def test_a_constructor_that_must_reject_its_arguments_is_still_assertable() -> None:
    """``expect(SomeClass).raises(...)`` is the reason to extend ``CallableExpect``.

    Calling ``Order`` with no arguments is what the assertion does, and a class
    whose ``__init__`` demands one raises. Fold that into a lambda and the
    subject name in the failure becomes the lambda.
    """

    class Strict:
        def __init__(self, value: int, /) -> None:
            self.value = value

    TypeExpect(Strict).raises(TypeError).with_message_containing("argument")
    TypeExpect(Order).does_not_raise()


def test_the_generic_catalogue_still_applies() -> None:
    """A class is an object; nothing inherited is lost by specialising the subject."""
    subject = TypeExpect(Duck)
    assert subject.is_not_none().subject is Duck
    assert subject.is_same_as(Duck) is subject
    assert subject.is_instance_of(type).subject is Duck
    assert subject.is_one_of(Duck, Bird) is subject


def test_the_explicit_entry_point_reaches_it_today() -> None:
    """``as_=`` is the typed way in, and it reaches this subject with no dispatch wiring."""
    subject = expect(Duck, as_=TypeExpect)
    assert isinstance(subject, TypeExpect)
    assert subject.is_subclass_of(Animal) is subject


# ---------------------------------------------------------------------------
# A passing assertion reaches nothing on the failure path
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("no_failure_machinery")
def test_no_passing_assertion_touches_the_failure_path() -> None:
    TypeExpect(Duck).is_subclass_of(Animal, because="the reason must not be read either")
    TypeExpect(Duck).is_not_subclass_of(dict)
    TypeExpect(Order).has_attribute("DEFAULTS")
    TypeExpect(Order).does_not_have_attribute("absent")
    TypeExpect(Order).has_method("save")
    TypeExpect(Repo).is_abstract()
    TypeExpect(Impl).is_not_abstract()
    TypeExpect(Session).implements(Closeable)
    TypeExpect(Order).does_not_implement(Closeable)


def test_the_trap_actually_detonates(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rule nobody can fail is not a rule."""
    from lovely_assertions import _formatting

    class Detonator:
        def __getattr__(self, name: str) -> NoReturn:
            raise AssertionError(name)

    monkeypatch.setattr(_formatting, "_ACTIVE", Detonator())
    with pytest.raises(AssertionError, match="get"):
        TypeExpect(Repo).is_not_abstract()


def test_no_passing_assertion_holds_on_to_memory() -> None:
    """A passing assertion is a comparison and a ``return self``, measured rather than argued.

    The subjects are built once, outside the loop, so what is counted is the
    assertion itself and not the construction of its wrapper.
    """
    baseline = blocks_allocated(lambda: None)
    duck = TypeExpect(Duck)
    order = TypeExpect(Order)
    repo = TypeExpect(Repo)
    session = TypeExpect(Session)
    cases: list[tuple[str, Callable[[], object]]] = [
        ("is_subclass_of", lambda: duck.is_subclass_of(Animal)),
        ("is_not_subclass_of", lambda: duck.is_not_subclass_of(dict)),
        ("has_attribute", lambda: order.has_attribute("DEFAULTS")),
        ("does_not_have_attribute", lambda: order.does_not_have_attribute("absent")),
        ("has_method", lambda: order.has_method("save")),
        ("is_abstract", repo.is_abstract),
        ("is_not_abstract", TypeExpect(Impl).is_not_abstract),
        ("implements", lambda: session.implements(Closeable)),
        ("does_not_implement", lambda: order.does_not_implement(Closeable)),
    ]
    for label, callback in cases:
        allocated = blocks_allocated(callback)
        assert allocated <= baseline, (
            f"{label} held on to {allocated - baseline} blocks over the run; "
            f"a passing assertion is a comparison and a `return self`."
        )


# ---------------------------------------------------------------------------
# is_subclass_of / is_not_subclass_of
# ---------------------------------------------------------------------------
def test_is_subclass_of_passes_and_chains() -> None:
    subject = TypeExpect(Duck)
    assert subject.is_subclass_of(Animal) is subject
    assert subject.is_subclass_of(Bird) is subject


def test_is_subclass_of_is_reflexive_as_issubclass_is() -> None:
    """``issubclass(C, C)`` is true, and this assertion is ``issubclass``."""
    assert TypeExpect(Animal).is_subclass_of(Animal) is not None


def test_is_subclass_of_names_what_the_class_does_inherit() -> None:
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Duck).is_subclass_of(dict)
    assert str(caught.value) == (
        "Expected Duck to be a subclass of dict, but it inherits from Bird, Animal, object."
    )


def test_is_subclass_of_has_something_to_say_about_object_itself() -> None:
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(object).is_subclass_of(int)
    assert str(caught.value) == (
        "Expected object to be a subclass of int, but it inherits from nothing."
    )


def test_is_subclass_of_counts_a_virtual_subclass() -> None:
    """``__subclasshook__`` and ``register`` are inheritance as far as Python is concerned."""
    assert TypeExpect(list).is_subclass_of(Sized) is not None


def test_is_not_subclass_of_passes_and_chains() -> None:
    subject = TypeExpect(Duck)
    assert subject.is_not_subclass_of(dict) is subject


def test_is_not_subclass_of_names_the_base_class_that_did_it() -> None:
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Duck).is_not_subclass_of(Animal)
    assert str(caught.value) == (
        "Expected Duck not to be a subclass of Animal, but Animal is one of its base classes."
    )


def test_is_not_subclass_of_explains_the_reflexive_case() -> None:
    """A class is a subclass of itself, which surprises people once each."""
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Animal).is_not_subclass_of(Animal)
    assert str(caught.value) == (
        "Expected Animal not to be a subclass of Animal, but it is Animal itself."
    )


def test_is_not_subclass_of_explains_a_virtual_subclass() -> None:
    """The case a reader cannot see in the source: nothing in the MRO says so."""
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(list).is_not_subclass_of(Sized)
    assert str(caught.value) == (
        "Expected list not to be a subclass of Sized, but it counts as one"
        " without inheriting from it: Sized is not in its MRO."
    )


# ---------------------------------------------------------------------------
# has_attribute / does_not_have_attribute
# ---------------------------------------------------------------------------
def test_has_attribute_finds_the_value_and_continues_on_it() -> None:
    found = TypeExpect(Order).has_attribute("DEFAULTS")
    assert isinstance(found, Found)
    assert found.subject == {"retries": 3}
    assert found.which.is_equal_to({"retries": 3}) is not None


def test_has_attribute_goes_back_to_the_class_with_and() -> None:
    subject = TypeExpect(Order)
    assert subject.has_attribute("DEFAULTS").and_ is subject


def test_has_attribute_says_where_it_looked() -> None:
    """The gotcha this assertion exists next to: instance attributes are not here."""
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Order).has_attribute("missing")
    assert str(caught.value) == (
        "Expected Order to have the attribute 'missing',"
        " but no such attribute is defined on the class."
    )


def test_an_attribute_assigned_in_init_is_not_on_the_class() -> None:
    """Pinned because it is the mistake, not an implementation detail."""

    class Built:
        def __init__(self) -> None:
            self.total = 0

    with pytest.raises(AssertionFailure, match="no such attribute is defined on the class"):
        TypeExpect(Built).has_attribute("total")


def test_has_attribute_accepts_an_attribute_whose_value_is_none() -> None:
    """The sentinel earns its place: ``None`` is a value, not an absence."""
    found = TypeExpect(Order).has_attribute("nothing")
    assert found.subject is None


def test_has_attribute_finds_an_inherited_attribute() -> None:
    class Child(Order): ...

    assert TypeExpect(Child).has_attribute("legacy_id").subject == 3


def test_does_not_have_attribute_passes_and_chains() -> None:
    subject = TypeExpect(Order)
    assert subject.does_not_have_attribute("absent") is subject


def test_does_not_have_attribute_names_how_the_class_declares_it() -> None:
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Order).does_not_have_attribute("legacy_id")
    assert str(caught.value) == (
        "Expected Order not to have the attribute 'legacy_id', but it is the int 3."
    )


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("total", "a property"),
        ("build", "a class method"),
        ("helper", "a static method"),
        ("save", "a method"),
        ("Row", "the nested class Row"),
        ("nothing", "None"),
        ("legacy_id", "the int 3"),
    ],
)
def test_the_failure_names_the_shape_the_member_actually_has(name: str, kind: str) -> None:
    """``getattr`` flattens four declarations into two shapes; the message unflattens them."""
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Order).does_not_have_attribute(name)
    assert str(caught.value) == (
        f"Expected Order not to have the attribute {name!r}, but it is {kind}."
    )


def test_the_shape_is_read_from_the_declaration_not_from_getattr() -> None:
    """Proof the distinction is real: all three come back callable from ``getattr``."""
    assert callable(Order.build)
    assert callable(Order.helper)
    assert callable(Order.save)
    assert not callable(Order.__dict__["total"])


# ---------------------------------------------------------------------------
# has_method: the four shapes
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["save", "build", "helper"])
def test_has_method_accepts_all_three_kinds_of_method(name: str) -> None:
    """A plain ``def``, a ``classmethod`` and a ``staticmethod`` are all methods."""
    found = TypeExpect(Order).has_method(name)
    assert callable(found.subject)


def test_has_method_continues_on_the_method_it_found() -> None:
    found = TypeExpect(Order).has_method("helper")
    assert found.subject() == 1
    assert found.which.is_not_none() is not None


def test_has_method_turns_down_a_property_and_says_so() -> None:
    """A property is a computed attribute, not a method, and is not callable."""
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Order).has_method("total")
    assert str(caught.value) == "Expected Order to have a method 'total', but it is a property."


def test_has_method_turns_down_a_nested_class() -> None:
    """``callable()`` says yes; a test that passed on it would pass for the wrong reason."""
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Order).has_method("Row")
    assert str(caught.value) == (
        "Expected Order to have a method 'Row', but it is the nested class Row."
    )


def test_has_method_turns_down_a_plain_value() -> None:
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Order).has_method("legacy_id")
    assert str(caught.value) == "Expected Order to have a method 'legacy_id', but it is the int 3."


def test_has_method_distinguishes_absent_from_present_but_wrong() -> None:
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Order).has_method("nope")
    assert str(caught.value) == (
        "Expected Order to have a method 'nope', but no such attribute is defined on the class."
    )


def test_has_method_accepts_a_callable_instance() -> None:
    """A member with ``__call__`` is callable and is not one of the three descriptors."""

    class Callback:
        def __call__(self) -> int:
            return 7

    class Widget:
        render = Callback()

    assert TypeExpect(Widget).has_method("render").subject() == 7


# ---------------------------------------------------------------------------
# is_abstract / is_not_abstract
# ---------------------------------------------------------------------------
def test_is_abstract_passes_for_an_abc_with_unimplemented_methods() -> None:
    subject = TypeExpect(Repo)
    assert subject.is_abstract() is subject


def test_is_not_abstract_passes_for_a_finished_implementation() -> None:
    subject = TypeExpect(Impl)
    assert subject.is_not_abstract() is subject


def test_is_not_abstract_names_what_is_left_unimplemented() -> None:
    """The useful half of the failure, and sorted so it does not vary between runs."""
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Repo).is_not_abstract()
    assert str(caught.value) == (
        "Expected Repo not to be abstract, but it leaves 'load', 'save' unimplemented."
    )


def test_the_list_of_unimplemented_methods_is_sorted_not_set_ordered() -> None:
    """``__abstractmethods__`` is a ``frozenset``; an unordered message is a flaky one."""
    assert isinstance(Repo.__abstractmethods__, frozenset)
    for _ in range(5):
        with pytest.raises(AssertionFailure, match=r"'load', 'save'"):
            TypeExpect(Repo).is_not_abstract()


def test_an_abc_that_declares_nothing_abstract_is_not_abstract() -> None:
    """It constructs. Calling it abstract would contradict the interpreter."""
    assert Bare() is not None
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Bare).is_abstract()
    assert str(caught.value) == (
        "Expected Bare to be abstract, but it leaves no abstract method unimplemented."
    )


def test_an_implementation_gets_the_same_message_as_an_empty_abc() -> None:
    with pytest.raises(AssertionFailure, match="leaves no abstract method unimplemented"):
        TypeExpect(Impl).is_abstract()


def test_a_class_that_never_declared_one_gets_a_different_message() -> None:
    """Two different mistakes: nothing was marked, or everything was implemented."""
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Order).is_abstract()
    assert (
        str(caught.value) == "Expected Order to be abstract, but it declares no abstract methods."
    )


def test_abstractness_is_read_from_the_attribute_not_from_the_metaclass() -> None:
    """The decision the module made, in the one case where the two definitions differ.

    A plain class with a non-empty ``__abstractmethods__`` counts as abstract
    here, though its metaclass is ``type`` and it is not an ABC at all.
    """
    assert type(DeclaredAbstract) is type
    subject = TypeExpect(DeclaredAbstract)
    assert subject.is_abstract() is subject


def test_being_abstract_is_not_the_same_claim_as_being_uninstantiable() -> None:
    """Both directions of the gap, pinned so the docstring cannot quietly drift.

    ``DeclaredAbstract`` is abstract by this test and constructs anyway --
    CPython sets its abstract flag on *assignment*, not on a class body naming
    the attribute. A ``Protocol`` is the mirror: it cannot be constructed and
    leaves nothing unimplemented, so it is not abstract here.
    """
    assert DeclaredAbstract() is not None

    class Assigned:
        def handle(self) -> None: ...

    setattr(Assigned, _ABSTRACT_METHODS, frozenset({"handle"}))
    assert TypeExpect(Assigned).is_abstract() is not None
    with pytest.raises(TypeError, match="abstract"):
        Assigned()

    # Through an untyped name: both checkers refuse to instantiate a Protocol, and
    # that refusal is the very thing being demonstrated at runtime here.
    uninstantiable: Any = Unchecked
    with pytest.raises(TypeError, match="Protocols cannot be instantiated"):
        uninstantiable()
    with pytest.raises(AssertionFailure, match="leaves no abstract method unimplemented"):
        TypeExpect(Unchecked).is_abstract()


def test_a_hostile_abstractmethods_does_not_blow_up_the_message() -> None:
    """Any class can put anything under that name; a message must still come out."""

    class Lying:
        __abstractmethods__ = "not a set"

    subject = TypeExpect(Lying)
    assert subject.is_not_abstract() is subject
    with pytest.raises(AssertionFailure, match="declares no abstract methods"):
        subject.is_abstract()


# ---------------------------------------------------------------------------
# implements / does_not_implement
# ---------------------------------------------------------------------------
def test_implements_passes_for_a_structural_match() -> None:
    subject = TypeExpect(Session)
    assert subject.implements(Closeable) is subject


def test_implements_lists_the_members_the_class_does_not_define() -> None:
    """The reason this is not just ``is_subclass_of`` with another message."""
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Order).implements(Closeable)
    assert str(caught.value) == (
        "Expected Order to implement Closeable, but it does not define 'close'."
    )


def test_implements_lists_an_abstract_base_class_s_members_too() -> None:
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Order).implements(Sized)
    assert str(caught.value) == (
        "Expected Order to implement Sized, but it does not define '__len__'."
    )


def test_implements_falls_back_to_inheritance_when_there_is_nothing_to_list() -> None:
    """A concrete class requires nothing structural, so the answer is nominal."""
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Order).implements(Animal)
    assert str(caught.value) == ("Expected Order to implement Animal, but it inherits from object.")


def test_implements_reports_several_missing_members_sorted() -> None:
    @runtime_checkable
    class Stream(Protocol):
        def read(self) -> bytes: ...
        def write(self, data: bytes, /) -> None: ...

    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Order).implements(Stream)
    assert str(caught.value) == (
        "Expected Order to implement Stream, but it does not define 'read', 'write'."
    )


def test_does_not_implement_passes_and_chains() -> None:
    subject = TypeExpect(Order)
    assert subject.does_not_implement(Closeable) is subject


def test_does_not_implement_lists_what_the_class_turned_out_to_provide() -> None:
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Session).does_not_implement(Closeable)
    assert str(caught.value) == (
        "Expected Session not to implement Closeable, but it defines 'close'."
    )


def test_does_not_implement_catches_the_accidental_conformance() -> None:
    """A class that grew a ``__len__`` became a ``Sized``, and nothing recorded it."""
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(list).does_not_implement(Sized)
    assert str(caught.value) == ("Expected list not to implement Sized, but it defines '__len__'.")


def test_does_not_implement_falls_back_to_the_inheritance_note() -> None:
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Duck).does_not_implement(Animal)
    assert str(caught.value) == (
        "Expected Duck not to implement Animal, but Animal is one of its base classes."
    )


def test_a_registered_virtual_subclass_is_not_said_to_define_anything() -> None:
    """``ABCMeta.register`` satisfies ``issubclass`` while defining nothing.

    A message listing what the protocol *asked for* would send the reader
    looking for a ``__len__`` that was never written.
    """

    class Registered: ...

    Sized.register(Registered)
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Registered).does_not_implement(Sized)
    assert str(caught.value) == (
        "Expected Registered not to implement Sized, but it counts as one"
        " without inheriting from it: Sized is not in its MRO."
    )


def test_implements_checks_members_not_signatures() -> None:
    """What a checker verifies and what this verifies are different things."""

    class WrongShape:
        def close(self, force: bool) -> None: ...

    assert TypeExpect(WrongShape).implements(Closeable) is not None


# ---------------------------------------------------------------------------
# The two protocols that cannot be checked: raised, never reported
# ---------------------------------------------------------------------------
def test_a_protocol_that_is_not_runtime_checkable_is_refused() -> None:
    with pytest.raises(TypeError) as caught:
        TypeExpect(Session).implements(Unchecked)
    assert not isinstance(caught.value, AssertionFailure), (
        "an unusable protocol is a bug in the test; an AssertionFailure would let a "
        "runner present it as a finding about the class"
    )
    assert str(caught.value) == (
        "Unchecked is not @runtime_checkable, so nothing can be checked against it at"
        " runtime. Decorate it with typing.runtime_checkable, or assert on the members"
        " you care about with has_method(...)."
    )


def test_the_refusal_names_the_protocol_that_caused_it() -> None:
    """``__cause__`` keeps CPython's own message, which said it first."""
    with pytest.raises(TypeError) as caught:
        TypeExpect(Session).implements(Unchecked)
    assert isinstance(caught.value.__cause__, TypeError)
    assert "runtime_checkable" in str(caught.value.__cause__)


def test_a_data_protocol_cannot_be_checked_against_a_class() -> None:
    """And the message says why, because the reader's next move is a different subject."""
    with pytest.raises(TypeError) as caught:
        TypeExpect(Session).implements(HasName)
    assert str(caught.value) == (
        "HasName has non-method members ('name'), and a data protocol cannot be checked"
        " against a class: those members live on instances, not on the class. Assert on"
        " an instance instead -- expect(obj).is_instance_of(HasName)."
    )


def test_the_instance_route_the_refusal_points_at_actually_works() -> None:
    """A message that names a fix has to be tested, or it is a guess in prose."""

    class Named:
        def __init__(self) -> None:
            self.name = "n"

    # `HasName` goes through an untyped name because mypy refuses a protocol class
    # where a `type[S]` is expected (`type-abstract`); pyright, the reference
    # checker, accepts the call as written in the message.
    protocol: Any = HasName
    # The claim is that the call is accepted, and that is all this asserts. Reaching
    # for `.subject` would not add to it: the continuation is overloaded on the type
    # that was asked for, and asking with an `Any` gives back an `Unknown` that
    # pyright strict reports rather than an answer worth checking.
    found = cast("object", expect(Named()).is_instance_of(protocol))
    assert found is not None


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda: TypeExpect(Session).implements(Unchecked), id="implements"),
        pytest.param(
            lambda: TypeExpect(Session).does_not_implement(Unchecked), id="does_not_implement"
        ),
        pytest.param(lambda: TypeExpect(Session).is_subclass_of(Unchecked), id="is_subclass_of"),
        pytest.param(
            lambda: TypeExpect(Session).is_not_subclass_of(Unchecked), id="is_not_subclass_of"
        ),
    ],
)
def test_every_assertion_that_asks_issubclass_explains_the_refusal(
    call: Callable[[], object],
) -> None:
    with pytest.raises(TypeError, match="not @runtime_checkable"):
        call()


def test_the_refusal_is_not_swallowed_by_a_soft_scope() -> None:
    """A bug in the test aborts the block; it is not collected as a finding."""
    with pytest.raises(TypeError, match="not @runtime_checkable"), soft_assertions():
        TypeExpect(Session).implements(Unchecked)


def test_a_type_error_that_is_not_about_protocols_is_left_alone() -> None:
    """CPython's own message is the true one when the subject is not a class."""
    with pytest.raises(TypeError) as caught:
        TypeExpect(len).is_subclass_of(Animal)
    assert "issubclass" in str(caught.value)
    assert "runtime_checkable" not in str(caught.value)


def test_a_runtime_checkable_protocol_with_only_methods_is_never_refused() -> None:
    """The guard must not fire on the ordinary case."""
    assert TypeExpect(Session).implements(Closeable) is not None
    assert TypeExpect(Session).is_subclass_of(Closeable) is not None


# ---------------------------------------------------------------------------
# because, and the soft-scope seam
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda: TypeExpect(Duck).is_subclass_of(dict, because="R"), id="subclass"),
        pytest.param(
            lambda: TypeExpect(Duck).is_not_subclass_of(Animal, because="R"), id="not_subclass"
        ),
        pytest.param(lambda: TypeExpect(Order).has_attribute("x", because="R"), id="attribute"),
        pytest.param(
            lambda: TypeExpect(Order).does_not_have_attribute("save", because="R"),
            id="not_attribute",
        ),
        pytest.param(lambda: TypeExpect(Order).has_method("x", because="R"), id="method"),
        pytest.param(lambda: TypeExpect(Order).is_abstract(because="R"), id="abstract"),
        pytest.param(lambda: TypeExpect(Repo).is_not_abstract(because="R"), id="not_abstract"),
        pytest.param(lambda: TypeExpect(Order).implements(Closeable, because="R"), id="implements"),
        pytest.param(
            lambda: TypeExpect(Session).does_not_implement(Closeable, because="R"),
            id="not_implements",
        ),
    ],
)
def test_because_reaches_every_assertion(call: Callable[[], object]) -> None:
    with pytest.raises(AssertionFailure, match="because R"):
        call()


def test_every_broken_clause_is_reported_in_a_soft_scope() -> None:
    with pytest.raises(AssertionFailure) as caught, soft_assertions():
        TypeExpect(Order).is_abstract().and_.implements(Closeable).and_.has_method("total")
    message = str(caught.value)
    assert "3 assertions failed:" in message
    assert "to be abstract, but it declares no abstract methods" in message
    assert "to implement Closeable, but it does not define 'close'" in message
    assert "to have a method 'total', but it is a property" in message


def test_a_failed_finder_absorbs_the_rest_of_its_chain_in_a_soft_scope() -> None:
    """One root cause, one message: the narrowed value never existed."""
    with pytest.raises(AssertionFailure) as caught, soft_assertions():
        TypeExpect(Order).has_attribute("missing").which.is_equal_to(3)
    message = str(caught.value)
    assert "1 assertion failed:" in message
    assert "no such attribute is defined on the class" in message


def test_a_failed_has_method_absorbs_the_rest_of_its_chain_too() -> None:
    with pytest.raises(AssertionFailure) as caught, soft_assertions():
        TypeExpect(Order).has_method("total").which.is_equal_to(3)
    assert "1 assertion failed:" in str(caught.value)


# ---------------------------------------------------------------------------
# Subject naming, and the formatting scope
# ---------------------------------------------------------------------------
def test_the_subject_name_is_recovered_from_the_call() -> None:
    """Subject naming needs no special case here: ``TypeExpect`` is an ``Expect``
    subclass, so the name is recovered from the calling source line as usual."""
    with pytest.raises(AssertionFailure, match=r"^Expected Duck "):
        TypeExpect(Duck).is_subclass_of(dict)


def test_an_explicit_name_wins() -> None:
    with pytest.raises(AssertionFailure, match=r"^Expected the repository "):
        TypeExpect(Order).described_as("the repository").is_abstract()


def test_a_long_list_of_unimplemented_methods_is_bounded_and_counted() -> None:
    """``max_items`` from the scope in force, and what is left out is counted."""
    names = frozenset("method_" + str(index) for index in range(15))

    class Many: ...

    setattr(Many, _ABSTRACT_METHODS, names)
    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Many).is_not_abstract()
    assert "... (5 more)" in str(caught.value)
    assert "'method_9'" not in str(caught.value)


def test_an_open_formatting_scope_widens_the_same_message() -> None:
    """The bound is read at failure time, so a block can ask for the whole list."""
    names = frozenset("method_" + str(index) for index in range(15))

    class Many: ...

    setattr(Many, _ABSTRACT_METHODS, names)
    with formatting(max_items=20), pytest.raises(AssertionFailure) as caught:
        TypeExpect(Many).is_not_abstract()
    assert "more)" not in str(caught.value)
    assert "'method_9'" in str(caught.value)


def test_a_long_value_is_clipped_and_its_length_reported() -> None:
    class Big:
        payload = "x" * 400

    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Big).does_not_have_attribute("payload")
    message = str(caught.value)
    assert "..." in message
    assert "(truncated from 402 characters)" in message


def test_the_formatting_scope_widens_a_clipped_value_too() -> None:
    class Big:
        payload = "x" * 400

    with formatting(max_chars=500), pytest.raises(AssertionFailure) as caught:
        TypeExpect(Big).does_not_have_attribute("payload")
    assert "truncated" not in str(caught.value)


# ---------------------------------------------------------------------------
# Odds and ends the catalogue has to survive
# ---------------------------------------------------------------------------
def test_a_class_with_a_hostile_repr_still_produces_a_message() -> None:
    """Rendering runs while a test is already failing; it must not raise there."""

    class Hostile(type):
        def __repr__(cls) -> str:
            raise RuntimeError("no")

    class Rude(metaclass=Hostile): ...

    with pytest.raises(AssertionFailure, match="to be a subclass of dict"):
        TypeExpect(Rude).is_subclass_of(dict)


def test_a_generic_alias_is_not_a_class_and_says_so() -> None:
    """``list[int]`` is not a ``type``; ``issubclass`` refuses it, and that stands."""
    alias: Any = list[int]
    with pytest.raises(TypeError):
        TypeExpect(Order).is_subclass_of(alias)


def test_the_catalogue_chains_with_the_inherited_one() -> None:
    subject = TypeExpect(Impl)
    assert (
        subject.is_subclass_of(Repo)
        .and_.is_not_abstract()
        .and_.has_method("save")
        .and_.is_not_none()
        .subject
        is Impl
    )


def test_an_iterable_protocol_is_checked_the_same_way() -> None:
    """``collections.abc`` structural ABCs are the common case in real suites."""

    class Feed:
        def __iter__(self) -> "Iterable[int]":  # pragma: no cover - never called
            return iter(())

    assert TypeExpect(Feed).implements(Iterable) is not None
    with pytest.raises(AssertionFailure, match="does not define '__iter__'"):
        TypeExpect(Order).implements(Iterable)


# ---------------------------------------------------------------------------
# Where the declaration actually is: up the MRO, on the metaclass, or nowhere
# ---------------------------------------------------------------------------
def test_a_decorator_on_an_inherited_declaration_is_still_named() -> None:
    """The walk is up the whole MRO, not a look in the subject's own dictionary.

    ``getattr`` dissolves the decorator, so the only place a ``property`` is
    still recognisable is the class dictionary that declared it -- and for an
    inherited member that is a base's, not the subject's. Stopping at the
    subject would print ``the property <property object at 0x...>``: an address,
    and a different one every run.
    """

    class Base:
        @property
        def cached_token(self) -> str:  # pragma: no cover - never read
            return "t"

    class Child(Base): ...

    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Child).does_not_have_attribute("cached_token")

    assert str(caught.value) == (
        "Expected Child not to have the attribute 'cached_token', but it is a property."
    )


def test_an_attribute_carried_by_the_metaclass_is_named_by_its_value() -> None:
    """``getattr`` on a class finds the metaclass too, and the MRO walk does not.

    A registry hung on the metaclass is reachable as ``Plugin.plugins`` and is in
    no class dictionary of ``Plugin``'s own MRO, so the search for a decorated
    declaration comes back with nothing. The fallback describes the value that
    ``getattr`` actually returned, which is the only account of it there is.
    """

    class Registry(type):
        plugins: ClassVar[dict[str, object]] = {}

    class Plugin(metaclass=Registry): ...

    with pytest.raises(AssertionFailure) as caught:
        TypeExpect(Plugin).does_not_have_attribute("plugins")

    assert str(caught.value) == (
        "Expected Plugin not to have the attribute 'plugins', but it is the dict {}."
    )


def test_dataclass_field_names_answers_nothing_for_what_is_not_a_record_instance() -> None:
    """The guard that keeps the helper total, asked directly because nothing else can.

    Both of its callers screen the value first -- ``_diff`` turns a class away
    before it gets here, and ``_equivalence`` classifies every ``type`` as an
    opaque leaf one function earlier -- so no assertion in the library can put
    either of these two values in front of it. The helper is asked directly
    rather than left untested on the strength of that argument, which is the
    same line ``tests/test_datetime.py`` takes with ``_offending_bound``.
    """

    @dataclass
    class Point:
        x: int = 0

    assert dataclass_field_names(Point()) == ("x",)
    assert dataclass_field_names(Point) == ()
    assert dataclass_field_names(object()) == ()
