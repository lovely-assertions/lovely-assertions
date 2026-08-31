"""Two objects compared field by field, by name, across types.

A record is a value whose members are the ones its author declared. Which names
those are is :mod:`lovely_assertions._equivalence._classification`'s answer, and
they arrive here already resolved; this file is what does something with them.
Names rather than positions is what lets a wire model and a domain model that
carry the same information come out equivalent however their ``__eq__`` feels
about each other.

It is a file of its own because it is where **the expectation drives**. The loop
runs over the expectation's names and not the subject's, so a member only the
subject carries is neither looked at nor reported, and the two options that move
that line -- ``comparing_all_members()`` and ``excluding_missing()`` -- reach
this branch and no other. The mapping branch answers the same question the other
way round, so keeping the two apart is what makes the contrast legible.

The other thing this file owns is that a declared member is not an assigned one.
A slot nobody wrote to and a property that decides it has nothing to return look
identical from outside, so every field is read behind a guard, per field rather
than around the loop, and the shape of what comes back -- neither side, one side,
both -- is what separates a member neither object has from a member they
disagree about. Counting how many of the declared names any side would give up
is part of the same job: a declaration nothing backs is not a resolution, and an
engine that reads nothing and calls that agreement passes a hostile class.
"""

from lovely_assertions._equivalence._classification import UNRESOLVED
from lovely_assertions._equivalence._findings import (
    items_difference,
    note_difference,
    pair_difference,
)
from lovely_assertions._equivalence._paths import attribute_path
from lovely_assertions._equivalence._reading import (
    NOT_ON_ACTUAL,
    NOT_ON_EXPECTED,
    UNREADABLE,
    read_field,
)
from lovely_assertions._equivalence._walk._selection import SelectingWalk
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class RecordWalk(SelectingWalk):
    """The link that compares records, given the names to compare them by.

    It sits directly on :class:`SelectingWalk` because selection is the only thing
    a record comparison needs on top of the recursion itself: every field it
    considers is put to :meth:`_selects` first, both on the way down and again
    when the surplus fields are collected. Nothing here pairs items up, reads
    keys, or asks what a value is -- only what its two sides say under a name.
    """

    __slots__ = ()

    def _field(
        self, actual: object, expected: object, name: str, child: str, depth: int, /
    ) -> bool:
        """Compare one field, and say whether either side gave it up at all.

        The answer feeds the resolver's own sanity check in :meth:`_record`, which
        is why it is returned rather than dropped.

        A declared member is not necessarily an assigned one: a ``__slots__``
        entry that was never written to raises ``AttributeError``, and so does a
        property that decides it has nothing to return. When *neither* side will
        give the field up, that is a member neither object has rather than a
        member they disagree about, and reporting it would fail an object against
        an identical one. When only one side will, the two objects genuinely
        differ and the finding says which side is holding the value.

        Guarded per field rather than around the loop on purpose: one hostile
        member of a twelve-field record must cost the reader that field, not the
        other eleven.
        """
        actual_value = read_field(actual, name)
        expected_value = read_field(expected, name)
        if actual_value is UNREADABLE and expected_value is UNREADABLE:
            return False
        if actual_value is UNREADABLE:
            self.findings.add(note_difference(child, NOT_ON_ACTUAL))
            return True
        if expected_value is UNREADABLE:
            self.findings.add(note_difference(child, NOT_ON_EXPECTED))
            return True
        self.compare(actual_value, expected_value, child, depth + 1)
        return True

    # -- records ------------------------------------------------------------
    def _record(
        self,
        actual: object,
        expected: object,
        names: tuple[tuple[str, ...], tuple[str, ...]],
        path: str,
        depth: int,
        /,
    ) -> None:
        """Field by field, by name, across types.

        Two records of *different* classes are compared here without complaint,
        and that is the point of the assertion: a wire model and a domain model
        that carry the same information are equivalent however their ``__eq__``
        feels about each other.

        **The expectation drives**: the rule the engine states for records, and
        this is the one branch that enforces it. The loop is over the
        expectation's fields; a field only the subject carries is not looked at and
        not reported. ``comparing_all_members()`` puts the second loop back, and
        ``excluding_missing()`` drops the first report. Neither of them reaches
        :meth:`_mapping`, which compares both directions whatever the options say.

        A symmetric comparison is what the asymmetry is chosen over, and the reason
        is the commonest use of the assertion there is:
        ``expect(row).is_equivalent_to(Expected(id=1, total=5))`` against a
        forty-column ORM row is unwritable if the thirty-eight columns the test is
        not about are reported as surplus. So naming a member is what asks for it
        to be compared, and asking for the other direction is a method.
        """
        options = self.options
        actual_names, expected_names = names
        on_actual = frozenset(actual_names)
        missing: list[object] = []
        looked_at = 0
        readable = 0
        for name in expected_names:
            if self.findings.full:
                return
            child = attribute_path(path, name)
            if not self._selects(name, child):
                continue
            if name not in on_actual:
                if not options.excluded_missing:
                    missing.append(name)
                continue
            looked_at += 1
            readable += self._field(actual, expected, name, child, depth)
        if looked_at and not readable:
            # A declaration nothing backs is not a resolution. A tuple subclass is
            # free to set ``_fields`` to names it does not carry, and an engine
            # that trusts the declaration, reads nothing, and calls that "no
            # differences" turns a hostile class into a green test.
            self.findings.add(pair_difference(path, actual, expected, UNRESOLVED))
            return
        if missing:
            self.findings.add(items_difference(path, "missing fields:", missing))
        if not options.all_members:
            return
        on_expected = frozenset(expected_names)
        extra = [
            name
            for name in actual_names
            if name not in on_expected and self._selects(name, attribute_path(path, name))
        ]
        if extra:
            self.findings.add(items_difference(path, "extra fields:", extra))
