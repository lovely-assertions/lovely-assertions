"""The mapping catalogue: ``MappingExpect[K, V]``.

Beyond pass/fail, two message properties are pinned here because they are the
reason the subject exists at all: a lookup that misses names the key it probably
meant, and a *present* key holding the wrong value never reports as a missing
key. Both are the difference between a message that ends the investigation and
one that starts it.
"""

from collections import ChainMap
from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final, cast

import pytest
from benchmarks import blocks_allocated

from lovely_assertions import (
    AssertionFailure,
    CollectionExpect,
    MappingExpect,
    expect,
    soft_assertions,
)
from lovely_assertions._formatting import formatting
from lovely_assertions._occurrence import (
    Occurrence,
    at_least,
    at_most,
    exactly,
    less_than,
    more_than,
    once,
    twice,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

#: An empty mapping needs its element types spelled out; `{}` alone is `dict[?, ?]`.
EMPTY: dict[str, int] = {}


def missing_mapping() -> MappingExpect[str, int]:
    """A subject whose value is ``None`` -- a cast is how one really gets here."""
    return MappingExpect(cast("Mapping[str, int]", None))


def test_expect_on_a_dict_gives_the_mapping_subject() -> None:
    assert isinstance(expect({"a": 1}), MappingExpect)


# ---------------------------------------------------------------------------
# Size
# ---------------------------------------------------------------------------
def test_is_empty_passes_and_chains() -> None:
    subject = expect(EMPTY)
    assert subject.is_empty() is subject


def test_is_empty_shows_the_keys_that_were_there() -> None:
    rows = {"name": "ada", "age": 36}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).is_empty()
    assert str(caught.value) == (
        "Expected rows to be empty, but had 2 entries with keys ['name', 'age']."
    )


def test_is_not_empty() -> None:
    expect({"a": 1}).is_not_empty()
    rows: dict[str, int] = {}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).is_not_empty()
    assert str(caught.value) == "Expected rows not to be empty, but it was."


def test_has_length_reports_both_counts_and_the_keys() -> None:
    rows = {"name": "ada", "age": 36}
    expect(rows).has_length(2)
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).has_length(3)
    assert str(caught.value) == (
        "Expected rows to have 3 entries, but had 2 entries with keys ['name', 'age']."
    )


def test_has_length_says_entry_in_the_singular() -> None:
    """One entry is not "1 entries": the failure messages are the product here."""
    rows = {"name": "ada"}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).has_length(2)
    assert str(caught.value).startswith("Expected rows to have 2 entries, but had 1 entry with")


def test_does_not_have_length() -> None:
    rows = {"name": "ada"}
    expect(rows).does_not_have_length(2)
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).does_not_have_length(1)
    assert str(caught.value) == "Expected rows not to have 1 entry, but it did."


def test_is_none_or_empty_accepts_both_cases() -> None:
    expect(EMPTY).is_none_or_empty()
    subject = missing_mapping()
    assert subject.is_none_or_empty() is subject


def test_is_none_or_empty_shows_what_was_in_there() -> None:
    rows = {"name": "ada", "age": 36}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).is_none_or_empty()
    assert str(caught.value) == (
        "Expected rows to be None or empty, but had 2 entries with keys ['name', 'age']."
    )


def test_is_not_none_or_empty_reports_which_case_it_was() -> None:
    """The message says which of the two happened, because they are different bugs.

    A fixture that returned nothing and one that returned an empty mapping fail
    for different reasons, and only the message can tell the reader which.
    ``missing_mapping()`` is not a call name-recovery recognises, so that subject
    falls back cleanly, exactly as the twin test in ``test_collection.py`` does.
    """
    expect({"a": 1}).is_not_none_or_empty()
    with pytest.raises(AssertionFailure) as caught:
        missing_mapping().is_not_none_or_empty()
    assert str(caught.value) == "Expected the value not to be None or empty, but was None."

    rows: dict[str, int] = {}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).is_not_none_or_empty()
    assert str(caught.value) == "Expected rows not to be None or empty, but was {}."


def test_the_length_family_counts_entries_where_a_collection_counts_items() -> None:
    """Same four comparisons as ``CollectionExpect``, same words, mapping's noun."""
    rows = {"name": "ada", "age": 36}
    expect(rows).has_length_greater_than(1).and_.has_length_greater_than_or_equal_to(2)
    expect(rows).has_length_less_than(3).and_.has_length_less_than_or_equal_to(2)

    with pytest.raises(AssertionFailure) as caught:
        expect(rows).has_length_greater_than(3)
    assert str(caught.value) == (
        "Expected rows to have more than 3 entries, but had 2 entries with keys ['name', 'age']."
    )

    with pytest.raises(AssertionFailure) as caught:
        expect(rows).has_length_greater_than_or_equal_to(3)
    assert str(caught.value) == (
        "Expected rows to have at least 3 entries, but had 2 entries with keys ['name', 'age']."
    )

    with pytest.raises(AssertionFailure) as caught:
        expect(rows).has_length_less_than(2)
    assert str(caught.value) == (
        "Expected rows to have fewer than 2 entries, but had 2 entries with keys ['name', 'age']."
    )

    with pytest.raises(AssertionFailure) as caught:
        expect(rows).has_length_less_than_or_equal_to(1)
    assert str(caught.value) == (
        "Expected rows to have at most 1 entry, but had 2 entries with keys ['name', 'age']."
    )


def test_the_length_family_says_entry_in_the_singular_too() -> None:
    rows = {"name": "ada"}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).has_length_greater_than(1)
    assert str(caught.value) == (
        "Expected rows to have more than 1 entry, but had 1 entry with keys ['name']."
    )


def test_has_length_matching_names_the_predicate() -> None:
    def is_odd(count: int) -> bool:
        return count % 2 == 1

    rows = {"name": "ada", "age": 36}
    expect(rows).has_length_matching(lambda count: count == 2)
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).has_length_matching(is_odd)
    assert str(caught.value) == (
        "Expected rows to have a length matching is_odd, "
        "but had 2 entries with keys ['name', 'age']."
    )


def test_has_length_matching_falls_back_for_a_lambda() -> None:
    rows = {"name": "ada"}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).has_length_matching(lambda count: count > 5)
    assert "to have a length matching the predicate" in str(caught.value)


