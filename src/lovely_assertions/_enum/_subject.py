"""The enumeration subject, assembled from one mixin per family of question.

Names, values and flags share the member they are asked about and nothing else:
no mixin calls another, no name appears in two of them, and none of them
overrides anything the generic subject already declares. So the base list
resolves no clash and is free to read in the order a reader meets the questions
-- what the member is called, what it holds, which bits are set -- with
``Expect[T]`` last, because the MRO admits a base only after the classes that
already derive from it.

The type parameter is repeated on every mixin rather than pinned to ``Enum`` at
the seam, and that is what makes the flag operand's typing work: ``has_flag``
takes a ``T``, so ``T`` has to be the caller's own enumeration the whole way
through the base list for the checkers to refuse a member of a different one
before it can run. Every mixin carries empty ``__slots__``, and so does the class
below, so the assembly adds no storage of its own: a member's subject is one
allocation holding the subject and its name, exactly as the generic one is.

The assembly sits beside the mixins rather than in the package's ``__init__``,
which stays a front door: the exported names, and nothing to read past them.
"""

from typing import TYPE_CHECKING

from lovely_assertions._core import Expect
from lovely_assertions._enum._flags import FlagAssertions
from lovely_assertions._enum._names import NameAssertions
from lovely_assertions._enum._values import ValueAssertions
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from enum import Enum

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class EnumExpect[T: "Enum"](NameAssertions[T], ValueAssertions[T], FlagAssertions[T], Expect[T]):
    """Assertions for a member of an enumeration.

    ``T`` is the enumeration, not ``Enum``: ``expect(Colour.RED).subject`` is a
    ``Colour``, so the chain keeps whatever the caller put into it and
    ``has_same_name_as`` can still be handed a member of a different one.
    """

    __slots__ = ()
