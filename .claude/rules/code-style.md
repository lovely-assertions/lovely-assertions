---
paths:
  - "src/**/*.py"
---

# Core code style — one shape, repeated

**The assertion idiom.** Every assertion is the same shape: compare, return
`self` on success, `return self._fail(...)` on failure — or
`return self._fail_narrowing(...)` where the assertion was supposed to hand back
a *narrowed* subject, since there is then no narrowed subject to return and a
soft scope gets a stand-in that absorbs the rest of the chain instead of a
cascade derived from the first failure. Both end in `report_failure`
(`_core/_routing.py`), the one function that renders a failure and then either
raises it or appends it to an open soft scope — that is what gives soft scopes,
subject naming and `because` to every assertion at once. Never raise
`AssertionFailure` directly from an assertion, and never build the message
before the failure branch. A helper that builds one says **"Failure path only."**
in its docstring, and `tests/test_happy_path.py` reads that phrase: the marker is
what exempts the helper from the rule against formatting above the branch, and it
buys that exemption by never being reachable from a passing assertion — a marked
builder the call graph reaches from one fails. The shape is the rule and not the
line count — an assertion whose message has to explain itself is longer than
this, and one that delegates to a neighbour never calls `_fail` at all.

```python
def starts_with(self, prefix: str, /, *, because: str = "") -> Self:
    """Assert the string begins with ``prefix``."""
    subject = self._subject
    if subject.startswith(prefix):
        return self
    return self._fail(f"to start with {clipped(prefix)}, but was {clipped(subject)}", because)
```

**Signatures.**
- The expected value is **positional-only** (`/`), as is `expect()`'s own value:
  the parameter name is not part of the public API and can be renamed without
  breaking a caller.
- `because: str = ""` is **keyword-only** on every assertion, passed straight
  through to `_fail`, never interpolated.
- An assertion that narrows returns the narrowed subject type; one that *finds*
  a value returns a `Found` over it; a few hand back a different subject
  entirely (`RaisedExpect`, `WarnedExpect`) or half a chain for another call to
  finish (`WithinDelta`); everything else returns `Self`. Nothing returns
  `None`. Where overloads decide the answer the implementation returns `Any`,
  and the types live on the `@overload` declarations above it.

**Classes.**
- A subject is assembled from **mixins**, one per seam: a class deriving from
  the subject's base with `__slots__ = ()`, carrying assertions and no state.
  The subject class is its base list, with that base last. Mixin names are
  package-scoped and repeat — `_string`, `_sequence` and `_collection` each
  declare a `ContainmentAssertions` — because an assembly imports only its own
  package's seams.
- `__slots__` on every class, always — a subject is allocated per assertion.
  ruff's `SLOT` rules do not reach an ordinary class, so the guard is
  `tests/test_performance_invariants.py` over the subject classes; everywhere
  else it holds by discipline.
- Subject state is exactly `_subject` and `_name`. The two context-manager
  handles are the exception: `CaughtExpect` and `CaughtWarnings` carry the state
  their block has not produced yet, and override `_fail` to fall silent once a
  soft scope has collected the block's own failure. Nothing else may.
- `@override` on every method that overrides one. Both checkers require it in
  `src/` and only there — pyright's `reportImplicitOverride` under an execution
  environment rooted at `src`, mypy's `explicit-override` on
  `lovely_assertions.*` — and it costs nothing at runtime.
- Every module assigns `__tracebackhide__ = hide_internal_frames` at module
  scope. pytest reads it from a frame's globals, so a module that forgets puts
  its own frames in front of the line the reader wrote; `tests/test_packaging.py`
  fails on the next module to forget, with the root `__init__` and `_exceptions`
  exempt and the reason recorded there.

**Module boundaries.** Imports point down the layering, and are acyclic at module
scope. `_core` imports no subject package at runtime — it names `_bool`, `_enum`
and `_string` under `TYPE_CHECKING`, because `is_instance_of` and `as_type`
overload on `Enum`, `bool` and `str` to hand back the subjects `expect()` would.
Subject packages import the shared helpers, and build on each other where a
catalogue really is shared: `_sequence` extends `_collection`, `_numeric` extends
`_ordered`. `_subjects` owns the overload chain, the runtime dispatch and
`register`; the subjects themselves are assembled inside their own packages.
Where a cycle is real it is broken by deferring the import into the function
body, with a comment saying which way it runs — `Found.which` reaching
`_subjects`, name recovery in `_names` reaching `_core` for `Expect`, and the two
`extracting` seams rebuilding the subject their own package assembles. Absolute
imports only, and ruff enforces that (`ban-relative-imports = "all"`).

The two engines a failure needs are named through `_engine`, which re-exports
`_diff` and `_equivalence` through a table and a module `__getattr__` binding on
first access. **No module outside those two packages may import either at module
scope**: they are the most expensive work the library does, and neither runs
until an assertion has already failed. That one is discipline — the import
budgets in `tests/test_performance_invariants.py` sit underneath it, but they
catch a catastrophe, not a gram.

**Naming.** An assertion's negation mirrors its positive form and carries the
negation where the positive carries its meaning — usually the verb (`is_not_`,
`does_not_`, `was_not_`), otherwise the quantity (`has_no_`, `contains_no_`,
`contains_none_of`, `satisfies_none`, `was_never_called_with`). Configuration
methods are not assertions and read as what they do (`excluding`,
`ignoring_order`). A private *package* is a directory carrying the leading
underscore, and every module inside it is still `_name.py`. Within the package
the file is not the privacy boundary, though: a name only its own file uses
keeps the leading underscore, and a name a sibling imports drops it —
`report_failure`, `subject_for`, `claimed_by`, `clipped`. That is not a
preference; a name imported across a module boundary is that module's public
surface, and pyright's `reportPrivateUsage` fails the build for the private
spelling. Those plain names are package-scoped too and may repeat. A public name
takes three edits in the root `__init__.py`, which is lazy: the `TYPE_CHECKING`
re-export alias, a `_HOME` entry and an `__all__` entry — where `__all__` is
sorted, and every entry in it must also appear in `docs/reference/assertions.md`.

**Errors.** `AssertionFailure` is for a failed assertion. A caller who passed the
wrong thing — an empty variadic, a matcher where a value belongs, a subject
registered for a type that already has one — gets `ValueError` or `TypeError`
with a message naming what was received and what would be valid. A caller who
called at the wrong *time* — re-entering a scope that is already open, leaving
one that is not, asking a block's handle for its subject before the block has
finished — gets `RuntimeError`.

Catch the type you can actually name. `except Exception` is right in two kinds of
place and nowhere else. The first is the call into **someone else's code** — a
`__repr__`, an `__eq__`, a registered formatter, a caller's predicate — behind a
documented promise not to raise: rendering a value must never turn a failure
message into an error, and a comparison must never turn a difference into one.
The second is the outer edge of a subsystem that reaches such code somewhere
inside, where the guard is a backstop rather than a wrapper on one call, and
`describe_difference` and `compare` return a degraded message instead of
propagating. Either way the promise is stated where the reader meets it — a
comment at the site, or the enclosing docstring. And a backstop must not enclose
an exception that is control flow rather than a verdict: `TruncatedError` is an
`Exception` and not a `BaseException` only because no `except Exception` in the
equivalence engine sits between a `spend` and the handler meant to see it.
Anywhere else it hides a bug.

**Layout.** `ruff format` is the floor. Group a subject's methods under
`# -- group name ---` banners; those banners are structure, not decoration, and
the generated reference reads them. One responsibility per function.
