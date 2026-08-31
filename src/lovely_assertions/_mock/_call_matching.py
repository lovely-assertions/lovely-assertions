"""Whether one recorded call was made with exactly these arguments.

Runs on the happy path, so it allocates nothing it does not need and returns as
soon as the answer is settled. Matchers are honoured here rather than special-
cased by the assertions, which is what lets ``any_instance_of(int)`` stand in an
expected call the same way it stands anywhere else.
"""

from typing import TYPE_CHECKING, Any

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


# ---------------------------------------------------------------------------
# Matching -- these run on the happy path, so they allocate nothing beyond what
# the question itself requires.
# ---------------------------------------------------------------------------
def matches_call(
    recorded: "Sequence[Any]", args: "tuple[object, ...]", kwargs: "Mapping[str, object]", /
) -> bool:
    """Whether one recorded call was made with exactly these arguments.

    A recorded call is a ``(args, kwargs)`` pair, or a ``(name, args, kwargs)``
    triple when it came from ``mock_calls``; the last two entries are the
    arguments either way, so it is indexed from the end. Indexed rather than read
    through the ``.args``/``.kwargs`` properties so that a call recorded as a
    plain tuple -- by a mock this module did not build -- compares the same way,
    and so that nothing is allocated to ask the question.

    No signature normalisation: see the module docstring.

    The result is coerced, as ``_diff._equal`` coerces its own: the subject is a
    mock and both operands come back as ``Any``, so without it the declared
    ``bool`` would be a promise nothing checked. The ``and`` still short-circuits.
    """
    return bool(recorded[-2] == args and recorded[-1] == kwargs)
