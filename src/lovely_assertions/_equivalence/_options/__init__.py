"""The configuration object, and the functions that hand one out or read one back.

The builder methods are split by the question they answer -- which members are
compared, and what comparing one means -- into the files this one stacks. What
stays here is the part that needs every field at once: :class:`Equivalency`, whose
``__repr__`` replays the options in the order a caller would have chained them,
and :func:`configuration`, which spells the same state as the prose printed on
every equivalence failure. Both would have to be edited by any new option anyway,
so they sit where the assembled class does rather than being spread across the
links.

The rest is the boundary around a configuration rather than a part of one.
:func:`equivalency` hands out the shared default. :func:`close_within` builds a
comparator for :meth:`Equivalency.using`, and is the reason a tolerance can be a
``timedelta`` without this package ever importing ``datetime``: the annotation is
under ``TYPE_CHECKING`` and the value is only ever subtracted and compared.
:func:`require_options` is the single check that makes :func:`compare` raise on
its arguments, because an ``options`` that is not an :class:`Equivalency` says
nothing about the two graphs and everything about the call.

That is the shape of both refusals here. A negative tolerance and a wrong
``options`` are reported where the mistake was made, not at the first comparison
that would have stumbled over them, where either would read as a claim about the
values.
"""

from typing import TYPE_CHECKING, Any, Final, override

from lovely_assertions._equivalence._labels import callable_name, names_text, render_names
from lovely_assertions._equivalence._options._base import DEFAULT_MAX_DEPTH
from lovely_assertions._equivalence._options._behaviour import BehaviourOptions
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import timedelta

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class Equivalency(BehaviourOptions):
    """How two graphs are to be compared. Immutable; every method returns a new one.

        >>> equivalency().excluding("password").ignoring_order()
        equivalency().excluding('password').ignoring_order()

    Immutable for the reason :class:`~lovely_assertions.FormattingOptions` is: a
    configuration built in a fixture is shared by every test that uses it, and one
    that a test could edit would change what the others compare. Building on top
    of a shared one is what the methods are for.

    The fields are public and readable, because a reader debugging an equivalence
    failure is usually asking exactly what was in force -- which is also why
    :func:`compare` prints it into the failure message (a deliberate copy of
    FluentAssertions; it is what makes the assertion debuggable, and it is cheap).
    """

    __slots__ = ()

    @override
    def __repr__(self) -> str:
        """The chain of calls that would build these options.

        Pasteable but for one part. A comparator is rendered by name, so
        ``close_within(0.01)`` comes back as ``close_within``: the line says which
        function is in force rather than the expression that made it, and a lambda
        has no name to give at all.
        """
        calls = ["equivalency()"]
        if self.excluded_names:
            calls.append(".excluding(" + names_text(self.excluded_names) + ")")
        if self.excluded_paths:
            calls.append(".excluding_path(" + names_text(self.excluded_paths) + ")")
        if self.included_names:
            calls.append(".including(" + names_text(self.included_names) + ")")
        if self.all_members:
            calls.append(".comparing_all_members()")
        if self.excluded_missing:
            calls.append(".excluding_missing()")
        if self.ignore_order:
            calls.append(".ignoring_order()")
        for kind, comparator in self.comparators:
            calls.append(".using(" + kind.__name__ + ", " + callable_name(comparator) + ")")
        if self.max_depth != DEFAULT_MAX_DEPTH:
            calls.append(".with_max_depth(" + str(self.max_depth) + ")")
        if self.enums_by_name:
            calls.append(".comparing_enums_by_name()")
        return "".join(calls)


#: The default configuration. One shared instance rather than a fresh one per
#: call: it is immutable, so sharing it across threads shares nothing that can
#: change, and every method builds a copy anyway.
_DEFAULT: Final = Equivalency()


