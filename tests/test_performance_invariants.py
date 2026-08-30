"""The performance claims that hold on any machine.

Timings belong in ``benchmarks/``, not here: a wall-clock assertion in CI is a
flaky test wearing a useful disguise. What is asserted here are the claims that
do not depend on how fast the machine is —

*A passing assertion allocates nothing.* A passing assertion is a comparison and
a ``return self``. That is measurable, and it is measured three ways, because
"allocates nothing" is three claims that fail independently:

    *nothing is built and thrown away* — the peak bytes held during a single call
    must not exceed what the assertion's own work requires, or the library is
    formatting a message on the happy path;

    *no bytes are retained* — the traced bytes still held when the calls are over
    must not move relative to a no-op, or the library is leaking;

    *no blocks are retained* — the same claim counted in objects rather than
    bytes, which is the number that says "one allocation per assertion".

Each of the three is blind to a violation one of the others catches, and the
blind spots are demonstrated by planting the violation rather than argued about.
``blocks_allocated`` is a before/after count of *live* blocks, so a discarded
f-string is back on the free list before the count is taken and reads as exactly
zero: ``_ = f"{expected!r}"`` on the happy path of ``Expect.is_equal_to`` moves
neither retention measurement. And counting *blocks* misses a leak that stores
something that already exists — a registry appending the subject to a
module-level list grows by a reference per call with the block count sitting
exactly on the baseline and the peak reading zero.
``test_the_three_measurements_see_three_different_bugs`` plants both violations
and pins all six answers, so neither blind spot can come back unannounced.

*Importing the library is cheap.* Not to a millisecond — to an order of
magnitude. The failure this catches is a dependency creeping in, or a module-level
import of something heavy, and either one moves the number far enough that a
generous bound still catches it.

``tests/test_happy_path.py`` covers the same ground from two other sides, and the
three are complementary rather than redundant. Its booby trap proves the failure
machinery is never *called*. Its AST passes prove that no message-shaped
expression — an f-string, a ``%``, a ``+ repr(...)``, a ``.join`` — is evaluated
while the assertion could still pass.

Those two read the source; this one reads the allocator, and that is the whole of
the difference. A syntactic check has to enumerate the forms it knows, and covers
exactly those: a message assembled by a form nobody added to the list is a message
it cannot see. Allocation has no forms to enumerate. It also catches what is not
message-building at all and so is out of scope for either pass — a helper that
builds a list on the way past, a ``sorted()`` copy taken to answer a question a
scan would have answered, a memo that fills up once per subject.

**The whole surface is measured here, not a sample.** One assertion per subject
class is cheap and it is not enough: a message formatted on a happy path is
written where it is written, and a sample catches it only if the sample happens
to include that assertion. So every entry in ``tests/_happy_calls.py`` — the same
table ``tests/test_happy_path.py`` points its detonator at — gets one parametrized
test of its own, for well under a second of fixture.

What that costs is honesty about what "allocates nothing" means. Read against a
reference that runs the same call with the assertion itself removed, most
assertions allocate literally zero; the rest do not, and almost none of those are
doing anything wrong — a ``for`` loop allocates its iterator, a ``stat`` allocates
a ``stat_result``, ``str.lower()`` copies. Every one of them is named, measured
and reasoned about in :data:`_ALLOCATES_BY_DESIGN`. The hand-written references
below stay, because they are the one measurement here that does not depend on a
stand-in.
"""

import enum
import statistics
import subprocess
import sys
import tempfile
import warnings
from collections.abc import Awaitable
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from functools import partial
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final, NamedTuple
from unittest.mock import Mock

import pytest
from benchmarks import CALLS as _CALLS
from benchmarks import (
    blocks_allocated,
    bytes_retained,
    measuring_peaks,
    peak_bytes_allocated,
)

import lovely_assertions
from _happy_calls import HAPPY_CALLS, SUBJECT_CLASSES, World, declared_by_the_subject
from conftest import measured
from lovely_assertions import Expect, MockExpect, expect, expect_raises, expect_warns

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

REPO_ROOT: Final = Path(__file__).resolve().parent.parent

#: An order of magnitude above what the library actually costs. This is not a
#: budget to optimise against -- it is the line past which something is wrong that
#: no amount of tuning explains.
_IMPORT_BUDGET_MS: Final = 60.0


def _nothing() -> None:
    """The reference for an assertion whose work is genuinely free."""


# ---------------------------------------------------------------------------
# Retention: nothing is kept
# ---------------------------------------------------------------------------
def test_a_passing_assertion_retains_nothing() -> None:
    """A passing assertion keeps nothing: the half a within-call peak cannot see.

    The subject is built once and reused, because building it is an allocation by
    construction — the claim is about the *assertion*, not about the wrapper.

    Retention is what the within-call peak cannot see: an object the assertion
    *holds on to* raises that peak by no more than its own size once, while this
    number moves further on every call. A ``Found`` that outlives the call, a memo
    of formatted strings, a cache keyed on the subject — all of them show up here.

    Asserted in both units, and the second one is not decoration. A registry that
    appends the subject to a module-level list leaks a reference per call and
    creates no object at all: the list's pointer array is reallocated in place, so
    the *block* count does not move and only the byte count does.
    """
    blocks_baseline = blocks_allocated(_nothing)
    bytes_baseline = bytes_retained(_nothing)
    subject = expect(3)
    assert blocks_allocated(lambda: subject.is_equal_to(3)) <= blocks_baseline
    assert bytes_retained(lambda: subject.is_equal_to(3)) <= bytes_baseline


@measured
def test_chaining_does_not_allocate_either() -> None:
    """``.and_`` returns ``self``; it must not build anything to do it."""
    baseline = blocks_allocated(_nothing)
    peak_baseline = peak_bytes_allocated(_nothing)
    subject = expect(3)

    def chained() -> object:
        return subject.is_equal_to(3).and_.is_not_equal_to(4)

    assert blocks_allocated(chained) <= baseline
    assert peak_bytes_allocated(chained) <= peak_baseline


# ---------------------------------------------------------------------------
# Transience: nothing is built and thrown away
# ---------------------------------------------------------------------------
@measured
def test_a_passing_assertion_builds_nothing_it_throws_away() -> None:
    """A passing assertion builds no message: measured rather than asserted in prose.

    The number this compares against is not an estimate with slack in it. A
    passing ``is_equal_to`` peaks at exactly zero traced bytes, on every call, on
    every run — so does the no-op — and the smallest message the library could
    build and discard is a two-digit repr at seventy-odd bytes. There is no
    overlap to be careful about.
    """
    baseline = peak_bytes_allocated(_nothing)
    subject = expect(3)
    assert peak_bytes_allocated(lambda: subject.is_equal_to(3)) <= baseline


class _Case(NamedTuple):
    """One assertion, and the bare-Python work it is entitled to cost.

    ``reference`` is the point. Most assertions are free and reference
    :func:`_nothing`, which makes the claim the strict one: this call allocated
    nothing at all. A few are not free, and for those the honest claim is not
    "nothing" but *nothing on top of the work the assertion exists to do* —
    ``PathExpect.is_file`` has to make a ``stat`` call, and a ``stat_result`` is
    hundreds of bytes on any platform.

    Writing that as a hardcoded byte budget would be guessing at another
    machine's ``stat_result``, and a guess in CI is a flake. Running the bare
    operation and measuring it is not a guess: it self-calibrates, and it fails
    the moment the library adds a single byte of its own on top.

    The obvious way to cheat this is to write a reference that does more than the
    assertion does. ``why`` exists so that a reviewer can see what is being
    conceded and object to it; every non-free case has to say out loud what it is
    paying for.
    """

    label: str
    assertion: "Callable[[], object]"
    reference: "Callable[[], object]"
    why: str


class _Colour(enum.Enum):
    RED = "red"


def _holds_text(issued: "Sequence[object]", text: str, /) -> bool:
    """The bare-Python half of ``WarnedExpect.with_message_containing``."""
    for warning in issued:  # noqa: SIM110  (a generator expression would allocate)
        if text in str(warning):
            return True
    return False


def _returns_none() -> object:
    """A callable subject for ``CallableExpect`` that does nothing at all.

    Annotated ``-> object`` rather than ``-> None`` so that the reference below
    can run the same ``isinstance`` the library runs. Against a declared ``None``
    pyright answers the check at type level and reports it as unnecessary, which
    would leave the reference measuring a check that never happened.
    """
    return None


