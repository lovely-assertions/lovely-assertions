"""Reading the subject as a type it already is, without asserting first.

The escape hatch out of a subject the dispatch chose and the caller disagrees
with. It asserts nothing about the value -- that is the point, and the reason it
is not spelled like the assertions around it.
"""

from typing import TYPE_CHECKING, Any, overload

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from enum import Enum

    from lovely_assertions._bool import BoolExpect
    from lovely_assertions._core import Expect
    from lovely_assertions._enum import EnumExpect
    from lovely_assertions._string import StringExpect
from lovely_assertions._core._instance import InstanceAssertions

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class CoercionAssertions[T](InstanceAssertions[T]):
    """The assertions of the type seam that hand back a different subject.

    Built on :class:`InstanceAssertions` rather than beside it, because
    ``as_type`` is ``is_instance_of`` with the check skipped -- the caller has
    already decided what the value is, and is asking for the catalogue that
    goes with it. Stating the dependency as inheritance keeps the two from
    drifting into two ideas of what a type answer looks like.
    """

    __slots__ = ()

    @overload
    def as_type[S: "Enum"](
        self, expected_type: type[S], /, *, because: str = ...
    ) -> "EnumExpect[S]": ...
    @overload
    def as_type(self, expected_type: type[bool], /, *, because: str = ...) -> "BoolExpect": ...
    @overload
    def as_type(self, expected_type: type[str], /, *, because: str = ...) -> "StringExpect": ...
    @overload
    def as_type[S](self, expected_type: type[S], /, *, because: str = ...) -> "Expect[S]": ...
    def as_type(self, expected_type: type[Any], /, *, because: str = "") -> Any:
        """Assert the subject's type and continue on the narrowed value.

        Sugar for ``is_instance_of(t).which``, for when the type check is a step
        on the way somewhere rather than the point of the assertion. Its overloads
        are that sugar read through: entry for entry, they are what
        :meth:`is_instance_of` promises with ``.which`` already applied. The
        original subject is gone from the chain, so use :meth:`is_instance_of` and
        ``.and_`` where you still have something to say about it.
        """
        return self.is_instance_of(expected_type, because=because).which
