"""Every marked line here must be rejected by pyright and mypy.

These are the mistakes a mapping subject exists to catch: a key or value of the
wrong type, a continuation used as if it were the subject, and a ``.whose_value``
that was assumed to be something it is not.

The views and the predicate forms bring two more. A view must carry *its own*
half of the mapping's parameters -- crossing them would typecheck against nothing
and fail at runtime for everyone -- and an entry predicate takes the key and the
value as two arguments, so the pair spelling that was considered and rejected has
to be rejected by the checkers too.
"""

from collections.abc import Mapping
from typing import assert_type

from lovely_assertions import CollectionExpect, Expect, MappingExpect, expect


def the_subject_is_the_mapping_abc(rows: dict[str, int]) -> None:
    assert_type(expect(rows).subject, dict[str, int])  # expect-error: it is `Mapping[str, int]`


def the_subject_is_not_the_base_class(rows: dict[str, int]) -> None:
    assert_type(expect(rows).is_empty(), Expect[Mapping[str, int]])  # expect-error


def a_key_has_the_mapping_s_key_type(rows: dict[str, int]) -> None:
    expect(rows).contains_key(1)  # expect-error: the keys are `str`


def a_missing_key_check_is_typed_too(rows: dict[str, int]) -> None:
    expect(rows).does_not_contain_key(None)  # expect-error


def variadic_keys_are_typed_one_by_one(rows: dict[str, int]) -> None:
    expect(rows).contains_keys("a", 2)  # expect-error: `2` is not a key of this mapping


def only_keys_is_typed_as_well(rows: dict[str, int]) -> None:
    expect(rows).contains_only_keys(1)  # expect-error


def a_value_has_the_mapping_s_value_type(rows: dict[str, int]) -> None:
    expect(rows).contains_values("one")  # expect-error: the values are `int`


def a_single_value_is_typed_like_the_plural(rows: dict[str, int]) -> None:
    """The singular and plural forms must be equally strict, or one is a hole."""
    expect(rows).contains_value("one")  # expect-error: the values are `int`


def a_negated_value_is_typed_too(rows: dict[str, int]) -> None:
    expect(rows).does_not_contain_value("one")  # expect-error


def an_entry_is_typed_on_both_sides(rows: dict[str, int]) -> None:
    expect(rows).contains_entry("a", "one")  # expect-error


def an_entry_key_is_typed_as_well(rows: dict[str, int]) -> None:
    expect(rows).contains_entry(1, 1)  # expect-error: the keys are `str`


def a_negated_entry_is_typed_on_both_sides(rows: dict[str, int]) -> None:
    expect(rows).does_not_contain_entry("a", "one")  # expect-error


def entries_must_match_the_mapping(rows: dict[str, int]) -> None:
    expect(rows).contains_entries({"a": "one"})  # expect-error


def a_length_is_a_number(rows: dict[str, int]) -> None:
    expect(rows).has_length("2")  # expect-error


def the_other_of_a_length_comparison_must_be_sized(rows: dict[str, int]) -> None:
    expect(rows).has_same_length_as(3)  # expect-error: an `int` has no length


def because_is_keyword_only(rows: dict[str, int]) -> None:
    expect(rows).is_empty("it was just built")  # expect-error: `because` is keyword-only


def found_is_not_the_subject(rows: dict[str, int]) -> None:
    """`.and_` or `.whose_value` is required; `Found` carries no assertions."""
    expect(rows).contains_key("a").has_length(1)  # expect-error


def whose_value_is_the_value_not_the_mapping(rows: dict[str, int]) -> None:
    assert_type(expect(rows).contains_key("a").whose_value, MappingExpect[str, int])  # expect-error


def whose_value_is_typed_by_the_mapping(rows: dict[str, int]) -> None:
    found = expect(rows).contains_key("a")
    assert_type(found.whose_value, Expect[str])  # expect-error: the values are `int`


def a_found_value_is_not_the_mapping(rows: dict[str, int]) -> None:
    assert_type(expect(rows).contains_value(1).subject, Mapping[str, int])  # expect-error


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------
def a_view_is_not_the_mapping(rows: dict[str, int]) -> None:
    assert_type(expect(rows).keys, MappingExpect[str, int])  # expect-error


def the_two_views_are_not_interchangeable(rows: dict[str, int]) -> None:
    """Crossing them is the silent mistake: both are `CollectionExpect`."""
    assert_type(expect(rows).values, CollectionExpect[str])  # expect-error: values are `int`


def the_keys_view_carries_the_key_type(rows: dict[str, int]) -> None:
    expect(rows).keys.contains(1)  # expect-error: the keys are `str`


def the_values_view_carries_the_value_type(rows: dict[str, int]) -> None:
    expect(rows).values.contains("one")  # expect-error: the values are `int`


def a_view_is_a_property_not_a_method(rows: dict[str, int]) -> None:
    """It is a continuation, spelled like `.and_` and `.which`."""
    expect(rows).keys()  # expect-error


def there_is_no_items_view(rows: dict[str, int]) -> None:
    """Deliberately absent: `contains_entry` answers it, and better."""
    expect(rows).items  # expect-error


# ---------------------------------------------------------------------------
# The length family
# ---------------------------------------------------------------------------
def a_length_comparison_takes_a_number(rows: dict[str, int]) -> None:
    expect(rows).has_length_greater_than("2")  # expect-error


def has_length_matching_takes_a_predicate_over_the_count(rows: dict[str, int]) -> None:
    expect(rows).has_length_matching(2)  # expect-error: it is a predicate, not a length


def a_count_predicate_is_given_the_count(rows: dict[str, int]) -> None:
    def by_text(count: str) -> bool:
        return count.isdigit()

    expect(rows).has_length_matching(by_text)  # expect-error: the count is an `int`


def is_none_or_empty_is_keyword_only_too(rows: dict[str, int]) -> None:
    expect(rows).is_none_or_empty("the fixture returned nothing")  # expect-error: keyword-only


# ---------------------------------------------------------------------------
# The predicate forms
# ---------------------------------------------------------------------------
def a_key_predicate_is_given_a_key(rows: dict[str, int]) -> None:
    def by_number(key: int) -> bool:
        return key > 0

    expect(rows).contains_key_matching(by_number)  # expect-error: the keys are `str`


def a_value_predicate_is_given_a_value(rows: dict[str, int]) -> None:
    def by_text(value: str) -> bool:
        return value.isdigit()

    expect(rows).contains_value_matching(by_text)  # expect-error: the values are `int`


def an_entry_predicate_takes_two_arguments_not_a_pair(rows: dict[str, int]) -> None:
    """The pair spelling was considered and rejected; it must not typecheck."""

    def by_pair(entry: tuple[str, int]) -> bool:
        return entry[1] > 0

    expect(rows).contains_entry_matching(by_pair)  # expect-error


def an_entry_predicate_is_given_the_key_first(rows: dict[str, int]) -> None:
    def by_value_then_key(value: int, key: str) -> bool:
        return value > 0 and key != ""

    expect(rows).contains_entry_matching(by_value_then_key)  # expect-error


def a_found_key_is_not_the_mapping(rows: dict[str, int]) -> None:
    found = expect(rows).contains_key_matching(lambda key: key != "")
    assert_type(found.subject, Mapping[str, int])  # expect-error: it is the key


def a_found_entry_is_the_pair_not_the_value(rows: dict[str, int]) -> None:
    found = expect(rows).contains_entry_matching(lambda key, value: key != "" and value > 0)
    assert_type(found.subject, int)  # expect-error: it is the `(key, value)` pair