def _boom() -> None:
    """Raise, from a function rather than inline.

    ``raise`` written straight into an ``expect_raises`` block leaves mypy calling
    everything after the block unreachable, so the rest of the file does it this
    way too.
    """
    message = "boom"
    raise ValueError(message)


#: A real file that is certain to exist while this module is running.
_A_REAL_FILE: Final = Path(__file__).resolve()

_A_DECIMAL: Final = Decimal("1.50")


def _every_subject() -> list[_Case]:
    """One assertion per exported subject class, defined *on* that class.

    **This table is not the coverage; the sweep below is.** One assertion per
    class cannot answer for the class: a ``subject = list(self._subject)`` in
    ``SequenceExpect.starts_with_sequence`` allocates on every passing call, and a
    sample that happens to exercise some other sequence assertion never sees it.

    What this table does is the part the sweep cannot. Every reading in the sweep
    is taken against a *stand-in* — the same call with the assertion replaced by
    something that returns and does nothing — so it measures the assertion's own
    allocation and has to be told, per assertion, when that allocation is the
    work rather than waste. These cases are measured against a hand-written
    reference that does the work in bare Python instead: ``PathExpect.is_file``
    against ``Path.is_file``, ``OrderedExpect.is_positive`` against
    ``decimal > 0``. That is a stricter claim than the sweep makes on any row it
    records, and it depends on nothing being patched.

    ``reference`` is the point of it. Most cases are free and reference
    :func:`_nothing`, which makes the claim the strict one: this call allocated
    nothing at all. The handful that are not free say out loud what they are
    paying for, so a reviewer can object to it.

    The methods are chosen to be defined on the class itself rather than
    inherited — ``test_every_exported_subject_class_is_covered`` enforces it —
    because an inherited method would measure ``Expect`` once per subject class
    and the subject families themselves not at all.
    """
    with expect_raises(ValueError) as caught:
        _boom()

    flag = expect(True)
    call = expect(_returns_none)
    items = expect(frozenset({1, 2, 3}))
    day = expect(date(2024, 1, 1))
    moment = expect(datetime(2024, 1, 1, 12, 0, tzinfo=UTC))
    colour = expect(_Colour.RED)
    anything = expect(object())
    rows = expect({"a": 1, "b": 2})
    mock = expect(Mock(), as_=MockExpect)
    number = expect(5.5)
    amount = expect(_A_DECIMAL)
    file = expect(_A_REAL_FILE)
    pure = expect(PurePosixPath("/etc/hosts.conf"))
    sequence = expect([1, 2, 3])
    text = expect("hello")
    span = expect(timedelta(seconds=5))
    clock = expect(time(0, 0))
    klass = expect(bool)
    with expect_warns(UserWarning) as warned:
        warnings.warn("parse() is deprecated since 2.0", UserWarning, stacklevel=2)

    return [
        _Case("BoolExpect.is_true", flag.is_true, _nothing, ""),
        _Case(
            "CallableExpect.does_not_raise",
            call.does_not_raise,
            lambda: isinstance(_returns_none(), Awaitable),
            "the happy path calls the subject and then asks "
            "`isinstance(result, Awaitable)` -- the guard that stops an `async def` "
            "passing without ever running -- and an isinstance against an ABC "
            "allocates inside `abc`. The reference is those two steps and nothing "
            "else, so the library still has to add zero on top",
        ),
        _Case("CollectionExpect.contains", lambda: items.contains(2), _nothing, ""),
        _Case("DateExpect.is_weekday", day.is_weekday, _nothing, ""),
        _Case("DateTimeExpect.has_timezone", lambda: moment.has_timezone(UTC), _nothing, ""),
        _Case("EnumExpect.has_name", lambda: colour.has_name("RED"), _nothing, ""),
        _Case("Expect.is_not_none", anything.is_not_none, _nothing, ""),
        _Case("MappingExpect.contains_entry", lambda: rows.contains_entry("a", 1), _nothing, ""),
        _Case("MockExpect.was_not_called", mock.was_not_called, _nothing, ""),
        _Case("NumericExpect.is_not_nan", number.is_not_nan, _nothing, ""),
        _Case(
            "OrderedExpect.is_positive",
            amount.is_positive,
            lambda: _A_DECIMAL > 0,
            "comparing a Decimal to an int coerces, and the coercion is Decimal's "
            "allocation rather than the library's",
        ),
        _Case(
            "PathExpect.is_file",
            file.is_file,
            _A_REAL_FILE.is_file,
            "a filesystem assertion has to touch the filesystem, and a stat_result "
            "is several hundred bytes on any platform",
        ),
        _Case("PurePathExpect.has_name", lambda: pure.has_name("hosts.conf"), _nothing, ""),
        _Case("RaisedExpect.has_no_notes", caught.has_no_notes, _nothing, ""),
        _Case(
            "SequenceExpect.does_not_contain", lambda: sequence.does_not_contain(9), _nothing, ""
        ),
        _Case("StringExpect.starts_with", lambda: text.starts_with("he"), _nothing, ""),
        _Case(
            "WarnedExpect.with_message_containing",
            lambda: warned.with_message_containing("deprecated"),
            lambda: _holds_text(warned.subject, "deprecated"),
            "walks the captured warnings looking for the text, and a `for` over a "
            "tuple allocates its iterator. The reference is that same walk written "
            "out, so what is conceded is the iterator and nothing else",
        ),
        _Case("TimeDeltaExpect.is_positive", span.is_positive, _nothing, ""),
        _Case("TimeExpect.is_midnight", clock.is_midnight, _nothing, ""),
        _Case("TypeExpect.is_subclass_of", lambda: klass.is_subclass_of(int), _nothing, ""),
    ]


@measured
def test_no_assertion_on_any_subject_builds_anything_it_throws_away() -> None:
    """The transient claim, measured against work rather than against a stand-in.

    One assertion per subject class, each against a reference written by hand to
    do the same bare-Python work. The sweep over the whole table is the coverage;
    this is the calibration. A stand-in reference can only ever say "the assertion
    allocated this much more than nothing", which is why every recorded row there
    needs a reason written beside it; a reference that runs the ``stat`` says "the
    assertion allocated nothing the ``stat`` did not", which is the claim the
    library actually makes.

    It is also the one measurement in this file that patches nothing. If the
    stand-in ever stopped being a fair reference -- if replacing a method changed
    what the rest of the call allocates -- these rows would still be right, and
    the disagreement would show up as one of them failing while its row in the
    sweep passed.
    """
    for case in _every_subject():
        allowed = peak_bytes_allocated(case.reference)
        peaked = peak_bytes_allocated(case.assertion)
        entitled = f" (entitled to {allowed} for: {case.why})" if case.why else ""
        assert peaked <= allowed, (
            f"{case.label} peaked at {peaked} bytes against {allowed} for its reference"
            f"{entitled}. A passing assertion is a comparison and a `return self`; "
            f"a message is built in the failure branch only."
        )


def test_no_assertion_on_any_subject_retains_anything() -> None:
    """The retention claim over the same table, for the leak the peak cannot see.

    In both units, because a leak that stores an object which already exists moves
    the byte count and not the block count. Neither measurement is entitled to a
    reference the way the peak is: an assertion is allowed to *spend* memory doing
    real work, and never allowed to keep it.
    """
    blocks_baseline = blocks_allocated(_nothing)
    bytes_baseline = bytes_retained(_nothing)
    for case in _every_subject():
        allocated = blocks_allocated(case.assertion)
        assert allocated <= blocks_baseline, (
            f"{case.label} retained {allocated - blocks_baseline} blocks over {_CALLS} "
            f"passing calls; a passing assertion is a comparison and a `return self`."
        )
        held = bytes_retained(case.assertion)
        assert held <= bytes_baseline, (
            f"{case.label} retained {held - bytes_baseline} bytes over {_CALLS} passing "
            f"calls; a passing assertion is a comparison and a `return self`. "
            f"A leak that keeps a reference to something that already exists moves this "
            f"number and not the block count."
        )


