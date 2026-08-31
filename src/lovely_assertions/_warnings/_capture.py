"""Selecting the warnings of a category, and putting back the rest.

Re-issuing what an assertion did not ask about is the half people forget. A
capture swallows every warning in the block, so one that nobody asserted on would
disappear from the run -- and a warning that vanishes because a test looked for a
different one is a warning nobody will ever see again.
"""

from typing import TYPE_CHECKING

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Sequence
    from warnings import WarningMessage

    from lovely_assertions._occurrence import Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


# ---------------------------------------------------------------------------
# The capture, and the verdict over it
# ---------------------------------------------------------------------------
def matching[W: Warning](
    records: "Sequence[WarningMessage]", category: type[W], /
) -> "tuple[W, ...]":
    """The warnings of ``category`` among ``records``, in the order they were issued.

    A subclass counts, matching ``raises`` and ``isinstance`` and every other type
    test in this library; ``raises_exactly`` is where the other question lives,
    and no warning test has yet wanted it.

    A plain loop rather than a comprehension because this runs on a *passing*
    assertion, where the only allocation allowed is the iterator a ``for`` needs
    -- ``_text.holds_every`` states the same rule at more length. The tuple it
    returns is the assertion's product, not waste: it is the subject the caller
    goes on to assert against.

    ``WarningMessage.message`` is typed ``Warning | str`` and is a ``Warning``
    every time in practice -- ``warn_explicit`` instantiates the category before
    it records anything -- so the ``isinstance`` is a narrowing the checkers need
    rather than a check the runtime does.
    """
    found: list[W] = []
    for record in records:
        message = record.message
        if isinstance(message, category):
            found.append(message)
    return tuple(found)


def allowed(found: int, occurrences: "Occurrence | None", /) -> bool:
    """Whether ``found`` matching warnings satisfy the constraint.

    ``None`` means "at least one", which is what the assertion says when it is
    written without a count. It is not spelled ``at_least(1)`` internally because
    that would put "at least once" into every message that has no constraint in
    it, and the reader would go looking for the argument that produced it.
    """
    if occurrences is None:
        return found > 0
    return occurrences.allows(found)


def reissue_unmatched(records: "Sequence[WarningMessage]", category: type[Warning], /) -> None:
    """Hand every warning the assertion was not about back to the ambient filters.

    Called once the capture has been closed, so the project's own filters and
    ``showwarning`` are back in place and the warning goes where it would have
    gone without the block. The module docstring gives the reasoning and the two
    prices; what is here is the mechanics.

    ``warn_explicit`` rather than ``warn``: it takes the recorded filename and
    line number, so a re-issued warning still points at the code that issued it
    instead of at this function. ``registry=None`` is left to default, which makes
    ``warn_explicit`` use a throwaway dict -- there is no way to recover the
    module registry the original went through, and a fresh one shows the warning
    rather than hiding it, which is the safe direction to be wrong in.

    The instance is passed through as it stands, so its type, its arguments and
    anything a subclass carries survive. A ``str`` cannot reach here through
    ``warnings.warn`` -- see :func:`matching` -- but the annotation permits one,
    and re-wrapping it in the recorded category is precisely what ``warn_explicit``
    would have done with it.
    """
    import warnings  # noqa: PLC0415  (deferred: only a warning assertion pays for it)

    for record in records:
        message = record.message
        if isinstance(message, category):
            continue
        warnings.warn_explicit(
            message if isinstance(message, Warning) else record.category(message),
            record.category,
            record.filename,
            record.lineno,
            source=record.source,
        )
