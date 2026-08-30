"""Running a caller's callback with its failures collected rather than raised.

Two shapes of callback reach this library and they are told apart by what they
return, not by which method took them: an *inspector* asserts and returns
nothing, a *predicate* answers true or false. Handing a predicate where an
inspector belongs is the mistake this refuses -- silently accepting it would
count `False` as a pass, which is the one wrong answer nobody would question.
"""

from typing import TYPE_CHECKING, Any

from lovely_assertions._core._routing import ACTIVE_COLLECTOR, Collector
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Callable

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def describe_predicate(predicate: object) -> str:
    """Name a predicate for a failure message. Failure path only."""
    name = getattr(predicate, "__name__", None)
    if isinstance(name, str) and name != "<lambda>":
        return name
    return "the predicate"


def collect_failures(
    inspector: "Callable[[Any], object]",
    subject: Any,  # noqa: ANN401  (whatever the caller handed to `expect`)
    /,
    predicate_form: str = "",
) -> list[str]:
    """Run ``inspector`` with failures collected rather than raised.

    Used by the inspector-taking assertions -- ``satisfies``, ``satisfies_any``,
    ``satisfies_none``, ``all_satisfy`` and ``satisfies_respectively`` -- and by
    nothing else, which is why the guard below lives here rather than at each of
    their call sites, where a newly added one could forget it. A non-assertion
    exception still propagates: a broken inspector is a bug in the test, not a
    finding about the subject.

    **A ``bool`` handed back is refused.** These take an *inspector*, which
    asserts on what it is given. Other methods on the same subjects take a
    *predicate*, which returns a verdict instead -- ``matches``, ``only_contains``,
    ``satisfies_in_any_order``, ``contains_matching`` and their neighbours all
    teach that lambda shape, so writing one here is a short step away and the
    checkers cannot see it: ``Callable[[T], object]`` accepts ``bool`` happily.
    An inspector that returns ``True`` or ``False`` has asserted nothing, so the
    call is unconditionally green -- the worst thing an assertion can be.

    ``predicate_form`` names the sibling that would have been right, where one
    exists. Two pointer comparisons on the happy path, and nothing built unless
    the guard fires.
    """
    collector = Collector("")
    token = ACTIVE_COLLECTOR.set(collector)
    try:
        outcome = inspector(subject)
    finally:
        ACTIVE_COLLECTOR.reset(token)
    if outcome is True or outcome is False:
        raise TypeError(_predicate_not_inspector(outcome, predicate_form))
    return collector.failures


def _predicate_not_inspector(outcome: bool, predicate_form: str, /) -> str:
    """Explain the inspector/predicate mix-up. Failure path only."""
    remedy = (
        "use `" + predicate_form + "` to pass a predicate, or assert instead: "
        if predicate_form
        else "assert instead: "
    )
    return (
        "the callback returned "
        + repr(outcome)
        + " instead of asserting anything, so this would have passed whatever the "
        + "subject was. An inspector asserts; a predicate returns a verdict. "
        + remedy
        + "`lambda it: expect(it).is_positive()`"
    )