def _calls_the_method_it_names(
    assertion: "Callable[[], object]", function: object, method_name: str, /
) -> bool:
    """Does ``assertion`` actually reach the method its ``_Case`` is filed under?

    Without this the label is a comment. Every other check in this file reads it
    -- the coverage set, the inheritance check, every failure message -- and none
    of them looks at what the callable does, so the way to make a failing row go
    green is to replace its callable and leave the label alone. Swapping
    ``StringExpect.starts_with``'s callable for ``_nothing`` leaves every other
    test in this file passing, the coverage test that exists to prevent exactly
    this drift included.

    Two shapes are accepted because the table uses two. A bound method is checked
    by identity against the function found in the class ``__dict__``, which is
    exact. A ``lambda`` is checked by looking for the method's name among the
    attributes its code object loads, which is not exact -- a lambda could name
    the method and call something else besides -- but it does catch the case that
    matters, a callable that no longer mentions the method at all.
    """
    own = getattr(assertion, "__func__", None)
    if own is not None:
        return own is function
    code = getattr(assertion, "__code__", None)
    return code is not None and method_name in code.co_names


def test_every_exported_subject_class_is_covered() -> None:
    """The table is a sample; it must not silently become an outdated one.

    Derived from ``__all__`` rather than written down, so a subject class added
    tomorrow fails here by name instead of quietly widening the gap.

    The method is also required to be defined on the class it is filed under.
    Without that, a case could satisfy this test with ``is_not_none`` and measure
    ``Expect`` one more time instead of the family it claims to cover.
    """
    exported = {
        name
        for name in lovely_assertions.__all__
        if isinstance(getattr(lovely_assertions, name), type)
        and issubclass(getattr(lovely_assertions, name), Expect)
    }
    covered = {case.label.split(".", 1)[0] for case in _every_subject()}
    assert covered == exported, (
        f"subject classes with no allocation case: {sorted(exported - covered)}; "
        f"cases naming a class that is not exported: {sorted(covered - exported)}"
    )

    inherited: list[str] = []
    unrelated: list[str] = []
    for case in _every_subject():
        class_name, method_name = case.label.split(".", 1)
        subject_class: type = getattr(lovely_assertions, class_name)
        # A subject is assembled from one mixin per seam, so its own dictionary
        # holds nothing. What counts as its own is what its seams declare, which
        # stops at the first base a *different* subject also has.
        defined: dict[str, object] = declared_by_the_subject(subject_class)
        if method_name not in defined:
            inherited.append(case.label)
        elif not _calls_the_method_it_names(case.assertion, defined[method_name], method_name):
            unrelated.append(case.label)
    assert not inherited, (
        f"these cases call a method the class inherits rather than defines: {inherited}. "
        f"Pick one that exercises the subject, or the case measures Expect again."
    )
    assert not unrelated, (
        f"these cases do not call the method their label names: {unrelated}. "
        f"The label is what every other check in this file trusts; a case whose "
        f"callable has drifted away from it measures nothing and says so nowhere."
    )


# ---------------------------------------------------------------------------
# Transience, over the whole public surface
#
# The table above samples one assertion per subject class, which is a calibration
# and not a coverage claim: a violation sits in whichever method it was written
# into, and a sample only finds it by luck. What follows is every entry in
# `tests/_happy_calls.py` -- the same calls `tests/test_happy_path.py` points its
# detonator at -- measured one assertion at a time, in well under a second.
# ---------------------------------------------------------------------------
type _Key = tuple[str, str]

#: Calls per reading, and calls discarded before it. Far below
#: ``benchmarks.PEAK_CALLS``, because this sweep takes two readings per assertion
#: rather than one reading in total, and because the peak is an exact high-water
#: mark rather than a sample -- the repetitions exist only to catch an allocation
#: that happens *sometimes*. Checked rather than picked: raising both fivefold
#: multiplies the runtime and reports, to the byte, the same readings.
_SWEEP_CALLS: Final = 100
_SWEEP_WARMUP: Final = 50

#: Independent passes, of which the *smallest* reading counts. The noise in this
#: instrument is one-sided: memory freed during a measured call lowers the total
#: the peak is read against and so *inflates* the reading, while nothing deflates
#: it. Repeated sweeps of the whole table move at most one reading --
#: ``DateTimeExpect.is_utc``'s reference, by a few bytes at a time -- and a second
#: pass is what keeps a stray handful of bytes from failing a build.
_SWEEP_PASSES: Final = 2

#: How far a recorded cost may move before the bound complains, as a multiple.
#:
#: Without a ceiling, an entry in :data:`_ALLOCATES_BY_DESIGN` asserts only that
#: the assertion still allocates *something*, so a row recorded at sixty-four
#: bytes could grow to sixty-four thousand in silence. That is the shape of a real
#: regression, not a hypothetical one: an assertion that quietly starts building
#: and dropping a full difference report on its passing branch stays exempt at
#: what a pair of integers costs while holding orders of magnitude more.
#:
#: **Doubling rather than the byte, because the instrument drifts and the bugs do
#: not.** A handful of these readings move by two to six bytes between CPython
#: patch levels, and the two ``CallableExpect.raises`` rows move by fourteen per
#: cent, because the size of an exception and its traceback is the runtime's
#: business rather than this library's. Every regression worth the name is an
#: order of magnitude away from that, so a factor of two clears the drift several
#: times over and still catches one.
_MAY_NOT_DOUBLE: Final = 2

#: The interpreter every byte in :data:`_ALLOCATES_BY_DESIGN` was measured on.
#:
#: The claim this file exists to make -- *a passing assertion allocates nothing*
#: -- is the library's, and it is checked on every interpreter, because it is true
#: on every interpreter: not one unrecorded row allocates a byte on either version
#: this suite runs on.
#:
#: The recorded rows are a different kind of claim. Each names a cost in bytes,
#: and those bytes are CPython's rather than this library's: on 3.14 a good third
#: of them are *zero*, because the interpreter no longer makes allocations 3.13
#: makes -- `CollectionExpect.contains` needs 48 bytes there and none here. Both
#: directions of the recorded check then say something untrue off the reference
#: interpreter. "The exemption has stopped covering anything, delete the line"
#: would have the reader delete an exemption that 3.13 still needs, and the
#: doubling ceiling would compare against a number measured somewhere else.
#:
#: So the recorded rows are checked where their numbers came from, and the
#: invariant is checked everywhere. The alternative -- a table of numbers per
#: interpreter -- buys nothing: an exemption that rots does so in the library, not
#: in CPython, and one reading of it catches that.
_REFERENCE_INTERPRETER: Final = (3, 13)
_ON_REFERENCE_INTERPRETER: Final = sys.version_info[:2] == _REFERENCE_INTERPRETER

_SUBJECT_CLASS_BY_NAME: Final = {cls.__name__: cls for cls in SUBJECT_CLASSES}

#: The two entries a stand-in cannot be installed over, with the reason it
#: cannot. :func:`test_the_pair_that_cannot_be_isolated_still_cannot` fails if a
#: reason stops holding, so this cannot become the place awkward entries go.
_NOT_ISOLATED: Final[dict[_Key, str]] = {
    ("WithinDelta", "before"): (
        "`is_within(delta)` hands back a WithinDelta that warns from `__del__` when "
        "no continuation ran -- the library catching a test that asserts nothing. "
        "Replacing `.before` with a stand-in commits exactly that mistake, once per "
        "call: every call leaves an unconsumed WithinDelta whose finaliser builds "
        "the warning's message. The reference then measures the warning -- 800 bytes "
        "against the real call's 388 -- so the comparison inverts and the row would "
        "pass for the wrong reason. The chain is still measured: the "
        "`DateTimeExpect.is_within` row runs it with `.before` real."
    ),
    ("WithinDelta", "after"): (
        "The same finaliser and the same inversion; `.after` is `.before` with the "
        "direction reversed."
    ),
}

# -- Why an assertion is entitled to allocate -------------------------------
#
# Shared because the answers repeat, the way `NO_HAPPY_PATH`'s `_NESTED` does:
# many of these rows say "it walks a collection", and a copy of that sentence per
# row would be one more place for it to drift. Every row still carries its own
# measured number.
#
# The distinction this table exists to keep visible: **a recorded cost is not an
# excused cost.** `all(value in subject for value in values)` and the loop that
# tests the same thing differ by an order of magnitude on every *passing* call --
# a generator object against a bare iterator -- and both would sit here as
# "recorded". So the library spells those tests as loops (`_text.holds_every`,
# `_text.holds_any`, and the two sites in `_collection.py` carrying a ruff
# suppression that says why), and the row stays in this table at the iterator's
# cost, because the iterator is not zero either.

#: The commonest answer, and the one worth stating plainly because it makes
#: "a passing assertion allocates nothing" false as written: in CPython, `for x in
#: xs` allocates the iterator, and `tracemalloc` sees it. 48 bytes over a list or
#: a tuple, 64 over a set, 72 over a dict. An assertion about more than one item
#: cannot avoid it and should not try.
_ITERATOR: Final = (
    "walks its subject or its operands, and a `for` loop allocates the iterator: "
    "48 bytes over a list or tuple, 64 over a set, 72 over a dict"
)