def test_has_same_length_as_accepts_any_sized_container() -> None:
    rows = {"name": "ada", "age": 36}
    expect(rows).has_same_length_as(["first", "second"])
    expect(rows).has_same_length_as({"other": 1, "keys": 2})
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).has_same_length_as([1, 2, 3])
    assert str(caught.value) == (
        "Expected rows to have as many entries as [1, 2, 3], but had 2 entries against 3."
    )


def test_does_not_have_same_length_as() -> None:
    rows = {"name": "ada", "age": 36}
    expect(rows).does_not_have_same_length_as([1])
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).does_not_have_same_length_as([1, 2])
    assert str(caught.value) == (
        "Expected rows not to have as many entries as [1, 2], but both had 2 entries."
    )


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------
def test_the_views_are_collection_subjects_over_the_live_view() -> None:
    """No copy: the wrapper holds ``dict.keys()`` / ``dict.values()`` themselves."""
    rows = {"name": "ada", "age": 36}
    keys = expect(rows).keys
    values = expect(rows).values
    assert isinstance(keys, CollectionExpect)
    assert isinstance(values, CollectionExpect)
    assert keys.subject == rows.keys()
    assert list(values.subject) == list(rows.values())


def test_a_view_brings_the_whole_collection_catalogue_with_it() -> None:
    """The point of handing back ``CollectionExpect`` rather than re-declaring.

    The keys are asked the questions the mapping catalogue does not answer --
    subset, wildcard match -- rather than ``has_unique_items``, which cannot fail
    on keys and is exactly the vacuity the missing ``items`` view is refused for.
    """
    rows = {"name": "ada", "nickname": "ada"}
    expect(rows).keys.is_subset_of({"name", "nickname", "age"}).and_.contains_match("n*")
    expect(rows).values.all_are_instance_of(str)
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).values.has_unique_items()
    assert str(caught.value) == (
        "Expected rows to have unique items, but 'ada' appeared again: ['ada', 'ada']."
    )


def test_a_failure_through_a_view_still_names_the_mapping() -> None:
    """``.keys`` is an attribute, not a call, so the one ``expect(...)`` still wins."""
    rows = {"name": "ada", "age": 36}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).keys.contains("id")
    assert str(caught.value) == "Expected rows to contain 'id', but was ['name', 'age']."


def test_a_view_carries_an_explicit_name_across() -> None:
    """A name the caller gave on purpose must not be dropped by a step sideways."""
    rows = {"name": "ada"}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).described_as("payload").values.contains("bob")
    assert str(caught.value) == "Expected payload to contain 'bob', but was ['ada']."


def test_a_view_chains_on_itself_not_on_the_mapping() -> None:
    """``.and_`` after a view is the view. Going back to the mapping means saying so."""
    rows = {"name": "ada"}
    keys = expect(rows).keys
    assert keys.contains("name").and_ is keys


def test_there_is_deliberately_no_items_view() -> None:
    """The decision, pinned rather than left to be rediscovered.

    ``contains_entry`` answers what an items view would be asked -- and answers it
    better, naming the value the key actually held. Uniqueness over pairs cannot
    fail, because keys are unique. The one case left over is still one call away,
    and it lands on the same subject a property would have returned.
    """
    rows = {"name": "ada"}
    assert not hasattr(expect(rows), "items")
    assert isinstance(expect(rows.items()), CollectionExpect)


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------
def test_contains_key_continues_on_the_value() -> None:
    rows = {"name": "ada", "age": 36}
    assert expect(rows).contains_key("name").subject == "ada"
    assert expect(rows).contains_key("name").whose_value.subject == "ada"
    assert expect(rows).contains_key("name").which.subject == "ada"


def test_contains_key_goes_back_to_the_mapping_with_and() -> None:
    rows = {"name": "ada", "age": 36}
    subject = expect(rows)
    assert subject.contains_key("name").and_ is subject
    assert subject.contains_key("name").and_.contains_key("age").subject == 36


def test_contains_key_hands_on_the_stored_value_for_further_assertions() -> None:
    rows = {"name": "ada"}
    with pytest.raises(AssertionFailure, match="to equal 'bob', but was 'ada'"):
        expect(rows).contains_key("name").whose_value.is_equal_to("bob")


def test_contains_key_lists_the_keys_that_are_present() -> None:
    rows = {"name": "ada", "age": 36}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_key("email")
    assert str(caught.value) == (
        "Expected rows to contain key 'email', but the keys were ['name', 'age']."
    )


def test_contains_key_suggests_a_near_spelling() -> None:
    """A typo is the common case, so the message answers it rather than hinting."""
    rows = {"name": "ada", "age": 36}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_key("nmae")
    assert str(caught.value) == (
        "Expected rows to contain key 'nmae' (did you mean 'name'?), "
        "but the keys were ['name', 'age']."
    )


def test_contains_key_suggests_nothing_when_nothing_is_close() -> None:
    rows = {"name": "ada", "age": 36}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_key("zzzzzz")
    assert "did you mean" not in str(caught.value)


def test_contains_key_does_not_guess_at_non_string_keys() -> None:
    codes = {1: "one", 2: "two"}
    with pytest.raises(AssertionFailure) as caught:
        expect(codes).contains_key(3)
    assert str(caught.value) == "Expected codes to contain key 3, but the keys were [1, 2]."


def test_a_large_mapping_is_previewed_not_dumped() -> None:
    """Ten keys, then a count. A message nobody reads is a message that failed."""
    rows = {f"k{index}": index for index in range(14)}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_key("missing")
    message = str(caught.value)
    assert message.endswith(
        "the keys were ['k0', 'k1', 'k2', 'k3', 'k4', 'k5', 'k6', 'k7', 'k8', 'k9', ... 4 more]."
    )


def test_the_preview_boundary_is_exactly_the_limit() -> None:
    """Ten keys are all shown; the eleventh is what turns the list into a count."""
    ten = {f"k{index}": index for index in range(10)}
    with pytest.raises(AssertionFailure) as caught:
        expect(ten).contains_key("missing")
    assert str(caught.value).endswith(
        "the keys were ['k0', 'k1', 'k2', 'k3', 'k4', 'k5', 'k6', 'k7', 'k8', 'k9']."
    )

    eleven = {f"k{index}": index for index in range(11)}
    with pytest.raises(AssertionFailure) as caught:
        expect(eleven).contains_key("missing")
    assert str(caught.value).endswith(
        "the keys were ['k0', 'k1', 'k2', 'k3', 'k4', 'k5', 'k6', 'k7', 'k8', 'k9', ... 1 more]."
    )


