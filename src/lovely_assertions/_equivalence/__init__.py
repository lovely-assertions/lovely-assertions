"""Structural equivalence: two object graphs compared member by member.

``is_equal_to`` asks one question -- ``__eq__`` -- and a great many Python types
answer it by identity, by type, or not at all. Equivalence asks a different one:
*do these two graphs hold the same information?* A ``dict`` against a dataclass
member, a ``list`` against a ``tuple``, a record whose ``password`` field nobody
cares about, two timestamps a millisecond apart. FluentAssertions built its
reputation on that assertion; this is the engine behind the Python one.

The package has two entry points -- :func:`compare`, which says how two graphs
differ, and :func:`differs`, which says only whether they do -- and one
configuration object, :class:`Equivalency`, handed out by :func:`equivalency` and
given a tolerance by :func:`close_within`. Everything else is private.

Seven rules shape it.

**"" means equivalent.** :func:`compare` returns an empty string when the two
graphs agree and a rendered block when they do not, so the caller branches on
emptiness and reports every finding in a single ``_fail``. That is the shape
``Expect.satisfies`` already uses, which is why soft-scope behaviour falls out of
it for free.

**It never raises because a value misbehaved.** A property that explodes, a ``__repr__``
that lies, an ``__eq__`` that throws, a structure that contains itself: each of
those costs the reader detail and never turns their test failure into an error
raised inside the assertion library. The guards are per member rather than around
the walk, so one hostile field of a twelve-field record costs that field and not
the other eleven. A *misconfigured call* is different and does raise, at the call,
where the mistake is.

**Failing is the safe direction.** ``_diff`` degrades to ``""`` because its block
is appended to a message that has already failed. Here ``""`` is a verdict, so
degrading to it would turn a broken comparison into a **passing test**. Every
degradation in this module therefore produces a *difference*, never silence.

**Equality settles equivalence.** Two values that are ``==`` hold the same
information, so the walk stops there and reports nothing. That is not only an
optimisation: it is what keeps equivalence from being *stricter* than equality.
``Point(1, 2) == (1, 2)`` is true, so an engine that took the pair apart
and called a field ``x`` unmatched against index ``0`` would fail the weaker
assertion where the stronger one passes -- the one pair of answers a reader could
never make sense of. Two options escape that by being asked *before* ``==`` rather
than after it: :meth:`Equivalency.using` replaces equality for the types it
registers, so a comparator narrower than ``==`` refuses a pair Python calls equal,
and :meth:`Equivalency.comparing_enums_by_name` does the same for two members
sharing a value under different names. Every other option only *widens* what
counts as equivalent, which is why those two are the only ones that can be
stricter.

**Strict ordering is the default (a deliberate inversion of FluentAssertions).**
In Python a ``list`` is ordered by definition and ``set`` exists for the other
case, so a default under which ``[1, 2]`` matches ``[2, 1]`` writes tests that
pass when they should not. ``ignoring_order()`` opts in, and pays the quadratic
matching cost that opting in implies.

**The expectation drives, and a mapping is not a record.** ``is_equivalent_to``
compares the members the *expectation* names. A field only the subject carries is
not a difference -- asserting an ORM row, a pydantic model or a wire payload
against a small literal that names the three fields the test is about is the
commonest reason anyone reaches for structural equivalence, and a rule that
reported the other nine fields as surplus makes that unwritable. It is also the
asymmetry that gives ``BeEquivalentTo`` a reason to exist as something other than
``Be``. ``comparing_all_members()`` compares both member sets, for an expectation
meant to be exhaustive; ``excluding_missing()`` relaxes the other direction, so
that a member the expectation names and the subject lacks is skipped rather than
reported.

A **mapping is decided separately and the other way**: both directions are still
reported there, and neither option touches it. A record's fields are the shape its
author declared, and an expectation object is a *stand-in* for that shape -- what
it leaves out, it leaves out on purpose. A dictionary's keys are its data. The
expectation ``{"id": 1, "total": 5}`` is not a partial description of a payload,
it is a payload, and "the response carried a key I did not expect" is precisely
what a test written against one is asked to catch. FluentAssertions keeps
dictionary equivalency apart for the same reason. ``excluding()`` still reaches a
key by name, which is the escape when a payload carries a timestamp.

The consequence worth knowing is that an expectation naming *no* members is
satisfied by anything -- the same vacuity ``including()`` documents for a name
nothing carries, reached the same way and answered the same way, because saying so
would need a channel for reporting on the comparison itself rather than on the two
values, and this engine has none.

**It is bounded, and a bound it hits is never a verdict.** The engine stops
collecting differences at :data:`MAX_DIFFERENCES`, which is a bound on *detail*:
two hundred findings already settle "not equivalent", so the report is truncated
and the answer stands. The two bounds on order-insensitive pairing --
:data:`_MAX_MATCHING` and :data:`_MAX_SCANNING` -- are different in kind: hitting
one means the items were never paired off, so neither answer was established.
Those raise :class:`ValueError` out of :func:`compare` rather than returning a
verdict, for the reason spelled out on :class:`TruncatedError`, and a walk that
uses up the interpreter's stack leaves the same way for the same reason. The
*rendering* bounds -- how many differences are shown, how long a value may be --
come from :func:`~lovely_assertions.current_formatting` and are therefore read on
the reporting path only, never during the walk.

Two house rules show up in the shape of the code. A message is never built outside
the argument list of a ``_fail(...)`` call, and there is no ``_fail`` here, so
there are no f-strings either: every message is concatenated, exactly as in
``_diff``, ``_formatters`` and ``_formatting``. And nothing a passing assertion
would pay for is imported at module scope -- nothing here imports ``dataclasses``
at all, the field resolver it borrows imports it inside itself, ``attrs`` is
duck-typed through ``__attrs_attrs__`` with nothing imported at all, and pydantic
v2 keeps its field values in ``__dict__`` and needs nothing.

A note on the duplication with ``_diff``. Its clipping, counting and item
rendering are the conventions this package follows, and they live in modules that
package keeps to itself: only :func:`~lovely_assertions._diff.render_operand`,
:func:`~lovely_assertions._diff.describe_difference` and
:func:`~lovely_assertions._diff.stable_order` cross out of it, and reaching around
that for a leaf helper would tie this engine to an arrangement the diff engine is
free to change. So ``render_operand`` is reused and the rest is reimplemented here
to the same behaviour. Field resolution is not duplicated: both engines read it
from ``_reflection``, because two resolvers that drift produce a message that
contradicts the comparison behind it.
"""

