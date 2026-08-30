"""The path subject that asks the filesystem nothing.

Assembled from the two seams a path name has: what it is called, and where it
sits. Everything here answers for a path that does not exist, which is what makes
it the right subject for a value that was computed rather than opened.
"""

from typing import TYPE_CHECKING

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._path._names import NameAssertions
from lovely_assertions._path._placement import PlacementAssertions

if TYPE_CHECKING:
    from pathlib import Path

if TYPE_CHECKING:
    from pathlib import PurePath

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: The value type again, this time as a PEP 695 alias, for the class
#: statements whose *base* names it.
#:
#: A base is evaluated when the class is created, so it cannot be a name only
#: the checkers can see. A string is the obvious escape and it is not free: on
#: CPython 3.14, subscripting a generic with a string builds a ``ForwardRef``,
#: and building one imports ``annotationlib``, which pulls in ``ast`` and
#: ``enum`` -- three modules that would then load for every program that merely
#: says ``import lovely_assertions``, and invisible on 3.13 where a
#: ``ForwardRef`` costs nothing.
#:
#: A PEP 695 alias is lazily evaluated in the one way that matters here: the
#: object exists without its right-hand side being resolved, so the alias can
#: name a type from a module this library refuses to import, and a checker still
#: reads through it to ``PurePathExpect[Path]``. A bound -- ``[T: "PurePath"]``
#: -- is lazy already and stays a string; only a base needs this.
type DiskPath = Path


class PurePathExpect[T: "PurePath"](
    NameAssertions[T],
    PlacementAssertions[T],
    Expect[T],
):
    """Assertions answerable without a filesystem (``PurePath``).

    :class:`PathExpect` extends this with the ones that need a disk, mirroring
    ``Path``'s own inheritance from ``PurePath``.
    """

    __slots__ = ()
