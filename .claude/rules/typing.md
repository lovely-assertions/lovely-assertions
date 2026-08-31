---
paths:
  - "src/**/*.py"
  - "typing_tests/**/*.py"
---

# Typing — the surface is the product, and it is tested separately

A green runtime suite proves nothing about what a checker sees. Every typing
claim is pinned in `typing_tests/`, in two halves proved by different machinery.
`positive/` must type-check clean under both checkers, and it sits inside
pyright's `include` and mypy's `files`, so the ordinary checker runs are what
prove it. `negative/` must be **rejected**, and it is deliberately outside both
roots — a directory whose whole purpose is to fail cannot live where the gates
read — so `tests/test_typing_surface.py` shells out to the real pyright and mypy
over that half alone. Without it the positive half is worthless: a harness that
cannot detect a wrong `assert_type` rubber-stamps. A new overload, narrowing
method or generic parameter lands with cases in both corpora, in the same change
— held by review, not by a guard, unlike `docs/reference/assertions.md`, whose
drift is a test failure.

Rejection is pinned per line rather than per file. `# expect-error` means both
checkers must report that line; `# expect-error(pyright)` or `(mypy)` names one,
for the places the two are documented to disagree; anything after a colon is
prose for the reader. The harness fails three ways, and the third is what keeps
the corpus from rotting: a marked line nobody reported, an unmarked line somebody
reported, and a line marked for the *other* checker that this one also rejects —
the divergence has closed, and the marker must go.

**Two checkers, both strict, on every interpreter the package supports.** pyright
is the reference; mypy runs beside it and must also be clean. Both are configured
against the lowest supported version, and CI runs both across the whole supported
range, so a change can be clean locally and fail on another row. They are kept
independent on purpose — `enableTypeIgnoreComments` is off, so a `# type: ignore`
written for mypy cannot silence pyright — and a stale suppression of either kind
is an error rather than a warning. When they genuinely disagree, the divergence is
written down: in `docs/concepts/typing-divergences.md` where it touches the
shipped API, and in the docstring beside the marked line where it is a fact about
the corpus alone. That ledger has teeth: `tests/test_divergences.py` requires
every suppression code used in `src/` to appear there, and fails outright on a
bare `# type: ignore` or `# pyright: ignore` carrying no code at all. **Never
shave the API to make a checker happy**: an overload removed or a return widened
to `Any` costs every user of the library.

**The overload chain is a table, and the runtime walks the same one.** Order is
first-match-wins and load-bearing at every position, on three grounds rather than
the two a reader expects: narrower before wider, subclass before superclass, and
an order that settles multiple inheritance across a built-in and an ABC. The
third is why `Mapping` sits *below* `bool`, `str` and `int | float` though none
of them is its supertype — `Mapping` has `ABCMeta` for a metaclass, so
`class Config(str, Mapping[str, int])` is a class anyone can write, and only this
order hands it one answer from both halves. It is why `type[Any]` leads, too: an
`Enum` class is a `Collection` through `EnumMeta`, so anywhere below `Collection`
a checker answers `CollectionExpect` for a class the runtime builds a `TypeExpect`
for. Deliberate shadowing is suppressed per line for each checker that reports it
and only those — `bool` and `str` carry both suppressions, `Mapping` carries
mypy's alone, because pyright does not report that pair and adding its
suppression there would fail the build.

Edit the chain and everything that copies it, in the same change, because neither
side is one place any more. The runtime is several tables: the exact type table,
keyed on type identity; the table naming subjects per module, so `datetime`,
`pathlib`, `decimal` and `fractions` are never imported; the `issubclass` chain
behind both; and the mock check inlined at the head of the fallthrough. The
static side is copied wherever a return type depends on a type *argument* —
`is_instance_of` and `is_exactly_instance_of` in one module, `as_type` in
another — each carrying the head of the table rather than the whole of it,
deliberately, since every entry added is one more place the halves can drift. The
two halves are pinned against each other by a pair of files written to the same
expectations, `typing_tests/positive/dispatch.py` and `tests/test_narrowing.py`,
and by nothing that reads both.