def test_does_not_contain_key_shows_the_value_it_found() -> None:
    rows = {"name": "ada"}
    expect(rows).does_not_contain_key("email")
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).does_not_contain_key("name")
    assert str(caught.value) == "Expected rows not to contain key 'name', but it held 'ada'."


def test_contains_keys_reports_only_the_missing_ones() -> None:
    rows = {"name": "ada", "age": 36}
    expect(rows).contains_keys("name", "age")
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_keys("name", "email", "id")
    assert str(caught.value) == (
        "Expected rows to contain keys ['name', 'email', 'id'], "
        "but was missing ['email', 'id']; the keys were ['name', 'age']."
    )


def test_does_not_contain_keys_reports_only_the_ones_found() -> None:
    rows = {"name": "ada"}
    expect(rows).does_not_contain_keys("email", "id")
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).does_not_contain_keys("name", "id")
    assert str(caught.value) == (
        "Expected rows not to contain keys ['name', 'id'], but found ['name']."
    )


def test_contains_only_keys_ignores_order_and_repeats() -> None:
    rows = {"name": "ada", "age": 36}
    expect(rows).contains_only_keys("age", "name")
    expect(rows).contains_only_keys("name", "age", "name")


def test_contains_only_keys_names_the_surplus() -> None:
    rows = {"name": "ada", "age": 36}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_only_keys("name")
    assert str(caught.value) == (
        "Expected rows to contain only the keys ['name'], but also had ['age']."
    )


def test_contains_only_keys_names_what_is_missing() -> None:
    rows = {"name": "ada", "age": 36}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_only_keys("name", "age", "email")
    assert str(caught.value) == (
        "Expected rows to contain only the keys ['name', 'age', 'email'], "
        "but was missing ['email']."
    )


def test_contains_only_keys_names_both_when_both_happen() -> None:
    rows = {"name": "ada", "age": 36}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_only_keys("name", "email")
    assert str(caught.value) == (
        "Expected rows to contain only the keys ['name', 'email'], "
        "but was missing ['email'] and also had ['age']."
    )


def test_contains_key_matching_hands_back_the_key_it_found() -> None:
    """The caller did not know which key matched; that is what earns a ``Found``."""
    rows = {"db_host": "local", "port": "5432"}
    found = expect(rows).contains_key_matching(lambda key: key.startswith("db_"))
    assert found.subject == "db_host"
    assert found.which.subject == "db_host"
    assert found.and_.has_length(2).subject is rows


def test_contains_key_matching_names_the_predicate_and_lists_the_keys() -> None:
    def is_secret(key: str) -> bool:
        return key.startswith("secret_")

    rows = {"name": "ada", "age": "36"}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_key_matching(is_secret)
    assert str(caught.value) == (
        "Expected rows to contain a key matching is_secret, but the keys were ['name', 'age']."
    )


def test_contains_key_matching_falls_back_for_a_lambda() -> None:
    rows = {"name": "ada"}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_key_matching(lambda key: key == "id")
    assert "to contain a key matching the predicate" in str(caught.value)


# ---------------------------------------------------------------------------
# Values
# ---------------------------------------------------------------------------
def test_contains_value_continues_on_the_value() -> None:
    rows = {"name": "ada", "nickname": "ada"}
    assert expect(rows).contains_value("ada").subject == "ada"
    assert expect(rows).contains_value("ada").which.subject == "ada"
    assert expect(rows).contains_value("ada").and_.has_length(2).subject is rows


def test_contains_value_hands_on_the_stored_object_not_the_argument() -> None:
    """They compare equal; only the stored one is worth asserting against."""
    stored = [1, 2]
    rows = {"items": stored}
    assert expect(rows).contains_value([1, 2]).subject is stored


def test_contains_value_lists_the_values_that_are_there() -> None:
    rows = {"name": "ada", "age": 36}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_value("bob")
    assert str(caught.value) == (
        "Expected rows to contain value 'bob', but the values were ['ada', 36]."
    )


def test_does_not_contain_value_names_the_key_that_held_it() -> None:
    rows = {"name": "ada", "age": 36}
    expect(rows).does_not_contain_value("bob")
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).does_not_contain_value("ada")
    assert str(caught.value) == (
        "Expected rows not to contain value 'ada', but key 'name' held it."
    )


def test_contains_values_reports_only_the_missing_ones() -> None:
    rows = {"name": "ada", "age": 36}
    expect(rows).contains_values("ada", 36)
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_values("ada", "bob")
    assert str(caught.value) == (
        "Expected rows to contain values ['ada', 'bob'], but was missing ['bob']; "
        "the values were ['ada', 36]."
    )


def test_does_not_contain_values_reports_only_the_ones_found() -> None:
    rows = {"name": "ada", "age": 36}
    expect(rows).does_not_contain_values("bob", 99)
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).does_not_contain_values("ada", 99)
    assert str(caught.value) == (
        "Expected rows not to contain values ['ada', 99], but found ['ada']."
    )


def test_contains_value_matching_hands_back_the_first_match() -> None:
    rows = {"a": 1, "b": 20, "c": 30}
    found = expect(rows).contains_value_matching(lambda value: value > 5)
    assert found.subject == 20
    assert found.and_.has_length(3).subject is rows


def test_contains_value_matching_lists_the_values() -> None:
    def is_negative(value: int) -> bool:
        return value < 0

    rows = {"a": 1, "b": 2}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_value_matching(is_negative)
    assert str(caught.value) == (
        "Expected rows to contain a value matching is_negative, but the values were [1, 2]."
    )


# ---------------------------------------------------------------------------
# Entries
# ---------------------------------------------------------------------------
def test_contains_entry_passes_and_chains() -> None:
    subject = expect({"name": "ada"})
    assert subject.contains_entry("name", "ada") is subject


