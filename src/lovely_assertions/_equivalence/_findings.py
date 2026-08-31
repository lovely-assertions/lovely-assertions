"""What a finding is made of, and the collector that decides when there are enough.

The walk produces findings and the rendering consumes them. The vocabulary they
share lives here rather than in either of them, in a file that imports from
neither, so that neither side has to be entered to reach the record type.

Everything it holds is data rather than text. A finding carries the values it is
about and a tag saying what is to be said about them; nothing in this file reads
:func:`~lovely_assertions.current_formatting` or renders a value, which is what
keeps that ``ContextVar`` lookup off the walk -- and the walk is where a passing
``is_not_equivalent_to`` spends all of its time.

The limit rides on the collector rather than being applied to the finished list,
because a bound checked afterwards bounds nothing: the walk asks whether the
collector is full at the head of every loop and stops there. Carrying it as state
is also what lets the same collector answer a yes-or-no question -- one finding is
enough to know that two items do not match -- which is the form order-insensitive
pairing needs.
"""

from typing import TYPE_CHECKING, Final, override

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Sequence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Differences collected before the walk gives up and says so. This bounds what
#: the *engine* may spend while comparing, which is why it is a constant here and
#: not an option: a caller who could raise it could hang a test run. Well past
#: anything a reader will look at, and small enough that two mismatched
#: ten-thousand-node graphs cost a few hundred small records rather than twenty
#: thousand.
MAX_DIFFERENCES: Final = 200


#: What one difference has to show. Kept as tags on a single record rather than as
#: a class hierarchy: a difference is data gathered during the walk and rendered
#: afterwards, and the split is what keeps `current_formatting()` -- a ContextVar
#: read -- off the walk entirely.
_SHOWS_PAIR: Final = "pair"


SHOWS_TYPES: Final = "types"


SHOWS_NOTE: Final = "note"


SHOWS_ITEMS: Final = "items"


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------
class Difference:
    """One finding: where it is, and what to say about it.

    Holds *values* rather than rendered text, and that is the load-bearing part.
    Rendering reads ``current_formatting()``, which is a ``ContextVar`` lookup and
    so must not happen on the path a passing assertion takes -- and the walk *is*
    that path, because ``is_not_equivalent_to`` passes by finding differences. So
    the walk gathers, and the reporting path renders.

    The notes that are built during the walk are made of constants, type names and
    counts. None of those reads a ``ContextVar`` or formats a value.
    """

    __slots__ = ("items", "note", "pair", "path", "shows")

    def __init__(
        self,
        path: str,
        shows: str,
        note: str,
        pair: tuple[object, object] | None,
        items: tuple[object, ...],
        /,
    ) -> None:
        self.path: str = path
        self.shows: str = shows
        self.note: str = note
        self.pair: tuple[object, object] | None = pair
        self.items: tuple[object, ...] = items

    @override
    def __repr__(self) -> str:
        return "Difference(" + repr(self.path) + ", " + repr(self.shows) + ")"


def pair_difference(path: str, actual: object, expected: object, note: str = "", /) -> Difference:
    """Two values that disagree, rendered as ``actual instead of expected``."""
    return Difference(path, _SHOWS_PAIR, note, (actual, expected), ())


def types_difference(path: str, actual: object, expected: object, /) -> Difference:
    """Two values with nothing structural in common."""
    return Difference(path, SHOWS_TYPES, "", (actual, expected), ())


def note_difference(path: str, note: str, /) -> Difference:
    """A finding that is a sentence rather than a pair of values."""
    return Difference(path, SHOWS_NOTE, note, None, ())


def items_difference(path: str, note: str, items: "Sequence[object]", /) -> Difference:
    """A finding about a set of members: keys, fields or items."""
    return Difference(path, SHOWS_ITEMS, note, None, tuple(items))


class Findings:
    """The differences one comparison has collected, and whether it stopped early.

    The limit does double duty. For a real comparison it is
    :data:`MAX_DIFFERENCES`, which bounds what the engine spends. For the probe
    that asks "do these two items match?" during order-insensitive pairing it is
    ``1``, which turns the same walk into a boolean that stops at the first
    disagreement instead of describing all of them.
    """

    __slots__ = ("items", "limit")

    def __init__(self, limit: int, /) -> None:
        self.limit: int = limit
        self.items: list[Difference] = []

    @override
    def __repr__(self) -> str:
        return "Findings(" + str(len(self.items)) + " of " + str(self.limit) + ")"

    @property
    def full(self) -> bool:
        """Whether this collector has taken everything it is going to take.

        Read at the head of every loop in the walk, which is what makes the bound
        a *stopping* rule rather than a filter: a comparison of two mismatched
        ten-thousand-node graphs stops at two hundred findings instead of
        producing ten thousand and discarding all but two hundred. It is also why
        the report says the comparison stopped rather than counting what it left
        out -- past the bound nothing was looked at, so there is no honest number
        to give.
        """
        return len(self.items) >= self.limit

    def add(self, difference: Difference, /) -> None:
        """Record a finding, unless this collector has already taken its fill."""
        if self.full:
            return
        self.items.append(difference)
