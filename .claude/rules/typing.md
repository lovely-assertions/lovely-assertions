---
paths:
  - "src/**/*.py"
  - "typing_tests/**/*.py"
---

# Typing — the surface is the product, and it is tested separately

A green runtime suite proves nothing about what a checker sees. Every typing
claim is pinned in `typing_tests/`: `positive/` must type-check clean under both
checkers, `negative/` must be **rejected** by both, and the suite shells out to
the real pyright and mypy to prove it. A new overload, narrowing method or
generic parameter lands with cases in both corpora, in the same change.

**Two checkers, both strict.** pyright is the reference; mypy runs beside it and
must also be clean. They are kept independent on purpose — a `# type: ignore`
written for mypy must not silence pyright, and a stale suppression of either kind
is an error rather than a warning. When they genuinely disagree, the divergence
is documented and lived with. **Never shave the API to make a checker happy**: an
overload removed or a return widened to `Any` costs every user of the library.

**The overload chain is a table, and the runtime walks the same one.** Order is
first-match-wins and load-bearing at every position — narrower before wider,
subclass before superclass, and any type whose members are also `int` or `str`
above the overloads that would claim them. Deliberate shadowing is annotated with
a targeted per-line suppression and a comment saying which case it protects. Edit
the chain and the runtime branch order together, always.

**Narrowing flows through the returned subject**, never the caller's variable —
`TypeIs` and `TypeGuard` can only narrow a function's first positional argument,
and `expect()` captures its subject inside a wrapper. So `is_not_none()` returns
a subject re-typed to the narrowed type, and the caller rebinds it. Say this
limitation out loud rather than implying more than the checker delivers.

**Annotations are complete.** Every public signature is fully annotated, `Self`
for chaining, PEP 695 syntax for generics and aliases, no bare `Any` outside a
documented escape hatch. `py.typed` stays in the package, and
`--verifytypes --ignoreexternal` stays at full completeness.

**Values that defeat static dispatch exist, and pretending otherwise is worse.**
A `Mock` is assignable to everything through typeshed's `Any`, so no overload can
reach it — the runtime is left to be right on its own, and the explicit
`as_=`/`expect_...` route is the typed answer. When a static answer would be a
fiction, write no overload rather than a wrong one.