_ENUMERATE: Final = (
    "walks the subject with `enumerate`, so the failure can say *which* item -- "
    "the iterator plus the `enumerate` wrapper"
)

_PAIRWISE: Final = (
    "compares the sequence against another, or against itself shifted by one; the "
    "walk is the assertion"
)

_VIEW: Final = "takes a `keys()`/`values()` view of the mapping and walks the operands against it"

#: Not waste, and the one place the stand-in is knowingly generous: it hands back
#: the object the real method returned the first time instead of building a new
#: one, so the whole cost of the continuation lands on the assertion's side of
#: the subtraction. Named rather than corrected because a reference that
#: allocated a `Found` of its own would be a reference doing the assertion's work.
_CONTINUATION: Final = (
    "returns a narrowing continuation -- a fresh `Found`, subject or `WithinDelta` "
    "-- which is the assertion's product, not waste. The stand-in hands back a "
    "captured one, so the object shows up here in full"
)

_FINDS: Final = "walks the subject to find the item, then returns a `Found` on it: both costs"

_SET: Final = "builds a set, which is how it answers in one pass instead of in n squared"

_EXTRACTS: Final = "builds the extracted collection and the subject that carries it, and returns it"

_CLAIMED: Final = (
    "keeps track of which items are already claimed, which is what a one-to-one "
    "pairing in any order requires"
)

_CALL_ITERATOR: Final = (
    "walks the recorded calls looking for a match, and a `for` over a sequence "
    "allocates its iterator -- 48 bytes, and the floor for reading a list at all. "
    "It was 120: the indices of every match were collected into a list *before* "
    "`not matched` decided, so the branch that passes built one too"
)

_REGEX: Final = (
    "matches a regular expression: the match object is `re`'s, and the compiled "
    "pattern is `re`'s cache, filled by the warmup"
)

_WILDCARD: Final = "translates the wildcard into a regular expression and matches it"

_FOLDS_CASE: Final = (
    "lower-cases both sides, and `str.lower()` copies. Here the copy *is* the comparison"
)

_UUID: Final = "parses the string into a `UUID`, which is the assertion"

_RAISES: Final = (
    "calls the subject and catches what it raises; an exception carrying a "
    "traceback is most of a kilobyte, and producing it is the whole assertion"
)

_CAPTURES_WARNINGS: Final = (
    "installs a `warnings.catch_warnings` block, calls the subject inside it and "
    "restores the filter state afterwards. There is no way to find out whether "
    "something warned without standing somewhere it can be heard, so the capture "
    "is the assertion rather than a cost on the way to it"
)

_CALLS_THE_SUBJECT: Final = (
    "calls the subject, and calling a Python callable allocates its frame. Always "
    "spent, never visible: the dispatch used to walk the whole `issubclass` chain "
    "for a function, and that transient peak was larger than the frame, so the "
    "reference and the real call read the same. Putting the exact-type table ahead "
    "of the mock check took `expect(fn)` from 1112ns to 456ns and uncovered it -- "
    "an optimisation revealing a measurement it had been hiding"
)

_SUPER: Final = (
    "`super()` builds a proxy object on every call. The override is a guard on "
    "`_absorbed` plus a delegation, and the delegation is the 48 bytes"
)

_STAT: Final = (
    "asks the filesystem, and a `stat_result` is several hundred bytes on any "
    "platform -- the concession `_every_subject`'s `PathExpect.is_file` case "
    "already makes with a reference of its own"
)

_CHILD: Final = "the same `stat`, plus the child path it has to build to ask about"

_READS_THE_FILE: Final = "reads the file it is asserting about; the text is the assertion"

#: What reading that file costs before the library sees a byte of it. CPython
#: sizes the buffer behind ``Path.read_bytes`` from the filesystem's own block
#: size, so most of the figures below are the host's number rather than the
#: library's. Written as a sum for that reason: a bare literal would be this
#: machine's block size in disguise, and a filesystem with larger blocks -- ZFS
#: records and NFS read sizes are commonly 128 KiB, against 4 KiB here -- would
#: fail the growth check by a factor of thirty while nothing had grown at all.
#:
#: ``st_blksize`` is POSIX and absent from a Windows ``stat_result`` entirely,
#: where the buffer is sized another way; the fallback is the block size these
#: figures were first taken against, which is the number Windows was already
#: being measured under.
_FILE_READ_BUFFER: Final = getattr(Path(tempfile.gettempdir()).stat(), "st_blksize", 4096)

#: An artefact of how the table is written rather than a cost the library
#: imposes, and the clearest example of why each of these had to be read rather
#: than counted. `pathlib` computes `_raw_paths`, `_tail` and `_root` on first
#: access; the happy call builds a fresh `PurePosixPath` on every iteration, so
#: the parse happens *inside* the assertion instead of before it. A path a real
#: test asserts on twice pays it once.
_LAZY_PATH: Final = (
    "pathlib parses lazily on first access and the happy call builds a fresh path "
    "every time, so the parse lands inside the assertion. An artefact of the "
    "invocation: the same path asserted on twice pays this once"
)

_TODAY: Final = "asks the clock; `date.today()` is a fresh `date` and a syscall behind it"

_TIMEDELTA: Final = "builds a `timedelta` to answer with -- `abs(a - b)`, or `utcoffset()`'s offset"

_FLOAT: Final = "`total_seconds()` returns a fresh float"

#: Also an artefact of the invocation, and a pretty one: `has_day(2)` and
#: `has_month(1)` allocate nothing and are held to zero, while `has_year(2020)`
#: does not, because 2020 is past CPython's small-integer cache and `date.year`
#: has to box it.
_BOXES_AN_INT: Final = (
    "reads an integer component; 2020 is past CPython's small-integer cache, so "
    "`date.year` boxes a new `int`. `has_day` and `has_month` pay nothing, which "
    "is why they are not on this list"
)

_FLAG: Final = "`other in subject` is `Flag.__contains__`, which builds the intersection to answer"

_DECIMAL: Final = (
    "compares a `Decimal` to an `int`, and the coercion is `Decimal`'s allocation "
    "rather than the library's -- the concession `OrderedExpect.is_positive` "
    "already makes above"
)

_EQUIVALENCE: Final = (
    "walks both object graphs, which is what structural equivalence means; "
    "`compare` is already the one exemption `test_happy_path.py`'s rule B grants"
)

#: The sharper half of `_EQUIVALENCE`. This assertion *passes* when the graphs
#: differ, so the expensive branch is the happy one: a full difference report
#: built here would be built on every passing call and read by nobody, and it
#: costs several times what reaching the verdict costs. It asks `differs` instead
#: -- the same walk, stopped at the first disagreement -- so what is left is the
#: walk itself, which is the work structural inequivalence *is*.
_VERDICT_ONLY: Final = (
    "walks both graphs to reach its verdict, which is what structural "
    "inequivalence means; it asks `differs` so the report is built where it is "
    "read and nowhere else"
)

_PROTOCOL: Final = (
    "`issubclass` against a runtime-checkable `Protocol` allocates inside `abc` "
    "and `typing` -- the same cost `CallableExpect.does_not_raise`'s reference "
    "concedes above"
)

_ABSTRACT: Final = "reads `__abstractmethods__` and asks whether anything is left in it"


