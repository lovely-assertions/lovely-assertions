"""What a class declares, asked of the class and never of an instance.

That restriction is the seam rather than a limitation of it. ``getattr`` on a
class cannot see what ``__init__`` assigns, so a class whose every instance
carries a ``total`` has no ``total`` here -- a correct answer to a question the
reader very often did not mean to ask. A failure that reports an absence says
where it looked, for that reason alone.

``getattr`` also dissolves the ways a member can be written: a ``def`` comes back
a function, a ``classmethod`` bound, a ``staticmethod`` a plain function again, a
``property`` the descriptor object. The checks need little of that -- presence is
presence, and callability turns the property down by itself -- but the messages
need all of it, which is why naming a declaration lives in
:mod:`lovely_assertions._type._members` and runs only once an assertion has
already failed. "A property" is the whole finding when a method was wanted, and
``<property object at 0x...>`` would be none of it.

A member that is found is handed onward rather than merely reported:
:meth:`TypeExpect.has_attribute` and :meth:`TypeExpect.has_method` return a
``Found``, so a chain can go from "the class defines it" straight to an assertion
about the member itself, with the class still waiting under ``.and_``.
"""

from typing import Any, Self, cast

from lovely_assertions._callable import CallableExpect
from lovely_assertions._core import Found
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._type._members import declaration_kind
from lovely_assertions._type._naming import MISSING

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class AttributeAssertions(CallableExpect):
    """Which names the class answers to, and what they turned out to be."""

    __slots__ = ()

    # -- attributes and methods --------------------------------------------
    def has_attribute(self, name: str, /, *, because: str = "") -> "Found[Self, Any]":
        """Assert the class defines ``name``; continue on its value with ``.which``.

            expect(Order).has_attribute("DEFAULTS").which.is_instance_of(dict)

        The question is asked of the **class**, and only of the class: an
        attribute assigned in ``__init__`` belongs to instances and is not found
        here. The failure says where it looked, because that is the mistake this
        assertion is most often used to make.

        What ``.which`` receives is what ``getattr`` on the class returns, which
        for a ``property`` is the descriptor rather than any value -- there is no
        instance for it to compute one from. :meth:`has_method` names the three
        ways a method can be written, and is the one to reach for when the
        member is meant to be callable rather than merely present.

        An attribute holding ``None`` is found like any other; "defined as
        ``None``" and "not defined" are told apart. Returns a ``Found``, whose
        ``.and_`` continues on the class and whose ``.which`` continues on the
        attribute's value.
        """
        found: Any = getattr(self._subject, name, MISSING)
        if found is not MISSING:
            return Found(self, found)
        return cast(
            "Found[Self, Any]",
            self._fail_narrowing(
                f"to have the attribute {format_value(name)},"
                f" but no such attribute is defined on the class",
                because,
            ),
        )

    def does_not_have_attribute(self, name: str, /, *, because: str = "") -> Self:
        """Assert the class does not define ``name``.

        The assertion a removal wants: a deprecation that landed, an internal
        that must not have leaked. The failure names *how* the class declares
        it -- a property, a class method, a value -- because "it is still there"
        is a fact the reader already had.

        Asked of the class, and only of the class, exactly as
        :meth:`has_attribute` is: an attribute assigned in ``__init__`` belongs to
        instances and passes here. Returns the subject, so the call chains.
        """
        found: Any = getattr(self._subject, name, MISSING)
        if found is MISSING:
            return self
        return self._fail(
            f"not to have the attribute {format_value(name)},"
            f" but it is {declaration_kind(self._subject, name, found)}",
            because,
        )

    def has_method(self, name: str, /, *, because: str = "") -> "Found[Self, Any]":
        """Assert the class defines ``name`` as a method; continue on it with ``.which``.

        A method is a callable attribute, and ``getattr`` on a class flattens the
        three ways of writing one: a plain ``def`` comes back as a function, a
        ``classmethod`` as a bound method, a ``staticmethod`` as a plain function
        again. All three are callable and all three pass. A ``property`` comes
        back as the descriptor, which is *not* callable and does not pass -- a
        property is a computed attribute, not a method, and the failure says
        exactly that rather than printing an address.

        A nested class is turned down too, for all that ``callable()`` says yes
        to it. ``expect(Repo).has_method("Row")`` where ``Row`` is an inner class
        is a test that passes for the wrong reason, and this library exists to
        stop those; without the carve-out the assertion would mean nothing more
        than "has a callable attribute", losing the one distinction it is for.

        A missing name and a name declared as something other than a method are
        different findings and get different sentences. Signatures are not
        checked, only that the member is there and callable. Returns a ``Found``,
        whose ``.and_`` continues on the class and whose ``.which`` continues on
        the method object. Reach for :meth:`has_attribute` when a property or a
        plain value is what is wanted.
        """
        found: Any = getattr(self._subject, name, MISSING)
        if found is MISSING:
            return cast(
                "Found[Self, Any]",
                self._fail_narrowing(
                    f"to have a method {format_value(name)},"
                    f" but no such attribute is defined on the class",
                    because,
                ),
            )
        if callable(found) and not isinstance(found, type):
            return Found(self, found)
        return cast(
            "Found[Self, Any]",
            self._fail_narrowing(
                f"to have a method {format_value(name)},"
                f" but it is {declaration_kind(self._subject, name, found)}",
                because,
            ),
        )
