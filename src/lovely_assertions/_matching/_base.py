"""What every matcher is, and the equality that makes one work at all.

A matcher stands where a value is expected and answers ``==`` for it, which is
the whole trick: the comparison a caller already writes does the work, and no
assertion has to know matchers exist. That puts the entire design in one
``__eq__`` -- total, never raising, and symmetric, because the caller decides
which side the matcher lands on and a rule that only works one way is not a rule.

Immutable, so a matcher built once in a fixture cannot be edited by the
assertion that used it and then reused meaning something else.
"""

from typing import Final, Never, override

from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Refused so that ``anything()`` -- which hands back one shared object -- cannot
#: be re-pointed by whichever test ran first. Same reasoning, and the same
#: wording, as ``_occurrence._IMMUTABLE``.
_IMMUTABLE: Final = "matchers are immutable values; cannot change "


class Matcher:
    """Everything the matchers share -- which is not the match itself.

    :meth:`matches` lives on each subclass, because the match *is* the subclass.
    What is shared is the equality protocol, the hashing, the immutability and
    the refusal to be a subject.

    **``__eq__`` is total.** It is called by anything, from either side, against
    any value -- a ``dict`` comparison, a ``list.__contains__`` scan, a mock's
    call record, a difference engine rendering a failed assertion. It therefore
    never raises on account of the value it is handed: a match that blows up in
    somebody's ``__eq__`` or predicate is read as "no match", because the
    alternative is turning somebody's failing assertion into an error inside the
    assertion library while it is in the middle of explaining itself.
    (``_formatters._apply`` and ``_diff.describe_difference`` take the same line
    for the same reason.) The one thing it does let out is a subclass that never
    overrode :meth:`matches`, which is this library's own contract broken rather
    than a value misbehaving, and is not what the promise is here to absorb.

    **Two matchers do not match each other.** Comparing a matcher against another
    matcher of a *different* kind answers ``NotImplemented``, which hands the
    question to the other one, which declines it too -- so Python falls back to
    identity. The alternative is worse than it looks: if ``anything()`` matched
    ``any_instance_of(int)`` the way it matches everything else, then
    ``anything() == any_int`` would be ``True`` and ``any_int == anything()``
    would be ``False``, and ``==`` would depend on which side of the operator each
    was written. Two matchers of the *same* kind compare by what they were built
    from, exactly as ``_occurrence._Constraint`` does, so an expectation can be
    compared with another expectation.

    **Hashing is coarse on purpose.** ``__hash__`` answers from the class alone.
    Equal matchers hash equal, which is the contract; distinct matchers of one
    kind collide, which is legal and costs nothing because nobody keeps a
    thousand matchers in a set. The alternative -- hashing what the matcher was
    built from -- raises on an unhashable spec, and a ``__hash__`` that raises
    would make a matcher unusable as a dict key at all. What no hash can buy is
    hash-based *containment*: see the module docstring.

    **Every slot is spelled ``_like_this_``, and that is not a style choice.**
    ``_equivalence._classify`` reads an object's ``__slots__`` to decide whether
    it is a *record* -- a thing with fields, to be compared field by field -- or a
    *leaf*, and it drops the names its ``_is_reserved`` helper calls machinery:
    the ones that both start and end with an underscore. A matcher holding a
    plainly-named ``_kind`` is therefore a record, and ``is_equivalent_to``
    reports a failure against one as ``types differ: str instead of AnyInstance``
    -- a private class name, and no account of what was expected. Spelled
    ``_kind_``, the matcher is a leaf, and the same failure reads
    ``'oops' instead of <any int>``.

    It really is machinery rather than state: a matcher has no fields anybody
    would want compared, and comparing two of them field by field is precisely
    the reading :meth:`__eq__` exists to override. The tidier fix lives one module
    over -- ``_equivalence._is_opaque`` naming matchers outright, the way it
    already names classes and enum members -- and this file cannot make it, so the
    naming convention here is load-bearing rather than decorative.
    """

    __slots__ = ()

    def matches(self, value: object, /) -> bool:
        """Whether this matcher stands in for ``value``. Every matcher overrides it.

        One that does not override it raises ``NotImplementedError``, through
        ``==`` as well as from a direct call: an incomplete matcher that quietly
        stood for nothing would pass every negative assertion it was written into,
        for ever.
        """
        raise NotImplementedError

    def _spec_key(self) -> tuple[object, ...]:
        """What this matcher was built from, for comparing two of the same kind."""
        return ()

    @override
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Matcher):
            if type(other) is not type(self):
                return NotImplemented
            try:
                same = self._spec_key() == other._spec_key()
            except Exception:
                return False
            return bool(same)
        try:
            verdict = self.matches(other)
        except NotImplementedError:
            # Let this out only when it came from the base method above -- a
            # subclass that never wrote its own. Reading that as "no match" buys a
            # matcher standing for nothing wherever it is placed, which in a
            # negative assertion is a test that can never fail; the totality this
            # class promises is to *somebody else's* code, and a half-written
            # subclass of it is not that. A `NotImplementedError` out of a
            # caller's predicate or a value's `__eq__` still reads as no match,
            # because that is exactly the code the promise was made to.
            if type(self).matches is Matcher.matches:
                raise
            return False
        except Exception:
            return False
        return verdict

    @override
    def __hash__(self) -> int:
        return hash(type(self))

    @override
    def __setattr__(self, name: str, _value: object, /) -> Never:
        raise AttributeError(_IMMUTABLE + type(self).__name__ + "." + name)

    @override
    def __delattr__(self, name: str, /) -> Never:
        raise AttributeError(_IMMUTABLE + type(self).__name__ + "." + name)


def is_matcher(value: object, /) -> bool:
    """Whether ``value`` is one of this library's matchers.

        >>> is_matcher(any_instance_of(int))
        True
        >>> is_matcher(7)
        False

    Exported because the answer is otherwise unavailable: a matcher's whole
    design is to be indistinguishable from the type it stands in for, so code
    that has to tell the difference -- a custom assertion deciding whether to
    render an operand or assert on it -- cannot get there with ``isinstance``
    against a public name.
    """
    return isinstance(value, Matcher)
