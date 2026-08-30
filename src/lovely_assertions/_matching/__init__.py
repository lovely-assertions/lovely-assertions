"""Asymmetric matchers: a placeholder that stands in for a value in an expectation.

The point of use is a value you cannot name and can describe::

    expect(row).is_equal_to({"id": any_instance_of(int), "name": "ada"})
    expect(payload).is_equal_to({"token": string_matching(r"^ey"), "ttl": close_to(60)})
    expect(sender).was_called_with(any_instance_of(Request), retries=one_of(0, 1))

and the thing it replaces is three assertions that have lost the shape of the
thing under test::

    expect(row["name"]).is_equal_to("ada")
    expect(row["id"]).is_instance_of(int)
    expect(row).has_length(2)

**The objection this trick usually attracts, and why it misses in Python.**
Jest's ``expect.any(Number)`` is type-erased: TypeScript sees ``any``, the object
slot it is dropped into stops being checked, and a typo in the *neighbouring* key
goes through. That is a true account of the trick in JavaScript and a false one
in Python, because a Python matcher can lie about its type in a way the checker
still enforces:

.. code-block:: python

    def any_instance_of[T](kind: type[T]) -> T: ...

    assert_type(any_instance_of(int), int)              # passes
    rows: dict[str, int] = {"a": any_instance_of(int)}  # accepted
    bad: list[int] = [any_instance_of(str)]             # rejected, as it must be

A function *declared* to return ``T`` is statically indistinguishable from a
``T``, so every slot the checker was already policing stays policed -- while at
runtime the object is a placeholder whose ``__eq__`` answers loosely.
``dirty-equals``, the closest thing Python has to this today, cannot do it: its
matchers are their own types, so ``list[int]`` has to be widened to
``list[int | IsInt]`` and the element type stops meaning anything.

**Where the checking actually bites, stated before anybody is disappointed by
it.** A matcher is refused where the *slot* it lands in has a declared type: an
annotated variable, a container element, an assertion parameter that carries the
element type -- ``expect(names).contains(any_instance_of(int))`` on a
``list[str]`` is an error, and so is ``rows: dict[str, int] = {"a":
any_instance_of(str)}``. It is **not** refused by ``is_equal_to``, whose
parameter is ``object`` on purpose so that any two values can be compared: an
unannotated ``{"id": any_instance_of(str)}`` written straight into that call has
no slot to be checked against, and neither checker will say anything. The
protection is real and it is the caller's annotations that switch it on, which is
one more reason to declare the expectation rather than inline it.

**No walker, at any depth.** Nothing in this library knows matchers exist. A
matcher works because Python's comparison protocol reaches it on its own:
``{"id": 7} == {"id": <any int>}`` compares the two values, ``int.__eq__``
answers ``NotImplemented``, and the reflected call lands on the matcher. That is
true at every depth of every structure ``==`` descends, which is why
``is_equal_to``, ``is_equivalent_to``, ``contains``, ``was_called_with`` and the
difference engine all support matchers without a line written for them.

**The lie is deliberate, and here is what it costs.** ``any_instance_of(str)`` is
annotated ``str`` and is not a ``str``. A reader who follows the annotation and
calls ``.upper()`` on one gets ``AttributeError``, and no checker will have
warned them. The trade is narrow and worth stating exactly:

* what it buys -- a placeholder that survives an *invariant* container slot
  (``dict[str, int]``, ``list[int]``), which no honestly-typed value can do,
  and which is the only reason to reach for a matcher at all;
* what it costs -- the annotation of a matcher is not the truth about the
  object, and a matcher used as anything other than an expectation misbehaves at
  runtime with no static warning.

So the rule is one sentence: **a matcher goes in an expectation and nowhere
else.** It is never the subject, never stored as application data, never
operated on. ``expect(any_instance_of(int))`` is refused with a ``TypeError``
that says so -- the refusal is registered through :func:`~lovely_assertions.register`,
so the dispatch pays nothing for it on any other value (see
:func:`_refuse_matcher_subject`).

**Where a matcher does not reach.** ``in`` against a ``set``, a ``frozenset`` or
a mapping's keys is a *hash* lookup, not a scan: Python computes the hash first
and only compares against the values in that bucket, so
``expect({1, 2}).contains(any_instance_of(int))`` finds nothing. A matcher
therefore cannot be hashed into agreement with the values it matches -- no object
can -- and the assertion to write there is one over the items rather than one
over containment. Sequences, mappings' *values* and call arguments are all
scans, so they work.

**Rendering.** Every matcher's ``repr`` is the phrase it stands for --
``<any int>``, ``<string matching '^ey'>`` -- because it is the text a reader
meets in a failure message ``Expected row to equal {'id': <any int>}, but was
{'id': 'oops'}``. That works through ``repr`` alone, since every rendering site
in this library falls back to it. :class:`_MatcherFormatter` is registered on top
of that for one narrower reason, given at the class.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._matching._base import is_matcher
from lovely_assertions._matching._choice import one_of
from lovely_assertions._matching._containers import containing
from lovely_assertions._matching._instances import any_instance_of, anything
from lovely_assertions._matching._numbers import close_to
from lovely_assertions._matching._predicate import matching
from lovely_assertions._matching._strings import string_containing, string_matching
from lovely_assertions._matching._wiring import install

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

install()

__all__ = [
    "any_instance_of",
    "anything",
    "close_to",
    "containing",
    "is_matcher",
    "matching",
    "one_of",
    "string_containing",
    "string_matching",
]