def test_contains_entry_says_the_key_was_present_with_another_value() -> None:
    """ "Key missing" and "key holds something else" are different bugs.

    So they read differently: the present-key failure names the value that key
    actually held, which is the next thing the reader would have gone to look up.
    """
    rows = {"name": "ada", "age": 36}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_entry("name", "bob")
    assert str(caught.value) == (
        "Expected rows to contain entry 'name': 'bob', but that key held 'ada'."
    )


def test_contains_entry_says_so_when_the_key_is_absent() -> None:
    rows = {"name": "ada", "age": 36}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_entry("email", "ada@example.com")
    assert str(caught.value) == (
        "Expected rows to contain entry 'email': 'ada@example.com', but the key was missing; "
        "the keys were ['name', 'age']."
    )


def test_contains_entry_suggests_a_near_spelling_for_the_missing_key() -> None:
    rows = {"name": "ada", "age": 36}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_entry("nmae", "ada")
    assert "but the key was missing (did you mean 'name'?)" in str(caught.value)


def test_contains_entry_holding_none_is_still_a_present_key() -> None:
    """A stored ``None`` must not read as an absent key."""
    rows: dict[str, int | None] = {"total": None}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_entry("total", 0)
    assert str(caught.value) == (
        "Expected rows to contain entry 'total': 0, but that key held None."
    )


def test_does_not_contain_entry() -> None:
    rows = {"name": "ada"}
    expect(rows).does_not_contain_entry("name", "bob")
    expect(rows).does_not_contain_entry("email", "ada")
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).does_not_contain_entry("name", "ada")
    assert str(caught.value) == (
        "Expected rows not to contain entry 'name': 'ada', but it was there."
    )


def test_contains_entries_accepts_a_subset() -> None:
    subject = expect({"name": "ada", "age": 36})
    assert subject.contains_entries({"name": "ada"}) is subject


def test_contains_entries_separates_missing_keys_from_wrong_values() -> None:
    rows = {"name": "ada", "age": 36}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_entries({"name": "bob", "email": "ada@example.com"})
    assert str(caught.value) == (
        "Expected rows to contain entries {'name': 'bob', 'email': 'ada@example.com'}, "
        "but was missing ['email'] and 'name' held 'ada' instead of 'bob'."
    )


def test_contains_entries_reports_wrong_values_alone_when_nothing_is_missing() -> None:
    rows = {"name": "ada", "age": 36}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_entries({"name": "bob", "age": 7})
    assert str(caught.value).endswith(
        "but 'name' held 'ada' instead of 'bob', 'age' held 36 instead of 7."
    )


def test_contains_entries_previews_what_it_was_asked_for() -> None:
    """The echo of the expectation obeys the cap too, or the diff scrolls away."""
    rows = {f"k{index}": index for index in range(30)}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_entries({**rows, "missing": 1})
    assert str(caught.value) == (
        "Expected rows to contain entries "
        "{'k0': 0, 'k1': 1, 'k2': 2, 'k3': 3, 'k4': 4, 'k5': 5, 'k6': 6, 'k7': 7, "
        "'k8': 8, 'k9': 9, ... 21 more}, but was missing ['missing']."
    )


def test_contains_entry_matching_takes_the_key_and_the_value_apart() -> None:
    """Two arguments, not one pair: the same spelling ``contains_entry`` uses.

    A pair form would have to be written ``lambda entry: entry[0]...``, since
    Python 3 has no tuple parameter unpacking -- indexing a tuple inside a test
    predicate being exactly what this library exists to replace.
    """
    rows = {"db_host": "local", "db_port": ""}
    found = expect(rows).contains_entry_matching(
        lambda key, value: key.startswith("db_") and not value
    )
    assert found.subject == ("db_port", "")
    assert found.which.subject == ("db_port", "")
    assert found.and_.has_length(2).subject is rows


def test_contains_entry_matching_previews_the_entries() -> None:
    def is_blank(key: str, value: object) -> bool:
        return bool(key) and value == ""

    rows: dict[str, object] = {"name": "ada", "age": 36}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_entry_matching(is_blank)
    assert str(caught.value) == (
        "Expected rows to contain an entry matching is_blank, "
        "but the entries were {'name': 'ada', 'age': 36}."
    )


def test_contains_entry_matching_caps_the_preview_like_every_other_message() -> None:
    rows = {f"k{index}": index for index in range(14)}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_entry_matching(lambda key, value: bool(key) and value > 100)
    assert str(caught.value).endswith(
        "but the entries were {'k0': 0, 'k1': 1, 'k2': 2, 'k3': 3, 'k4': 4, 'k5': 5, "
        "'k6': 6, 'k7': 7, 'k8': 8, 'k9': 9, ... 4 more}."
    )


def test_every_predicate_form_hands_back_the_first_match() -> None:
    """First in iteration order, for all three -- the documented contract.

    Worth its own case because only ``contains_value_matching`` otherwise has a
    subject with two matches behind it: an implementation that returned the
    *last* match would pass every other test in this file, keys and entries
    included.
    """
    rows = {"db_host": "local", "db_port": "5432", "db_name": "app"}
    matching_key = expect(rows).contains_key_matching(lambda key: key.startswith("db_"))
    assert matching_key.subject == "db_host"
    matching_value = expect(rows).contains_value_matching(lambda value: value != "")
    assert matching_value.subject == "local"
    matching_entry = expect(rows).contains_entry_matching(
        lambda key, value: key != "" and value != ""
    )
    assert matching_entry.subject == ("db_host", "local")


# ---------------------------------------------------------------------------
# Containment follows Python's own rule: identity first, then equality
# ---------------------------------------------------------------------------
def test_a_value_that_is_not_equal_to_itself_is_still_in_the_mapping() -> None:
    """``in`` and ``dict.__eq__`` both try identity before equality; so does this.

    ``float("nan") != float("nan")``, so a subject comparing with ``==`` alone
    calls a value the mapping demonstrably holds *absent* -- and has
    ``contains_value`` contradict ``contains_values`` on the same argument, and
    ``contains_entry`` contradict the inherited ``is_equal_to`` on the same data.
    """
    nan = float("nan")
    rows = {"score": nan}
    assert nan in rows.values()  # the rule being followed, straight from Python
    assert rows == {"score": nan}

    subject = expect(rows)
    subject.contains_value(nan)
    subject.contains_values(nan)
    subject.contains_entry("score", nan)
    subject.contains_entries({"score": nan})
    subject.is_equal_to({"score": nan})


