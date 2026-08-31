"""Refusing a misconfigured option call, at the call that made it.

The engine's standing promise is that a *value* never raises: a property that
explodes, an ``__eq__`` that throws, a comparator that cannot handle the pair it
was handed -- each of those costs the reader detail and is reported as a
difference, never as an error out of the assertion library. A caller's mistake is
the opposite case and wants the opposite treatment. A comparator that is not
callable, or a depth that is negative, says nothing at all about the two graphs,
and reporting it as though it did sends the reader hunting through their data for
a defect that is in their test.

So these run before any comparison starts, and raise :class:`TypeError` or
:class:`ValueError` naming what arrived and what would have been valid. Each one
takes the suspect value as ``object`` and, where more than one method can make
the mistake, the name of the method to blame; none of them knows anything further
-- not the options class, not the field the answer ends up in. That is what lets
the whole option surface share one set of checks: the options are links in an
inheritance chain, and a guard written on one of them is out of reach of every
link below it.

One caller is not by itself a reason to keep a check with its method:
``require_depth`` serves ``with_max_depth`` alone and still sits here, because it
is the same shape as the rest -- one suspect value in, a refusal naming what
arrived out. What stays with a method is a check written in that method's own
vocabulary: ``excluding_path`` refuses the empty path where it is written,
because the sentence it raises is about paths and would say nothing on any other
builder.
"""

from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def require_names(names: "tuple[object, ...]", owner: str, /) -> None:
    """Refuse a selection call that names something which is not a name.

    A call with *no* names at all is allowed, following :func:`formatting`, which
    documents an override-less call as "the honest result of
    ``formatting(max_items=configured)`` when nothing was configured". The same
    reading applies to ``excluding(*configured)``. This is a builder rather than
    an assertion, so the rule behind ``_NEEDS_VALUES`` -- an assertion given
    nothing to look for either passes whatever it is handed or can never pass --
    does not reach it: an empty selection decides nothing, and a name that went
    missing shows up in the configuration this engine prints on every failure.

    Takes ``object`` rather than ``str`` so that the type check means something:
    against the declared type it would be a tautology, and a call site is exactly
    where a caller's declaration might be wrong (``_formatters._check`` and
    ``_formatting._checked`` take the same line for the same reason).
    """
    for name in names:
        if not isinstance(name, str):
            message = owner + " needs names, not " + type(name).__name__
            raise TypeError(message)


def require_class(candidate: object, owner: str, /) -> None:
    """Refuse something ``isinstance`` could not use as a class, for the same reason."""
    if isinstance(candidate, type):
        return
    message = owner + " needs a class to claim, not " + type(candidate).__name__
    raise TypeError(message)


def require_callable(candidate: object, owner: str, /) -> None:
    """Refuse a comparator that is not callable.

    Worth reporting here rather than at the first comparison: the engine treats a
    comparator that raises as a finding about the *values*, so a non-callable one
    would quietly turn every value of its type into a difference and never say why.
    """
    if callable(candidate):
        return
    message = owner + " needs a callable comparator, not " + type(candidate).__name__
    raise TypeError(message)


def require_depth(candidate: object, /) -> int:
    """Validate a depth bound, or say which way it was wrong."""
    if not isinstance(candidate, int):
        message = "with_max_depth needs an integer, not " + type(candidate).__name__
        raise TypeError(message)
    if candidate < 0:
        message = "with_max_depth needs zero or more, not " + str(candidate)
        raise ValueError(message)
    return candidate
