"""What ``add_note`` attached to the exception.

PEP 678 notes are the context a library adds on the way out -- which file, which
row, which retry -- and they are the part of a failure a caller most wants to
assert on without pinning the message the exception was raised with.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._callable._rendering import notes_of, render_notes, rendered
from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._text import pattern_text, regex_matcher

if TYPE_CHECKING:
    import re

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class NoteAssertions[E: BaseException](Expect[E]):
    """What ``add_note`` attached to it."""

    __slots__ = ()

    def with_note(self, text: str, /, *, because: str = "") -> Self:
        """Assert the exception carries ``text`` as one of its notes, exactly.

        ``exc.add_note(...)`` is how a library on Python 3.11+ attaches context to
        an exception it re-raises, and the note is often the only place the
        interesting detail lives. The match is on the whole note, not a substring
        of one: :meth:`with_note_matching` is the search.
        """
        notes = notes_of(self._subject)
        if notes is not None and text in notes:
            return self
        return self._fail(f"to carry the note {rendered(text)}, but {render_notes(notes)}", because)

    def with_note_matching(
        self,
        pattern: "str | re.Pattern[str]",
        /,
        *,
        because: str = "",
    ) -> Self:
        """Assert some note matches the regular expression ``pattern``.

        A ``re.search`` per note, not a full match, exactly as
        :meth:`with_message`: ``with_note_matching("attempt 3")`` finds it inside
        ``"failed on attempt 3 of 3"``. Anchor the pattern yourself when a whole
        note is meant.
        """
        notes = notes_of(self._subject)
        if notes is not None:
            matcher = regex_matcher(pattern)
            for note in notes:
                if matcher.search(note) is not None:
                    return self
        return self._fail(
            f"to carry a note matching {rendered(pattern_text(pattern))},"
            f" but {render_notes(notes)}",
            because,
        )

    def has_no_notes(self, *, because: str = "") -> Self:
        """Assert nothing has been attached to the exception with ``add_note``.

        Worth asserting because a note is invisible until something prints the
        traceback: an exception that has quietly accumulated retry context is a
        different exception from the one the test meant to provoke.
        """
        notes = notes_of(self._subject)
        if not notes:
            return self
        return self._fail(f"to carry no notes, but {render_notes(notes)}", because)