def test_the_negations_agree_that_such_a_value_is_there() -> None:
    """The plural and singular forms must not answer the same question differently."""
    nan = float("nan")
    rows = {"score": nan}
    with pytest.raises(AssertionFailure, match="not to contain value nan"):
        expect(rows).does_not_contain_value(nan)
    with pytest.raises(AssertionFailure, match=r"not to contain values \[nan\]"):
        expect(rows).does_not_contain_values(nan)
    with pytest.raises(AssertionFailure, match="not to contain entry 'score': nan"):
        expect(rows).does_not_contain_entry("score", nan)


def test_a_different_value_that_is_not_equal_to_itself_is_still_absent() -> None:
    """Identity-first is not "anything goes": another NaN is another value."""
    rows = {"score": float("nan")}
    other = float("nan")
    with pytest.raises(AssertionFailure, match="to contain value nan"):
        expect(rows).contains_value(other)
    with pytest.raises(AssertionFailure, match="but that key held nan"):
        expect(rows).contains_entry("score", other)
    expect(rows).does_not_contain_value(other)
    expect(rows).does_not_contain_entry("score", other)


# ---------------------------------------------------------------------------
# Occurrences: how many keys hold the value
# ---------------------------------------------------------------------------
#: Two keys holding "failed" and one holding "ok". A ``dict`` keeps insertion
#: order, so the preview in an asserted message is stable.
STATUSES: Final = {"first": "failed", "second": "failed", "third": "ok"}

#: One NaN, reused. Two NaNs are two values, and that difference is the whole of
#: the identity-first rule this module follows.
NAN: Final = float("nan")

#: A deliberately untyped door to the subject, so a call that is *meant* to be
#: wrong needs no suppression -- one spelling for mypy and another for pyright is
#: how a test file fills up with noise. ``tests/test_formatting.py`` does the same.
UNTYPED: Any = MappingExpect


class Between:
    """A user's own occurrence constraint: ``Occurrence`` is a structural protocol.

    Two methods and no base class is the whole of what it asks for.
    """

    __slots__ = ("_high", "_low")

    def __init__(self, low: int, high: int, /) -> None:
        self._low = low
        self._high = high

    def allows(self, count: int, /) -> bool:
        return self._low <= count <= self._high

    def describe(self) -> str:
        return "between " + str(self._low) + " and " + str(self._high) + " times"


def counted(rows: "Mapping[str, object]", value: object, constraint: Occurrence, /) -> bool:
    """Whether ``contains_value`` held under a constraint.

    ``occurrences`` is keyword-only on purpose, so a table-driven comparison needs
    a spelling of its own.
    """
    try:
        expect(rows).contains_value(value, occurrences=constraint)
    except AssertionFailure:
        return False
    return True


#: Each constraint against a count of **two**, with the answer it owes.
COUNTED_TWICE: Final = [
    pytest.param(exactly(2), True, id="exactly-2"),
    pytest.param(exactly(3), False, id="exactly-3"),
    pytest.param(at_least(2), True, id="at_least-2"),
    pytest.param(at_least(3), False, id="at_least-3"),
    pytest.param(at_most(2), True, id="at_most-2"),
    pytest.param(at_most(1), False, id="at_most-1"),
    pytest.param(more_than(1), True, id="more_than-1"),
    pytest.param(more_than(2), False, id="more_than-2"),
    pytest.param(less_than(3), True, id="less_than-3"),
    pytest.param(less_than(2), False, id="less_than-2"),
    pytest.param(once, False, id="once"),
    pytest.param(twice, True, id="twice"),
]


def test_no_constraint_leaves_contains_value_exactly_as_it_was() -> None:
    """An unconstrained call is the default branch: same lookup, same message."""
    rows = {"name": "ada", "age": 36}
    assert expect(rows).contains_value("ada").subject == "ada"
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_value("bob")
    assert str(caught.value) == (
        "Expected rows to contain value 'bob', but the values were ['ada', 36]."
    )


def test_contains_value_counts_the_keys_that_hold_it() -> None:
    statuses = STATUSES
    expect(statuses).contains_value("failed", occurrences=twice)
    expect(statuses).contains_value("ok", occurrences=once)
    expect(statuses).contains_value("pending", occurrences=exactly(0))


def test_the_constrained_failure_names_the_constraint_and_the_count() -> None:
    statuses = STATUSES
    with pytest.raises(AssertionFailure) as caught:
        expect(statuses).contains_value("failed", occurrences=exactly(3))
    assert str(caught.value) == (
        "Expected statuses to contain value 'failed' exactly 3 times,"
        " but found 2: ['failed', 'failed', 'ok']."
    )


@pytest.mark.parametrize(("constraint", "holds"), COUNTED_TWICE)
def test_every_shipped_constraint_is_asked_about_the_count(
    constraint: Occurrence, holds: bool
) -> None:
    assert counted(STATUSES, "failed", constraint) is holds


def test_distinct_keys_holding_equal_values_each_count() -> None:
    """The count is of keys, not of one object: ``1``, ``1.0`` and ``True`` all equal ``1``."""
    rows = {"int": 1, "float": 1.0, "bool": True}
    expect(rows).contains_value(1, occurrences=exactly(3))
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_value(1, occurrences=once)
    assert str(caught.value) == (
        "Expected rows to contain value 1 exactly once, but found 3: [1, 1.0, True]."
    )


def test_a_nan_is_counted_where_it_actually_is() -> None:
    """Identity first, then equality -- the rule the section above pins for the plain form.

    Counting by equality alone would report zero occurrences of a value the
    mapping demonstrably holds, and have ``contains_value(nan)`` and
    ``contains_value(nan, occurrences=more_than(0))`` disagree about one mapping.
    """
    same = {"a": NAN, "b": NAN}
    other = {"a": float("nan")}
    expect(same).contains_value(NAN, occurrences=twice)
    expect(same).contains_value(NAN)
    expect(other).contains_value(NAN, occurrences=exactly(0))
    with pytest.raises(AssertionFailure, match="to contain value nan"):
        expect(other).contains_value(NAN)