#: Assertions whose own body allocates something on a passing call, with what it
#: cost when it was measured and why it is entitled to. A minority of the rows the
#: sweep reaches; every row not listed here is held to zero.
#:
#: **The number is a recorded observation, not a budget.** The guard asserts only
#: that an entry is still needed, because an ``os.stat_result`` is a different
#: size on Linux, macOS and Windows and this suite runs on all three, and object
#: layouts move between CPython releases and it runs on two. A byte count pinned
#: here would be a guess at another machine's, which is the flake
#: ``blocks_allocated``'s warmup exists to avoid. The cost of that decision is
#: stated rather than buried: a message built and discarded inside one of these
#: recorded assertions would not be caught by this file. The AST passes in
#: ``tests/test_happy_path.py`` are what covers them, and they cover every method
#: in the library at once.
#:
#: :func:`test_no_passing_assertion_builds_anything_it_throws_away` fails for an
#: entry that has dropped to zero, so an exemption cannot outlive the cost it
#: records -- the same shape as ``_EXEMPT_EDGES`` in ``tests/test_happy_path.py``.
#:
#: Read the reasons rather than the count. Most are the language's own price for
#: iterating, or work the assertion exists to do, or -- twice -- an artefact of
#: how the happy call is written rather than anything the library does.
_ALLOCATES_BY_DESIGN: Final[dict[_Key, tuple[int, str]]] = {
    # -- CallableExpect ----------------------------------------------
    ("CallableExpect", "does_not_raise"): (64, _CALLS_THE_SUBJECT),
    ("CallableExpect", "does_not_warn"): (726, _CAPTURES_WARNINGS),
    ("CallableExpect", "warns"): (1212, _CAPTURES_WARNINGS),
    ("CallableExpect", "raises"): (784, _RAISES),
    ("CallableExpect", "raises_exactly"): (792, _RAISES),
    # -- narrowing ---------------------------------------------------
    ("CollectionExpect", "contains_single"): (48, _CONTINUATION),
    ("DateTimeExpect", "is_within"): (192, _CONTINUATION),
    ("Expect", "as_type"): (96, _CONTINUATION),
    ("Expect", "is_exactly_instance_of"): (48, _CONTINUATION),
    ("Expect", "is_instance_of"): (48, _CONTINUATION),
    ("MappingExpect", "contains_key"): (48, _CONTINUATION),
    ("MockExpect", "last_call"): (48, _CONTINUATION),
    ("RaisedExpect", "with_cause"): (48, _CONTINUATION),
    ("RaisedExpect", "with_cause_exactly"): (48, _CONTINUATION),
    ("SequenceExpect", "has_element_at"): (48, _CONTINUATION),
    ("TypeExpect", "has_attribute"): (48, _CONTINUATION),
    ("TypeExpect", "has_method"): (48, _CONTINUATION),
    # -- regular expressions -----------------------------------------
    ("RaisedExpect", "with_message"): (120, _REGEX),
    ("RaisedExpect", "with_note_matching"): (168, _REGEX),
    ("StringExpect", "does_not_match"): (1094, _REGEX),
    ("StringExpect", "matches"): (1214, _REGEX),
    # -- super() -----------------------------------------------------
    ("_CaughtExpect", "matches"): (48, _SUPER),
    ("_CaughtExpect", "where"): (48, _SUPER),
    # -- enumerate ---------------------------------------------------
    ("CollectionExpect", "all_are_exactly_type"): (120, _ENUMERATE),
    ("CollectionExpect", "all_are_instance_of"): (120, _ENUMERATE),
    ("CollectionExpect", "all_equal_to"): (120, _ENUMERATE),
    ("CollectionExpect", "contains_items_of_type"): (120, _ENUMERATE),
    ("CollectionExpect", "does_not_contain_items_of_type"): (120, _ENUMERATE),
    ("CollectionExpect", "does_not_contain_matching"): (120, _ENUMERATE),
    ("CollectionExpect", "does_not_contain_none"): (120, _ENUMERATE),
    # -- iteration ---------------------------------------------------
    ("CollectionExpect", "contains"): (48, _ITERATOR),
    ("CollectionExpect", "contains_all"): (48, _ITERATOR),
    ("CollectionExpect", "contains_any"): (48, _ITERATOR),
    ("CollectionExpect", "contains_none_of"): (48, _ITERATOR),
    ("CollectionExpect", "contains_only"): (48, _ITERATOR),
    ("CollectionExpect", "does_not_contain_all"): (48, _ITERATOR),
    ("CollectionExpect", "does_not_intersect"): (48, _ITERATOR),
    ("CollectionExpect", "intersects"): (48, _ITERATOR),
    ("CollectionExpect", "is_disjoint_from"): (48, _ITERATOR),
    ("CollectionExpect", "is_not_subset_of"): (48, _ITERATOR),
    ("CollectionExpect", "is_not_superset_of"): (48, _ITERATOR),
    ("CollectionExpect", "is_proper_subset_of"): (48, _ITERATOR),
    ("CollectionExpect", "is_proper_superset_of"): (48, _ITERATOR),
    ("CollectionExpect", "is_subset_of"): (48, _ITERATOR),
    ("CollectionExpect", "is_superset_of"): (48, _ITERATOR),
    ("CollectionExpect", "only_contains"): (48, _ITERATOR),
    ("MappingExpect", "contains_entries"): (112, _ITERATOR),
    ("MappingExpect", "contains_keys"): (48, _ITERATOR),
    ("MappingExpect", "does_not_contain_keys"): (48, _ITERATOR),
    ("MockExpect", "was_ever_called_with"): (48, _ITERATOR),
    ("SequenceExpect", "contains_in_order"): (120, _ITERATOR),
    ("SequenceExpect", "does_not_contain_in_order"): (120, _ITERATOR),
    # -- wildcards ---------------------------------------------------
    ("CollectionExpect", "contains_match"): (1306, _WILDCARD),
    ("CollectionExpect", "does_not_contain_match"): (1258, _WILDCARD),
    ("PurePathExpect", "matches_pattern"): (1686, _WILDCARD),
    ("StringExpect", "does_not_match_wildcard"): (1138, _WILDCARD),
    ("StringExpect", "does_not_match_wildcard_ignoring_case"): (1138, _WILDCARD),
    ("StringExpect", "matches_wildcard"): (1258, _WILDCARD),
    ("StringExpect", "matches_wildcard_ignoring_case"): (1258, _WILDCARD),
    # -- find + narrow -----------------------------------------------
    ("CollectionExpect", "contains_matching"): (96, _FINDS),
    ("CollectionExpect", "contains_single_matching"): (48, _FINDS),
    ("MappingExpect", "contains_entry_matching"): (120, _FINDS),
    ("MappingExpect", "contains_key_matching"): (120, _FINDS),
    ("MappingExpect", "contains_value"): (120, _FINDS),
    ("MappingExpect", "contains_value_matching"): (120, _FINDS),
    # -- sets --------------------------------------------------------
    ("CollectionExpect", "contains_no_duplicates"): (336, _SET),
    ("CollectionExpect", "has_unique_items"): (336, _SET),
    ("MappingExpect", "contains_only_keys"): (432, _SET),
    # -- extracting --------------------------------------------------
    ("CollectionExpect", "extracting"): (393, _EXTRACTS),
    ("SequenceExpect", "extracting"): (401, _EXTRACTS),
    # -- one-to-one matching -----------------------------------------
    ("CollectionExpect", "satisfies_in_any_order"): (192, _CLAIMED),
    # -- boxed ints --------------------------------------------------
    ("DateExpect", "has_year"): (32, _BOXES_AN_INT),
    # -- the clock ---------------------------------------------------
    ("DateExpect", "is_in_the_future"): (176, _TODAY),
    ("DateExpect", "is_in_the_past"): (176, _TODAY),
    ("DateExpect", "is_today"): (80, _TODAY),
    # -- timedeltas --------------------------------------------------
    ("TimeDeltaExpect", "is_close_to"): (16, _TIMEDELTA),
    ("TimeDeltaExpect", "is_not_close_to"): (16, _TIMEDELTA),
    ("_ClockExpect", "is_aware"): (72, _TIMEDELTA),
    # -- floats ------------------------------------------------------
    ("TimeDeltaExpect", "has_total_seconds"): (64, _FLOAT),
    # -- Flag --------------------------------------------------------
    ("EnumExpect", "does_not_have_flag"): (72, _FLAG),
    ("EnumExpect", "has_flag"): (72, _FLAG),
    # -- structural comparison ---------------------------------------
    ("Expect", "is_equivalent_to"): (296, _EQUIVALENCE),
    ("Expect", "is_not_equivalent_to"): (4287, _VERDICT_ONLY),
    # -- Decimal -----------------------------------------------------
    ("OrderedExpect", "is_zero"): (120, _DECIMAL),
    # -- a list read to the end --------------------------------------
    ("MockExpect", "was_never_called_with"): (48, _CALL_ITERATOR),
    # -- mapping views -----------------------------------------------
    ("MappingExpect", "contains_values"): (160, _VIEW),
    ("MappingExpect", "does_not_contain_value"): (112, _VIEW),
    ("MappingExpect", "does_not_contain_values"): (160, _VIEW),
    # -- file contents -----------------------------------------------
    ("PathExpect", "contains_text"): (_FILE_READ_BUFFER + 542, _READS_THE_FILE),
    ("PathExpect", "does_not_contain_text"): (_FILE_READ_BUFFER + 542, _READS_THE_FILE),
    ("PathExpect", "has_text"): (_FILE_READ_BUFFER + 542, _READS_THE_FILE),
    # -- stat --------------------------------------------------------
    ("PathExpect", "does_not_exist"): (722, _STAT),
    ("PathExpect", "exists"): (858, _STAT),
    ("PathExpect", "has_size"): (858, _STAT),
    ("PathExpect", "has_size_greater_than"): (858, _STAT),
    ("PathExpect", "has_size_less_than"): (858, _STAT),
    ("PathExpect", "is_directory"): (849, _STAT),
    ("PathExpect", "is_empty"): (859, _STAT),
    ("PathExpect", "is_file"): (858, _STAT),
    ("PathExpect", "is_not_directory"): (858, _STAT),
    ("PathExpect", "is_not_empty"): (858, _STAT),
    ("PathExpect", "is_not_file"): (849, _STAT),
    ("PathExpect", "is_not_symlink"): (858, _STAT),
    ("PathExpect", "is_same_file_as"): (1534, _STAT),
    ("PathExpect", "is_symlink"): (851, _STAT),
    # -- stat + a child path -----------------------------------------
    ("PathExpect", "does_not_have_child"): (1713, _CHILD),
    ("PathExpect", "has_child"): (1728, _CHILD),
    # -- pathlib's lazy parse ----------------------------------------
    ("PurePathExpect", "has_name"): (746, _LAZY_PATH),
    ("PurePathExpect", "has_no_suffix"): (634, _LAZY_PATH),
    ("PurePathExpect", "has_parent"): (1749, _LAZY_PATH),
    ("PurePathExpect", "has_stem"): (746, _LAZY_PATH),
    ("PurePathExpect", "has_suffix"): (746, _LAZY_PATH),
    ("PurePathExpect", "has_suffixes"): (818, _LAZY_PATH),
    ("PurePathExpect", "is_absolute"): (48, _LAZY_PATH),
    ("PurePathExpect", "is_not_relative_to"): (1657, _LAZY_PATH),
    ("PurePathExpect", "is_relative"): (48, _LAZY_PATH),
    ("PurePathExpect", "is_relative_to"): (1657, _LAZY_PATH),
    # -- pairwise walks ----------------------------------------------
    ("SequenceExpect", "contains_in_consecutive_order"): (88, _PAIRWISE),
    ("SequenceExpect", "does_not_contain_in_consecutive_order"): (88, _PAIRWISE),
    ("SequenceExpect", "ends_with_sequence"): (88, _PAIRWISE),
    ("SequenceExpect", "equals_approximately"): (88, _PAIRWISE),
    ("SequenceExpect", "equals_sequence"): (88, _PAIRWISE),
    ("SequenceExpect", "is_not_sorted"): (88, _PAIRWISE),
    ("SequenceExpect", "is_not_sorted_descending"): (88, _PAIRWISE),
    ("SequenceExpect", "is_sorted"): (88, _PAIRWISE),
    ("SequenceExpect", "is_sorted_descending"): (88, _PAIRWISE),
    ("SequenceExpect", "starts_with_sequence"): (88, _PAIRWISE),
    # -- iteration over the operands ---------------------------------
    ("StringExpect", "contains_all"): (48, _ITERATOR),
    ("StringExpect", "contains_any"): (48, _ITERATOR),
    ("StringExpect", "does_not_contain_all"): (48, _ITERATOR),
    ("StringExpect", "does_not_contain_any"): (48, _ITERATOR),
    # -- case folding ------------------------------------------------
    ("StringExpect", "contains_ignoring_case"): (86, _FOLDS_CASE),
    ("StringExpect", "does_not_contain_ignoring_case"): (86, _FOLDS_CASE),
    ("StringExpect", "does_not_end_with_ignoring_case"): (86, _FOLDS_CASE),
    ("StringExpect", "does_not_start_with_ignoring_case"): (86, _FOLDS_CASE),
    ("StringExpect", "ends_with_ignoring_case"): (86, _FOLDS_CASE),
    ("StringExpect", "is_equal_ignoring_case"): (88, _FOLDS_CASE),
    ("StringExpect", "is_not_equal_ignoring_case"): (88, _FOLDS_CASE),
    ("StringExpect", "starts_with_ignoring_case"): (86, _FOLDS_CASE),
    # -- UUID --------------------------------------------------------
    ("StringExpect", "is_uuid"): (253, _UUID),
    # -- runtime protocols -------------------------------------------
    ("TypeExpect", "does_not_implement"): (64, _PROTOCOL),
    ("TypeExpect", "implements"): (64, _PROTOCOL),
    # -- __abstractmethods__ -----------------------------------------
    ("TypeExpect", "is_not_abstract"): (104, _ABSTRACT),
}


