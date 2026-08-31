"""What a configuration *is*: the fields, the copy, and the refusal to change.

The state is declared once, here, because it is copied once, here. Every builder
method in the chain above ends in :meth:`OptionsBase._but`, which builds the new
instance by walking ``OptionsBase.__slots__`` -- so a field declared on a link
further up would be dropped from every copy without a word. That is why the links
above carry empty slots and hold nothing but methods, and why the default depth
lives down here too: it is the one field whose default is not the empty value of
its type, and the constructor and ``Equivalency.__repr__`` both have to agree on
what it is.

Nothing here knows what any of the fields *mean*. Which members a name excludes
and what a comparator is consulted for are the business of the files that write
those fields; this one only keeps them, hands out modified copies, and says no to
anything that tries to change one in place.
"""

from typing import TYPE_CHECKING, Any, Final, Self, override

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Callable

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Levels of structure the walk descends by default. FluentAssertions' number,
#: and it is chosen for the same reason: ten levels is deeper than any object
#: graph a test asserts on by hand, and shallow enough that a mistake -- a model
#: that reaches back into its session, a node with a parent pointer -- stops
#: rather than running until the interpreter does.
DEFAULT_MAX_DEPTH: Final = 10


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------
def _immutable(action: str, name: str, /) -> str:
    """The message behind a refused mutation."""
    return (
        "cannot "
        + action
        + " "
        + name
        + " on Equivalency: it is immutable."
        + " Every method returns a new one, so chain them instead."
    )


class OptionsBase:
    """The bottom of the options chain: the fields and their value semantics.

    Every link above adds methods and no state, so this is the one class that
    holds a configuration rather than describing what can be asked of one. Each of
    those methods ends in :meth:`_but`, which is what gives all of them
    immutability and copy-on-write without any of them mentioning a field twice.

    A frozen dataclass in everything but generation. ``dataclasses`` is one of the
    imports this package will not pay for at module scope, so the assignments go
    through ``object`` and the refusals, the equality and the hash are written out
    by hand. They are written out *together*: a class that defined ``__eq__``
    alone would be unhashable, and a configuration a caller cannot put in a set is
    a needless surprise from a value that never changes.
    """

    __slots__ = (
        "all_members",
        "comparators",
        "enums_by_name",
        "excluded_missing",
        "excluded_names",
        "excluded_paths",
        "ignore_order",
        "included_names",
        "max_depth",
    )

    #: Member names skipped wherever they appear.
    excluded_names: frozenset[str]
    #: Paths skipped, together with everything beneath them.
    excluded_paths: frozenset[str]
    #: When non-empty, the only *named* members compared. Members with no name --
    #: a sequence index, a mapping key that is not a string -- are unaffected.
    included_names: frozenset[str]
    #: Whether a sequence's order is part of what is compared. ``False`` -- strict
    #: ordering -- is the default, inverting FluentAssertions on purpose.
    ignore_order: bool
    #: Custom comparators by type, in registration order; the last one that claims
    #: both sides of a pair wins.
    comparators: "tuple[tuple[type[Any], Callable[[Any, Any], bool]], ...]"
    #: Levels of structure the walk descends before falling back to ``==``.
    max_depth: int
    #: Whether two enum members are compared by name rather than by value.
    enums_by_name: bool
    #: Whether a *record* field only the subject carries is compared too. ``False``
    #: -- the expectation drives -- is the default. Mappings are unaffected; see
    #: the module docstring's sixth rule.
    all_members: bool
    #: Whether a *record* field the expectation names and the subject lacks is
    #: skipped instead of reported. Mappings are unaffected, for the same reason.
    excluded_missing: bool

    def __init__(self) -> None:
        """The default configuration. Prefer :func:`equivalency`, which reads better."""
        # Assigned through `object` because `__setattr__` below refuses -- the
        # hand-written half of a frozen dataclass, which cannot be a real one
        # because `dataclasses` may not be imported at module level.
        object.__setattr__(self, "excluded_names", frozenset())
        object.__setattr__(self, "excluded_paths", frozenset())
        object.__setattr__(self, "included_names", frozenset())
        object.__setattr__(self, "ignore_order", False)
        object.__setattr__(self, "comparators", ())
        object.__setattr__(self, "max_depth", DEFAULT_MAX_DEPTH)
        object.__setattr__(self, "enums_by_name", False)
        object.__setattr__(self, "all_members", False)
        object.__setattr__(self, "excluded_missing", False)

    @override
    def __setattr__(self, name: str, _value: object, /) -> None:
        raise AttributeError(_immutable("set", name))

    @override
    def __delattr__(self, name: str, /) -> None:
        raise AttributeError(_immutable("delete", name))

    def _but(self, name: str, value: object, /) -> Self:
        """A copy of these options with one field replaced.

        One field, not several, and that is not a simplification: every builder in
        the chain above changes exactly one, which is what makes a chain of them
        read as a sequence of independent decisions.
        """
        clone = type(self)()
        for field in OptionsBase.__slots__:
            object.__setattr__(clone, field, value if field == name else getattr(self, field))
        return clone

    def _state(self) -> tuple[object, ...]:
        """Every field, in one tuple, for equality and hashing."""
        return (
            self.excluded_names,
            self.excluded_paths,
            self.included_names,
            self.ignore_order,
            self.comparators,
            self.max_depth,
            self.enums_by_name,
            self.all_members,
            self.excluded_missing,
        )

    # -- value semantics ----------------------------------------------------
    @override
    def __eq__(self, other: object, /) -> bool:
        """Two configurations that would compare the same way are the same options."""
        if not isinstance(other, OptionsBase):
            return NotImplemented
        return self._state() == other._state()

    @override
    def __hash__(self) -> int:
        return hash(self._state())