def test_the_count_and_the_unconstrained_form_never_disagree() -> None:
    """Two spellings of one question must not have two answers."""
    rows: dict[str, object] = {"a": 1, "b": NAN, "c": "ada"}
    for value in (1, NAN, "ada", float("nan"), 9, "bob"):
        try:
            expect(rows).contains_value(value)
        except AssertionFailure:
            present = False
        else:
            present = True
        assert present is counted(rows, value, more_than(0)), value


def test_the_continuation_is_still_the_first_stored_match() -> None:
    """The constrained branch keeps the promise the plain one makes.

    They compare equal; only the stored object is worth asserting against.
    """
    stored = [1, 2]
    rows = {"first": stored, "second": [1, 2]}
    found = expect(rows).contains_value([1, 2], occurrences=twice)
    assert found.subject is stored
    assert found.and_.subject is rows


def test_a_constraint_satisfied_by_no_match_continues_on_what_was_asked_for() -> None:
    """The one wrinkle of one return type for both branches, stated rather than hidden.

    ``at_most(0)`` holds precisely when nothing matched, so there is no stored
    value to hand on. The alternatives -- a ``Found`` over a sentinel, or a second
    return type for one assertion -- are worse than handing back the argument.
    """
    rows = {"a": 1}
    found = expect(rows).contains_value(9, occurrences=at_most(0))
    assert found.subject == 9
    assert found.and_.subject is rows


def test_a_user_written_constraint_is_accepted_and_read_back() -> None:
    constraint: Occurrence = Between(1, 2)
    statuses = STATUSES
    expect(statuses).contains_value("failed", occurrences=constraint)
    with pytest.raises(AssertionFailure) as caught:
        expect(statuses).contains_value("ok", occurrences=Between(2, 3))
    assert str(caught.value) == (
        "Expected statuses to contain value 'ok' between 2 and 3 times,"
        " but found 1: ['failed', 'failed', 'ok']."
    )


def test_the_constraint_is_keyword_only() -> None:
    """Positionally it would read as a second value to look for."""
    with pytest.raises(TypeError):
        UNTYPED({"a": 1}).contains_value(1, once)


def test_because_reaches_the_constrained_form() -> None:
    """The ``because`` table below calls the unconstrained branch; this is the other."""
    with pytest.raises(AssertionFailure, match="because R"):
        expect(STATUSES).contains_value("failed", occurrences=once, because="R")


def test_a_constrained_failure_absorbs_its_chain_in_a_soft_scope() -> None:
    """It narrows, so a failure has no value to continue on (``_fail_narrowing``)."""
    statuses = STATUSES
    with soft_assertions() as scope:
        expect(statuses).contains_value("failed", occurrences=once).which.is_equal_to("ok")
        messages = scope.discard()
    assert messages == [
        (
            "Expected statuses to contain value 'failed' exactly once,"
            " but found 2: ['failed', 'failed', 'ok']."
        )
    ]


def test_a_passing_constrained_assertion_allocates_nothing_extra() -> None:
    """A passing assertion allocates nothing: counting is a loop, not a generator expression.

    Measured against the *unconstrained* call rather than against a no-op, because
    this assertion hands back a ``Found`` either way. The claim under test is that
    counting adds nothing to that.
    """
    subject = expect(STATUSES)
    plain = blocks_allocated(lambda: subject.contains_value("failed"))
    counting = blocks_allocated(lambda: subject.contains_value("failed", occurrences=twice))
    assert counting <= plain
    assert counting <= blocks_allocated(lambda: None)


# ---------------------------------------------------------------------------
# Any Mapping, not just dict
# ---------------------------------------------------------------------------
def test_a_read_only_mapping_is_a_mapping() -> None:
    rows = MappingProxyType({"name": "ada"})
    expect(rows).contains_entry("name", "ada").and_.has_length(1)
    with pytest.raises(AssertionFailure, match="to contain key 'email'"):
        expect(rows).contains_key("email")


def test_a_chain_map_is_a_mapping() -> None:
    rows = ChainMap({"name": "ada"}, {"nickname": "ada"})
    expect(rows).contains_keys("name", "nickname").and_.has_length(2)


def test_the_views_work_on_a_mapping_that_is_not_a_dict() -> None:
    """``ChainMap`` hands back an abstract ``KeysView``, not ``dict_keys``."""
    chained = ChainMap({"name": "ada"}, {"nickname": "ada"})
    expect(chained).keys.has_unique_items().and_.has_length(2)
    expect(chained).values.contains("ada")

    proxy = MappingProxyType({"name": "ada"})
    expect(proxy).keys.contains("name")
    with pytest.raises(AssertionFailure) as caught:
        expect(proxy).values.contains("bob")
    assert str(caught.value) == "Expected proxy to contain 'bob', but was ['ada']."


# ---------------------------------------------------------------------------
# Soft scopes
# ---------------------------------------------------------------------------
def test_a_soft_scope_collects_every_mapping_failure() -> None:
    rows = {"name": "ada"}
    with soft_assertions("payload") as scope:
        expect(rows).is_empty()
        expect(rows).contains_key("email")
        messages = scope.discard()
    assert len(messages) == 2
    assert all(message.startswith("Expected payload/rows ") for message in messages)


def test_a_missing_key_absorbs_the_rest_of_its_chain() -> None:
    """One root cause, one message: the value that was never found cannot be wrong too."""
    rows = {"name": "ada"}
    with soft_assertions() as scope:
        expect(rows).contains_key("email").whose_value.is_equal_to("ada@example.com")
        messages = scope.discard()
    assert len(messages) == 1
    assert "to contain key 'email'" in messages[0]


def test_every_finding_assertion_absorbs_its_chain_the_same_way() -> None:
    """The three predicate forms narrow too, so they get the same treatment."""
    rows = {"name": "ada"}
    with soft_assertions() as scope:
        expect(rows).contains_key_matching(lambda key: key == "id").which.is_equal_to("x")
        expect(rows).contains_value_matching(lambda value: value == "bob").which.is_equal_to("x")
        expect(rows).contains_entry_matching(lambda key, value: key == value).which.is_equal_to(())
        messages = scope.discard()
    assert len(messages) == 3
    assert [message.partition(" matching")[0] for message in messages] == [
        "Expected rows to contain a key",
        "Expected rows to contain a value",
        "Expected rows to contain an entry",
    ]