def _returning(value: object, /) -> "Callable[..., object]":
    """A stand-in for one assertion: does nothing, hands back ``value``.

    This is the reference every reading is taken against, and it is the whole
    reason a table of hand-written happy calls can be measured at all. Installed
    over the real method, it leaves the rest of the call running exactly as it
    was -- the ``expect(...)`` dispatch, the subject's construction, the operands
    built inside the lambda, the attribute lookup, the call itself -- and removes
    only the body of the assertion. What separates the two readings is the
    assertion's own allocation and nothing else.

    Without it there is nothing to measure. Every entry in the table builds its
    own subject, because a passing call cannot be generated from a signature and
    ``lambda _: expect(3).is_equal_to(3)`` is what keeps the table readable; and
    ``expect(3)`` allocates a subject. Read raw, every entry allocates and the
    guard says nothing at all. Read against this, most of them allocate zero.

    ``value`` is what the real method returned when it was called once for real,
    rather than ``self``, because not every assertion returns ``self``:
    ``is_within(...)`` hands back a ``WithinDelta`` and the happy call goes on to
    ``.before(...)``. A stand-in returning ``self`` breaks that chain with an
    ``AttributeError``; one returning what the method returned does not.

    Handing back a *captured* object rather than a fresh one is the one place the
    reference is generous, and it is generous in the direction that reports
    rather than hides: an assertion whose product is a new object --
    ``is_instance_of`` returning a ``Found``, ``last_call`` returning a subject --
    pays for that object in the reading and is listed in
    :data:`_ALLOCATES_BY_DESIGN` with exactly that as its reason.
    """

    def stand_in(_subject: object, /, *_args: object, **_kwargs: object) -> object:
        return value

    return stand_in


def _recording(
    original: "Callable[..., object]", seen: "list[object]", /
) -> "Callable[..., object]":
    """``original``, with what it returns kept, so the stand-in can hand it back.

    Doubles as proof that a happy call reaches the assertion it is filed under:
    if ``seen`` is empty afterwards, the entry named one method and ran another.
    :func:`test_every_happy_call_reaches_the_assertion_it_names` is what reads
    that.
    """

    def record(subject: object, /, *args: object, **kwargs: object) -> object:
        value = original(subject, *args, **kwargs)
        seen.append(value)
        return value

    return record


class _Sweep(NamedTuple):
    """What one full pass over the happy-call table produced."""

    #: Bytes the assertion itself held at once, over and above the same happy
    #: call with the assertion replaced by a stand-in.
    cost: dict[_Key, int]
    #: ``owner.name`` for every entry whose happy call never reached the method
    #: it names -- a row that measures nothing and says so nowhere.
    unreached: list[str]


def _captured_returns(world: World) -> tuple[dict[_Key, object], list[str]]:
    """Run every happy call once for real, keeping what each assertion returned."""
    held: dict[_Key, object] = {}
    unreached: list[str] = []
    for key, call in sorted(HAPPY_CALLS.items()):
        owner, name = key
        subject_class = _SUBJECT_CLASS_BY_NAME[owner]
        # Patched on the class that *declares* the method rather than on the
        # assembled subject: a subject is built from one mixin per seam, so its
        # own dictionary holds none of them, and setting the name on the subject
        # would shadow rather than record.
        declaring = next(c for c in subject_class.__mro__ if name in vars(c))
        original: Callable[..., object] = vars(declaring)[name]
        seen: list[object] = []
        setattr(declaring, name, _recording(original, seen))
        try:
            call(world)
        finally:
            setattr(subject_class, name, original)
        if seen:
            held[key] = seen[-1]
        else:
            unreached.append(f"{owner}.{name}")
    return held, unreached