from abc import get_cache_token

from lovely_assertions._equivalence._budget import (
    Budget,
    TruncatedError,
    out_of_stack,
)
from lovely_assertions._equivalence._classification import ROUTE_BY_TYPE, ROUTE_TOKEN
from lovely_assertions._equivalence._findings import MAX_DIFFERENCES, Findings
from lovely_assertions._equivalence._labels import INDENT
from lovely_assertions._equivalence._memo import Memo
from lovely_assertions._equivalence._options import require_options
from lovely_assertions._equivalence._rendering import render
from lovely_assertions._equivalence._walk import Walk
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

from lovely_assertions._equivalence._options import Equivalency as Equivalency
from lovely_assertions._equivalence._options import close_within as close_within
from lovely_assertions._equivalence._options import equivalency as equivalency

__all__ = ["Equivalency", "close_within", "compare", "differs", "equivalency"]


# ---------------------------------------------------------------------------
# The entry points
# ---------------------------------------------------------------------------
def compare(actual: object, expected: object, options: Equivalency, /) -> str:
    """An account of how two graphs differ, or ``""`` when they are equivalent.

        >>> compare({"id": 1}, {"id": 1}, equivalency())
        ''

    ``""`` means equivalent, so the caller can branch on emptiness. Otherwise a
    block that starts with a newline and does not end with one, ready to be
    appended to a one-line failure message -- the same shape
    ``_diff.describe_difference`` returns.

    **No misbehaving value makes this raise.** A property that raises, a hostile
    ``__repr__``, an ``__eq__`` that throws, a cycle: each costs detail, never the
    caller's test. Note which way the degradation runs, because it is the opposite
    of ``_diff``'s. There, ``""`` is a block nobody could build and the message
    stands without it; here ``""`` is the verdict *equivalent*, so a comparison
    that could not be completed reports a difference rather than falling silent. A
    broken engine fails a test that should have passed, which is loud; the
    alternative passes a test that should have failed, which is not.

    What does raise is never a verdict. A misconfigured ``options`` raises at the
    call, because the failure it prevents is otherwise a confusing message about
    the values rather than a clear one about the mistake. An order-insensitive
    comparison of more items than :data:`_MAX_MATCHING` or :data:`_MAX_SCANNING`
    will pay for raises :class:`ValueError` naming the bound it stopped at, and so
    does a walk that used up the interpreter's stack -- not because a value
    misbehaved, but because the pairing, or the descent, never finished and neither
    answer was reached. See :class:`TruncatedError` for why that cannot be reported
    as a difference instead.

    "Never raises" means never for an ``Exception``, which is where every guard in
    this module and in ``_diff`` is drawn. A ``BaseException`` -- a ``Ctrl-C``, an
    exiting interpreter -- goes through, because a value that raises one of those
    is not reporting a difference, it is asking everything to stop.
    """
    require_options(options)
    # Forget every remembered route if the ABC registry has moved; see
    # `ROUTE_TOKEN`. Written here rather than called, because a helper's frame
    # is half the cost of the check on a comparison that answers in a microsecond.
    token = get_cache_token()
    if token != ROUTE_TOKEN[0]:
        ROUTE_BY_TYPE.clear()
        ROUTE_TOKEN[0] = token
    findings = Findings(MAX_DIFFERENCES)
    try:
        Walk(options, Memo(), findings, Budget(), False).compare(actual, expected, "", 0)
    except TruncatedError as stopped:
        # Caught before the blanket handler below, and deliberately not returned as
        # a difference: this is the one outcome that is neither verdict.
        raise ValueError(str(stopped)) from None
    except RecursionError:
        # The same rule, for the other way a walk can stop without finishing. A
        # `RecursionError` is not a statement about the values -- it is the walk
        # saying it never got to the end of them -- so it is caught here rather
        # than by the blanket handler below, which would turn it into "the two are
        # not equivalent", which `is_not_equivalent_to` reads as "they differ" and
        # **passes**. A graph a couple of hundred levels deep with a
        # `with_max_depth` to match is all it takes, and the green is silent.
        raise ValueError(out_of_stack(options.max_depth)) from None
    # the contract: a value never turns into an error here
    except Exception:
        return (
            "\n" + INDENT + "the comparison could not be completed, so the two are not equivalent"
        )
    if not findings.items:
        return ""
    try:
        return render(findings, options)
    # same contract, one step later
    except Exception:
        return "\n" + INDENT + "they are not equivalent, but the differences could not be rendered"


