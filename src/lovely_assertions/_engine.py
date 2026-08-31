"""The two engines a failure needs, reached without importing them.

Describing where two values part company, and comparing two object graphs, are
the most expensive things this library can do -- and neither runs until an
assertion has already failed. Importing them at module level charges every
program that says ``import lovely_assertions`` for machinery most of them will
never reach.

So they are named through this module instead. The first attribute access
imports what it needs and binds the result here, which is what makes the second
one an ordinary attribute lookup rather than a hook: the cost is paid once, by
the first failure, and never by a passing assertion.

To a checker this module simply re-exports them, with their real signatures.
"""

from typing import TYPE_CHECKING, Any

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    # The redundant-looking ``as`` is what makes these re-exports rather than
    # private bindings, and the suppression is what stops `ruff --fix` from
    # removing it: without the alias every name here answers `Any` to mypy, and
    # this module is the whole surface the failure path is written against.
    from lovely_assertions._diff import describe_difference as describe_difference  # noqa: PLC0414
    from lovely_assertions._diff import render_operand as render_operand  # noqa: PLC0414
    from lovely_assertions._diff import stable_order as stable_order  # noqa: PLC0414
    from lovely_assertions._equivalence import compare as compare  # noqa: PLC0414
    from lovely_assertions._equivalence import differs as differs  # noqa: PLC0414
    from lovely_assertions._equivalence import equivalency as equivalency  # noqa: PLC0414

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

#: Which module each name comes from. A table rather than a search, so a name
#: that moves fails at the one line that has to change rather than at the call.
_HOME: dict[str, str] = {
    "describe_difference": "lovely_assertions._diff",
    "render_operand": "lovely_assertions._diff",
    "stable_order": "lovely_assertions._diff",
    "compare": "lovely_assertions._equivalence",
    "differs": "lovely_assertions._equivalence",
    "equivalency": "lovely_assertions._equivalence",
}


def __getattr__(name: str) -> Any:  # noqa: ANN401  (the engines share no signature)
    """Import the engine that owns ``name``, and bind it here for next time."""
    from importlib import import_module  # noqa: PLC0415  (kept off import time)

    home = _HOME.get(name)
    if home is None:
        message = "module " + __name__ + " has no attribute " + repr(name)
        raise AttributeError(message)
    value = getattr(import_module(home), name)
    globals()[name] = value
    return value