def _sweep(world: World) -> _Sweep:
    """Every assertion in the table, measured against itself doing nothing.

    One tracing session per pass rather than one per reading, which is most of
    what this costs. The ``gc.collect()`` that
    :func:`benchmarks.peak_bytes_allocated` runs before each measurement costs a
    couple of milliseconds on a pytest-sized heap, and the sweep takes two
    readings per assertion: paid per reading, that is seconds of setting up rather
    than measuring.
    """
    held, unreached = _captured_returns(world)
    keys = [key for key in sorted(HAPPY_CALLS) if key in held and key not in _NOT_ISOLATED]
    best: dict[_Key, tuple[int, int]] = {}
    for _ in range(_SWEEP_PASSES):
        with measuring_peaks(_SWEEP_CALLS, _SWEEP_WARMUP) as peak:
            for key in keys:
                owner, name = key
                subject_class = _SUBJECT_CLASS_BY_NAME[owner]
                original: Callable[..., object] = subject_class.__dict__[name]
                invoke = partial(HAPPY_CALLS[key], world)
                measured = peak(invoke)
                setattr(subject_class, name, _returning(held[key]))
                try:
                    reference = peak(invoke)
                finally:
                    setattr(subject_class, name, original)
                previous = best.get(key, (measured, reference))
                best[key] = (min(previous[0], measured), min(previous[1], reference))
    return _Sweep({key: own - bare for key, (own, bare) in best.items()}, unreached)


@pytest.fixture(scope="module")
def sweep(world: World) -> _Sweep:
    """The whole table, measured once for the module.

    Module-scoped because the sweep is the expensive part and every test that
    reads it is an assertion about one number out of it. Per test, it would be one
    whole sweep per assertion in the table.
    """
    return _sweep(world)


_SWEPT: Final = sorted(key for key in HAPPY_CALLS if key not in _NOT_ISOLATED)


@pytest.mark.parametrize(
    ("owner", "name"),
    _SWEPT,
    ids=[f"{owner}.{name}" for owner, name in _SWEPT],
)
@measured
def test_no_passing_assertion_builds_anything_it_throws_away(
    owner: str, name: str, sweep: _Sweep
) -> None:
    """A passing assertion builds nothing it discards -- every one, not a sample.

    One test per assertion, so a failure names the assertion instead of naming
    the sweep. Two claims, depending on which side of
    :data:`_ALLOCATES_BY_DESIGN` the row falls:

    *Not recorded* -- the assertion's body must allocate nothing at all. Most rows
    do exactly that, and the smallest message that could be built and discarded is
    tens of bytes, so there is no margin to argue about.

    *Recorded* -- the entry must still be needed, and must not have grown past
    double. An exemption that has stopped covering anything is an allow-list
    waiting to be extended, so it fails here and the answer is to delete the
    line, not to widen it. Both halves run on the reference interpreter only;
    :data:`_REFERENCE_INTERPRETER` says why, and the first claim above still runs
    everywhere.
    """
    key = (owner, name)
    cost = sweep.cost.get(key)
    assert cost is not None, (
        f"{owner}.{name} was never measured. Either its happy call does not reach "
        f"it -- test_every_happy_call_reaches_the_assertion_it_names says which -- "
        f"or it is listed in _NOT_ISOLATED without being excluded from this sweep."
    )
    recorded = _ALLOCATES_BY_DESIGN.get(key)
    if recorded is not None and not _ON_REFERENCE_INTERPRETER:
        # Its two checks are about a number this interpreter did not produce.
        # See _REFERENCE_INTERPRETER. The invariant below is checked here as
        # everywhere, because it is the library's claim rather than CPython's.
        return
    if recorded is None:
        assert cost <= 0, (
            f"{owner}.{name} held {cost} bytes at once that the same call with the "
            f"assertion replaced by a stand-in did not. A passing assertion is a "
            f"comparison and a `return self`; a message is built in the failure "
            f"branch only. If the allocation is the work the "
            f"assertion exists to do rather than waste, record it in "
            f"_ALLOCATES_BY_DESIGN with what it costs and why."
        )
        return
    was, reason = recorded
    assert cost > 0, (
        f"{owner}.{name} is recorded in _ALLOCATES_BY_DESIGN as costing {was} bytes "
        f"({reason}), and now costs {cost}. The exemption has stopped covering "
        f"anything: delete the line."
    )
    assert cost <= was * _MAY_NOT_DOUBLE, (
        f"{owner}.{name} is exempted at {was} bytes ({reason}) and now holds {cost}, "
        f"which is more than double. An exemption names a cost that was argued for; "
        f"it is not a licence to grow. Either the growth is waste -- find it -- or it "
        f"is work the assertion now does, in which case raise the number deliberately "
        f"and say in its reason what the extra buys."
    )


def test_every_subject_class_declares_slots() -> None:
    """Every subject class declares ``__slots__``, so no subject carries a dict.

    A subject is allocated once per ``expect()`` and thrown away immediately, so
    the wrapper's own size is the one allocation the library cannot avoid.
    Measured: 48 bytes with ``__slots__ = ()`` against 64 without, a third more
    for a dictionary no subject ever puts anything in.

    ruff's ``SLOT`` rules are selected and do not reach this -- they fire for
    subclasses of ``str``, ``tuple`` and ``NamedTuple``, not for an ordinary
    class -- so removing ``__slots__`` from ``BoolExpect`` passes every lint the
    repository runs. Read off the package rather than listed, for the reason
    ``subject_classes`` gives: a subject added tomorrow is checked whether or not
    anyone remembers this file.

    An extension author's own subclass is theirs to keep -- their class, their
    instances, their sixteen bytes.
    """
    missing = sorted(cls.__name__ for cls in SUBJECT_CLASSES if "__slots__" not in vars(cls))
    assert not missing, (
        f"these subject classes do not declare `__slots__ = ()`: {missing}. Every one "
        f"of them gets a per-instance `__dict__` nothing writes to, on an object built "
        f"once per assertion and dropped."
    )


def test_the_exemption_table_cannot_grow() -> None:
    """Shrink only, the way ``NO_HAPPY_PATH`` in ``tests/_happy_calls.py`` is.

    Every row here is an assertion allowed to allocate, and each was argued for
    once. Uncounted, the table could take a hundred more entries without a test
    moving -- and adding a line to it is always the cheapest way to make this file
    green, cheaper than finding the waste.

    143 is where it stands. Editing this number down is what removing an
    exemption looks like; editing it up means arguing for it in review rather
    than in a commit nobody reads.
    """
    assert len(_ALLOCATES_BY_DESIGN) <= 143, (
        f"_ALLOCATES_BY_DESIGN has grown to {len(_ALLOCATES_BY_DESIGN)} entries. "
        f"It is a shrinking list: an exemption is a cost that was argued for, not "
        f"a place to put a new one."
    )


def test_every_happy_call_reaches_the_assertion_it_names(sweep: _Sweep) -> None:
    """A row filed under a method it never calls measures a different method.

    Exact rather than heuristic: the method is replaced by a recorder, the happy
    call runs, and the recorder either fired or it did not. The shape it catches
    is a row whose subject dispatches to a subclass that overrides the method --
    a ``list`` handed to ``CollectionExpect.extracting`` reaches
    ``SequenceExpect.extracting`` instead, so two rows drive one implementation
    and the one they name between them is never run by either.
    """
    assert not sweep.unreached, (
        f"these happy calls never reach the assertion they are filed under: "
        f"{sweep.unreached}. The row exercises some other implementation -- usually "
        f"an override on the subject the call happens to build -- so both guards "
        f"read it as covered and neither covers it."
    )


def test_the_sweep_covers_every_entry_in_the_table(sweep: _Sweep) -> None:
    """A guard over a shrunken sweep would pass for nothing.

    Two floors rather than one: the sweep has to reach the whole table, and the
    part of it held to *zero* has to stay the majority. An exemption list that
    grew until nothing was checked strictly would still satisfy the first.
    """
    unmeasured = sorted(
        f"{owner}.{name}" for owner, name in set(HAPPY_CALLS) - set(sweep.cost) - set(_NOT_ISOLATED)
    )
    assert not unmeasured, (
        f"the sweep did not reach {unmeasured}. Every entry in the table is either "
        f"measured or named in _NOT_ISOLATED with the reason it cannot be."
    )
    strict = [key for key in sweep.cost if key not in _ALLOCATES_BY_DESIGN]
    assert len(strict) > 100, (
        f"only {len(strict)} assertions are held to zero allocation; the rest are "
        f"recorded in _ALLOCATES_BY_DESIGN. The old sample checked 18, so this is "
        f"still a floor rather than a target -- but a list that swallowed the "
        f"surface would be a guard that measures and asserts nothing."
    )