# ---------------------------------------------------------------------------
# because reaches all of them
# ---------------------------------------------------------------------------
#: Every assertion this subject declares, called so that it fails, with a reason.
#: Kept as a named table rather than inline in the decorator so the coverage guard
#: below can compare it against the class.
BECAUSE_CALLS: Final = [
    pytest.param(lambda: expect({"a": 1}).is_empty(because="R"), id="is_empty"),
    pytest.param(lambda: expect(EMPTY).is_not_empty(because="R"), id="is_not_empty"),
    pytest.param(lambda: expect({"a": 1}).is_none_or_empty(because="R"), id="is_none_or_empty"),
    pytest.param(
        lambda: expect(EMPTY).is_not_none_or_empty(because="R"), id="is_not_none_or_empty"
    ),
    pytest.param(lambda: expect({"a": 1}).has_length(2, because="R"), id="has_length"),
    pytest.param(
        lambda: expect({"a": 1}).has_length_matching(lambda n: n > 1, because="R"),
        id="has_length_matching",
    ),
    pytest.param(
        lambda: expect({"a": 1}).has_length_greater_than(2, because="R"),
        id="has_length_greater_than",
    ),
    pytest.param(
        lambda: expect({"a": 1}).has_length_greater_than_or_equal_to(2, because="R"),
        id="has_length_greater_than_or_equal_to",
    ),
    pytest.param(
        lambda: expect({"a": 1}).has_length_less_than(1, because="R"),
        id="has_length_less_than",
    ),
    pytest.param(
        lambda: expect({"a": 1}).has_length_less_than_or_equal_to(0, because="R"),
        id="has_length_less_than_or_equal_to",
    ),
    pytest.param(
        lambda: expect({"a": 1}).does_not_have_length(1, because="R"),
        id="does_not_have_length",
    ),
    pytest.param(
        lambda: expect({"a": 1}).has_same_length_as([], because="R"), id="has_same_length_as"
    ),
    pytest.param(
        lambda: expect({"a": 1}).does_not_have_same_length_as([2], because="R"),
        id="does_not_have_same_length_as",
    ),
    pytest.param(lambda: expect({"a": 1}).contains_key("b", because="R"), id="contains_key"),
    pytest.param(
        lambda: expect({"a": 1}).does_not_contain_key("a", because="R"),
        id="does_not_contain_key",
    ),
    pytest.param(lambda: expect({"a": 1}).contains_keys("b", because="R"), id="contains_keys"),
    pytest.param(
        lambda: expect({"a": 1}).does_not_contain_keys("a", because="R"),
        id="does_not_contain_keys",
    ),
    pytest.param(
        lambda: expect({"a": 1}).contains_only_keys("b", because="R"), id="contains_only_keys"
    ),
    pytest.param(lambda: expect({"a": 1}).contains_value(2, because="R"), id="contains_value"),
    pytest.param(
        lambda: expect({"a": 1}).does_not_contain_value(1, because="R"),
        id="does_not_contain_value",
    ),
    pytest.param(lambda: expect({"a": 1}).contains_values(2, because="R"), id="contains_values"),
    pytest.param(
        lambda: expect({"a": 1}).does_not_contain_values(1, because="R"),
        id="does_not_contain_values",
    ),
    pytest.param(lambda: expect({"a": 1}).contains_entry("a", 2, because="R"), id="contains_entry"),
    pytest.param(
        lambda: expect({"a": 1}).does_not_contain_entry("a", 1, because="R"),
        id="does_not_contain_entry",
    ),
    pytest.param(
        lambda: expect({"a": 1}).contains_entries({"b": 2}, because="R"), id="contains_entries"
    ),
    pytest.param(
        lambda: expect({"a": 1}).contains_key_matching(lambda k: k == "b", because="R"),
        id="contains_key_matching",
    ),
    pytest.param(
        lambda: expect({"a": 1}).contains_value_matching(lambda v: v == 2, because="R"),
        id="contains_value_matching",
    ),
    pytest.param(
        lambda: expect({"a": 1}).contains_entry_matching(
            lambda k, v: k == "b" and v == 2, because="R"
        ),
        id="contains_entry_matching",
    ),
]


@pytest.mark.parametrize("call", BECAUSE_CALLS)
def test_because_reaches_every_assertion(call: object) -> None:
    with pytest.raises(AssertionFailure, match="because R"):
        call()  # type: ignore[operator]  # pyright: ignore[reportCallIssue]


def test_the_because_table_has_not_fallen_behind_the_catalogue() -> None:
    """A new assertion must arrive with its ``because`` case, or this fails.

    ``vars()`` rather than ``dir()``: the inherited half of the surface belongs to
    ``Expect`` and has its own tests. The views are excluded by construction --
    they are ``property`` objects, not callables, and a continuation takes no
    reason because it reports nothing.
    """
    covered = {parameters.id for parameters in BECAUSE_CALLS}
    declared = {
        name
        for name, attribute in vars(MappingExpect).items()
        if not name.startswith("_") and callable(attribute)
    }
    assert covered == declared


# ---------------------------------------------------------------------------
# A passing assertion never reaches the failure path, for this subject
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("no_failure_machinery")
def test_no_passing_mapping_assertion_touches_the_failure_path() -> None:
    """Every assertion here, in its passing case, with the failure path booby-trapped.

    ``tests/test_happy_path.py`` runs this trap over the base subject and parses
    the whole library for eagerly built messages. Neither half looks at whether
    *this* module's assertions route a passing call through ``_fail``, read the
    scope ``ContextVar`` or resolve a subject name. This does.

    The trap itself is ``conftest``'s, and it patches every module the package
    has rather than a named few, so a message built in a module nobody thought
    of is still caught.
    """
    rows = {"name": "ada", "age": 36}
    subject = expect(rows)
    subject.is_not_empty()
    expect(EMPTY).is_empty()
    subject.is_not_none_or_empty()
    expect(EMPTY).is_none_or_empty()
    subject.has_length(2)
    subject.does_not_have_length(3)
    subject.has_length_matching(lambda count: count == 2)
    subject.has_length_greater_than(1)
    subject.has_length_greater_than_or_equal_to(2)
    subject.has_length_less_than(3)
    subject.has_length_less_than_or_equal_to(2)
    subject.has_same_length_as([1, 2])
    subject.does_not_have_same_length_as([1])
    subject.contains_key("name")
    subject.does_not_contain_key("email")
    subject.contains_keys("name", "age")
    subject.does_not_contain_keys("email")
    subject.contains_only_keys("name", "age")
    subject.contains_value("ada")
    subject.does_not_contain_value("bob")
    subject.contains_values("ada", 36)
    subject.does_not_contain_values("bob")
    subject.contains_entry("name", "ada")
    subject.does_not_contain_entry("name", "bob")
    subject.contains_entries({"name": "ada"})
    subject.contains_key_matching(lambda key: key == "name")
    subject.contains_value_matching(lambda value: value == "ada")
    subject.contains_entry_matching(lambda key, value: key == "name" and value == "ada")
    subject.keys.contains("name")
    subject.values.contains("ada")
    expect(STATUSES).contains_value("failed", occurrences=twice)


