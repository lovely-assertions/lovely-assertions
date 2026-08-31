"""How a class declares a name, as against what ``getattr`` hands back.

Finding a member is one ``getattr`` at the assertion site, which is the right
tool for finding it and the wrong one for describing it: the descriptor protocol
runs on the way out, so a ``property`` arrives as the descriptor, a
``classmethod`` as a bound method and a ``staticmethod`` as a plain function --
three declarations a reader wrote differently and one lookup cannot tell apart.
The class dictionaries along the MRO are the only place they are still
themselves, so that is where this module reads, and what it returns is the
phrase a reader would have used: a property, a class method, a nested class, or
the value itself named by its type.

Describing, never deciding. Whether the member is there and whether it counts as
a method are settled at the assertion site, and nothing here is asked until a
sentence has to be finished -- so a passing assertion never walks an MRO.
Bounding and rendering the pieces that go into the phrase stay in
:mod:`lovely_assertions._type._naming`.
"""

from typing import Final

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._type._hierarchy import mro_of
from lovely_assertions._type._naming import MISSING, named, rendered

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def _declared(subject: object, name: str, /) -> object:
    """The undecorated declaration of ``name``, from the class dictionaries.

    ``getattr`` runs the descriptor protocol, which is exactly what hides the
    difference this function exists to see: it turns a ``classmethod`` into a
    bound method, a ``staticmethod`` into a plain function and a ``property``
    into the descriptor. The declaration in ``__dict__`` is the only place the
    four are still distinguishable.
    """
    for base in mro_of(subject):
        declaration = vars(base).get(name, MISSING)
        if declaration is not MISSING:
            return declaration
    return None


#: The three decorators ``getattr`` on a class dissolves, and what a reader calls
#: them. Keyed on the exact type rather than matched with ``isinstance``:
#: ``staticmethod`` and ``classmethod`` are generic, and narrowing to one of them
#: yields the partially unknown type pyright's strict mode will not let a caller
#: pass on (the trap ``_callable._is_awaitable`` documents). Nothing here needs
#: the narrowed value, only its name, so the exact test stays out of that hole.
_DECORATED: Final[dict[type, str]] = {
    property: "a property",
    staticmethod: "a static method",
    classmethod: "a class method",
}


def declaration_kind(subject: object, name: str, value: object, /) -> str:
    """How the class declares ``name``, as a reader would say it. Failure path only.

    Named rather than printed: ``<property object at 0x10f3a2d90>`` is the kind
    of rendering that tells a reader nothing, and "a property" is the entire
    finding when ``has_method`` turned one down.
    """
    decorated = _DECORATED.get(type(_declared(subject, name)))
    if decorated is not None:
        return decorated
    if value is None:
        return "None"
    if isinstance(value, type):
        return "the nested class " + named(value)
    if callable(value):
        return "a method"
    return "the " + type(value).__name__ + " " + rendered(value)
