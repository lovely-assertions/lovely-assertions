"""What this package installs, once, when it is imported.

Two things, and neither is optional. A subject that refuses ``expect(<a
matcher>)`` and says where the matcher belongs instead -- because a matcher on
the left of an assertion is a mistake with a very confusing failure otherwise --
and a formatter so a matcher inside a message reads as the phrase it stands for
rather than as an object.

Both are installed by :func:`install`, called from this package's ``__init__``.
A named call rather than a side effect of importing the module: the effect is
the same, and this way a reader who wonders when it happens can see the line.
"""

from typing import Final, Never

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import register_formatter
from lovely_assertions._matching._base import Matcher
from lovely_assertions._matching._choice import OneOf
from lovely_assertions._matching._containers import ItemsPresent, MappingSubset
from lovely_assertions._matching._instances import AnyInstance, Anything
from lovely_assertions._matching._numbers import CloseTo
from lovely_assertions._matching._predicate import Matching
from lovely_assertions._matching._strings import StringContaining, StringMatching
from lovely_assertions._subjects import register

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def refuse_matcher_subject(value: object, /) -> Never:
    """Refuse ``expect(<a matcher>)``, and say why.

    Wired through :func:`~lovely_assertions.register` at the bottom of this
    module rather than as a branch in the dispatch chain, which is the whole
    reason it is worth doing: ``_subjects._dispatch`` already looks the subject's
    type up in the registry on its way past, so this check costs every *other*
    value in every other test exactly nothing. A branch at the head of the chain
    would have cost an ``isinstance`` on the hottest path in the library to catch
    a mistake that is made at most once per reader.

    The static side cannot help here and says so honestly:
    ``expect(any_instance_of(int))`` type-checks as ``NumericExpect``, because the
    matcher is *declared* to be an ``int``. That is the lie doing exactly what it
    was built to do, in the one place where it has nothing to offer -- so the
    runtime has to be the one to speak up.
    """
    raise TypeError(
        f"{value!r} is a matcher, so it belongs in an expectation rather than under "
        f"expect(). Its declared type is a deliberate fiction -- the object is a "
        f"placeholder, not a value of the type it claims -- so an assertion about it "
        f"would be an assertion about the placeholder. Put it in the expected value "
        f"instead: expect(row).is_equal_to({{'id': any_instance_of(int)}})."
    )


class MatcherFormatter:
    """Renders a matcher through its own ``repr``, ahead of the registry.

    This looks redundant and nearly is: ``format_value`` already falls back to
    ``repr``, so every message in this library renders ``<any int>`` with nothing
    registered at all. What the registration buys is *priority*. The global
    registry is consulted in registration order and the first claim wins, so a
    user formatter written broadly -- ``ObjectFormatter(SomeBase, "id")`` over a
    hierarchy wider than its author meant -- can claim a matcher and render it as
    something it is not. Registering here, at import, puts this in front of
    anything a user's ``conftest`` can add later.

    A *scoped* formatter still overrides it, and that is right: scoping is how a
    block asks for a different rendering, and this is not a rendering worth
    refusing to give up.

    The one cost, stated because it is paid by suites that never touch a matcher:
    registering anything at all means ``format_value`` takes its general path
    rather than its "nothing is registered" shortcut, and this class is registered
    at import, so that shortcut is never taken in a program that imports the
    library. It costs one ``can_handle`` -- an ``isinstance`` -- per rendered
    value, and nothing beyond that.

    That is failure-path work only -- nothing in this class runs until an
    assertion has already failed -- so it is bought at the one moment the library
    is allowed to spend, and it buys a message that cannot be taken over by
    somebody else's formatter.
    """

    __slots__ = ()

    def can_handle(self, value: object, /) -> bool:
        return isinstance(value, Matcher)

    def format(self, value: object, /) -> str:
        return repr(value)


# ---------------------------------------------------------------------------
# Wiring, once, at import
# ---------------------------------------------------------------------------
#: Every matcher class, so the two registrations below stay one list.
MATCHER_TYPES: Final[tuple[type[Matcher], ...]] = (
    AnyInstance,
    Anything,
    CloseTo,
    ItemsPresent,
    MappingSubset,
    Matching,
    OneOf,
    StringContaining,
    StringMatching,
)


def install() -> None:
    """Register the refusal for every matcher type, and the matcher formatter.

    Called once, from this package's ``__init__``, so that importing
    ``lovely_assertions`` is what puts both in place. Registering the refusal per
    type rather than by a predicate keeps the dispatch a table lookup: the cost
    of matchers existing is paid by the caller who passes one, and by nobody else.
    """
    for matcher_type in MATCHER_TYPES:
        register(matcher_type, refuse_matcher_subject)
    register_formatter(MatcherFormatter())
