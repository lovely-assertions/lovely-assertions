"""What the mock was called with.

The seam that has to explain itself when it fails: "was never called with these
arguments" is true of a mock that was called four times with nearly-these, and
the message says which of the four came closest and what differed about it.
"""

from typing import TYPE_CHECKING, Any, Self

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._mock._base import MockBase
from lovely_assertions._mock._call_matching import matches_call
from lovely_assertions._mock._differences import (
    describe_call_difference,
    earlier_matches_note,
    nearest_note,
    which_matched,
)
from lovely_assertions._mock._rendering import (
    call_numbers,
    last_clause,
    render_call,
    render_calls,
    render_options,
    wanted,
)
from lovely_assertions._text import count_of

if TYPE_CHECKING:
    from collections.abc import Sequence


#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class ArgumentAssertions(MockBase):
    """What the mock was called with."""

    __slots__ = ()

    def was_called_with(self, *args: object, because: str = "", **kwargs: object) -> Self:
        """Assert the **most recent** call was made with these arguments.

        The same rule ``assert_called_with`` follows, and the same trap: earlier
        calls are not looked at. That trap is why the failure says so. When an
        earlier call *did* match, the message names it -- otherwise the reader is
        left staring at two identical-looking argument lists wondering why the
        assertion failed.

        ``because`` is keyword-only, and therefore shadows a keyword argument of
        the same name that the subject itself may have been called with; see the
        module docstring for the escape hatch. Reach for
        :meth:`was_ever_called_with` when the call under test need not be the last
        one.
        """
        recorded: Sequence[Any] = self._subject.call_args_list
        if recorded and matches_call(recorded[-1], args, kwargs):
            return self
        if not recorded:
            return self._fail(
                f"to have been called with {wanted(args, kwargs)}, but {self._how_it_was_called()}",
                because,
            )
        return self._fail(
            f"to have been called with {wanted(args, kwargs)},"
            f" but was {last_clause(len(recorded))} {render_call(recorded[-1], render_options())}"
            + describe_call_difference(recorded[-1], args, kwargs)
            + earlier_matches_note(recorded, args, kwargs),
            because,
        )

    def was_called_once_with(self, *args: object, because: str = "", **kwargs: object) -> Self:
        """Assert the mock was called exactly once, and with these arguments.

        Three different bugs fail this assertion, and each gets its own message:
        it was never called, it was called once with something else, or it was
        called more than once. ``assert_called_once_with`` reports all three as
        the same sentence about the count, which is the single worst message in
        the module it comes from.
        """
        recorded: Sequence[Any] = self._subject.call_args_list
        if len(recorded) == 1 and matches_call(recorded[0], args, kwargs):
            return self
        if not recorded:
            return self._fail(
                f"to have been called once with {wanted(args, kwargs)},"
                f" but {self._how_it_was_called()}",
                because,
            )
        if len(recorded) == 1:
            return self._fail(
                f"to have been called once with {wanted(args, kwargs)},"
                f" but was called with {render_call(recorded[0], render_options())}"
                + describe_call_difference(recorded[0], args, kwargs),
                because,
            )
        return self._fail(
            f"to have been called once with {wanted(args, kwargs)},"
            f" but {self._how_it_was_called()}" + which_matched(recorded, args, kwargs),
            because,
        )

    def was_ever_called_with(self, *args: object, because: str = "", **kwargs: object) -> Self:
        """Assert some call -- any of them -- was made with these arguments.

        ``assert_any_call``, and the assertion to reach for when the call under
        test is one of several and its position is not the point. The failure
        shows the calls that were made and picks the nearest of them to explain,
        because "none of these four matched" is a fact the reader already had.
        """
        recorded: Sequence[Any] = self._subject.call_args_list
        for one in recorded:
            if matches_call(one, args, kwargs):
                return self
        if not recorded:
            return self._fail(
                f"to have been called with {wanted(args, kwargs)} at some point,"
                f" but {self._how_it_was_called()}",
                because,
            )
        if len(recorded) == 1:
            return self._fail(
                f"to have been called with {wanted(args, kwargs)} at some point,"
                f" but its only call was {render_call(recorded[0], render_options())}"
                + describe_call_difference(recorded[0], args, kwargs),
                because,
            )
        return self._fail(
            f"to have been called with {wanted(args, kwargs)} at some point,"
            f" but none of its {count_of(len(recorded), 'call')} was:"
            f" {render_calls(recorded, render_options())}" + nearest_note(recorded, args, kwargs),
            because,
        )

    def was_never_called_with(self, *args: object, because: str = "", **kwargs: object) -> Self:
        """Assert no call was made with these arguments.

        ``unittest.mock`` has nothing for this, which is why a test that means
        "the cache must not be refetched" usually ends up asserting a call count
        instead -- and passes for the wrong reason the day an unrelated call is
        added. The failure names the calls that were made with those arguments.
        """
        recorded: Sequence[Any] = self._subject.call_args_list
        for one in recorded:
            if matches_call(one, args, kwargs):
                break
        else:
            return self
        # Past the branch, so the list the message needs is built where it is
        # read. Building it first and testing it for emptiness instead would put
        # a comprehension and a list allocation on the branch that *passes*.
        matched = [
            index for index, one in enumerate(recorded, 1) if matches_call(one, args, kwargs)
        ]
        options = render_options()
        return self._fail(
            f"never to have been called with {wanted(args, kwargs)},"
            f" but {call_numbers(matched, options)}"
            f" {'was' if len(matched) == 1 else 'were'}:"
            f" {render_calls(recorded, options)}",
            because,
        )
