"""``MappingExpect[K, V]``: both type parameters must survive every hop.

A mapping subject carries two type parameters, and the interesting claim is that
neither is lost on the way through a continuation: ``contains_key`` hands back the
*value* type, ``.and_`` hands back the mapping subject itself, and a user's own
subclass keeps its own identity through inherited assertions.

The views add a second claim of the same kind. ``.keys`` and ``.values`` cross
into another subject entirely, and each has to take exactly one of the two
parameters with it -- a ``.values`` typed ``CollectionExpect[str]`` on a
``dict[str, int]`` would be the easy mistake and a silent one.
"""

from collections.abc import Collection, Mapping
from typing import Self, assert_type

from lovely_assertions import (
    CollectionExpect,
    Expect,
    Found,
    MappingExpect,
    custom_assertion,
    expect,
)


# ---------------------------------------------------------------------------
# Dispatch and the subject itself
# ---------------------------------------------------------------------------
def a_mapping_gets_the_mapping_subject(rows: dict[str, int]) -> None:
    assert_type(expect(rows), MappingExpect[str, int])
    assert_type(expect(rows).subject, Mapping[str, int])


def both_parameters_survive_a_chain(rows: dict[str, int]) -> None:
    assert_type(expect(rows).is_not_empty(), MappingExpect[str, int])
    assert_type(expect(rows).has_length(1).and_.contains_key("a").and_, MappingExpect[str, int])
    assert_type(
        expect(rows).contains_entry("a", 1).and_.does_not_contain_key("b").subject,
        Mapping[str, int],
    )


# ---------------------------------------------------------------------------
# Views: one parameter each, and the collection catalogue behind it
# ---------------------------------------------------------------------------
def each_view_takes_exactly_one_of_the_two_parameters(rows: dict[str, int]) -> None:
    assert_type(expect(rows).keys, CollectionExpect[str])
    assert_type(expect(rows).values, CollectionExpect[int])
    assert_type(expect(rows).keys.subject, Collection[str])
    assert_type(expect(rows).values.subject, Collection[int])


def a_view_is_a_collection_subject_all_the_way_down(rows: dict[str, int]) -> None:
    """Whatever the collection catalogue returns, it returns *the view*."""
    assert_type(expect(rows).keys.contains("a"), CollectionExpect[str])
    assert_type(expect(rows).values.has_unique_items().and_, CollectionExpect[int])
    assert_type(expect(rows).keys.is_subset_of({"a", "b"}), CollectionExpect[str])
    assert_type(expect(rows).values.contains_single(), Found[CollectionExpect[int], int])
    assert_type(expect(rows).keys.contains_match("a*"), CollectionExpect[str])


def a_view_over_a_composite_value_keeps_it_whole(config: dict[str, dict[str, str]]) -> None:
    assert_type(expect(config).values, CollectionExpect[dict[str, str]])
    assert_type(expect(config).values.contains({"host": "local"}), CollectionExpect[dict[str, str]])


# ---------------------------------------------------------------------------
# contains_key: `Found` on the value
# ---------------------------------------------------------------------------
def contains_key_finds_the_value(rows: dict[str, int]) -> None:
    found = expect(rows).contains_key("a")
    assert_type(found, Found[MappingExpect[str, int], int])
    assert_type(found.subject, int)
    assert_type(found.which, Expect[int])
    assert_type(found.whose_value, Expect[int])
    assert_type(found.and_, MappingExpect[str, int])


def whose_value_reads_the_same_as_which(rows: dict[str, str]) -> None:
    assert_type(expect(rows).contains_key("a").whose_value.is_equal_to("b"), Expect[str])
    assert_type(expect(rows).contains_key("a").whose_value.subject, str)


def a_nested_mapping_keeps_its_own_parameters(config: dict[str, dict[str, str]]) -> None:
    """``.whose_value`` widens to ``Expect[V]``; the value type itself is intact.

    It does *not* re-dispatch to ``MappingExpect``: the declared return is
    ``Expect[V]``, which is sound for any ``V``. Re-bind through ``expect()`` to
    get mapping assertions on the inner mapping.
    """
    assert_type(expect(config).contains_key("db").whose_value, Expect[dict[str, str]])
    assert_type(expect(config).contains_key("db").subject, dict[str, str])
    assert_type(expect(expect(config).contains_key("db").subject), MappingExpect[str, str])


# ---------------------------------------------------------------------------
# contains_value: `Found` on the value too
# ---------------------------------------------------------------------------
def contains_value_finds_the_stored_value(rows: dict[str, int]) -> None:
    assert_type(expect(rows).contains_value(1), Found[MappingExpect[str, int], int])
    assert_type(expect(rows).contains_value(1).which.subject, int)
    assert_type(expect(rows).contains_value(1).and_.is_not_empty(), MappingExpect[str, int])


# ---------------------------------------------------------------------------
# The predicate forms: `Found` on what the caller could not name in advance
# ---------------------------------------------------------------------------
def a_predicate_is_typed_by_the_parameter_it_searches(rows: dict[str, int]) -> None:
    """The lambda parameters are inferred, so the bodies below are the proof.

    ``key.startswith`` only resolves if ``key`` came through as ``str``, and
    ``value > 0`` only if ``value`` came through as ``int``.
    """
    assert_type(
        expect(rows).contains_key_matching(lambda key: key.startswith("a")),
        Found[MappingExpect[str, int], str],
    )
    assert_type(
        expect(rows).contains_value_matching(lambda value: value > 0),
        Found[MappingExpect[str, int], int],
    )
    assert_type(
        expect(rows).contains_entry_matching(lambda key, value: bool(key) and value > 0),
        Found[MappingExpect[str, int], tuple[str, int]],
    )


