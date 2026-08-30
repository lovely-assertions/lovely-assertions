"""The questions asked of a value before anything walks into it.

Four small, total answers. Each is a question the describers and the equivalence
walk have to settle before they can choose what to do at all -- what a type is
called, whether a float is the one value unequal to itself, whether something
answers to being a mapping or a set -- and none of them may raise, because they
are asked about values that are already suspect.
"""

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from typing import TypeIs

from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def qualified(subject_type: type, /) -> str:
    """``package.module.Class``, for when the bare name does not tell them apart."""
    return subject_type.__module__ + "." + subject_type.__qualname__


def is_float_nan(value: object, /) -> bool:
    """Whether a value is a float NaN, without importing ``math``.

    Deliberately *not* :func:`lovely_assertions._ordered.is_nan`, which asks the
    same question of a wider world and gets a different answer. That one is the
    bare ``value != value``, so it recognises a ``Decimal("nan")`` -- which is
    what the ordering catalogue needs of it -- and so it also answers ``True`` for
    a ``Mock``, whose ``__eq__`` returns a new mock every time it is asked. A
    describer that called a mock a NaN would explain a failure with a fact about
    floating point that has nothing to do with it. Two questions, two names.
    """
    return isinstance(value, float) and value != value  # noqa: PLR0124  (that is what NaN means)


def is_mapping(value: object, /) -> TypeIs[Mapping[object, object]]:
    """Whether a value is a mapping, narrowed to what a caller needs to read.

    The two ``is_*`` predicates carry ``TypeIs`` rather than being written as bare
    ``isinstance`` calls at the call site: an un-parameterised ``isinstance``
    narrows ``object`` to ``Mapping[Unknown, Unknown]``, and the unknowns then leak
    into every branch after it. ``Mapping[object, object]`` is a supertype only for
    reading, which is all either caller ever does with them.
    """
    return isinstance(value, Mapping)


def is_set(value: object, /) -> TypeIs[AbstractSet[object]]:
    """Whether a value is a set, narrowed to what a caller needs to read."""
    return isinstance(value, AbstractSet)
