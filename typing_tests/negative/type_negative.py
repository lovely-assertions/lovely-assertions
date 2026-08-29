"""Every marked line here must be rejected by pyright and mypy.

Without this half, `typing_tests/positive/type_subject.py` proves nothing: a
subject that had quietly collapsed to `Any` would satisfy every `assert_type` in
it. These are the mistakes a class subject exists to catch -- handing an instance
where a class belongs, a name where a type belongs, losing the subject a chain was
called on, and reaching for a catalogue that belongs to some other subject.
"""

from typing import assert_type

from lovely_assertions import CallableExpect, Expect, Found, expect
from lovely_assertions._type import TypeExpect


class Animal: ...


class Bird(Animal): ...


class Order:
    def save(self) -> None: ...


def the_subject_has_to_be_callable() -> None:
    """Inherited from ``CallableExpect``, and a class is the callable this is for."""
    TypeExpect(3)  # expect-error: a class is not an int
    TypeExpect("Order")  # expect-error: a class, not its name


def a_class_is_a_class_not_an_instance_of_one() -> None:
    TypeExpect(Order).is_subclass_of(Animal())  # expect-error: an instance, not a type
    TypeExpect(Order).is_subclass_of("Animal")  # expect-error: a type, not its name
    TypeExpect(Order).is_not_subclass_of(3)  # expect-error
    TypeExpect(Order).implements(Animal())  # expect-error
    TypeExpect(Order).does_not_implement("Closeable")  # expect-error


def a_tuple_of_types_is_an_issubclass_habit() -> None:
    """``issubclass`` takes one; this does not, and the checker has to say so."""
    TypeExpect(Order).is_subclass_of((Animal, Bird))  # expect-error


def attribute_names_are_strings() -> None:
    TypeExpect(Order).has_attribute(3)  # expect-error
    TypeExpect(Order).has_method(b"save")  # expect-error
    TypeExpect(Order).does_not_have_attribute(Order)  # expect-error
    TypeExpect(Order).has_attribute()  # expect-error: the name is required


def because_is_keyword_only() -> None:
    """`because` is keyword-only, on every assertion in the catalogue."""
    TypeExpect(Order).is_subclass_of(Animal, "a reason")  # expect-error
    TypeExpect(Order).is_not_subclass_of(Animal, "a reason")  # expect-error
    TypeExpect(Order).has_attribute("save", "a reason")  # expect-error
    TypeExpect(Order).does_not_have_attribute("save", "a reason")  # expect-error
    TypeExpect(Order).has_method("save", "a reason")  # expect-error
    TypeExpect(Order).is_abstract("a reason")  # expect-error
    TypeExpect(Order).is_not_abstract("a reason")  # expect-error


def the_chain_keeps_the_subject_it_was_called_on() -> None:
    subject = TypeExpect(Order)
    assert_type(subject.is_subclass_of(Animal), CallableExpect)  # expect-error
    assert_type(subject.is_abstract(), Expect[object])  # expect-error
    assert_type(subject.implements(Animal), Found[TypeExpect, object])  # expect-error


def the_finders_hand_back_a_found_not_the_subject() -> None:
    assert_type(TypeExpect(Order).has_attribute("save"), TypeExpect)  # expect-error
    assert_type(TypeExpect(Order).has_method("save"), TypeExpect)  # expect-error


def the_subject_is_not_re_specialised_to_a_type() -> None:
    """A knowing widening: ``.subject`` is what ``CallableExpect`` fixed, not the class."""
    assert_type(TypeExpect(Order).subject, type)  # expect-error
    assert_type(TypeExpect(Order).subject, type[Order])  # expect-error


def other_subjects_catalogues_are_not_here() -> None:
    TypeExpect(Order).has_length(3)  # expect-error: not a sequence subject
    TypeExpect(Order).starts_with("Or")  # expect-error: not a string subject
    TypeExpect(Order).is_positive()  # expect-error: not a numeric subject


def the_explicit_entry_point_is_typed() -> None:
    assert_type(expect(Order, as_=TypeExpect), CallableExpect)  # expect-error
    expect(Order, as_=TypeExpect).is_subclass_of(Animal())  # expect-error