def differs(actual: object, expected: object, options: Equivalency, /) -> bool:
    """Whether two graphs differ, without saying how.

        >>> differs({"id": 1}, {"id": 1}, equivalency())
        False
        >>> differs({"id": 1}, {"id": 2}, equivalency())
        True

    :func:`compare`'s verdict without :func:`compare`'s report, for the caller that
    is about to throw the report away. ``Expect.is_not_equivalent_to`` **passes**
    on the branch where the two differ, so a report built there is built and
    dropped unread -- and building it means gathering up to two hundred
    ``Difference`` records, rendering every one of them and reading
    :func:`~lovely_assertions.current_formatting` -- a ``ContextVar`` -- several
    times over. A passing assertion is meant to cost a comparison and a return.
    ``Expect.is_equivalent_to`` calls :func:`compare` instead, because the report is
    exactly what its failing branch has to print.

    The saving is in the collector rather than in a second algorithm: this is the
    same walk with :class:`Findings` bounded at one, which is what the pairing
    probes already use, so it stops at the first disagreement instead of
    describing all of them.

    **It answers the verdict and never the message, and the caller must keep that
    true.** A ``True`` here is a promise that :func:`compare` has something to
    report, not a substitute for it: an assertion whose failure has to name *what*
    differed calls :func:`compare` on that branch, or it loses the account, which is
    the whole product. So the walk that only decides sits on the passing branch, and
    the report is built exactly where it is read.

    Raises what :func:`compare` raises and for the same reasons -- a misconfigured
    ``options``, a pairing that ran out of allowance, a walk that ran out of stack
    -- because those are not verdicts and a boolean has no room for a third answer
    either.
    """
    require_options(options)
    # Forget every remembered route if the ABC registry has moved; see
    # `ROUTE_TOKEN`. Written here rather than called, because a helper's frame
    # is half the cost of the check on a comparison that answers in a microsecond.
    token = get_cache_token()
    if token != ROUTE_TOKEN[0]:
        ROUTE_BY_TYPE.clear()
        ROUTE_TOKEN[0] = token
    findings = Findings(1)
    try:
        Walk(options, Memo(), findings, Budget(), False).compare(actual, expected, "", 0)
    except TruncatedError as stopped:
        raise ValueError(str(stopped)) from None
    except RecursionError:
        raise ValueError(out_of_stack(options.max_depth)) from None
    # the contract: a comparison that broke is not an equivalence
    except Exception:
        return True
    return bool(findings.items)
