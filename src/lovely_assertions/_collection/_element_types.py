"""What the items are, rather than what they equal.

``instance`` and ``exactly`` are kept apart for the reason they always are: a
``bool`` is an ``int``, and a test that meant one and got the other passes.
"""

from typing import TYPE_CHECKING, Any, Self

from lovely_assertions._collection._base import CollectionBase
from lovely_assertions._collection._render import render_items
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value

if TYPE_CHECKING:
    from collections.abc import Collection

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class ElementTypeAssertions[E, C: Collection[Any] = Collection[E]](CollectionBase[E, C]):
    """Every item an instance of, or exactly of, a type."""

    __slots__ = ()

    def all_are_instance_of(self, expected_type: type[object], /, *, because: str = "") -> Self:
        """Assert every item is an instance of ``expected_type``, subclasses included."""
        subject = self._subject
        for index, item in enumerate(subject):
            if not isinstance(item, expected_type):
                return self._fail(
                    f"to contain only instances of {expected_type.__name__}, but "
                    f"{
                        self._names_type(lambda v: not isinstance(v, expected_type), (index, item))
                    }",
                    because,
                )
        return self

    def all_are_exactly_type(self, expected_type: type[object], /, *, because: str = "") -> Self:
        """Assert every item is exactly ``expected_type`` -- a subclass does not count."""
        subject = self._subject
        for index, item in enumerate(subject):
            if type(item) is not expected_type:
                return self._fail(
                    f"to contain only {expected_type.__name__} exactly, but "
                    f"{self._names_type(lambda v: type(v) is not expected_type, (index, item))}",
                    because,
                )
        return self

    def all_equal_to(self, value: E, /, *, because: str = "") -> Self:
        """Assert every item equals ``value``."""
        subject = self._subject
        for index, item in enumerate(subject):
            if item != value:
                return self._fail(
                    f"to contain only {format_value(value)}, but "
                    f"{self._names(lambda v: v != value, (index, item))}"
                    f" did not match: {render_items(subject)}",
                    because,
                )
        return self