def each_predicate_form_continues_both_ways(rows: dict[str, int]) -> None:
    found_key = expect(rows).contains_key_matching(lambda key: key != "")
    assert_type(found_key.subject, str)
    assert_type(found_key.which, Expect[str])
    assert_type(found_key.and_, MappingExpect[str, int])

    found_entry = expect(rows).contains_entry_matching(lambda key, value: bool(key) and value > 0)
    assert_type(found_entry.subject, tuple[str, int])
    assert_type(found_entry.which, Expect[tuple[str, int]])
    assert_type(found_entry.and_.is_not_empty(), MappingExpect[str, int])


# ---------------------------------------------------------------------------
# Arguments are typed by the subject's parameters
# ---------------------------------------------------------------------------
def arguments_follow_the_key_and_value_types(rows: dict[str, int]) -> None:
    assert_type(expect(rows).contains_keys("a", "b"), MappingExpect[str, int])
    assert_type(expect(rows).does_not_contain_keys("a"), MappingExpect[str, int])
    assert_type(expect(rows).contains_values(1, 2), MappingExpect[str, int])
    assert_type(expect(rows).contains_only_keys("a", "b"), MappingExpect[str, int])
    assert_type(expect(rows).contains_entries({"a": 1}), MappingExpect[str, int])
    assert_type(expect(rows).has_same_length_as([1, 2]), MappingExpect[str, int])


def a_mapping_of_any_shape_is_accepted(rows: Mapping[tuple[int, int], list[str]]) -> None:
    """Keys need not be strings, and values need not be scalars."""
    assert_type(expect(rows), MappingExpect[tuple[int, int], list[str]])
    assert_type(expect(rows).contains_key((1, 2)).subject, list[str])
    assert_type(
        expect(rows).contains_entry((1, 2), ["a"]), MappingExpect[tuple[int, int], list[str]]
    )


def every_plain_assertion_hands_the_subject_back(rows: dict[str, int]) -> None:
    """One chain through every ``Self``-returning assertion.

    Written as a single chain on purpose: each hop is only reachable if the hop
    before it returned the subject, so the one ``assert_type`` at the end is a
    claim about all of them. A method that returned ``Expect[Mapping[str, int]]``
    -- the easy mistake when an override forgets ``Self`` -- breaks it here.
    """
    assert_type(
        expect(rows)
        .is_not_empty()
        .and_.has_length(1)
        .and_.does_not_have_length(2)
        .and_.has_same_length_as([1])
        .and_.does_not_have_same_length_as([1, 2])
        .and_.does_not_contain_key("b")
        .and_.contains_keys("a")
        .and_.does_not_contain_keys("b")
        .and_.contains_only_keys("a")
        .and_.contains_values(1)
        .and_.does_not_contain_values(2)
        .and_.does_not_contain_value(2)
        .and_.contains_entry("a", 1)
        .and_.does_not_contain_entry("b", 2)
        .and_.contains_entries({"a": 1})
        .and_.is_not_none_or_empty()
        .and_.has_length_matching(lambda count: count > 0)
        .and_.has_length_greater_than(0)
        .and_.has_length_greater_than_or_equal_to(1)
        .and_.has_length_less_than(9)
        .and_.has_length_less_than_or_equal_to(9),
        MappingExpect[str, int],
    )
    assert_type(expect(rows).is_empty(), MappingExpect[str, int])
    assert_type(expect(rows).is_none_or_empty(), MappingExpect[str, int])


# ---------------------------------------------------------------------------
# Extension subjects
# ---------------------------------------------------------------------------
class HeadersExpect(MappingExpect[str, str]):
    __slots__ = ()

    @custom_assertion
    def is_json(self, *, because: str = "") -> Self:
        if self._subject.get("content-type") == "application/json":
            return self
        return self._fail(f"to be JSON, but was {self._subject.get('content-type')!r}", because)


def a_subclass_keeps_its_own_identity(headers: dict[str, str]) -> None:
    subject = HeadersExpect(headers)
    assert_type(subject.is_json(), HeadersExpect)
    assert_type(subject.contains_key("accept").and_, HeadersExpect)
    assert_type(subject.contains_key("accept").and_.is_json(), HeadersExpect)
    assert_type(subject.is_not_empty().and_.is_json().subject, Mapping[str, str])
    assert_type(subject.contains_key("accept"), Found[HeadersExpect, str])
    assert_type(subject.contains_key_matching(lambda key: key != ""), Found[HeadersExpect, str])
    assert_type(subject.has_length_greater_than(1), HeadersExpect)


def a_subclass_takes_its_own_views(headers: dict[str, str]) -> None:
    """Both parameters are ``str`` here, so a view that crossed them would pass.

    It is pinned anyway: the claim is that the property reads the subclass's own
    parameters rather than the base class's, and the next subclass will not be
    symmetric.
    """
    subject = HeadersExpect(headers)
    assert_type(subject.keys, CollectionExpect[str])
    assert_type(subject.values, CollectionExpect[str])
    assert_type(subject.keys.contains("accept").and_.has_unique_items(), CollectionExpect[str])
