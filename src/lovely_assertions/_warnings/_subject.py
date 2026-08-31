"""The warning subject: what was issued, and what it said.

Two seams, message and predicate, over a list of captured warnings rather than
over one. A block usually issues several and an assertion is usually about
whether *any* of them matches, which is a different question from what the first
one said.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._core import Expect, describe_predicate
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatting import current_formatting
from lovely_assertions._text import pattern_text, regex_matcher
from lovely_assertions._warnings._rendering import messages_of, rendered

if TYPE_CHECKING:
    import re
    from collections.abc import Callable

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def unsatisfied(found: "tuple[Warning, ...]", /) -> str:
    """Say which warnings the predicate turned down. Failure path only.

    Separate from :func:`messages_of` because a predicate is not about the
    message: it was handed the warning objects, so the objects are what the
    reader has to look at to see why none of them qualified.
    """
    if not found:
        return "no warning was captured"
    if len(found) == 1:
        return rendered(found[0]) + " did not"
    limit = current_formatting().max_items
    shown = ", ".join([rendered(warning) for warning in found[:limit]])
    if len(found) <= limit:
        return "none of them did: " + shown
    return "none of them did: " + shown + ", ... (" + str(len(found) - limit) + " more)"


class WarnedExpect[W: Warning](Expect[tuple[W, ...]]):
    """The warnings that were issued, as a subject.

    Everything on :class:`~lovely_assertions.Expect` already works here -- the
    subject is an ordinary tuple, so ``is_equal_to``, ``matches`` and
    ``satisfies`` apply to it as a whole -- and this class adds only the
    assertions that are about being a run of warnings.

    Those read "some warning", never "every warning". A call that deprecates one
    argument and defaults another issues two warnings and the test is about one of
    them; an assertion that quantified over all of them would fail on the warning
    the test was not written about. ``with_note_matching`` on the exception
    subject makes the same choice about notes, for the same reason.
    """

    __slots__ = ()

    # -- continuations ---------------------------------------------------------
    @property
    def which(self) -> Self:
        """The warnings themselves: here a spelling, not a step.

        Elsewhere ``.which`` descends into a value an assertion *found*. ``warns``
        found the warnings and made them the subject already, so there is nothing
        to descend into; ``.which`` exists because
        ``warns(UserWarning).which.with_message("x")`` is how the assertion reads
        aloud, and it costs a property call that returns ``self``. ``RaisedExpect``
        carries the same property for the same reason.
        """
        return self

    # -- message ---------------------------------------------------------------
    def with_message(self, pattern: "str | re.Pattern[str]", /, *, because: str = "") -> Self:
        """Assert some captured warning's message matches the regular expression ``pattern``.

        A ``re.search``, not a full match, exactly as ``StringExpect.matches`` and
        ``RaisedExpect.with_message``: ``with_message("deprecated")`` passes for
        ``"parse() is deprecated since 2.0"``. Anchor the pattern yourself when the
        whole message is meant.

        The message is ``str(warning)``, which is what the interpreter prints --
        not ``args[0]``, which is only sometimes the same thing.
        """
        matcher = regex_matcher(pattern)
        for warning in self._subject:
            if matcher.search(str(warning)) is not None:
                return self
        return self._fail(
            f"to have a message matching {rendered(pattern_text(pattern))},"
            f" but {messages_of(self._subject)}",
            because,
        )

    def with_message_containing(self, text: str, /, *, because: str = "") -> Self:
        """Assert some captured warning's message contains ``text`` -- a substring, no regex.

        The message is ``str(warning)``, as in :meth:`with_message`; reach for
        that one when the expectation is a regular expression rather than a
        literal fragment. One matching warning is enough, and the failure lists
        the message of every warning the subject holds, bounded like every other
        listing in a message.
        """
        for warning in self._subject:
            if text in str(warning):
                return self
        return self._fail(
            f"to have a message containing {rendered(text)}, but {messages_of(self._subject)}",
            because,
        )

    # -- predicate -------------------------------------------------------------
    def where(self, predicate: "Callable[[W], bool]", /, *, because: str = "") -> Self:
        """Assert some captured warning satisfies ``predicate``.

        The warning-flavoured spelling of ``matches``, and the reason ``warns``
        narrows to the category asked for: a warning class that carries fields --
        a removal version, an offending attribute name -- gets them checked here
        with the type the checker knows, where ``matches`` would hand the
        predicate the whole tuple.

        The expectation says "to satisfy", not "to warn something satisfying",
        because the subject name is not always the caller: reached through the
        callable form it is the thunk, and ``Expected legacy to warn something
        satisfying is_final, but ...`` reads as a claim about ``legacy`` that was
        never made. What was tested is named in the tail either way.
        """
        for warning in self._subject:
            if predicate(warning):
                return self
        return self._fail(
            f"to satisfy {describe_predicate(predicate)}, but {unsatisfied(self._subject)}",
            because,
        )