def test_the_recorded_allocations_name_assertions_that_exist() -> None:
    """Neither list may outlive the table it annotates."""
    for label, table in (
        ("_ALLOCATES_BY_DESIGN", set(_ALLOCATES_BY_DESIGN)),
        ("_NOT_ISOLATED", set(_NOT_ISOLATED)),
    ):
        stale = sorted(f"{owner}.{name}" for owner, name in table - set(HAPPY_CALLS))
        assert not stale, f"{label} names assertions that are no longer in the table: {stale}"
    unexplained = sorted(
        f"{owner}.{name}" for (owner, name), (_, why) in _ALLOCATES_BY_DESIGN.items() if not why
    )
    assert not unexplained, f"recorded without a reason: {unexplained}"


def test_the_pair_that_cannot_be_isolated_still_cannot(world: World) -> None:
    """The two rows :data:`_NOT_ISOLATED` gives up on, and the reason, re-checked.

    The reason is specific and could stop being true -- if ``WithinDelta`` ever
    stopped warning from its finaliser, or warned without building a message, the
    stand-in would become a usable reference and these two rows would join the
    sweep. So it is asserted rather than asserted-in-prose: install the stand-in,
    run the happy call, and the warning must still arrive.
    """
    for key, reason in _NOT_ISOLATED.items():
        assert reason.strip(), f"{key} is excluded without a reason"
        owner, name = key
        subject_class = _SUBJECT_CLASS_BY_NAME[owner]
        original: Callable[..., object] = subject_class.__dict__[name]
        setattr(subject_class, name, _returning(None))
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                HAPPY_CALLS[key](world)
        finally:
            setattr(subject_class, name, original)
        assert caught, (
            f"{owner}.{name} no longer warns when a stand-in replaces it, so the "
            f"reference is no longer inflated by the warning. Take it out of "
            f"_NOT_ISOLATED and let the sweep measure it."
        )


# ---------------------------------------------------------------------------
# The guards' own guard
# ---------------------------------------------------------------------------
@measured
def test_the_three_measurements_see_three_different_bugs() -> None:
    """A guard nobody can fail is not a guard, and both of these could not fail.

    Two violations, planted here because each one walks straight past two of the
    three instruments that are supposed to stop it.

    ``wasteful`` is the banned anti-pattern reproduced exactly: a message
    assembled on the happy path, looked at, and dropped. Written into
    ``Expect.is_equal_to`` as ``_ = f"{expected!r}"``, it moves neither retention
    reading, because both count *live* blocks or bytes and the string is not live
    by the time the count is taken.

    ``hoarding`` is a registry -- "keep every subject we asserted on", the shape a
    debug feature or a soft-assertion buffer takes. Written into
    ``MockExpect.was_not_called``, it accumulates a reference per call while
    reading *exactly the no-op baseline* on the block count and *zero* on the
    peak, because appending an object that already exists creates no block and no
    bytes the call did not already own: the list's pointer array is reallocated in
    place.

    All six answers are pinned -- three instruments against two plants -- the
    blind ones included. A blind spot recorded is a blind spot that cannot come
    back quietly; and if someone ever makes one of these instruments sharper, the
    assertion that fails is one of the blindness claims, and this docstring is
    what tells them the news is good.
    """
    subject = expect(3)
    registry: list[object] = []

    def clean() -> object:
        return subject.is_equal_to(3)

    def wasteful() -> object:
        _ = f"to equal {3!r}, but was {subject.subject!r}"  # the forbidden act
        return subject.is_equal_to(3)

    def hoarding() -> object:
        registry.append(subject.subject)  # the other forbidden act
        return subject.is_equal_to(3)

    # A discarded message: only the peak sees it.
    assert peak_bytes_allocated(wasteful) > 0
    assert peak_bytes_allocated(clean) == 0
    assert blocks_allocated(wasteful) <= blocks_allocated(clean), (
        "net-retained blocks are expected to be blind to a discarded message; "
        "if this now fails, peak_bytes_allocated has been made redundant"
    )
    assert bytes_retained(wasteful) <= bytes_retained(clean), (
        "net-retained bytes are expected to be blind to a discarded message; "
        "if this now fails, peak_bytes_allocated has been made redundant"
    )

    # A growing registry: only the retained bytes see it.
    assert bytes_retained(hoarding) > bytes_retained(clean)
    assert blocks_allocated(hoarding) <= blocks_allocated(clean), (
        "the block count is expected to be blind to a leak of references to "
        "objects that already exist; if this now fails, bytes_retained has been "
        "made redundant"
    )
    assert peak_bytes_allocated(hoarding) <= peak_bytes_allocated(clean), (
        "the within-call peak is expected to be blind to a leak; "
        "if this now fails, bytes_retained has been made redundant"
    )
    assert len(registry) > _CALLS, "the registry test did not actually accumulate"


@measured
def test_the_measurements_leave_the_interpreter_as_they_found_it() -> None:
    """They stop the collector and start a global tracer; both must be put back.

    Worth a test because the damage is silent and lands on whatever runs next:
    a suite continuing with ``gc`` disabled leaks until it dies, and a suite
    continuing with ``tracemalloc`` on runs several times slower for no visible
    reason. ``bytes_retained`` is checked too -- it does not touch the collector,
    but it is the second function in this package that starts the global tracer,
    and the one that leaves it running is the one nobody suspects.

    ``measuring_peaks`` is the third, and the one with the longest window: it
    holds the collector off and the tracer on across a whole sweep rather than
    across one measurement, and it hands control back to a caller that may raise
    in the middle of it. Its restoration is a ``finally`` around a ``yield``,
    which is exactly the shape that is easy to get wrong, so it is checked both
    ways -- once for an ordinary exit and once for an exception thrown through
    the body.
    """
    import gc
    import tracemalloc

    assert gc.isenabled()
    assert peak_bytes_allocated(_nothing) == 0
    assert gc.isenabled()
    assert not tracemalloc.is_tracing()

    _ = bytes_retained(_nothing)
    assert gc.isenabled()
    assert not tracemalloc.is_tracing()

    with measuring_peaks(2, 1) as peak:
        assert peak(_nothing) == 0
        assert not gc.isenabled()
        assert tracemalloc.is_tracing()
    assert gc.isenabled()
    assert not tracemalloc.is_tracing()

    boom = RuntimeError("thrown through the session")
    with pytest.raises(RuntimeError, match="thrown through"), measuring_peaks(2, 1):
        raise boom
    assert gc.isenabled()
    assert not tracemalloc.is_tracing()


# ---------------------------------------------------------------------------
# Import cost
# ---------------------------------------------------------------------------
def test_importing_the_library_is_cheap() -> None:
    """A generous bound, so it catches a real regression and never flakes."""
    timings: list[float] = []
    for _ in range(5):
        result = subprocess.run(
            [sys.executable, "-X", "importtime", "-c", "import lovely_assertions"],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        rows = [
            line
            for line in result.stderr.splitlines()
            if line.rstrip().endswith("lovely_assertions")
        ]
        if rows:
            timings.append(int(rows[-1].split("|")[1].strip()) / 1000)
    assert timings, "could not read an import time from -X importtime"
    median = statistics.median(timings)
    assert median < _IMPORT_BUDGET_MS, (
        f"importing lovely_assertions took {median:.1f}ms, past the {_IMPORT_BUDGET_MS}ms bound. "
        f"Something heavy is being imported at module level, or a dependency crept in."
    )


def test_dispatch_does_not_call_a_subscripted_generic() -> None:
    """The dispatch never calls a subscripted generic alias.

    ``SequenceExpect[Any](value)`` is the natural way to keep pyright quiet about
    ``Unknown``, and it costs an order of magnitude more than
    ``SequenceExpect(value)``: the call goes through ``_GenericAlias.__call__``
    rather than straight to the class, which is more than the rest of the dispatch
    put together and buys nothing. The form reads innocently, so the source is
    checked directly rather than left to a benchmark nobody runs.
    """
    import ast

    source = (REPO_ROOT / "src" / "lovely_assertions" / "_subjects.py").read_text(encoding="utf-8")
    offenders = [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Subscript)
    ]
    assert not offenders, (
        f"_subjects.py calls a subscripted generic alias at lines {offenders}. "
        f"Call the plain class and `cast` the argument instead."
    )