**The dispatch tables address subjects by string**, so neither checker reads
them: each row is a module name and a class name, resolved with `getattr` over a
freshly imported module and `cast` to a subject. What keeps a rename honest is
not the tables but the package's `TYPE_CHECKING` block, which re-exports every
subject under its real name — rename a subject or its package and that block
stops resolving, loudly, under both checkers. Move a subject between modules
while keeping that block in step and only the runtime suite notices.

**Narrowing flows through the returned subject**, never the caller's variable —
`TypeIs` and `TypeGuard` can only narrow a function's first positional argument,
and `expect()` captures its subject inside a wrapper. So `is_not_none()` returns
a subject re-typed to the narrowed type, and the caller rebinds it; it returns
`self` under a `cast`, so the narrowing allocates nothing. It stops at the
*generic* subject, and that is the larger limitation:
`expect(maybe_text).is_not_none()` is an `Expect[str]`, not a `StringExpect`,
because re-specialising would also claim a user's own `class Mine(Expect[str])`
and hand it back mislabelled. Say both out loud rather than implying more than
the checker delivers. When a narrowing assertion fails inside a soft scope there
is no narrowed subject to hand back, so `_fail_narrowing` returns an absorbing
stand-in declared `Any` — the one place the library knowingly gives a checker
nothing, chosen over a wrapper whose static type has become a lie.

**PEP 698 is required of the library and not of the corpora that test it.**
`reportImplicitOverride` is an error under a pyright execution environment rooted
at `src`, and `explicit-override` under a mypy override for `lovely_assertions.*`.
It is not asked of `tests/` or `typing_tests/`, where most of what it would flag
is `__repr__` and `__eq__` on a test double that exists to define them.

**A subject is a composition, and the typing follows from that.** Each seam is a
mixin over whatever base its family shares, carrying empty `__slots__` and no
state of its own, and an assertion returns `Self` rather than the class it is
declared on, so a chain crossing three seams ends holding the assembled subject's
whole catalogue rather than one mixin's. The order of the bases is load-bearing
wherever a seam overrides a name a lower one already declares — `StringExpect`
reaches `matches` on its regex seam and not the predicate one — which is exactly
the hazard `@override` closes: rename or retype the base and the override quietly
becomes a new method nothing calls. Seam names repeat across families, so read the
class a method is declared on rather than its name. A method that must narrow
annotates `self` with its own mixin type rather than relying on the class it is
assembled into.

**Annotations are complete.** Every public signature is fully annotated, `Self`
for chaining, PEP 695 syntax for generics and aliases, no bare `Any` outside a
site that carries its reason inline. What enforces that is ruff's `ANN401` plus a
per-site `# noqa: ANN401` naming the reason — not the completeness gate, which
counts a *declared* `Any` as a known type and would hold if far more of the
surface were `Any`. `py.typed` stays in the package and
`--verifytypes --ignoreexternal` stays at full completeness; the same gate also
asserts that no public function or class is missing a docstring, so an
undocumented method fails the *typing* build.

**Values that defeat static dispatch exist, and pretending otherwise is worse.**
A `Mock` is assignable to everything through typeshed's `Any`, so no overload can
reach it — the runtime is left to be right on its own, and
`expect(mock, as_=MockExpect)` is the typed answer. A mock is not the only such
value: `types.NotImplementedType` has the same property, and both checkers answer
`TypeExpect` for it where the runtime correctly answers the generic subject. The
divergence recurs one level down, in `is_instance_of`'s own table, where an
argument annotated `type[Any]` or a bare `type` satisfies the leading
`type[S: Enum]` overload and the two checkers disagree about what it resolves to.
When a static answer would be a fiction, write no overload rather than a wrong
one — and do not go on claiming the fiction has only one instance.