def equivalency() -> Equivalency:
    """Return the default configuration: strict ordering, ten levels, nothing excluded.

        >>> equivalency().max_depth
        10

    The starting point for a chain of options, and what ``is_equivalent_to`` uses
    when it is given none. The instance is shared and immutable, so keeping it in
    a fixture and building on it in each test is safe.
    """
    return _DEFAULT


# ---------------------------------------------------------------------------
# Tolerance
# ---------------------------------------------------------------------------
def close_within(tolerance: "float | timedelta") -> "Callable[[Any, Any], bool]":
    """Build a comparator for :meth:`Equivalency.using` that allows ``tolerance``.

        >>> equivalency().using(float, close_within(0.01))
        equivalency().using(float, close_within)

    This is the vehicle for float and datetime tolerance, and it is one function
    for both because Python already makes them one problem: ``abs(a - b) <= t``
    reads a ``float`` against a ``float`` and a ``datetime`` against a
    ``timedelta`` without knowing which it has. Pass the tolerance in whatever
    type the values subtract to -- a ``float`` for numbers, a ``timedelta`` for
    datetimes -- and hand the result to :meth:`Equivalency.using`.

    Raises :class:`ValueError` here, at the call that builds the comparator,
    rather than at the first comparison that uses it. A negative tolerance means
    nothing is ever close and a NaN one means the same, so both would turn every
    value in the graph into a difference -- a failure a long way from the mistake
    that caused it. ``tolerance - tolerance`` is the zero of whatever type was
    passed, which is how one check covers both without importing ``datetime``.

    Subtracting two values that will not subtract raises, and that is left alone:
    the engine catches it and reports which member the comparator could not
    handle, which is the finding.
    """
    # Widened deliberately. Against the declared union the checker refuses the
    # arithmetic outright -- a `float` will not subtract a `timedelta` -- although
    # neither branch of the union ever meets the other. The widening is what lets
    # one expression cover both, and it is also what makes the check mean
    # something when a caller's declaration was wrong.
    bound: Any = tolerance
    if not bound >= bound - bound:
        message = "tolerance must be zero or more, not " + repr(tolerance)
        raise ValueError(message)

    def close_within(actual: Any, expected: Any, /) -> bool:  # noqa: ANN401 (a comparator takes whatever the graph holds)
        return bool(abs(actual - expected) <= tolerance)

    return close_within


def require_options(candidate: object, /) -> None:
    """Refuse an ``options`` argument that is not an :class:`Equivalency`.

    The one thing that makes :func:`compare` raise on its arguments. It is not a
    value being compared, it is the instruction for comparing them, and letting a
    wrong one through would produce a puzzling message about the graphs in place of
    a plain one about the call.
    """
    if isinstance(candidate, Equivalency):
        return
    message = "options must be an Equivalency, not " + type(candidate).__name__
    raise TypeError(message)


def configuration(options: Equivalency, /) -> str:
    """The effective configuration, in one clause per decision.

    Printed on every failure, deliberately, and copied from FluentAssertions
    because it is what makes an equivalence failure debuggable: a reader who
    excluded the wrong field, or forgot ``ignoring_order()``, can see that they
    did without reading the test's fixtures. The two defaults are printed too --
    they are the two settings a surprising result is most often explained by.
    """
    clauses = [
        "order ignored" if options.ignore_order else "strict ordering",
        "maximum depth " + str(options.max_depth),
    ]
    if options.excluded_names:
        clauses.append("excluding members " + render_names(options.excluded_names))
    if options.excluded_paths:
        clauses.append("excluding paths " + render_names(options.excluded_paths))
    if options.included_names:
        clauses.append("comparing only members " + render_names(options.included_names))
    if options.all_members:
        clauses.append("comparing every member of both")
    if options.excluded_missing:
        clauses.append("skipping members the subject does not carry")
    if options.enums_by_name:
        clauses.append("comparing enums by name")
    if options.comparators:
        claimed = [kind.__name__ for kind, _ in options.comparators]
        clauses.append("a custom comparator for " + ", ".join(claimed))
    return ", ".join(clauses)
