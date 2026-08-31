"""Two mappings compared entry by entry, and in both directions.

A mapping's keys are its data, which is why this is not the record branch with
different spelling. An expectation object stands in for a shape its author
declared, and what it leaves out it leaves out on purpose; ``{"id": 1,
"total": 5}`` is not a partial description of a payload, it is a payload. So a
key the subject carries and the expectation does not is reported here, and
neither ``comparing_all_members()`` nor ``excluding_missing()`` touches that.
``excluding()`` still reaches a string key by name, which is the escape when a
payload carries a timestamp; a key of any other type is addressable by path
alone.

Values under shared keys are walked before the keys only one side carries, so
that the finding a mapping comparison usually fails on is not preceded by lines
about a key that is simply absent.

Every read of a foreign mapping is guarded, and each guard costs one entry rather
than the comparison: a key whose ``__hash__`` will not answer is an absent key,
an entry that will not be indexed is a finding at that entry, and a mapping that
will not be iterated at all is a finding at the mapping. Keys reported as missing
or extra are put in a stable order first, because a mapping hands its keys over
in whatever order it happens to iterate, and a failure message that reads
differently between two runs of the same test is not one a reader can act on.
"""

from typing import TYPE_CHECKING

from lovely_assertions._equivalence._findings import items_difference, note_difference
from lovely_assertions._equivalence._paths import key_path
from lovely_assertions._equivalence._reading import (
    equal_or_unknown,
    has_key,
    key_name,
    read_keys,
    safe_list,
    stably_ordered,
)
from lovely_assertions._equivalence._rendering import leaf_difference
from lovely_assertions._equivalence._walk._record import RecordWalk
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._reflection import is_mapping

if TYPE_CHECKING:
    from collections.abc import Mapping

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class MappingWalk(RecordWalk):
    """The link that compares mappings, key by key.

    Like :class:`RecordWalk` it needs only selection and the recursion, and it
    calls nothing that link adds, so sitting directly above it buys no reuse. It
    sits there to be read against it: these two are the engine's by-name
    comparisons, and the rule that separates them -- the expectation drives a
    record, both directions are reported for a mapping -- is the one seam of the
    chain where a reader is best served by having both sides in view.

    A route is remembered against a type, and the question behind it is answered
    per instance by ``__class__``, so this branch also has to survive a pair that
    was routed here and turns out not to be a mapping at all.
    """

    __slots__ = ()

    def _shared_keys(
        self,
        actual: "Mapping[object, object]",
        expected: "Mapping[object, object]",
        keys: list[object],
        path: str,
        depth: int,
        /,
    ) -> list[object]:
        """Walk every selected key of ``expected``; hand back the ones ``actual`` lacks."""
        missing: list[object] = []
        for key in keys:
            if self.findings.full:
                return missing
            child = key_path(path, key)
            if not self._selects(key_name(key), child):
                continue
            if not has_key(actual, key):
                missing.append(key)
                continue
            pair = read_keys(actual, expected, key)
            if pair is None:
                self.findings.add(note_difference(child, "this entry could not be read"))
                continue
            self.compare(pair[0], pair[1], child, depth + 1)
        return missing

    # -- mappings -----------------------------------------------------------
    def _mapping(self, actual: object, expected: object, path: str, depth: int, /) -> None:
        """Values under shared keys first, then keys only one side carries.

        The order is the mapping describer's, for the mapping describer's reason:
        a wrong value under a right key is what a mapping comparison usually fails
        on, and when it is a key that is absent there are no value lines in the way.
        """
        if not is_mapping(actual) or not is_mapping(expected):
            # A route is remembered against `type(value)`, but the question behind
            # it is asked of `__class__`, which a proxy or a lazy stand-in answers
            # per instance. So a pair can arrive here routed to a shape neither
            # side turns out to have. The kind was a guess about the type and the
            # guess missed, so the pair is reported the way a leaf is: equality
            # decides, which is the one answer that was not guessed. Returning in
            # silence would declare it *equivalent*. Equality is asked again rather
            # than carried down from the caller, so that an ordinary mapping node
            # pays nothing for a branch it never takes. The two checks also narrow
            # `object` down to something with keys, on a path that is about to read
            # every one of them.
            self.findings.add(
                leaf_difference(path, actual, expected, equal_or_unknown(actual, expected))
            )
            return
        actual_keys = safe_list(actual)
        expected_keys = safe_list(expected)
        if actual_keys is None or expected_keys is None:
            self.findings.add(note_difference(path, "the keys of this mapping could not be read"))
            return
        missing = self._shared_keys(actual, expected, expected_keys, path, depth)
        extra = [
            key
            for key in actual_keys
            if not has_key(expected, key) and self._selects(key_name(key), key_path(path, key))
        ]
        if missing:
            self.findings.add(items_difference(path, "missing keys:", stably_ordered(missing)))
        if extra:
            self.findings.add(items_difference(path, "extra keys:", stably_ordered(extra)))
