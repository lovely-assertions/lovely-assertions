"""Which members take part in the comparison at all.

Two kinds of decision, and both are about membership rather than about values.
Naming members -- by name, by path, or by naming the only ones that count --
narrows what the walk looks at. The other pair moves the asymmetry the engine
starts from, where the expectation drives and a field only the subject carries is
not a difference; they are the two ways of saying otherwise, one per direction.

Nothing here decides whether two values agree, which is what keeps it apart from
:class:`BehaviourOptions` further up the chain. A reader asking why a field was
skipped and a reader asking why two numbers were called different arrive with
different questions, and each finds a file that answers only theirs. The one
thing the two groups share is the copy-on-write base underneath them; neither
reads a field the other writes.
"""

from typing import Self

from lovely_assertions._equivalence._options._base import OptionsBase
from lovely_assertions._equivalence._validation import require_names
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class SelectingOptions(OptionsBase):
    """The builder methods that decide which members are compared.

    Sits directly on :class:`OptionsBase` because that is all it needs: every
    method here ends in ``self._but(...)``, and the guards the ones that take
    names validate with belong to no link in particular. It reaches for nothing
    the link above it adds, which is why the chain could as easily run the other
    way round -- the order between the two groups of methods is a reading order,
    not a dependency.
    """

    __slots__ = ()

    # -- selection ----------------------------------------------------------
    def excluding(self, *names: str) -> Self:
        """Skip these member names wherever they appear.

            >>> equivalency().excluding("created_at", "id")
            equivalency().excluding('created_at', 'id')

        A name matches a record field and a string mapping key alike, because to
        the reader of ``{"password": ...}`` and ``User(password=...)`` those are
        the same member. Excluding a member also stops it being reported as
        missing or surplus: a member nobody is comparing cannot be absent.

        Returns a new configuration; this one is unchanged. A call naming nothing
        is allowed and changes nothing, so ``excluding(*configured)`` needs no
        guard. Anything that is not a string raises :class:`TypeError`.
        """
        require_names(names, "excluding")
        return self._but("excluded_names", self.excluded_names.union(names))

    def excluding_path(self, *paths: str) -> Self:
        """Skip these exact paths, and everything beneath them.

            >>> equivalency().excluding_path("user.address.city", "items[0]")
            equivalency().excluding_path('items[0]', 'user.address.city')

        A path is written in the notation the failure message prints, so a path a
        reader can see is a path they can paste back in here. Excluding
        ``user.address`` excludes ``user.address.city`` with it -- a subtree, not
        a single member -- because that is what naming a branch of a graph means.

        Returns a new configuration; this one is unchanged. Anything that is not a
        string raises :class:`TypeError`, and the empty path raises
        :class:`ValueError`: it names the root, and a call that excluded everything
        would report two values equivalent without having compared any of them.

        An index only names something while order is being compared. Under
        :meth:`ignoring_order` there is no item at ``items[0]``, so a path through
        an index reaches nothing; exclude the sequence itself, or a field name
        inside its items, instead.
        """
        require_names(paths, "excluding_path")
        for path in paths:
            if not path:
                message = "excluding_path needs a path; the empty path is the whole value"
                raise ValueError(message)
        return self._but("excluded_paths", self.excluded_paths.union(paths))

    def including(self, *names: str) -> Self:
        """Compare only these member names, and ignore every other *named* member.

            >>> equivalency().including("id", "total")
            equivalency().including('id', 'total')

        Members with no name are left alone: an item of a list is at an index
        rather than under a name, and a mapping keyed by dates has no names to
        select from. Without that rule, one ``including`` call would silently
        empty every collection in the graph and the comparison would pass by
        having compared nothing.

        ``excluding`` still wins where the two disagree, which is the order that
        lets a shared configuration be narrowed rather than fought with.

        A name **nothing carries** selects nothing, and two records with no
        selected member between them are equivalent -- a mistyped ``including``
        passes silently. That is the same answer ``excluding`` every field gives,
        and it is why the one vacuity that can be spotted at the call,
        ``excluding_path("")``, is refused there. FluentAssertions reports "no
        members were found for comparison" instead; saying so here would need a
        channel for reporting on the comparison itself rather than on the two
        values, which this engine does not have, and guessing at it would break the
        deliberate ``excluding`` case.

        Returns a new configuration; this one is unchanged. Anything that is not a
        string raises :class:`TypeError`.
        """
        require_names(names, "including")
        return self._but("included_names", self.included_names.union(names))

    def comparing_all_members(self) -> Self:
        """Compare every member of both records, not only the ones the expectation names.

            >>> equivalency().comparing_all_members()
            equivalency().comparing_all_members()

        By default the expectation drives: a field only the subject carries is not
        a difference, which is what lets a forty-column ORM row be asserted against
        a three-field literal. This turns that off, so that a member the
        expectation never mentioned is reported as surplus.

        Reach for it when the expectation is meant to be *exhaustive* -- a golden
        record, a serialiser's whole output, a model asserted against a full copy
        of itself -- where a field appearing that nobody wrote a line for is the
        regression the test exists to catch.

        Mappings are unaffected, because they already compare both directions: a
        dictionary's keys are its data rather than a declared shape, and an extra
        key in a payload is always a difference.
        """
        return self._but("all_members", True)

    def excluding_missing(self) -> Self:
        """Skip expectation members the subject does not carry, instead of reporting them.

            >>> equivalency().excluding_missing()
            equivalency().excluding_missing()

        FluentAssertions' ``ExcludingMissingMembers``. On top of the default it
        takes away the last report about member *sets*, so what is left is the
        members both sides carry, compared by value and nothing else said. Turned
        on together with :meth:`comparing_all_members` it inverts the asymmetry
        instead: the subject drives and the expectation may carry members it does
        not.

        The case it exists for is one expectation shared across versions of a
        model, where a field has been added on one side and the test is about the
        fields that were always there. It is a real hole in a test's cover --
        misspell a field name and the assertion stops looking at it silently -- so
        it is opt-in, and ``excluding`` a field by name is the narrower tool
        whenever the field is known.

        Mappings are unaffected, for the reason given on
        :meth:`comparing_all_members`.
        """
        return self._but("excluded_missing", True)
