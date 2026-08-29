---
paths:
  - "src/**/*.py"
---

# Performance — the happy path is sacred, the failure path is free

Loads alongside `code-style.md`. A passing assertion runs in test suites millions
of times; a failing one runs once and then a human reads it for a minute. Spend
accordingly.

**The happy path costs a comparison and a `return self`.** On the success branch
there is no allocation, no frame inspection, no `ContextVar` read, no `getattr`
on a missing attribute, no message. Ways this gets broken without anyone
noticing:

- An f-string built *before* the branch that decides, or passed as an argument to
  a helper — Python evaluates arguments eagerly, so `self._fail(render(x))` on a
  passing assertion still renders.
- A `try`/`except` is free until it fires, but a `finally` is not.
- A comprehension or `tuple(...)` used only to feed the comparison. Iterate and
  return early instead.
- Subscripting a generic at call time (`dict[str, int]()`) allocates. Bind the
  concrete type once at module level.

**Imports are a cost every user pays.** `re`, `difflib`, `ast`, `linecache`,
`dataclasses` and `uuid` are imported inside the failure branch that needs them,
each with a `# noqa: PLC0415` and a reason. The subjects for `datetime`, `enum`
and `pathlib` values are typed under `TYPE_CHECKING` and matched by name, so
importing this package imports none of the three. `datetime` and `pathlib` are
then never imported at all; `enum` is, but only lazily, from the flag assertions
and from enum-by-name equivalence, which cannot work without it.

**Dispatch is a dict lookup first.** `expect()` resolves the exact type through a
table keyed on type *identity* before it reaches any `isinstance` test — that
table is the only part of the chain ordered for speed. Everything after it is
ordered for **correctness**: first match wins, so narrower cases must precede the
wider ones that would otherwise claim them, and reordering for speed changes
which subject a value gets. Memoised subclass answers are guarded by
`abc.get_cache_token()`; a plain cache goes stale the moment someone registers a
virtual subclass.

**Measure, never assert by feel.** `benchmarks/` prints timings for a human and
blocks nothing. `tests/test_performance_invariants.py` asserts only what holds on
any machine: that a passing assertion allocates nothing, that a module is not
imported, that the happy path never calls the naming machinery. A speedup claim
that is not reproduced by reverting the change in one checkout, on one
interpreter, is not a claim — cross-tree numbers are noise.

**Don't trade a message for a microsecond.** The failure path may allocate, walk
frames, parse source and import whatever it needs. If an optimisation makes a
message vaguer, it is not an optimisation.
