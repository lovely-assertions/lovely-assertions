"""Where a failure goes: raised at once, or collected for a report.

One ``ContextVar`` decides, and it is the only place in the library that knows
both answers. An assertion calls one function and never learns which happened,
which is what lets a soft scope work without a single assertion being written
twice.

Read on the failure path and nowhere else. A passing assertion must not pay for
the lookup, and a lookup costs nothing measurable -- so nothing that measures
allocation can catch one, and the only instrument that can is a trap placed on
the variable itself.
"""

from contextvars import ContextVar

from lovely_assertions._exceptions import AssertionFailure, hide_internal_frames
from lovely_assertions._names import FALLBACK_SUBJECT_NAME, resolve_subject_name

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class Collector:
    """The failure sink belonging to one soft scope.

    Split out from :class:`SoftScope` on purpose: the reporting primitive is a
    module-level function, and a plain record with public attributes lets it
    write there without anything reaching into another object's privates.
    """

    __slots__ = ("closed", "failures", "path")

    def __init__(self, path: str, /) -> None:
        self.path: str = path
        self.failures: list[str] = []
        #: Set when the scope that owns this collector has reported and gone.
        #:
        #: A task started inside an open block inherits a *copy of the context*,
        #: and a copy holds the same collector object. Nothing can reset a
        #: ContextVar in somebody else's context, so when that task fails an
        #: assertion after the block has exited, it routes into this list -- which
        #: nobody will ever read, and pytest prints `passed`.
        #:
        #: The collector can say so even where the routing cannot be reached. See
        #: :func:`report`.
        self.closed: bool = False

        #: The innermost active collector, or ``None`` for ordinary raising behaviour.
        #: A ``ContextVar`` rather than a global: scopes are then isolated per thread and
        #: per asyncio task, which is what makes soft assertions safe under a parallel
        #: test runner. A global would let one test's scope swallow another test's
        #: failures, and the swallowing is silent.


ACTIVE_COLLECTOR: ContextVar["Collector | None"] = ContextVar(
    "lovely_assertions.active_collector", default=None
)


def _render_failure(expectation: str, because: str, given: str | None = None) -> str:
    """Build ``Expected {name} {expectation}{because}.`` -- failure path only.

    An expectation may carry a detail block after its first line -- a diff, a list
    of nested failures. The sentence ends, and the reason attaches, at the end of
    the *first* line; the block follows. Appending the reason to the whole thing
    would leave ``... extra keys: ['id'] because the sync ran.``, hanging the
    reason off the last line of a diff.
    """
    # An explicit name also spares the frame walk, which is the expensive part.
    name = given or resolve_subject_name() or FALLBACK_SUBJECT_NAME
    collector = ACTIVE_COLLECTOR.get()
    if collector is not None and collector.path:
        name = f"{collector.path}/{name}"
    sentence, newline, block = expectation.partition("\n")
    if because:
        # Users write it both ways; neither should read "because because".
        reason = because[8:].lstrip() if because[:8].casefold() == "because " else because
        sentence = f"{sentence} because {reason}"
    return f"Expected {name} {sentence}." + newline + block


def report_failure(
    expectation: str,
    because: str,
    cause: BaseException | None = None,
    name: str | None = None,
) -> None:
    """Render and route a failure. Failure path only."""
    message = _render_failure(expectation, because, name)
    collector = ACTIVE_COLLECTOR.get()
    if collector is None or collector.closed:
        # A closed collector is reachable only from a context that copied it and
        # outlived the block -- see `Collector.closed`. Raising is the loud,
        # correct answer: the failure is real, and there is no report left to
        # join. One attribute read, on the failure path.
        raise AssertionFailure(message) from cause
    collector.failures.append(message)
