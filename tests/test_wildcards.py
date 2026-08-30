"""One wildcard dialect, used everywhere it appears.

The wildcard FluentAssertions made familiar appears twice in this catalogue —
``StringExpect.matches_wildcard`` and ``SequenceExpect.contains_match``. Two
implementations means two dialects, and a library that answers a question
differently depending on which subject you asked is worse than one that answers
it badly. Both go through ``_text.matches_wildcard``; these tests are what keeps
that true.
"""

import itertools
import re
import time
from typing import TYPE_CHECKING

import pytest

from lovely_assertions import AssertionFailure, expect
from lovely_assertions._text import _compiled, _translation, matches_wildcard, wildcard_matcher
from lovely_assertions._text._compiled import (
    _MATCHERS,  # pyright: ignore[reportPrivateUsage]
    _MATCHERS_IGNORING_CASE,  # pyright: ignore[reportPrivateUsage]
    _MAX_MATCHERS,  # pyright: ignore[reportPrivateUsage]
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from _pytest.mark import ParameterSet

#: (subject, pattern, should_match). The interesting cases are the characters a
#: regex or a glob would claim and a wildcard must not.
CASES: list[tuple[str, str, bool]] = [
    ("abc", "a*c", True),
    ("abc", "a?c", True),
    ("ac", "a*c", True),
    ("ac", "a?c", False),
    ("abc", "*", True),
    ("", "*", True),
    ("", "?", False),
    ("abc", "abc", True),
    ("abc", "ABC", False),
    # `.` is a full stop, not "any character".
    ("a.c", "a.c", True),
    ("abc", "a.c", False),
    # `[...]` is literal text, not a character class — this is where `fnmatch`
    # and a hand-rolled translation part company.
    ("a[b]c", "a[b]c", True),
    ("abc", "a[b]c", False),
    # Other regex metacharacters are literal too.
    ("a+c", "a+c", True),
    ("a(b)c", "a(b)c", True),
    ("a|c", "a|c", True),
    ("a$", "a$", True),
    # The pattern is anchored to the whole string.
    ("xabcx", "abc", False),
    ("xabcx", "*abc*", True),
    # "any character" includes a newline.
    ("a\nc", "a?c", True),
    ("a\nc", "a*c", True),
]


def _string_matches(subject: str, pattern: str) -> bool:
    try:
        expect(subject).matches_wildcard(pattern)
    except AssertionFailure:
        return False
    return True


def _sequence_matches(subject: str, pattern: str) -> bool:
    try:
        expect([subject]).contains_match(pattern)
    except AssertionFailure:
        return False
    return True


@pytest.mark.parametrize(("subject", "pattern", "expected"), CASES)
def test_string_wildcard(subject: str, pattern: str, expected: bool) -> None:
    assert _string_matches(subject, pattern) is expected


@pytest.mark.parametrize(("subject", "pattern", "expected"), CASES)
def test_sequence_wildcard_agrees_with_string(subject: str, pattern: str, expected: bool) -> None:
    assert _sequence_matches(subject, pattern) is expected


def test_the_two_entry_points_never_disagree() -> None:
    """Stated as one assertion, so a regression names the real problem."""
    disagreements = [
        (subject, pattern)
        for subject, pattern, _ in CASES
        if _string_matches(subject, pattern) != _sequence_matches(subject, pattern)
    ]
    assert not disagreements, (
        f"matches_wildcard and contains_match disagree on {disagreements}. "
        f"They must share one implementation (_text.matches_wildcard)."
    )


def test_ignoring_case_variant_is_case_blind() -> None:
    expect("ABC").matches_wildcard_ignoring_case("a*c")
    with pytest.raises(AssertionFailure):
        expect("ABC").matches_wildcard("a*c")


# -- catastrophic backtracking ---------------------------------------------
#
# Translating every `*` to a bare `.*` is exponential. On a pattern that
# ultimately fails, each of those re-tries every split of the text the next one
# already rejected, so the cost doubles with every wildcard added: ten of them
# over the subject below is already the difference between a millisecond and a
# wait long enough to read as a hang. `_collection.contains_match` pays that per
# item, so a wildcard over a few hundred strings looks less like a slow assertion
# than like an infinite loop in the caller's own code.

#: Forty characters that cannot match, behind a run of wildcards. Nothing here is
#: unusual -- `*` runs turn up in hand-written patterns all the time -- which is
#: what makes the exponential shape dangerous rather than merely academic.
PATHOLOGICAL_SUBJECT: str = "a" * 40

#: A bare run of wildcards. This one is defused by collapsing `**` into `*`
#: alone: it translates to `.*z`, with no interior group left to be atomic about.
COLLAPSING_PATTERN: str = "*" * 10 + "z"

#: The same shape with a literal between every pair of wildcards, so that nothing
#: collapses and every interior `*` becomes a group. This is the pattern that
#: needs the group to be *atomic*, and it is the one a person is likelier to
#: write: `*a*a*...` is what a path or a log-line glob looks like. Dropping the
#: `(?>...)` and leaving `(?:.*?...)` sends this pattern exponential again while
#: `COLLAPSING_PATTERN` stays instant -- so a budget on that pattern alone pins
#: only half of the translation.
INTERLEAVED_PATTERN: str = "*a" * 12 + "z"

#: The third shape, and the quiet one: only *two* wildcards, which is what most
#: hand-written patterns have. Two free `.*` are not exponential -- they are
#: quadratic in the length of the subject -- so this one does not look alarming,
#: and yet `*a*b` over a log line of tens of thousands of characters is a visible
#: wait. It needs the atomic group exactly as much as the twelve-wildcard pattern
#: does, and it is the shape that would tempt someone into "the group is only
#: needed above two stars". Its subject has to be long, because the cost is in
#: the subject here and not in the pattern.
QUADRATIC_SUBJECT: str = "a" * 40_000
QUADRATIC_PATTERN: str = "*a*b"

#: (subject, pattern). All three shapes, so no part of the translation can be
#: dropped unnoticed: the first needs the `**` collapse, the second and third
#: need the atomic group, and the third is the one a person actually writes.
#: Named, because a parametrised id built from a 40,000-character subject is a
#: node id nobody can select on and nobody can read in a report.
PATHOLOGICAL_CASES: "tuple[ParameterSet, ...]" = (
    pytest.param(PATHOLOGICAL_SUBJECT, COLLAPSING_PATTERN, id="a-run-of-bare-wildcards"),
    pytest.param(PATHOLOGICAL_SUBJECT, INTERLEAVED_PATTERN, id="wildcards-around-literals"),
    pytest.param(QUADRATIC_SUBJECT, QUADRATIC_PATTERN, id="two-wildcards-long-subject"),
)

#: Two orders of magnitude above what the atomic translation costs on these
#: patterns (tens of microseconds), and three below what a backtracking one
#: costs. Loaded CI cannot reach it by being slow; an exponential regression
#: cannot miss it by being fast.
_TIME_BUDGET_SECONDS: float = 0.25


@pytest.mark.parametrize(("subject", "pattern"), PATHOLOGICAL_CASES)
def test_a_run_of_wildcards_does_not_backtrack_catastrophically(subject: str, pattern: str) -> None:
    """A real time budget, because what this guards against is purely a cost."""
    started = time.perf_counter()
    matched = matches_wildcard(subject, pattern, ignoring_case=False)
    elapsed = time.perf_counter() - started
    assert matched is False
    assert elapsed < _TIME_BUDGET_SECONDS, (
        f"{pattern!r} against {len(subject)} characters took "
        f"{elapsed:.3f}s, past the {_TIME_BUDGET_SECONDS}s budget. Consecutive `*` must "
        f"collapse into one, AND every `*` but the last must be an *atomic* group -- "
        f"drop either and some pattern shape starts backtracking."
    )


@pytest.mark.parametrize(("subject", "pattern"), PATHOLOGICAL_CASES)
def test_the_string_subject_does_not_backtrack_catastrophically(subject: str, pattern: str) -> None:
    """The same budget through the public entry point, flags and all."""
    wrapped = expect(subject)
    started = time.perf_counter()
    with pytest.raises(AssertionFailure):
        wrapped.matches_wildcard(pattern)
    with pytest.raises(AssertionFailure):
        wrapped.matches_wildcard_ignoring_case(pattern)
    wrapped.does_not_match_wildcard(pattern)
    elapsed = time.perf_counter() - started
    assert elapsed < _TIME_BUDGET_SECONDS, (
        f"StringExpect.matches_wildcard took {elapsed:.3f}s on {pattern!r}; "
        f"the ignoring-case variant must get the same treatment as the plain one"
    )


def test_the_collection_path_does_not_backtrack_either() -> None:
    """`contains_match` pays the cost per item, which is where it hurts most.

    A hundred non-matching strings against `INTERLEAVED_PATTERN` is 200 x the
    single-string cost, counting the `does_not_contain_match` pass that has to
    scan the whole collection even though it succeeds. Multiply a backtracking
    translation by that and the run produces no output at all while it lasts.
    """
    items = [f"{PATHOLOGICAL_SUBJECT}{index}" for index in range(100)]
    subject = expect(items)
    started = time.perf_counter()
    with pytest.raises(AssertionFailure):
        subject.contains_match(INTERLEAVED_PATTERN)
    subject.does_not_contain_match(INTERLEAVED_PATTERN)
    elapsed = time.perf_counter() - started
    assert elapsed < _TIME_BUDGET_SECONDS, (
        f"contains_match over {len(items)} items took {elapsed:.3f}s, past the "
        f"{_TIME_BUDGET_SECONDS}s budget"
    )


# -- equivalence with the obvious translation -------------------------------


def _naive_wildcard(subject: str, pattern: str, *, ignoring_case: bool) -> bool:
    """The obvious translation, kept as the reference answer.

    Every `*` becomes a bare `.*`. It is correct and it is exponential, which is
    exactly why it is useful here: the translation the library ships is allowed
    to change what a pattern *costs* and forbidden to change what it *means*.
    """
    translated: list[str] = []
    for char in pattern:
        if char == "*":
            translated.append(".*")
        elif char == "?":
            translated.append(".")
        else:
            translated.append(re.escape(char))
    flags = re.DOTALL | re.IGNORECASE if ignoring_case else re.DOTALL
    return re.fullmatch("".join(translated), subject, flags) is not None


#: The first of two corpora, and the wide one: leading, trailing, doubled and
#: tripled `*`, `?` next to `*`, the regex metacharacters the dialect keeps
#: literal, and a newline on both sides. It is capped at three characters, which
#: is what buys the alphabet -- see `_LONG_PATTERN_ALPHABET` for the other half.
_PATTERN_ALPHABET: str = "*?ab.[\n"
_SUBJECT_ALPHABET: str = "ab.[\nA"


#: The second corpus trades alphabet for length. Every claim the translation
#: makes about an *interior* `*` needs a pattern with two wildcards and something
#: after the second one to be visible at all -- `*?*?` is the shortest witness,
#: and it is four characters long, so a corpus capped at three cannot see it.
#: Four literal-ish characters and patterns up to five let it.
_LONG_PATTERN_ALPHABET: str = "*?ab"
_LONG_SUBJECT_ALPHABET: str = "ab"


def _words(alphabet: str, longest: int, /) -> list[str]:
    return [
        "".join(letters)
        for length in range(longest + 1)
        for letters in itertools.product(alphabet, repeat=length)
    ]


def _corpus() -> list[tuple[str, str]]:
    """Every (subject, pattern) pair both corpora between them cover."""
    wide = [
        (subject, pattern)
        for pattern in _words(_PATTERN_ALPHABET, 3)
        for subject in _words(_SUBJECT_ALPHABET, 3)
    ]
    deep = [
        (subject, pattern)
        for pattern in _words(_LONG_PATTERN_ALPHABET, 5)
        for subject in _words(_LONG_SUBJECT_ALPHABET, 4)
    ]
    return wide + deep


def test_the_fast_translation_means_exactly_what_the_naive_one_did() -> None:
    """Exhaustive over short patterns, because a subtle shift would be invisible.

    Collapsing `**` into `*` and committing a `*` to the first match it can reach
    are both claims about *equivalence*. They are argued in `_wildcard_source`'s
    docstring; this is the check that the argument is true.

    Two corpora, because one shape of counterexample needs breadth and the other
    needs depth. Swapping the interior group's `.*?` for a greedy `.*` -- which
    commits to the *last* run rather than the first, and is wrong -- shows up
    only from four-character patterns onward, so the short-and-wide corpus alone
    would accept it.
    """
    disagreements = [
        (subject, pattern, ignoring_case)
        for subject, pattern in _corpus()
        for ignoring_case in (False, True)
        if matches_wildcard(subject, pattern, ignoring_case=ignoring_case)
        != _naive_wildcard(subject, pattern, ignoring_case=ignoring_case)
    ]
    assert not disagreements, (
        f"the backtracking-proof translation answers differently from the one it "
        f"replaced on {disagreements[:10]}. Making a wildcard faster must not change "
        f"what it means."
    )


# -- one translation per pattern, not one per subject -----------------------
#
# `CollectionExpect.contains_match` calls `matches_wildcard` once PER ITEM, so a
# translation performed inside the call is performed once per item for a pattern
# that cannot change between them. Remembered in a table and hoisted above the
# loop, a scan of any length translates once -- an order of magnitude off the
# cost of the scan, and roughly five times off a single `matches_wildcard`.
#
# Counted, not timed. A wall-clock budget on a few microseconds of work is a
# flaky test wearing a useful disguise (a loaded machine reaches that honestly),
# while the number of translations is 1 or it is the length of the collection,
# on every machine.


@pytest.fixture
def a_cold_cache() -> "Iterator[None]":
    """Both matcher tables emptied, before and after.

    Emptied *after* as well, because a test that leaves five hundred entries
    behind changes what the next one measures -- and one of these fills the table
    to its bound on purpose.
    """
    _MATCHERS.clear()
    _MATCHERS_IGNORING_CASE.clear()
    yield
    _MATCHERS.clear()
    _MATCHERS_IGNORING_CASE.clear()


def _counting_translations(monkeypatch: pytest.MonkeyPatch) -> "Callable[[], int]":
    """Wrap the translation step and hand back a reader for how often it ran.

    ``_wildcard_source`` is the function to count because every implementation
    goes through it: one that translates inside the call reaches it once per
    subject, and this one reaches it once per pattern. A counter on a step only a
    memoising implementation performs could not go red when the memoisation is
    taken away, which is the regression this exists to catch.
    """
    calls = [0]
    original = _translation.wildcard_source

    def counted(pattern: str, escape: "Callable[[str], str]", /) -> str:
        calls[0] += 1
        return original(pattern, escape)

    monkeypatch.setattr(_compiled, "wildcard_source", counted)
    return lambda: calls[0]


@pytest.mark.usefixtures("a_cold_cache")
def test_a_pattern_is_translated_once_however_many_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One translation per pattern, stated as a count rather than as a duration."""
    translations = _counting_translations(monkeypatch)
    items = [f"item-{index:03d}" for index in range(100)]

    expect(items).does_not_contain_match("nothing-*")

    assert translations() == 1, (
        f"scanning {len(items)} items translated the wildcard {translations()} times. "
        f"The pattern cannot change between items, so it must be translated once and "
        f"the matcher hoisted above the loop."
    )


@pytest.mark.usefixtures("a_cold_cache")
def test_a_pattern_is_translated_once_across_separate_assertions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hoisting covers the collection path; the table is what covers everything else.

    ``StringExpect.matches_wildcard`` has no loop to hoist out of, so the saving
    there is entirely the remembering -- and a suite asserting the same pattern
    over a thousand strings is the ordinary case, not a corner.
    """
    translations = _counting_translations(monkeypatch)

    for subject in ("alpha", "beta", "gamma"):
        expect(subject).does_not_match_wildcard("nothing-*")

    assert translations() == 1


@pytest.mark.usefixtures("a_cold_cache")
def test_a_translated_pattern_is_kept_in_this_library_s_own_table() -> None:
    """Stated against the table rather than against object identity.

    ``wildcard_matcher(p) is wildcard_matcher(p)`` holds whether or not anything
    here remembers anything: ``re.compile`` keeps a cache of its own, so that
    assertion is a test of the standard library. What is being claimed is that
    the *lookup* stops before reaching it.
    """
    matcher = wildcard_matcher("a*c", ignoring_case=False)
    assert {"a*c": matcher} == _MATCHERS
    assert not _MATCHERS_IGNORING_CASE


@pytest.mark.usefixtures("a_cold_cache")
def test_the_two_case_tables_never_hand_out_the_wrong_matcher() -> None:
    """One key, two meanings -- which is the whole reason there are two tables.

    Keying a single table on the pattern alone would make
    ``matches_wildcard_ignoring_case`` answer with whichever variant was asked
    for first. That is a wrong answer, and it is the one a cache of this shape
    fails into.
    """
    sensitive = wildcard_matcher("a*c", ignoring_case=False)
    insensitive = wildcard_matcher("a*c", ignoring_case=True)
    assert sensitive is not insensitive
    assert sensitive.fullmatch("ABC") is None
    assert insensitive.fullmatch("ABC") is not None

    expect("ABC").matches_wildcard_ignoring_case("a*c")
    with pytest.raises(AssertionFailure):
        expect("ABC").matches_wildcard("a*c")


@pytest.mark.usefixtures("a_cold_cache")
def test_the_matcher_table_is_bounded() -> None:
    """A suite that *builds* patterns must not pin one compiled regex per pattern.

    Cleared wholesale rather than evicted one at a time, the way
    ``_subjects._LAZY_ANSWERS`` is: an LRU needs a write on every lookup, and the
    lookup is the thing being made cheap.
    """
    for index in range(_MAX_MATCHERS):
        wildcard_matcher(f"pattern-{index}-*", ignoring_case=False)
    assert len(_MATCHERS) == _MAX_MATCHERS

    wildcard_matcher("one-past-the-bound-*", ignoring_case=False)
    assert len(_MATCHERS) == 1
    assert _MATCHERS_IGNORING_CASE == {}


@pytest.mark.usefixtures("a_cold_cache")
def test_a_remembered_matcher_still_means_what_the_table_says() -> None:
    """The cache is not allowed to be a second dialect.

    ``CASES`` is the contract, and every entry is asked twice: once cold, once
    against the remembered matcher. A table keyed wrongly -- on the pattern
    without the flag, or on the subject by accident -- shows up here as an answer
    that changes on the second ask.
    """
    changed = [
        (subject, pattern)
        for subject, pattern, _ in CASES
        if matches_wildcard(subject, pattern, ignoring_case=False)
        != matches_wildcard(subject, pattern, ignoring_case=False)
    ]
    assert not changed
    disagreements = [
        (subject, pattern)
        for subject, pattern, expected in CASES
        if matches_wildcard(subject, pattern, ignoring_case=False) is not expected
    ]
    assert not disagreements, f"the remembered matcher answers differently on {disagreements}"
