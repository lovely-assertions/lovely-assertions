"""How a warning, and a run of them, reads inside a message.

A warning carries a category, a message and the line it was issued from, and the
line is the part a reader needs most -- a warning is usually about code somewhere
else, and naming the file and line is what turns "a DeprecationWarning was
issued" into somewhere to go.
"""

from typing import TYPE_CHECKING

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting
from lovely_assertions._text import count_of, length_note

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
# Rendering -- failure path only.
#
# No f-strings here: an f-string is a message, and a message is only ever built
# inside the `_fail` call itself, so a passing assertion formats nothing.
# ---------------------------------------------------------------------------
def rendered(value: object, /) -> str:
    """Render a value for a failure message, bounded by the formatting scope.

    Through :func:`~lovely_assertions.format_value` rather than ``repr``, so a
    warning class with a registered formatter reads as itself, and bounded by
    ``max_chars`` read at the moment of the failure rather than by a module
    constant -- a block that opened ``formatting(max_chars=...)`` asked for the
    longer rendering and gets it.

    ``_callable.rendered`` is the same helper against a fixed cap. The two are
    not shared because importing a private name across modules is what pyright
    reports as ``reportPrivateUsage``, and the suppression it would take costs
    more than the few lines it would save. Every subject module here --
    ``_enum``, ``_path``, ``_datetime``, ``_ordered``, ``_type`` -- carries its
    own ``rendered`` for that same reason.
    """
    text = format_value(value)
    limit = current_formatting().max_chars
    if len(text) <= limit:
        return text
    return text[:limit] + "..." + length_note(len(text))


def located(record: "WarningMessage", /) -> str:
    """One warning, with the place ``stacklevel`` said it came from. Failure path only.

    The location is the half of a warning that a message usually drops, and it is
    the half that ends the search: two ``DeprecationWarning('deprecated')`` from
    different call sites are the same string and different findings. The filename
    is printed as recorded -- absolute, normally -- rather than shortened to a
    basename, because two files in a project share a basename often enough that a
    shortened one sends the reader to the wrong one.
    """
    return rendered(record.message) + " at " + record.filename + ":" + str(record.lineno)


def listed(records: "Sequence[WarningMessage]", /) -> str:
    """Lay a run of warnings out in a sentence, bounded and counted. Failure path only.

    The bound is ``max_items`` from the scope in force, and what is left out is
    counted rather than dropped silently: a message that truncates without saying
    so is a message the reader will trust wrongly. ``_callable._render_notes``
    does the same for an exception's notes.
    """
    limit = current_formatting().max_items
    shown = ", ".join([located(record) for record in records[:limit]])
    if len(records) <= limit:
        return shown
    return shown + ", ... (" + str(len(records) - limit) + " more)"


def messages_of(found: "tuple[Warning, ...]", /) -> str:
    """Describe the messages the captured warnings carried. Failure path only.

    The listing is the point. "No warning matched" is a fact the reader already
    had; *which* messages were there is the one they would otherwise go and print
    by hand, and the singular case gets a singular sentence because a message
    that says "the messages were 'x'" reads as one nobody looked at.
    """
    if not found:
        return "no warning was captured"
    if len(found) == 1:
        return "the message was " + rendered(str(found[0]))
    limit = current_formatting().max_items
    shown = ", ".join([rendered(str(warning)) for warning in found[:limit]])
    if len(found) <= limit:
        return "the messages were " + shown
    return "the messages were " + shown + ", ... (" + str(len(found) - limit) + " more)"


def warned_report(
    records: "Sequence[WarningMessage]", found: int, occurrences: "Occurrence | None", /
) -> str:
    """The tail of a failure that expected a warning and did not get it. **Failure path only.**

    Shared by the three sites that report it -- the context manager's ``__exit__``
    and ``CallableExpect.warns``, in both their constrained and unconstrained
    forms -- because a tail written three times is a tail that will read three
    ways. It takes the *pieces* and never a built message, so nothing is formatted
    until one of the branches below runs, and all of them are already inside a
    failure.

    The constrained form borrows ``CollectionExpect.contains``'s sentence --
    ``{describe()}, but found {n}: {listing}`` -- rather than inventing a second
    way to say the same thing, so a reader who has seen one occurrence failure has
    seen them all.
    """
    if occurrences is not None:
        # The leading space belongs to the constraint, not to the caller: without a
        # constraint the tail starts at the comma, so the two forms cannot share
        # one separator and the sentence has to carry it here.
        return " " + occurrences.describe() + ", but found " + str(found) + ": " + issued(records)
    if not records:
        return ", but nothing was warned"
    return ", but the warnings issued were " + listed(records)


def issued(records: "Sequence[WarningMessage]", /) -> str:
    """The listing, or a phrase that fits where the listing would have gone."""
    if not records:
        return "no warnings at all"
    return listed(records)


def issued_report(records: "Sequence[WarningMessage]", category: type[Warning], /) -> str:
    """The tail of a failure that expected *no* warning. **Failure path only.**

    Only the offending warnings are listed. The others were re-issued on the way
    out and are not what failed, so naming them here would pad the finding with
    the one thing the assertion deliberately did not care about.
    """
    offending = [record for record in records if isinstance(record.message, category)]
    if len(offending) == 1:
        return "issued " + located(offending[0])
    return "issued " + count_of(len(offending), "warning") + ": " + listed(offending)