# ---------------------------------------------------------------------------
# How much a failure prints (lovely_assertions._formatting)
# ---------------------------------------------------------------------------
#: Fifteen entries -- more than the default ten -- so every preview in this
#: module has something to elide. A ``dict`` keeps insertion order, so where it
#: elides is fixed.
MANY: Final = {str(number): number for number in range(15)}


def test_the_key_preview_is_capped_by_default() -> None:
    rows = MANY
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).is_empty()
    assert str(caught.value) == (
        "Expected rows to be empty, but had 15 entries with keys"
        " ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', ... 5 more]."
    )


def test_widening_max_items_prints_more_keys() -> None:
    """The point of the option, proved from outside the library.

    Ten keys is right for a message being skimmed and exactly wrong for the one
    being debugged -- the key that matters is as likely to be the fifteenth.
    """
    rows = MANY
    with formatting(max_items=15), pytest.raises(AssertionFailure) as caught:
        expect(rows).is_empty()
    assert str(caught.value) == (
        "Expected rows to be empty, but had 15 entries with keys"
        " ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14']."
    )


def test_narrowing_max_items_prints_fewer_keys() -> None:
    rows = MANY
    with formatting(max_items=2), pytest.raises(AssertionFailure) as caught:
        expect(rows).is_empty()
    assert str(caught.value) == (
        "Expected rows to be empty, but had 15 entries with keys ['0', '1', ... 13 more]."
    )


def test_the_value_preview_follows_the_same_option() -> None:
    rows = MANY
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_value(99)
    assert "... 5 more]" in str(caught.value)
    with formatting(max_items=15), pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_value(99)
    assert str(caught.value).endswith("13, 14].")


def test_the_entry_preview_follows_it_too() -> None:
    """``contains_entries`` echoes what it was asked for, capped the same way."""
    rows = MANY
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_entries({"missing": 99})
    assert "to contain entries {'missing': 99}" in str(caught.value)
    with formatting(max_items=15), pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_entries(dict.fromkeys(MANY, 99))
    message = str(caught.value)
    assert "'14': 99}" in message
    assert "more}" not in message


def test_the_listing_of_differing_entries_is_capped_by_the_same_bound() -> None:
    """The clause that names every key holding the wrong value is a listing too."""
    rows = MANY
    wrong = dict.fromkeys(MANY, 99)
    with pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_entries(wrong)
    assert "... 5 more" in str(caught.value)
    with formatting(max_items=15), pytest.raises(AssertionFailure) as caught:
        expect(rows).contains_entries(wrong)
    assert "more" not in str(caught.value)


def test_a_scope_changes_what_is_printed_and_never_what_is_decided() -> None:
    rows = MANY
    for limit in (1, 500):
        with formatting(max_items=limit):
            expect(rows).contains_key("3").and_.does_not_contain_key("99")
            with pytest.raises(AssertionFailure):
                expect(rows).contains_key("99")


def test_a_view_carries_the_option_across() -> None:
    """``.keys`` and ``.values`` are collection subjects; the bound reaches them too."""
    rows = MANY
    with formatting(max_items=15), pytest.raises(AssertionFailure) as caught:
        expect(rows).values.contains(99)
    assert str(caught.value).endswith("13, 14].")


def test_an_open_scope_costs_a_passing_assertion_nothing() -> None:
    """A passing assertion allocates nothing, and the option must not change that.

    ``tests/test_performance_invariants.py`` measures this outside a scope; what
    it cannot see is a scope putting a ``ContextVar`` read on the hot path.
    """
    baseline = blocks_allocated(lambda: None)
    subject = expect({"a": 1, "b": 2})
    with formatting(max_items=100):
        assert blocks_allocated(lambda: subject.contains_key("a")) <= baseline
        assert blocks_allocated(subject.is_not_empty) <= baseline
        assert blocks_allocated(lambda: subject.has_length(2)) <= baseline


# ---------------------------------------------------------------------------
# A mapping whose two promises disagree
# ---------------------------------------------------------------------------
class Overcounted(Mapping[str, int]):
    """A mapping whose ``__len__`` claims more than iterating it hands over.

    ``__len__`` and ``__iter__`` are two separate promises, and a mapping backed
    by something counted separately from what it yields -- a cached row count, a
    query that has since narrowed -- can break the pair without meaning to. The
    library has no say in that; what it has a say in is whether a failure
    message survives it.
    """

    __slots__ = ()

    def __getitem__(self, key: str) -> int:
        return 1

    def __iter__(self) -> "Iterator[str]":
        return iter(("alpha", "beta"))

    def __len__(self) -> int:
        return 30


def test_a_mapping_that_over_counts_its_keys_is_still_previewed() -> None:
    """The listing stops when the keys run out, not when the count says it should.

    The count decides *whether* to truncate; only the iteration decides what is
    printed. Reading the count as a promise about how many items will arrive
    would raise ``StopIteration`` from inside the message the reader was about
    to be shown -- turning a plain assertion failure into a crash in the
    library.
    """
    settings = Overcounted()

    with pytest.raises(AssertionFailure) as caught:
        expect(settings).is_empty()

    assert str(caught.value) == (
        "Expected settings to be empty, but had 30 entries"
        " with keys ['alpha', 'beta', ... 20 more]."
    )
